"""tests/test_career_backend.py — career module schema + service + API tests (CAR-1).

Behavior-tested (not field-reads): CV parse from real-shaped markdown, idempotent
seeding, blog/demo CRUD round-trips with git-commit-landed proof, fail-open on
malformed files, and the FastAPI endpoints end-to-end.
"""

from __future__ import annotations

import subprocess

import pytest
from fastapi.testclient import TestClient

from modules.career import service
from modules.career.schema import BlogInput, DemoInput
from store import md_store


def _git_log(data_dir) -> list[str]:
    r = subprocess.run(["git", "-C", str(data_dir), "log", "--oneline"],
                       capture_output=True, text=True)
    return r.stdout.strip().splitlines()


SAMPLE_CV = """# Jane Doe
## Staff Engineer · Platforms

📞 000 · ✉ jane@example.com · 🌐 jane.dev

## SUMMARY
I build reliable systems.

## EXPERIENCE
### Acme — Senior
Did things.

## SKILLS
Python, Go.
"""


# --------------------------------------------------------------------------- #
# slug / id
# --------------------------------------------------------------------------- #
def test_slug_basic():
    assert service.slug("My Cool Title!!") == "my-cool-title"
    assert service.slug("!!!") == "item"


def test_new_id_has_6hex_suffix():
    nid = service._new_id("Hello World", "post")
    assert nid.startswith("hello-world-")
    suffix = nid.rsplit("-", 1)[1]
    assert len(suffix) == 6 and all(c in "0123456789abcdef" for c in suffix)


# --------------------------------------------------------------------------- #
# CV parsing (pure)
# --------------------------------------------------------------------------- #
def test_parse_cv_extracts_meta_and_sections():
    cv = service.parse_cv(SAMPLE_CV, seeded=True, updated_at="2026-01-01T00:00:00+00:00")
    assert cv.meta.name == "Jane Doe"
    assert cv.meta.title == "Staff Engineer · Platforms"
    assert "jane@example.com" in cv.meta.contact
    headings = [s.heading for s in cv.sections]
    assert headings == ["SUMMARY", "EXPERIENCE", "SKILLS"]
    assert cv.seeded is True


def test_parse_cv_h3_stays_in_h2_body():
    cv = service.parse_cv(SAMPLE_CV, seeded=False, updated_at=None)
    exp = next(s for s in cv.sections if s.id == "experience")
    # The H3 sub-heading must NOT become its own top-level section — it lives in body.
    assert "### Acme — Senior" in exp.body
    assert "Did things." in exp.body
    assert all(s.heading != "Acme — Senior" for s in cv.sections)


def test_parse_cv_attaches_proof_chips():
    cv = service.parse_cv(SAMPLE_CV, seeded=True, updated_at=None)
    skills = next(s for s in cv.sections if s.id == "skills")
    # SECTION_PROOF maps "skills" -> 2 blog chips.
    assert len(skills.proof) == 2
    assert {p.kind for p in skills.proof} == {"blog"}


def test_parse_cv_empty_is_safe():
    cv = service.parse_cv("", seeded=False, updated_at=None)
    assert cv.sections == [] and cv.meta.name == ""


# --------------------------------------------------------------------------- #
# CV seed + read + update (md_store)
# --------------------------------------------------------------------------- #
def test_get_cv_seeds_once_and_commits(isolated_paths, monkeypatch):
    # Force the embedded fallback (no source file dependency in the test).
    monkeypatch.setenv("LIFEOS_CAREER_CV_SOURCE", str(isolated_paths / "no-such-cv.md"))
    cv = service.get_cv()
    assert cv.seeded is True
    assert cv.meta.name == "Nguyen Van Tinh"
    assert any(s.id == "summary" for s in cv.sections)
    # commit landed
    log = _git_log(isolated_paths / "data")
    assert any("seed CV" in line for line in log), log
    # second read does NOT re-seed (idempotent: no new "seed CV" commit count growth)
    log_before = len([l for l in _git_log(isolated_paths / "data") if "seed CV from source" in l])
    service.get_cv()
    log_after = len([l for l in _git_log(isolated_paths / "data") if "seed CV from source" in l])
    assert log_before == log_after == 1


