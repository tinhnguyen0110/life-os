"""modules/career/service.py — Career cockpit logic (CAR-1).

Three resources over md_store (markdown + git, one commit per write):

  - CV    : `career/cv.md` (raw markdown). Parsed into header meta + H2 sections;
            proof chips per section come from seed.SECTION_PROOF (heading-slug).
  - Blog  : `career/blog/<id>.md` (YAML front-matter + body=dek/notes).
  - Demo  : `career/demo/<id>.md` (YAML front-matter + body=desc).

Logic (architect-style block, verbatim):
  - CV parse: split on lines matching ^#{1,6}\\s. The first H1 = meta.name; the
    first H2 immediately after it (before any other section) = meta.title; a
    contact line (starts with 📞 / ✉ / contains '·') in the preamble = meta.contact.
    Each subsequent H2 starts a section; its body is everything up to the next H2.
    Lower-level headings (H3+) stay inside the H2 body (kept as raw markdown).
  - section id = slug(heading); proof = SECTION_PROOF.get(id, []).
  - Seeding is idempotent: seed_cv only when cv.md absent; seed_blog/seed_demo
    only when the dir has zero items. Never overwrites user content.
  - Blog/demo id = slug(title|name)-<6hex>; create stamps created==updated, update
    preserves created + bumps updated. list sorts newest-updated first.
  - Fail-open on a malformed blog/demo file (skip + warn) — the stale-store lesson.
"""

from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

import yaml

from core.config import settings
from store import md_store

from . import seed
from .schema import (
    BlogInput,
    BlogPost,
    Cv,
    CvMeta,
    CvSection,
    DemoInput,
    DemoItem,
    ProofLink,
)

logger = logging.getLogger("life-os.career.service")

CV_REL = "career/cv.md"
_BLOG_DIR = "career/blog"
_DEMO_DIR = "career/demo"


# --------------------------------------------------------------------------- #
# helpers                                                                       #
# --------------------------------------------------------------------------- #
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or "item"


def _new_id(text: str, fallback: str) -> str:
    base = slug(text)
    if base == "item":
        base = fallback
    return f"{base}-{secrets.token_hex(3)}"


def _career_dir() -> Path:
    return settings.data_dir / "career"


# --------------------------------------------------------------------------- #
# CV — parse + read + seed + update                                             #
# --------------------------------------------------------------------------- #
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_CONTACT_HINT = ("📞", "✉", "🔗", "🌐", "📍")


def parse_cv(markdown: str, *, seeded: bool, updated_at: str | None) -> Cv:
    """Parse raw CV markdown → Cv (meta + ordered H2 sections). Never raises."""
    lines = (markdown or "").splitlines()
    meta = CvMeta()
    sections: list[CvSection] = []

    # First pass: pull the header (H1 name, first H2 title, a contact line) from the
    # preamble before the first "real" section. We treat the first H2 as the title
    # ONLY when it sits in the preamble (right after the H1); later H2s are sections.
    i = 0
    n = len(lines)
    seen_h1 = False
    title_taken = False

    # Walk the preamble: until we hit an H2 that should start a section.
    while i < n:
        line = lines[i]
        m = _HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            if level == 1 and not seen_h1:
                meta.name = text
                seen_h1 = True
                i += 1
                continue
            if level == 2 and seen_h1 and not title_taken:
                # First H2 after the H1 = the role/title line.
                meta.title = text
                title_taken = True
                i += 1
                continue
            # Any other heading → preamble is over; sections begin here.
            break
        else:
            # Contact line in preamble.
            stripped = line.strip()
            if stripped and not meta.contact and any(h in stripped for h in _CONTACT_HINT):
                meta.contact = stripped
            i += 1
            continue

    # Second pass: from i onward, build H2 sections (H3+ stay inside the H2 body).
    cur_heading: str | None = None
    cur_level = 2
    cur_body: list[str] = []

    def _flush() -> None:
        if cur_heading is None:
            return
        sid = slug(cur_heading)
        body = "\n".join(cur_body).strip("\n")
        proof = [ProofLink(**p) for p in seed.SECTION_PROOF.get(sid, [])]
        sections.append(
            CvSection(id=sid, heading=cur_heading, level=cur_level, body=body, proof=proof)
        )

    while i < n:
        line = lines[i]
        m = _HEADING_RE.match(line)
        if m and len(m.group(1)) <= 2:
            # New top-level section (H1 or H2) → flush the previous.
            _flush()
            cur_heading = m.group(2).strip()
            cur_level = len(m.group(1))
            cur_body = []
        else:
            if cur_heading is not None:
                cur_body.append(line)
            # (lines before the first section heading are dropped — they were preamble)
        i += 1
    _flush()

    return Cv(meta=meta, sections=sections, updatedAt=updated_at, seeded=seeded)


def _cv_meta_rel() -> str:
    """Sidecar file storing CV bookkeeping (seeded flag + updatedAt)."""
    return "career/cv.meta.yml"


