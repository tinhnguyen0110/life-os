"""modules/career/seed.py — one-time idempotent seeds for the career cockpit.

Seeds are applied ONLY when a surface is empty (no cv.md / no blog posts / no
demo items), so they NEVER clobber a user's edits. The CV seed prefers the user's
real source file (``CV_v3_Trustworthy_AI.md`` under the tinhdev root, configurable
via ``LIFEOS_CAREER_CV_SOURCE``); if that's absent (e.g. a container without the
file mounted) it falls back to a trimmed embedded copy.

Blog + demo seeds are derived from the user's real artifacts (blog/*.js,
case-study-*.md, repo-evidence.md) and embedded here so the module is
self-contained. NDA-safe: iNmobi stays "consumer music & social app" (CV already
anonymized) — never expanded; no inmobi/ or PSA/ content.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger("life-os.career.seed")


# --------------------------------------------------------------------------- #
# CV source resolution                                                          #
# --------------------------------------------------------------------------- #
def cv_source_path() -> Path:
    """Resolve the user's real CV markdown source. Precedence:
      1. ``LIFEOS_CAREER_CV_SOURCE`` (explicit override / tests).
      2. ``<TINHDEV_ROOT>/CV_v3_Trustworthy_AI.md`` — TINHDEV_ROOT is the same
         mount-aware root config.py uses for project repos (``LIFEOS_TINHDEV_ROOT``,
         set to ``/tinhdev`` in the compose mount). This is the host-file-source-
         must-mount lesson: in the container, derived paths resolve to ``/``, so we
         MUST read the env that points at the read-only mount.
      3. Fallback: three up from backend/ (bare-metal dev where repos sit beside life-os).
    """
    env = os.environ.get("LIFEOS_CAREER_CV_SOURCE")
    if env:
        return Path(env).expanduser()
    tinhdev_root_env = os.environ.get("LIFEOS_TINHDEV_ROOT")
    if tinhdev_root_env:
        return Path(tinhdev_root_env).expanduser() / "CV_v3_Trustworthy_AI.md"
    backend_root = Path(__file__).resolve().parent.parent.parent  # modules/career -> modules -> backend
    tinhdev_root = backend_root.parent.parent  # backend -> life-os -> tinhdev_root
    return tinhdev_root / "CV_v3_Trustworthy_AI.md"


def load_cv_markdown() -> str:
    """The CV markdown to seed: the real source file if readable, else the embedded
    fallback. Always returns non-empty markdown."""
    src = cv_source_path()
    try:
        if src.is_file():
            text = src.read_text(encoding="utf-8")
            if text.strip():
                logger.info("career: seeding CV from source %s", src)
                return text
    except OSError as exc:  # fail-soft → embedded fallback
        logger.warning("career: CV source %s unreadable (%s) — using embedded fallback", src, exc)
    logger.info("career: seeding CV from embedded fallback (source absent)")
    return _EMBEDDED_CV


# Trimmed embedded fallback — used only when the real source file isn't present.
# Anonymization preserved (iNmobi = "consumer music & social entertainment app").
_EMBEDDED_CV = """# Nguyen Van Tinh
## AI Automation Engineer · Agentic Systems & Trustworthy AI

📞 0889 129 664 · ✉ tinh2kqb@gmail.com · 🔗 github.com/tinhnguyen0110 · 🌐 tinhdev.com · 📍 Quang Binh, Vietnam

## SUMMARY
I build agentic systems that run autonomously **and stay trustworthy** — designing the orchestration that lets AI agents drive real business workflows, the safety gates and anti-hallucination invariants that make their output something a human can be accountable for, and the learning loop that lets the system improve itself with a human in the decision seat.

## EXPERIENCE
See the live CV for full experience. (Embedded fallback — mount the real source for full content.)

## FLAGSHIP PROJECTS
OutboundOS · DevCrew · Life OS · Groundwork · LexiOps · Crawl2Insight.

## SKILLS
Agentic systems, Trustworthy AI, Learning & eval, Core engineering, Cloud & infra, ML/CV.