def test_update_cv_replaces_and_marks_unseeded(isolated_paths, monkeypatch):
    monkeypatch.setenv("LIFEOS_CAREER_CV_SOURCE", str(isolated_paths / "no-such-cv.md"))
    service.get_cv()  # seed first
    cv = service.update_cv(SAMPLE_CV)
    assert cv.seeded is False
    assert cv.meta.name == "Jane Doe"
    # persisted: raw read-back reflects the edit
    raw = service.get_cv_raw()
    assert "Jane Doe" in raw and "Nguyen Van Tinh" not in raw


# --------------------------------------------------------------------------- #
# Blog CRUD
# --------------------------------------------------------------------------- #
def test_blog_seed_on_first_list(isolated_paths):
    posts, warnings = service.list_blog()
    assert warnings == []
    titles = [p.title for p in posts]
    assert "Code-Enforce What The Prompt Asks" in titles
    assert "Self-Improving Agent Loop" in titles
    # one published, one draft (mirrors source)
    statuses = {p.title: p.status for p in posts}
    assert statuses["Code-Enforce What The Prompt Asks"] == "published"
    assert statuses["Self-Improving Agent Loop"] == "draft"


def test_blog_seed_idempotent(isolated_paths):
    service.list_blog()
    n1 = len(service.list_blog()[0])
    n2 = len(service.list_blog()[0])
    assert n1 == n2  # no duplicate re-seed


def test_blog_create_read_update_delete(isolated_paths):
    service.list_blog()  # trigger seed so we operate on a populated store
    created = service.create_blog(BlogInput(title="New Post", dek="hi", status="draft", tags=["x"]))
    assert created.id.startswith("new-post-")
    assert created.createdAt == created.updatedAt
    # commit landed
    log = _git_log(isolated_paths / "data")
    assert any(f"create blog {created.id}" in l for l in log), log

    got = service.get_blog(created.id)
    assert got is not None and got.dek == "hi" and got.tags == ["x"]

    updated = service.update_blog(created.id, BlogInput(title="New Post", dek="bye", status="published", url="https://x"))
    assert updated is not None
    assert updated.createdAt == created.createdAt and updated.updatedAt >= created.updatedAt
    assert service.get_blog(created.id).status == "published"
    assert service.get_blog(created.id).dek == "bye"

    assert service.delete_blog(created.id) is True
    assert service.get_blog(created.id) is None
    assert service.delete_blog(created.id) is False  # idempotent absent → False


def test_blog_update_absent_returns_none(isolated_paths):
    assert service.update_blog("nope-abc123", BlogInput(title="x")) is None


def test_blog_fail_open_on_malformed(isolated_paths):
    service.list_blog()  # seed
    # write a junk file into the blog dir
    md_store.write_file("career/blog/broken.md", "not a valid note", "junk")
    posts, warnings = service.list_blog()
    assert any("broken" in w for w in warnings)
    # valid seeds still returned
    assert any(p.title == "Self-Improving Agent Loop" for p in posts)


# --------------------------------------------------------------------------- #
# Demo CRUD
# --------------------------------------------------------------------------- #
def test_demo_seed_on_first_list(isolated_paths):
    items, warnings = service.list_demo()
    assert warnings == []
    names = [i.name for i in items]
    assert "OutboundOS" in names and "DevCrew" in names and "Life OS" in names
    out = next(i for i in items if i.name == "OutboundOS")
    assert out.status == "live" and out.url and out.loc == 122000