def _read_cv_meta() -> dict:
    raw = md_store.read(_cv_meta_rel())
    if not raw:
        return {}
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def seed_cv() -> bool:
    """Seed `career/cv.md` from the user's source CV if it doesn't exist yet.
    Returns True if a seed write happened. Idempotent (no-op if cv.md exists)."""
    if md_store.exists(CV_REL):
        return False
    markdown = seed.load_cv_markdown()
    md_store.write_file(CV_REL, markdown, "career: seed CV from source")
    md_store.write_file(
        _cv_meta_rel(),
        yaml.safe_dump({"seeded": True, "updatedAt": _now_iso()}, sort_keys=True, allow_unicode=True),
        "career: seed CV meta",
    )
    logger.info("career: seeded CV")
    return True


def get_cv() -> Cv:
    """The living CV parsed into sections. Seeds on first read (idempotent)."""
    seed_cv()
    raw = md_store.read(CV_REL) or ""
    meta = _read_cv_meta()
    return parse_cv(
        raw,
        seeded=bool(meta.get("seeded", False)),
        updated_at=meta.get("updatedAt"),
    )


def get_cv_raw() -> str:
    """The CV's raw markdown (for export / copy). Seeds on first read."""
    seed_cv()
    return md_store.read(CV_REL) or ""


def update_cv(markdown: str) -> Cv:
    """Replace the CV's raw markdown (edit/export round-trip). Marks seeded=False
    (now user-authored) + bumps updatedAt. One git commit."""
    now = _now_iso()
    md_store.write_file(CV_REL, markdown, "career: update CV")
    md_store.write_file(
        _cv_meta_rel(),
        yaml.safe_dump({"seeded": False, "updatedAt": now}, sort_keys=True, allow_unicode=True),
        "career: update CV meta",
    )
    return parse_cv(markdown, seeded=False, updated_at=now)


# --------------------------------------------------------------------------- #
# Blog — CRUD over career/blog/<id>.md                                          #
# --------------------------------------------------------------------------- #
def _blog_rel(post_id: str) -> str:
    return f"{_BLOG_DIR}/{post_id}.md"


def _render_blog(post: BlogPost) -> str:
    fm = {
        "id": post.id, "title": post.title, "subtitle": post.subtitle,
        "status": post.status, "url": post.url, "tags": post.tags,
        "publishedDate": post.publishedDate, "readMinutes": post.readMinutes,
        "wordCount": post.wordCount,
        "createdAt": post.createdAt, "updatedAt": post.updatedAt,
    }
    block = yaml.safe_dump(fm, sort_keys=True, allow_unicode=True).strip()
    return f"---\n{block}\n---\n{post.dek}"


def _parse_blog(content: str) -> BlogPost | None:
    text = (content or "").lstrip("﻿")
    if not text.startswith("---"):
        return None
    parts = text[len("---"):].split("\n---", 1)
    if len(parts) < 2:
        return None
    fm_block, body = parts[0], parts[1].lstrip("\n")
    try:
        fm = yaml.safe_load(fm_block)
    except yaml.YAMLError:
        return None
    if not isinstance(fm, dict):
        return None
    try:
        return BlogPost(
            id=fm["id"], title=fm["title"], subtitle=fm.get("subtitle", "") or "",
            dek=body, status=fm.get("status", "draft"), url=fm.get("url"),
            tags=fm.get("tags") or [], publishedDate=fm.get("publishedDate"),
            readMinutes=fm.get("readMinutes"), wordCount=fm.get("wordCount"),
            createdAt=fm["createdAt"], updatedAt=fm["updatedAt"],
        )
    except (KeyError, ValueError, TypeError):
        return None


def seed_blog() -> int:
    """Seed the user's existing blog posts if the blog dir is empty. Idempotent.
    Returns the number of posts seeded."""
    if _list_blog_files():
        return 0
    count = 0
    for s in seed.BLOG_SEEDS:
        body = BlogInput(**s)
        create_blog(body)
        count += 1
    logger.info("career: seeded %d blog post(s)", count)
    return count


def _list_blog_files() -> list[Path]:
    d = _career_dir() / "blog"
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if p.suffix == ".md" and p.is_file())


def list_blog() -> tuple[list[BlogPost], list[str]]:
    """All blog posts, newest-updated first. Seeds on first call. Fail-open per file."""
    seed_blog()
    posts: list[BlogPost] = []
    warnings: list[str] = []
    for p in _list_blog_files():
        raw = md_store.read(_blog_rel(p.stem))
        post = _parse_blog(raw or "")
        if post is None:
            warnings.append(f"blog {p.stem!r}: malformed, skipped")
            continue
        posts.append(post)
    posts.sort(key=lambda x: x.updatedAt, reverse=True)
    return posts, warnings


def get_blog(post_id: str) -> BlogPost | None:
    raw = md_store.read(_blog_rel(post_id))
    if raw is None:
        return None
    return _parse_blog(raw)


def create_blog(body: BlogInput) -> BlogPost:
    now = _now_iso()
    post_id = _new_id(body.title, "post")
    post = BlogPost(
        id=post_id, title=body.title.strip(), subtitle=body.subtitle, dek=body.dek,
        status=body.status, url=body.url, tags=body.tags,
        publishedDate=body.publishedDate, readMinutes=body.readMinutes,
        wordCount=body.wordCount, createdAt=now, updatedAt=now,
    )
    md_store.write_file(_blog_rel(post_id), _render_blog(post), f"career: create blog {post_id}")
    return post


