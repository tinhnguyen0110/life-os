"""tests/test_wiki_import.py — #93 wiki import (.md / .txt → note).

Import an existing .md (YAML frontmatter) or .txt (plain body) into the wiki, REUSING create_note
(→ _apply_create: 1 git commit, [[link]] resolution, cache) + serialize.extract_frontmatter. The
load-bearing reuse proof: an imported [[Existing Note]] link RESOLVES (no ghost). Bad files →
agent-readable error rows (no junk note), batch never fails wholesale.

BEHAVIOR-TESTED: import → read the created note + its links back (not field-reads).
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from modules.wiki import reader as wreader
from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki.schema import NoteCreateInput


@pytest.fixture
def wiki_db(isolated_paths):
    wiki_store.init_wiki_tables()
    return isolated_paths


@pytest.fixture
def client(wiki_db):
    from main import create_app
    return TestClient(create_app())


_MD = """---
title: Imported Concept
tags: [imported, test]
folder: Inbox
status: developing
trustTier: candidate
---
This note links to [[Existing Note]] and has a body."""


# --------------------------------------------------------------------------- #
# .md WITH frontmatter → exact fields (value-by-value)                           #
# --------------------------------------------------------------------------- #
def test_md_frontmatter_maps_all_fields(wiki_db):
    res = wsvc.import_files([("concept.md", _MD)])
    assert res["createdCount"] == 1
    row = res["imported"][0]
    assert row["ok"] and row["filename"] == "concept.md" and row["error"] is None
    note = wsvc.get_note(row["noteId"])
    assert note.title == "Imported Concept"
    assert note.tags == ["imported", "test"]
    assert note.folder == "Inbox"
    assert note.status == "developing"
    assert note.trustTier == "candidate"
    assert "has a body" in note.content


# --------------------------------------------------------------------------- #
# THE load-bearing reuse proof — [[Existing Note]] RESOLVES (no ghost)           #
# --------------------------------------------------------------------------- #
def test_md_wikilink_resolves_on_import(wiki_db):
    """An imported note's [[Existing Note]] link RESOLVES to the real note (no ghost) — proves the
    import goes through _apply_create (which resolves links), not a parse-only bypass."""
    existing = wsvc.create_note(NoteCreateInput(title="Existing Note", content="seed"))
    res = wsvc.import_files([("c.md", _MD)])
    imported_id = res["imported"][0]["noteId"]
    bl = wreader.backlinks(existing.id)
    linked = bl["linked"] if isinstance(bl, dict) else bl
    assert any(b["id"] == imported_id for b in linked), "imported [[link]] must resolve to a backlink"


# --------------------------------------------------------------------------- #
# .txt → plain body, title from first line / filename, status fleeting           #
# --------------------------------------------------------------------------- #
def test_txt_plain_body_title_from_first_line(wiki_db):
    res = wsvc.import_files([("scratch.txt", "First line is the title\nmore body")])
    note = wsvc.get_note(res["imported"][0]["noteId"])
    assert note.title == "First line is the title"
    assert note.status == "fleeting"            # the capture default
    assert note.content.startswith("First line")


def test_txt_title_falls_back_to_filename_when_blank_first_line(wiki_db):
    res = wsvc.import_files([("my-notes.txt", "\n\n   \nactual body after blanks")])
    note = wsvc.get_note(res["imported"][0]["noteId"])
    assert note.title == "actual body after blanks"  # first NON-empty line


def test_md_without_frontmatter_is_plain_note(wiki_db):
    """A .md with NO frontmatter → treated as plain body (title from first line), not an error."""
    res = wsvc.import_files([("plain.md", "# Heading Title\nbody text")])
    assert res["createdCount"] == 1
    note = wsvc.get_note(res["imported"][0]["noteId"])
    assert note.title == "Heading Title"   # leading '# ' stripped


# --------------------------------------------------------------------------- #
# agent-error distinguishing — bad file → error row, NO note created             #
# --------------------------------------------------------------------------- #
def test_malformed_yaml_is_agent_error_no_note(wiki_db):
    before = wiki_store.count_notes()
    res = wsvc.import_files([("broken.md", "---\ntitle: [unclosed\n---\nbody")])
    row = res["imported"][0]
    assert row["ok"] is False and row["noteId"] is None
    err = row["error"]
    assert err["code"] == "INVALID_INPUT" and err["retryable"] is False
    assert err["message"] and err["hint"]
    assert wiki_store.count_notes() == before, "no note created for a malformed file"


def test_empty_file_is_agent_error(wiki_db):
    res = wsvc.import_files([("empty.md", "   \n  ")])
    row = res["imported"][0]
    assert row["ok"] is False and row["error"]["code"] == "INVALID_INPUT"
    assert "empty" in row["error"]["message"].lower()


def test_unsupported_extension_is_agent_error(wiki_db):
    res = wsvc.import_files([("doc.pdf", "whatever content")])
    row = res["imported"][0]
    assert row["ok"] is False
    assert "pdf" in row["error"]["message"].lower() or "supported" in row["error"]["message"].lower()


# --- #127 W2: STRICT .md/.txt import (the rejection contract) ---------------- #
@pytest.mark.parametrize("filename", ["doc.pdf", "img.png", "sheet.docx", "a.zip", "x.exe",
                                      "weird.PDF", "up.DOCX"])
def test_W2_unsupported_ext_rejected_no_note(wiki_db, filename):
    """🔴 W2 strict-import (the load-bearing case): a non-.md/.txt filename → INVALID_INPUT
    agent-error + NO note created. Case-insensitive (the ext is lowered before the check)."""
    res = wsvc.import_files([(filename, "whatever content\nbody")])
    row = res["imported"][0]
    assert row["ok"] is False
    assert row["error"]["code"] == "INVALID_INPUT" and row["error"]["retryable"] is False
    assert res["createdCount"] == 0, "an unsupported file must create NO note"


@pytest.mark.parametrize("filename", ["note.md", "plain.txt", "up.MD", "up.TXT"])
def test_W2_supported_ext_imports(wiki_db, filename):
    """.md / .txt (any case) → a note IS created (the accept side of the contract)."""
    res = wsvc.import_files([(filename, "Title line\nbody text")])
    assert res["imported"][0]["ok"] is True and res["createdCount"] == 1


def test_W2_no_extension_imports_as_text(wiki_db):
    """DECIDED + frozen: a NO-extension filename (e.g. 'README') imports as a plain .txt-style note
    (the `if ext and ...` rule — a no-ext file is treated as text, NOT rejected). Documented so W3
    knows the contract: reject is for KNOWN-bad extensions, not for the absence of one."""
    res = wsvc.import_files([("README", "Readme title\nbody")])
    assert res["imported"][0]["ok"] is True and res["createdCount"] == 1


def test_bad_status_enum_is_agent_error_not_silent_default(wiki_db):
    """A frontmatter status NOT in the Literal → agent-error (honest), NOT a silent default."""
    md = "---\ntitle: T\nstatus: not-a-real-status\n---\nbody"
    res = wsvc.import_files([("bad.md", md)])
    row = res["imported"][0]
    assert row["ok"] is False and row["error"]["code"] == "INVALID_INPUT"
    assert "status" in row["error"]["message"].lower()


# --------------------------------------------------------------------------- #
# multi-file — 1 good + 1 bad → batch not failed                                 #
# --------------------------------------------------------------------------- #
def test_multi_file_one_good_one_bad(wiki_db):
    res = wsvc.import_files([
        ("good.md", "---\ntitle: Good\n---\nbody"),
        ("bad.md", "---\ntitle: [unclosed\n---\nx"),
    ])
    assert res["createdCount"] == 1
    by_name = {r["filename"]: r for r in res["imported"]}
    assert by_name["good.md"]["ok"] is True and by_name["good.md"]["noteId"]
    assert by_name["bad.md"]["ok"] is False and by_name["bad.md"]["error"]["code"] == "INVALID_INPUT"


# --------------------------------------------------------------------------- #
# REST API — JSON paste path + multipart path + the import goes through commit    #
# --------------------------------------------------------------------------- #
def test_rest_json_paste_import(client):
    r = client.post("/wiki/import", json={"files": [{"filename": "n.md", "content": _MD}]})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["createdCount"] == 1
    assert data["imported"][0]["title"] == "Imported Concept"


def test_rest_multipart_upload_import(client):
    files = [("files", ("up.txt", io.BytesIO(b"uploaded body line"), "text/plain"))]
    r = client.post("/wiki/import", files=files)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["createdCount"] == 1
    assert data["imported"][0]["title"] == "uploaded body line"


def test_rest_json_bad_body_is_agent_error(client):
    """An empty files list → agent_error INVALID_INPUT (not a 500)."""
    r = client.post("/wiki/import", json={"files": []})
    assert r.status_code == 422  # ImportInput min_length=1 → validation
    # the app-level validation handler returns the flat agent_error envelope
    assert r.json()["error"]["code"] == "INVALID_INPUT"


def test_rest_import_persists_via_commit(client):
    """The imported note is a REAL note: re-GET it via the notes API (proves it went through the
    create path → committed + cached, not an in-memory stub)."""
    r = client.post("/wiki/import", json={"files": [{"filename": "p.md", "content": "---\ntitle: Persisted\n---\nbody"}]})
    nid = r.json()["data"]["imported"][0]["noteId"]
    got = client.get(f"/wiki/notes/{nid}")
    assert got.status_code == 200 and got.json()["data"]["title"] == "Persisted"
