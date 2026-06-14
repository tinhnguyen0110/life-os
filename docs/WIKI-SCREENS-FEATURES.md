# Life OS — Wiki-LLM · Screens Features + Data (for design)

> Input để design (không layout — designer tự dựng). Mỗi screen: mục đích · features · DATA shape cụ thể (field thật, khớp M1/M4 spec).
> Khung chung kế thừa life-os: Sidebar (thêm nhóm "Tri thức"/Wiki) · Top bar (breadcrumb + API live + Sync) · Command bar (`>` prefix, thêm verb `note`/`link`) · Ticker tape đáy.
> Identity: **integer-ID** (`47.md`), title = frontmatter mutable, link `[[47|title]]`. LLM/chat = Claude Code QUA MCP (không nhúng trong app) → KHÔNG có screen "chat box" trong app.

---

## Tổng quan: 5 screen + 1 panel tái dùng

| # | Screen | Route | Mục đích 1 câu |
|---|---|---|---|
| W1 | **Wiki Home / Vault Overview** | `/wiki` | Cửa vào kho tri thức: thống kê vault + inbox cần xử lý + orphan + hoạt động gần đây |
| W2 | **Note View/Edit** | `/wiki/[id]` | Đọc/sửa 1 note + backlinks + outbound + link-suggestion + provenance |
| W3 | **Inbox / Refine** | `/wiki/inbox` | Triage note `fleeting` → atomic + gắn link (≥1 link hard-gate) trước khi rời |
| W4 | **Graph Explorer** | `/wiki/graph` | Ego-graph (1-2 hop quanh 1 note) — thấy hàng xóm + cluster bằng mắt |
| W5 | **MOC Workspace** | `/wiki/moc/[id]` | Bàn làm việc curate: gom cluster → 1 note MOC nối members + nêu throughline |
| P1 | **Candidate/Proposal Queue** (panel, dùng ở W1+W2) | — | Hàng chờ AI đề xuất (link/MOC/merge) — accept/reject/pin, KHÔNG bao giờ auto-apply |

> Bản tối giản (build trước, theo backend-first): W1 + W2 + W3. W4 (graph viz) + W5 (MOC) + P1 (proposal queue) là lớp sau.

---

## W1 — Wiki Home / Vault Overview · `/wiki`

**Mục đích:** Cửa vào. Trả lời "kho tri thức của tôi đang thế nào + tôi cần xử lý gì hôm nay".

### Features
- **Tile thống kê vault** (4-6 số): tổng notes · theo status (fleeting/developing/evergreen) · tổng links · note orphan (degree=0) · ghost links (link trỏ tới note chưa tồn tại) · % notes có ≥1 link (mật độ = chỉ số chất lượng).
- **Inbox cần refine** (rút gọn): N note `fleeting` chờ triage, click → W3. Badge số ở sidebar.
- **Orphan sweep** (rút gọn): list note degree=0 hoặc stale (lâu không đụng) → click vào note → gợi gắn link.
- **Hoạt động gần đây:** note vừa tạo/sửa (từ op-log) — thời gian + loại op (create/edit/link/refine) + actor (human/agent).
- **Proposal queue rút gọn** (P1): N đề xuất AI đang chờ duyệt (link/MOC/merge) → xem tất cả.
- **Search nhanh:** ô FTS5 (full-text) → gõ → kết quả note (title + snippet match) → Enter mở.
- **Nút "+ Note mới"** → tạo note `fleeting` vào inbox (không phân loại lúc viết).

### DATA (GET /api/wiki/overview)
```json
{
  "stats": {
    "totalNotes": 142,
    "byStatus": { "fleeting": 8, "developing": 31, "evergreen": 103 },
    "totalLinks": 487,
    "orphanCount": 6,
    "ghostLinkCount": 3,
    "pctWithLink": 94.2,
    "asOf": "2026-06-13T10:00:00Z"
  },
  "inbox": [
    { "id": 47, "title": "Knowledge work accretes", "status": "fleeting",
      "created": "2026-06-13T08:12:00Z", "snippet": "raw dump về cách...", "linkCount": 0 }
  ],
  "orphans": [
    { "id": 12, "title": "Spaced repetition is interest-driven", "status": "evergreen",
      "degree": 0, "lastTouched": "2026-04-01T..." }
  ],
  "recentActivity": [
    { "ts": "2026-06-13T09:55:00Z", "op": "edit", "actor": "human", "noteId": 88, "noteTitle": "MOCs are workstations" },
    { "ts": "2026-06-13T09:40:00Z", "op": "link_candidate", "actor": "agent", "noteId": 47, "detail": "đề xuất [[47]]→[[88]]" }
  ],
  "proposalCount": 4
}
```
> `op` enum: create · edit · link · link_candidate · refine · merge · moc_proposal · delete.
> `actor` enum: human · agent.

