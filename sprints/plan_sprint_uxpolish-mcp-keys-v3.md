# plan_sprint_uxpolish-mcp-keys-v3 (#164) — COPY template 1:1, fix create-panel position+layout

> USER feedback: mcp-keys adapt "có giống mẫu đâu" — create-form ở GIỮA/cuối + layout không khớp template. Root cause: we RE-INTERPRETED the template instead of COPYING it. Fix = bám `template/mcp-key.html` 1:1, chỉ đổi MÀU → dark. Spec'd against template L244-299 (render order + #createPanel) + current page.tsx (the delta).

## Root cause (architect — honest)
mcp-keys-v2 (#162) got masthead/toolbar/aperture right but RE-LAID-OUT the create-form: it renders at page.tsx L350 (AFTER keys-list + key-once = bottom/middle) using an ad-hoc `.kicker` layout, NOT the template's `#createPanel` (a `.panel` directly under the toolbar). Lesson: when the user supplies a full template, COPY its structure/order/classes; only swap the palette. Do not re-interpret layout.

## The exact delta (template order vs current)
**Template render order (L244-334):**
`top-rule → mast → toolbar → #created(once) → #createPanel(panel, collapsed) → keylist-header(eyebrow+count) → #keyList → connPanel → catalog → toast`

**Current page.tsx order:**
`mast → toolbar → keys-empty/keyList → key-once(L328) → createPanel(L350) → connect → catalog`
→ TWO problems: (1) createPanel is BELOW keyList (should be ABOVE, right after created-once); (2) createPanel uses ad-hoc `.kicker` not the template `.panel` structure.

## Scope IN (#164)

### 1. MOVE createPanel up — render order to match template
Reorder the JSX so render order = template:
`mcpk-mast → mcpk-toolbar → key-once(created) → CREATE-PANEL → keylist-header(eyebrow "Keys đang có" + count) → keyList → connect → catalog → toast`
The create-panel must render IMMEDIATELY after key-once (which is right after toolbar), BEFORE the keylist. Keep it gated on `showCreate` (collapsed by default — template #createPanel is hidden until btnNew).

### 2. REBUILD create-panel to template #createPanel structure (L281-299), dark palette
Replace the current ad-hoc `.kicker` create-form with the template panel structure (map classes to existing dark classes — `.panel`/`.ph`/`.pb`/`.field`/`.hint`/`.err`/`.editor-actions` — these already exist in tokens.css from the wiki/other panels; if a needed one is missing, add a `.mcpk-*` scoped rule, NOT a global):
```
<section class="panel" (mcpk-createpanel)>  // or existing .panel
  <div class="ph"> <span class="t">Tạo key mới</span> <span class="c" onClick=close style margin-left:auto cursor:pointer>✕ đóng</span> </div>
  <div class="pb">
    <div class="field">
      <label>Nhãn key <span class="hint">— tên gợi nhớ, vd "finance-agent" (tối đa 80 ký tự)</span></label>
      <input maxlength=80 placeholder="Nhãn (vd: finance-agent)" ...wire to label state>
      <div class="err" (show when validation fails)>Cần đặt nhãn cho key trước khi tạo.</div>
    </div>
    <div class="field" style margin-bottom:18px>
      <label>Phạm vi <span class="hint">— chọn domain hoặc tool lẻ mà key này được thấy</span></label>
      <McpScopeEditor catalog scope=createScope onChange=setCreateScope />   // = template #createEditor
    </div>
    <div class="editor-actions">
      <button class="btn primary" onClick=handleCreate>Tạo key</button>     // disabled/text "Đang tạo…" while creating OK
      <button class="btn" onClick=close>Huỷ</button>
    </div>
  </div>
</section>
```

### 3. empty-state CTA opens THE SAME createPanel
The keys-empty "+ Key mới" CTA (`keys-empty-cta`) sets `showCreate=true` → opens the create-panel above. Do NOT render a separate inline form in the empty-state.

## Scope OUT
- KEEP unchanged (these are already correct per #162 + the user): masthead-98, aperture-bar (signature), toast, key-once mask (#128), 2-step delete, full CRUD, connect/catalog collapsible, all data-testids.
- Do NOT change behavior/logic/handlers — pure JSX reorder + create-panel restructure. Same useMcpKeys/create/validation/createScope state.
- 🔴 ONLY palette differs from template — dark tokens. Keep template's structure/spacing/class semantics. Do NOT re-interpret.
- No global-token mod (scoped .mcpk-* if a new rule needed). No new API.

## Verify-criteria (side-by-side vs template)
1. Click "+ Tạo key mới" → create-panel appears DIRECTLY UNDER the toolbar (above keys-list), NOT at bottom/middle.
2. Create-panel layout matches template L281-299: header "Tạo key mới · ✕ đóng" (✕ right) + field(label+hint+input+err) + field(label+hint+scope editor) + [Tạo key primary][Huỷ].
3. empty-state CTA opens the same panel (no separate inline form).
4. Render order top-to-bottom = mast→toolbar→key-once→createPanel→keylist→connect→catalog→toast.
5. Full CRUD still works (create→key-once masked→delete 2-step→empty), all testids present (≥ the 33 from #162, 0 dropped).
6. Dark, no paper-leak. vitest green, tsc clean, console clean.
7. tokens.css diff (if any) = scoped .mcpk-* only.

## Serialization (CRITICAL)
#164 touches `mcp-keys/page.tsx` + (maybe) `tokens.css`. #163 (round-2 A1/C1a) is IN FLIGHT on `tokens.css` (uncommitted). → **#164 DISPATCHES ONLY AFTER #163 COMMITS** (same-file serialization on tokens.css). Do not run both on tokens.css at once.

## Risk: MEDIUM (JSX reorder + create-panel restructure — behavior-preserving but touches the main render tree; 4-step must verify 0 testid dropped + CRUD intact + render order).