## EDUCATION
- B.Sc. Computer Science — Industrial University of Ho Chi Minh City (2018 – 2022), GPA 3.25/4.0
"""


# --------------------------------------------------------------------------- #
# Proof-link defaults per CV section (heading-slug -> proof chips)              #
# --------------------------------------------------------------------------- #
# Attaches the user's existing case studies / blog posts / demos to the right CV
# sections so the "living CV → proof" link is real on first load.
SECTION_PROOF: dict[str, list[dict]] = {
    "experience": [
        {"kind": "case-study", "label": "Independent Verification (50+ APIs)", "ref": "case-study-1-verification"},
        {"kind": "case-study", "label": "Supervision Dashboard in 5h", "ref": "case-study-2-dashboard"},
    ],
    "flagship-projects": [
        {"kind": "demo", "label": "OutboundOS demo", "ref": "outboundos"},
        {"kind": "demo", "label": "DevCrew demo", "ref": "devcrew"},
        {"kind": "demo", "label": "Life OS demo", "ref": "life-os"},
        {"kind": "repo", "label": "Repo evidence bank", "ref": "research/repo-evidence.md"},
    ],
    "skills": [
        {"kind": "blog", "label": "Anti-hallucination engineering", "ref": "blog-anti-hallucination"},
        {"kind": "blog", "label": "Self-improving agent loop", "ref": "blog-self-improving-loop"},
    ],
}


# --------------------------------------------------------------------------- #
# Blog seeds — derived from blog/*.js (NDA-safe, real metadata)                 #
# --------------------------------------------------------------------------- #
BLOG_SEEDS: list[dict] = [
    {
        "title": "Code-Enforce What The Prompt Asks",
        "subtitle": "Anti-Hallucination Engineering Cho Agent",
        "dek": "Prompt chỉ giảm TẦN SUẤT một failure. Chỉ có code mới GUARANTEE nó không "
               "xảy ra. Bốn pattern thật từ OutboundOS + DevCrew — provenance guard, "
               "honest-refuse, fail-direction, red-team.",
        "status": "published",
        "url": "https://blog.tinhdev.com/validate-before-you-build",
        "tags": ["AI Agents", "Trustworthy AI", "Engineering"],
        "publishedDate": "2026-06-14",
        "readMinutes": 10,
        "wordCount": 1980,
    },
    {
        "title": "Self-Improving Agent Loop",
        "subtitle": "Với Một Human Vẫn Ngồi Trong Ghế",
        "dek": "\"Self-improving agent\" thường bán như một closed loop tự rewrite qua đêm. "
               "Tôi build cái loop đó — và CỐ Ý để hở đúng một điểm: adoption. Cái gap đó "
               "chính là lý do nó trustworthy.",
        "status": "draft",
        "url": None,
        "tags": ["AI Agents", "Self-Improving", "Human-in-the-loop"],
        "publishedDate": None,
        "readMinutes": 9,
        "wordCount": 1850,
    },
]


# --------------------------------------------------------------------------- #
# Demo seeds — derived from CV flagship projects + repo-evidence.md             #
# --------------------------------------------------------------------------- #
DEMO_SEEDS: list[dict] = [
    {
        "name": "OutboundOS",
        "tagline": "Agent-First Pipeline with a Self-Improving Loop",
        "desc": "A multi-phase agentic pipeline (research → personalize → QA → classify → "
                "draft). Code-enforced anti-hallucination grounding (rejects a hallucinated "
                "URL even when the prompt says copy it verbatim), honest-refuse as a "
                "first-class path, and a closed learning loop with a human in the adopt seat.",
        "url": "https://demo.tinhdev.com/outboundos/",
        "repo": None,
        "status": "live",
        "tags": ["agentic", "anti-hallucination", "learning-loop"],
        "loc": 122000,
    },
    {
        "name": "DevCrew",
        "tagline": "Registry-Driven AI Team Orchestrator",
        "desc": "An orchestrator that drives a team of specialist agents (Claude Agent SDK, "
                "persistent sessions, live Kanban + SSE, BYOK for 10+ providers). Per-project "
                "Docker sandbox + a self-authored red-team harness attacking the bash "
                "guardrail. Scales by config: new team = 1 registry entry + 1 MCP + 1 prompt.",
        "url": "https://devcrew.tinhdev.com",
        "repo": None,
        "status": "live",
        "tags": ["orchestration", "agent-safety", "registry-driven"],
        "loc": 110000,
    },
    {
        "name": "Life OS",
        "tagline": "Personal AI Operating System (built solo via a 5-agent AI team)",
        "desc": "A project/finance/automation tracing OS built in ~11 hours across 15 sprints "
                "by orchestrating an AI dev team under a self-authored process. Registry-driven "
                "module auto-discovery; markdown-on-git memory + SQLite.",
        "url": "https://demo.tinhdev.com/life-command",
        "repo": None,
        "status": "live",
        "tags": ["personal-os", "velocity-proof", "registry-driven"],
        "loc": 27700,
    },
    {
        "name": "Groundwork",
        "tagline": "QA & Governance for AI Agents",
        "desc": "A management layer for the full API test lifecycle (Postman + MCP) where every "
                "AI action is attributable and reversible: human-AI dual-path, JWT-isolated "
                "workspaces, scoped agent tokens, a replayable audit trail, and an AES-GCM PII "
                "scrubber on stored payloads.",
        "url": "https://groundwork.tinhdev.com",
        "repo": None,
        "status": "live",
        "tags": ["governance", "audit", "agent-safety"],
        "loc": 194000,
    },
    {
        "name": "LexiOps · Crawl2Insight",
        "tagline": "Cloud-Native AIOps / Data Platforms",
        "desc": "LexiOps: a LangGraph multi-agent AIOps copilot for autonomous Kubernetes ops "
                "(per-tool RBAC over MCP) + a Vietnamese Legal RAG chatbot. Crawl2Insight: an "
                "end-to-end job-data platform on GKE (Terraform, ArgoCD GitOps, Airflow, "
                "LiteLLM gateway, full observability).",
        "url": "https://demo.tinhdev.com",
        "repo": "https://github.com/tinhnguyen0110",
        "status": "live",
        "tags": ["aiops", "rag", "cloud-native"],
        "loc": None,
    },
]