---

## W2 — Note View/Edit · `/wiki/[id]` (id = integer)

**Mục đích:** Đơn vị trung tâm. Đọc/sửa 1 atomic note + thấy MỌI kết nối của nó (backlink + outbound + đề xuất).

### Features
- **Header note:** title (claim-title, sửa được — chỉ sửa frontmatter, KHÔNG rewrite link nào) · integer-ID hiển thị (`#47`) · status pill (fleeting/developing/evergreen — đổi tại chỗ, soft status) · aliases · tags · created/updated.
- **Provenance/trust badge:** loại note (concept "bạn kết luận Y" vs literature "nguồn nói X") + trust-tier (verified human / candidate agent). Note do agent viết → badge "candidate", chưa sửa thân note người.
- **Body editor:** markdown, link `[[47|title]]` autocomplete (gõ `[[` → search title→id). Hỗ trợ `^block-id` cho citation passage.
- **Outbound links:** list link note này TRỎ RA (resolved + ghost link chưa resolve, ghost hiển thị khác màu + nút "tạo note này").
- **Backlinks panel** (2 phần):
  - *Linked mentions:* note khác `[[47]]` tới note này (title + snippet ngữ cảnh quanh chỗ nhắc).
  - *Unlinked mentions:* note khác nhắc title/alias nhưng CHƯA link → nút "link nó".
- **Link suggestions (AI candidate):** danh sách note AI đề xuất nên nối, **mỗi cái có GIẢI THÍCH WHY** (vì sao liên quan) + nút accept/reject/pin. **Chỉ là candidate tới khi accept — không bao giờ tự ghi.** Reject được nhớ (không gợi lại).
- **Citation-safe:** nếu note này từng được cite (note_id + span) → hiện. Edit đoạn có `^block-id` → cảnh báo "citation có thể lệch".

### DATA
```jsonc
// GET /api/wiki/notes/47
{
  "id": 47,
  "title": "Knowledge work accretes",
  "aliases": ["accretion model of knowledge"],
  "status": "evergreen",
  "noteType": "concept",            // concept | literature
  "trustTier": "verified",          // verified (human) | candidate (agent)
  "author": "human",                // human | agent:<name>
  "tags": ["learning", "pkm"],
  "frontmatter": { /* raw */ },
  "content": "Markdown body với [[88|MOCs are workstations]]...",
  "created": "...", "updated": "...", "contentHash": "..."
}

// GET /api/wiki/notes/47/backlinks
{
  "linked": [
    { "id": 88, "title": "MOCs are workstations", "snippet": "...as [[47]] shows, work accretes...", "anchor": "^b3" }
  ],
  "unlinked": [
    { "id": 102, "title": "Evergreen notes compound", "snippet": "...knowledge work accretes over time..." }
  ],
  "outbound": [
    { "id": 88, "title": "MOCs are workstations", "isResolved": true },
    { "ghost": "Atomicity principle", "isResolved": false }    // ghost link: chưa có note
  ]
}

// GET /api/wiki/notes/47/suggestions   (AI link candidates)
{
  "candidates": [
    { "id": 31, "title": "Concept-orientation beats source-orientation",
      "why": "Cả hai bàn về cách tri thức tích lũy qua tái kết hợp ý — chia sẻ 3 inbound chung",
      "confidence": 0.82, "state": "candidate" }   // candidate | accepted | rejected | pinned
  ]
}
```

---

## W3 — Inbox / Refine · `/wiki/inbox`

**Mục đích:** Nơi `fleeting` → atomic. Ritual triage định kỳ (KHÔNG ở lúc capture). Cổng cứng: **≥1 link trước khi rời triage** (có ngoại lệ cold-start cho note đầu tiên).