def test_demo_create_read_update_delete(isolated_paths):
    service.list_demo()
    created = service.create_demo(DemoInput(name="My Demo", desc="d", url="https://d", status="wip"))
    assert created.id.startswith("my-demo-")
    got = service.get_demo(created.id)
    assert got is not None and got.status == "wip"
    updated = service.update_demo(created.id, DemoInput(name="My Demo", desc="d2", status="live"))
    assert updated is not None and updated.createdAt == created.createdAt
    assert service.get_demo(created.id).status == "live"
    assert service.delete_demo(created.id) is True
    assert service.get_demo(created.id) is None


# --------------------------------------------------------------------------- #
# API (FastAPI endpoints end-to-end)
# --------------------------------------------------------------------------- #
@pytest.fixture
def client(isolated_paths, monkeypatch):
    monkeypatch.setenv("LIFEOS_CAREER_CV_SOURCE", str(isolated_paths / "no-such-cv.md"))
    from main import app
    return TestClient(app)


def test_api_cv_get_and_raw_and_put(client):
    r = client.get("/career/cv")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["meta"]["name"] == "Nguyen Van Tinh"
    assert len(body["data"]["sections"]) >= 1

    raw = client.get("/career/cv/raw").json()
    assert "markdown" in raw["data"] and raw["data"]["markdown"].startswith("# Nguyen")

    put = client.put("/career/cv", json={"markdown": SAMPLE_CV})
    assert put.status_code == 200
    assert put.json()["data"]["meta"]["name"] == "Jane Doe"
    assert put.json()["data"]["seeded"] is False


def test_api_cv_put_rejects_empty(client):
    r = client.put("/career/cv", json={"markdown": ""})
    assert r.status_code == 422


def test_api_blog_crud(client):
    lst = client.get("/career/blog").json()
    assert lst["success"] is True and len(lst["data"]) >= 2

    created = client.post("/career/blog", json={"title": "API Post", "dek": "x", "status": "draft"})
    assert created.status_code == 200
    pid = created.json()["data"]["id"]

    got = client.get(f"/career/blog/{pid}")
    assert got.status_code == 200 and got.json()["data"]["title"] == "API Post"

    upd = client.put(f"/career/blog/{pid}", json={"title": "API Post", "status": "published", "url": "https://x"})
    assert upd.status_code == 200 and upd.json()["data"]["status"] == "published"

    assert client.delete(f"/career/blog/{pid}").status_code == 200
    assert client.get(f"/career/blog/{pid}").status_code == 404


def test_api_blog_create_rejects_blank_title(client):
    r = client.post("/career/blog", json={"title": "   "})
    assert r.status_code == 422


def test_api_career_404s_are_agent_error_shape(client):
    """AGENT-ERROR-P4 (#46): blog + demo bad-id 404s → flat {error:{code:NOT_FOUND,hint,retryable:false}},
    NOT raw {detail}. (GET blog + GET demo on a nonexistent id.)"""
    for path in ("/career/blog/nope-xyz", "/career/demo/nope-xyz"):
        r = client.get(path)
        assert r.status_code == 404, path
        j = r.json()
        assert "detail" not in j, f"{path}: must be flat error, not {{detail}}"
        assert j["error"]["code"] == "NOT_FOUND" and j["error"]["retryable"] is False and j["error"]["hint"]


def test_api_demo_crud(client):
    lst = client.get("/career/demo").json()
    assert lst["success"] is True and len(lst["data"]) >= 3

    created = client.post("/career/demo", json={"name": "API Demo", "desc": "d", "status": "wip"})
    assert created.status_code == 200
    did = created.json()["data"]["id"]
    assert client.get(f"/career/demo/{did}").json()["data"]["status"] == "wip"
    assert client.put(f"/career/demo/{did}", json={"name": "API Demo", "status": "live"}).json()["data"]["status"] == "live"
    assert client.delete(f"/career/demo/{did}").status_code == 200
    assert client.get(f"/career/demo/{did}").status_code == 404


def test_api_demo_bad_status_422(client):
    r = client.post("/career/demo", json={"name": "X", "status": "nonsense"})
    assert r.status_code == 422
