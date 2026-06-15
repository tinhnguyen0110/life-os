"""modules/career — the Career / personal-brand cockpit module (CAR-1).

A self-contained feature module (registry pattern, like modules/notes / modules/
projects): the user's career revolves around three living surfaces —

  - **CV**      — the CV lives IN life-os: one markdown doc parsed into sections,
                  each linkable to proof (case studies / blog / repo-evidence),
                  editable + exportable.
  - **Blog**    — a list of blog posts (draft/published) with editable metadata.
  - **Demo**    — a showcase of live demos / flagship projects.

All three persist as markdown-on-git via md_store (ARCH §6 — metadata is md_store,
not SQLite; nothing here is time-series). Seeded ONCE from the user's existing
artifacts (CV_v3_Trustworthy_AI.md, blog/*.js, case-study-*.md, repo-evidence.md)
when the surface is empty — seeding is idempotent (never overwrites user edits).

The registry discovers MODULE from router.py.
"""