### Features
- **List inbox:** note `status=fleeting` cũ→mới, mỗi cái: snippet raw + thời gian capture + nguồn capture (gõ tay / command-bar `note ...`).
- **Refine panel (1 note 1 lúc):**
  - AI gợi (async, non-blocking): title-claim đề xuất + summary + phát hiện note KHÔNG atomic ("có vẻ 2 ý — tách?") + flag trùng (dupe) note đã có.
  - Người: viết lại thành atomic prose + claim-title → đổi status (fleeting→developing/evergreen).
  - **Hard gate ≥1 link:** không cho "Done refine" tới khi có ≥1 link (manual `[[]]` hoặc accept 1 suggestion). Ngoại lệ cold-start: vault còn quá ít note → cho qua + cảnh báo.
  - AI link-suggestion ngay trong refine (cùng schema W2: why + accept/reject).
- **Dupe-merge:** nếu AI flag trùng → đề xuất merge → tạo **ID-redirect tombstone** (citation cũ tự follow sang note đích, KHÔNG vỡ).
- **Đếm tiến độ:** "8 → 0" còn lại trong inbox.

### DATA
```jsonc
// GET /api/wiki/inbox
{ "items": [
  { "id": 47, "title": null, "status": "fleeting", "rawContent": "dump...",
    "captured": "2026-06-13T08:12:00Z", "captureSource": "command_bar",
    "linkCount": 0,
    "aiSuggest": {                       // async, có thể null lúc đầu
      "titleClaim": "Knowledge work accretes",
      "summary": "...",
      "atomicityFlag": "có vẻ chứa 2 ý: (a)... (b)... — cân nhắc tách",
      "dupeOf": null                     // hoặc { id, title, similarity }
    }
  }
] }

// POST /api/wiki/notes/47/refine  → body { title, content, status, tags }
//   → 422 nếu linkCount==0 và không phải cold-start  (hard gate)
// POST /api/wiki/notes/merge  → { sourceId, targetId }  → tạo redirect tombstone
```
> `captureSource` enum: command_bar · quick_add · mcp_agent · daily_note.

---

## W4 — Graph Explorer · `/wiki/graph`

**Mục đích:** Thấy bằng mắt vùng quanh 1 note — hàng xóm + cluster (cụm = ứng viên MOC). KHÔNG phải global graph (>5k notes để Phase 2).

### Features
- **Ego-graph:** chọn 1 note tâm → vẽ 1-2 hop quanh nó (sigma.js). Node = note (size theo degree, màu theo status), edge = link (kiểu link: typed).
- **Hover node:** title + status + degree. Click node → mở W2.
- **Điều khiển:** đổi note tâm (search) · depth 1↔2 · lọc theo status/tag · highlight orphan/ghost.
- **Cluster hint:** AI khoanh vùng cụm dày → "cụm này có thể thành MOC" → nút tạo MOC workspace (→ W5).
- Hiệu năng: 200 notes ego-graph < 1s (Gate spec).

### DATA (GET /api/wiki/graph?note=47&depth=2)
```json
{
  "center": 47,
  "nodes": [
    { "id": 47, "title": "Knowledge work accretes", "status": "evergreen", "degree": 7 },
    { "id": 88, "title": "MOCs are workstations", "status": "evergreen", "degree": 4 },
    { "id": 12, "title": "Spaced repetition...", "status": "developing", "degree": 0 }
  ],
  "edges": [
    { "source": 47, "target": 88, "type": "relates", "isResolved": true }
  ],
  "clusters": [
    { "label": "PKM methodology", "noteIds": [47, 88, 31, 102], "density": 0.7,
      "mocSuggestion": true }
  ]
}
```
> `edge.type` (typed edge): relates · supports · contradicts · refines · example_of (kiểu cạnh — typed graph từ M1).

---

## W5 — MOC Workspace · `/wiki/moc/[id]`

**Mục đích:** Payoff. Bàn curate: gom 1 cluster → 1 note MOC (Map of Content) nối members + nêu throughline ("sợi xuyên suốt"). MOC = note có thể GHI (workstation), KHÁC panel backlinks.