def update_blog(post_id: str, body: BlogInput) -> BlogPost | None:
    existing = get_blog(post_id)
    if existing is None:
        return None
    now = _now_iso()
    post = BlogPost(
        id=post_id, title=body.title.strip(), subtitle=body.subtitle, dek=body.dek,
        status=body.status, url=body.url, tags=body.tags,
        publishedDate=body.publishedDate, readMinutes=body.readMinutes,
        wordCount=body.wordCount, createdAt=existing.createdAt, updatedAt=now,
    )
    md_store.write_file(_blog_rel(post_id), _render_blog(post), f"career: update blog {post_id}")
    return post


def delete_blog(post_id: str) -> bool:
    sha = md_store.delete_file(_blog_rel(post_id), f"career: delete blog {post_id}")
    return sha is not None


# --------------------------------------------------------------------------- #
# Demo — CRUD over career/demo/<id>.md                                          #
# --------------------------------------------------------------------------- #
def _demo_rel(demo_id: str) -> str:
    return f"{_DEMO_DIR}/{demo_id}.md"


def _render_demo(item: DemoItem) -> str:
    fm = {
        "id": item.id, "name": item.name, "tagline": item.tagline,
        "url": item.url, "repo": item.repo, "status": item.status,
        "tags": item.tags, "loc": item.loc,
        "createdAt": item.createdAt, "updatedAt": item.updatedAt,
    }
    block = yaml.safe_dump(fm, sort_keys=True, allow_unicode=True).strip()
    return f"---\n{block}\n---\n{item.desc}"


def _parse_demo(content: str) -> DemoItem | None:
    text = (content or "").lstrip("﻿")
    if not text.startswith("---"):
        return None
    parts = text[len("---"):].split("\n---", 1)
    if len(parts) < 2:
        return None
    fm_block, body = parts[0], parts[1].lstrip("\n")
    try:
        fm = yaml.safe_load(fm_block)
    except yaml.YAMLError:
        return None
    if not isinstance(fm, dict):
        return None
    try:
        return DemoItem(
            id=fm["id"], name=fm["name"], tagline=fm.get("tagline", "") or "",
            desc=body, url=fm.get("url"), repo=fm.get("repo"),
            status=fm.get("status", "live"), tags=fm.get("tags") or [],
            loc=fm.get("loc"), createdAt=fm["createdAt"], updatedAt=fm["updatedAt"],
        )
    except (KeyError, ValueError, TypeError):
        return None


def seed_demo() -> int:
    """Seed the user's flagship demos if the demo dir is empty. Idempotent."""
    if _list_demo_files():
        return 0
    count = 0
    for s in seed.DEMO_SEEDS:
        body = DemoInput(**s)
        create_demo(body)
        count += 1
    logger.info("career: seeded %d demo item(s)", count)
    return count


def _list_demo_files() -> list[Path]:
    d = _career_dir() / "demo"
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if p.suffix == ".md" and p.is_file())


def list_demo() -> tuple[list[DemoItem], list[str]]:
    """All demo items, newest-updated first. Seeds on first call. Fail-open per file."""
    seed_demo()
    items: list[DemoItem] = []
    warnings: list[str] = []
    for p in _list_demo_files():
        raw = md_store.read(_demo_rel(p.stem))
        item = _parse_demo(raw or "")
        if item is None:
            warnings.append(f"demo {p.stem!r}: malformed, skipped")
            continue
        items.append(item)
    items.sort(key=lambda x: x.updatedAt, reverse=True)
    return items, warnings


def get_demo(demo_id: str) -> DemoItem | None:
    raw = md_store.read(_demo_rel(demo_id))
    if raw is None:
        return None
    return _parse_demo(raw)


def create_demo(body: DemoInput) -> DemoItem:
    now = _now_iso()
    demo_id = _new_id(body.name, "demo")
    item = DemoItem(
        id=demo_id, name=body.name.strip(), tagline=body.tagline, desc=body.desc,
        url=body.url, repo=body.repo, status=body.status, tags=body.tags,
        loc=body.loc, createdAt=now, updatedAt=now,
    )
    md_store.write_file(_demo_rel(demo_id), _render_demo(item), f"career: create demo {demo_id}")
    return item


def update_demo(demo_id: str, body: DemoInput) -> DemoItem | None:
    existing = get_demo(demo_id)
    if existing is None:
        return None
    now = _now_iso()
    item = DemoItem(
        id=demo_id, name=body.name.strip(), tagline=body.tagline, desc=body.desc,
        url=body.url, repo=body.repo, status=body.status, tags=body.tags,
        loc=body.loc, createdAt=existing.createdAt, updatedAt=now,
    )
    md_store.write_file(_demo_rel(demo_id), _render_demo(item), f"career: update demo {demo_id}")
    return item


def delete_demo(demo_id: str) -> bool:
    sha = md_store.delete_file(_demo_rel(demo_id), f"career: delete demo {demo_id}")
    return sha is not None