### Features
- **Cluster members:** list note trong cụm (từ W4 hoặc AI detect) — kéo thả sắp xếp.
- **MOC draft (AI scaffold):** AI nháp khung MOC: nối members bằng `[[]]` + 1 đoạn throughline. **Người sửa/ratify** — AI propose, human dispose.
- **Surface contradiction:** AI chỉ ra "note A và note B mâu thuẫn" trong cụm → người quyết. ("Challenge my thinking", không phải "summarize").
- **Ratify → tạo note MOC thật** (status evergreen, type=moc) → vào graph như note thường.
- Mọi đề xuất AI = candidate, người accept.

### DATA
```jsonc
// GET /api/wiki/moc/draft?cluster=...  (hoặc từ clusterId)
{
  "members": [ { "id": 47, "title": "...", "status": "evergreen" }, ... ],
  "draftScaffold": "## PKM Methodology\nCác note này...\n- [[47|...]]\n- [[88|...]]",
  "throughline": "Tri thức tích lũy qua tái kết hợp; MOC là nơi tái kết hợp đó diễn ra.",
  "contradictions": [
    { "a": 12, "b": 88, "note": "12 nói review nên interest-driven; 88 ngụ ý lịch cố định" }
  ]
}
// POST /api/wiki/moc  → { title, memberIds, content }  → tạo note type=moc
```

---

## P1 — Candidate / Proposal Queue (panel, dùng ở W1 + W2)

**Mục đích:** Một chỗ DUY NHẤT gom mọi mutation AI đề xuất (link / MOC / merge / candidate-note từ MCP agent) → human review hàng loạt. Trust boundary: AI write-back luôn vào đây trước, KHÔNG bao giờ sửa thân note evergreen của người tại chỗ.

### Features
- **List proposal** theo loại: link-candidate · moc-proposal · merge-suggestion · agent-note (note do Claude Code qua MCP viết, status=candidate).
- Mỗi proposal: nội dung đề xuất + **WHY** (giải thích) + actor (agent nào) + thời gian + nút **accept / reject / pin**.
- Accept → apply (qua changes-queue/op-log) → thành verified. Reject → nhớ, không gợi lại.
- Contradiction-check trước khi accept (cảnh báo nếu chọi note đã có).
- Provenance: proposal từ MCP ghi rõ correlation-id (audit).

### DATA (GET /api/wiki/proposals)
```json
{
  "proposals": [
    { "id": "p_1", "kind": "link_candidate", "actor": "agent:claude-code",
      "noteId": 47, "targetId": 31, "why": "chia sẻ 3 inbound...", "confidence": 0.82,
      "created": "...", "correlationId": "mcp-abc123" },
    { "id": "p_2", "kind": "agent_note", "actor": "agent:claude-code",
      "title": "Distilled: spaced repetition debate", "status": "candidate",
      "content": "...", "why": "tổng hợp từ session 2026-06-13", "correlationId": "mcp-def456" }
  ]
}
```
> `kind` enum: link_candidate · moc_proposal · merge_suggestion · agent_note.

---

## Cross-cutting (mọi Wiki screen)

- **Command bar verbs mới:** `note <text>` (capture nhanh → inbox) · `link <id> <id>` · `open note <id>` · `find <query>` (FTS).
- **Sidebar:** thêm nhóm **"Tri thức"** → Wiki Home · Inbox (badge N fleeting) · Graph · Proposals (badge N chờ).
- **KHÔNG có chat box trong app** — hỏi-đáp grounded = Claude Code cắm MCP (M4). Citation Claude Code trả về được **code post-verify** (note_id tồn tại + span thật) — nếu cần surface, hiện ở đâu đó nhỏ "answered via MCP, N citations verified".
- **Mọi mutation** đi qua changes-queue/op-log (single-writer) — không ghi file trực tiếp.
- **Status đổi tại chỗ** (soft): fleeting → developing → evergreen, GIỮ id + inbound links.
- **Trust:** note agent = candidate (vào P1 queue); note human = verified. AI không tự sửa thân note evergreen.

---

## Ưu tiên build (gợi ý — anh/architect chốt)
1. **W2 (Note View/Edit)** + **W3 (Inbox/Refine)** — lõi capture→refine→link, dùng được từ note #1.
2. **W1 (Vault Overview)** — cửa vào, thống kê.
3. **P1 (Proposal Queue)** — khi M4 MCP có agent write-back.
4. **W4 (Graph)** + **W5 (MOC)** — lớp synthesize, payoff, sau cùng.
