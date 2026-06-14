/* ============================================================
   SCREENS — Wiki / Knowledge vault (W1–W5 + P1)
   ============================================================ */
(function(){
const SM = window.STATUS_META;
const OP = window.WIKI_OP;

// ---- shared bits ----
function statusPill(status){
  const m = SM[status] || SM.fleeting;
  return `<span class="wstatus" style="color:${m.color};background:${m.dim}">${m.lbl}</span>`;
}
function trustBadge(tier, author){
  if(tier==='candidate') return `<span class="wtrust cand" title="Do agent đề xuất — chưa ratify">${icon('i-ai')} candidate</span>`;
  return `<span class="wtrust ver" title="Người xác nhận">${icon('i-check')} verified</span>`;
}
function typeBadge(t){
  return `<span class="wtype">${t==='concept'?'◆ concept':t==='literature'?'▢ literature':'⬡ '+t}</span>`;
}
// render [[id|title]] and [[ghost]] links inside note body
function renderWikiLinks(md){
  let html = md
    .replace(/\[\[(\d+)\|([^\]]+)\]\]/g, (m,id,t)=>`<a class="wlink" data-route="note/${id}">${t}</a>`)
    .replace(/\[\[(\d+)\]\]/g, (m,id)=>`<a class="wlink" data-route="note/${id}">#${id}</a>`)
    .replace(/\[\[([^\]\d][^\]]*)\]\]/g, (m,t)=>`<a class="wlink ghost" title="Ghost link — note chưa tồn tại">${t}</a>`)
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br>');
  return '<p>'+html+'</p>';
}

// ============================================================
//  W1 — Vault Overview
// ============================================================
SCREENS.wiki = function(){
  const s = WIKI.stats;
  const tile = (lbl, val, sub, cls)=>`<div class="wtile">
    <span class="wtile-l">${lbl}</span><span class="wtile-v ${cls||''}">${val}</span><span class="wtile-s">${sub}</span></div>`;

  const inboxItem = it => `<div class="wlist-row clickable" data-route="inbox">
    <span class="runi run" style="width:16px;height:16px;font-size:9px">${it.linkCount}</span>
    <div class="wlr-body"><div class="wlr-t">${it.aiSuggest?it.aiSuggest.titleClaim:'<span class="faint">chưa có title</span>'}</div>
    <div class="wlr-s mut">${it.rawContent.slice(0,70)}…</div></div>
    <span class="faint" style="font-family:var(--mono);font-size:10px;white-space:nowrap">${it.captured}</span>
  </div>`;

  const orphanRow = o => `<div class="wlist-row clickable" data-route="note/${o.id}">
    <span class="worphan-deg">${o.degree}</span>
    <div class="wlr-body"><div class="wlr-t">${o.title}</div></div>
    ${statusPill(o.status)}
    <span class="faint" style="font-family:var(--mono);font-size:10px">${o.lastTouched}</span>
  </div>`;

  const actRow = a => {
    const op = OP[a.op]||{lbl:a.op,color:'var(--tx-1)'};
    return `<div class="wact-row">
      <span class="wact-ts num">${a.ts}</span>
      <span class="wact-op" style="color:${op.color};background:color-mix(in oklch,${op.color} 14%,transparent)">${op.lbl}</span>
      <span class="wact-actor ${a.actor}">${a.actor==='agent'?'◇ AI':'● bạn'}</span>
      <span class="wact-detail mut">${a.detail}</span>
    </div>`;
  };

  return `
  <div class="vtitle"><h1>Vault · Tri thức</h1><span class="sub">${s.totalNotes} notes · ${s.totalLinks} links · cập nhật ${s.asOf}</span>
    <span class="sp"></span>
    <button class="btn" data-route="graph">${icon('i-graph')} Graph</button>
    <button class="btn accent" id="wNewNote">${icon('i-plus')} Note mới</button>
  </div>

  <!-- search -->
  <div class="wsearch">
    <span class="pr">${icon('i-search')}</span>
    <input placeholder="Tìm full-text trong ${s.totalNotes} notes…  (FTS5 · gõ title hoặc nội dung)" readonly>
    <kbd>⌘F</kbd>
  </div>

  <!-- stat tiles -->
  <div class="wtiles">
    ${tile('Tổng notes', s.totalNotes, `${s.byStatus.evergreen} evergreen`, 'acc')}
    ${tile('Fleeting', s.byStatus.fleeting, 'chờ refine', 'amber')}
    ${tile('Developing', s.byStatus.developing, 'đang chín', 'blue')}
    ${tile('Tổng links', s.totalLinks, `mật độ ${s.pctWithLink}%`, 'pos')}
    ${tile('Orphan', s.orphanCount, 'degree = 0', s.orphanCount>3?'neg':'mut')}
    ${tile('Ghost links', s.ghostLinkCount, 'note chưa tạo', 'amber')}
  </div>

  <!-- density bar -->
  <div class="panel" style="padding:13px 16px">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:9px">
      <span class="kicker">Mật độ liên kết — chỉ số chất lượng vault</span>
      <span class="sp" style="flex:1"></span>
      <span class="num pos" style="font-size:13px;font-weight:700">${s.pctWithLink}%</span>
      <span class="faint" style="font-size:11px">notes có ≥1 link</span>
    </div>
    <div class="bar" style="height:8px"><i style="width:${s.pctWithLink}%;background:var(--green);box-shadow:0 0 8px -2px var(--green)"></i></div>
    <div class="hint" style="margin-top:8px">${s.orphanCount} orphan + ${s.ghostLinkCount} ghost links cần xử lý — vault khỏe khi mật độ &gt; 90%.</div>
  </div>

  <!-- 3 columns -->
  <div class="grid" style="grid-template-columns:1fr 1fr;align-items:start">
    <div class="panel">
      <div class="phead"><span class="kicker">Inbox cần refine</span>
        <span class="wstatus" style="color:var(--amber);background:var(--amber-dim)">${WIKI.inbox.length} fleeting</span>
        <span class="link" data-route="inbox" style="margin-left:auto">triage →</span>
      </div>
      <div class="wlist">${WIKI.inbox.slice(0,4).map(inboxItem).join('')}</div>
    </div>
    <div class="panel">
      <div class="phead"><span class="kicker">Orphan sweep</span>
        <span class="wstatus" style="color:var(--red);background:var(--red-dim)">${WIKI.orphans.length} cô lập</span>
        <span class="link" data-route="graph" style="margin-left:auto">xem graph →</span>
      </div>
      <div class="wlist">${WIKI.orphans.slice(0,4).map(orphanRow).join('')}</div>
    </div>
  </div>

  <div class="grid" style="grid-template-columns:1.5fr 1fr;align-items:start">
    <div class="panel">
      <div class="phead"><span class="kicker">Hoạt động gần đây · op-log</span><span class="hint" style="margin-left:auto">single-writer</span></div>
      <div class="wact-list">${WIKI.recentActivity.map(actRow).join('')}</div>
    </div>
    <div class="panel wproposal-mini">
      <div class="phead"><span class="kicker">Proposal queue</span>
        <span class="wstatus" style="color:var(--accent);background:var(--accent-dim)">${WIKI.proposals.length} chờ duyệt</span>
        <span class="link" data-route="proposals" style="margin-left:auto">duyệt →</span>
      </div>
      <div class="wlist" style="padding:8px">
        ${WIKI.proposals.slice(0,3).map(p=>`<div class="wprop-mini clickable" data-route="proposals">
          <span class="wprop-kind ${p.kind}">${propKindShort(p.kind)}</span>
          <div class="wlr-body"><div class="wlr-t" style="font-size:12px">${propTitle(p)}</div>
          <div class="wlr-s mut">${p.actor.replace('agent:','◇ ')}</div></div>
        </div>`).join('')}
      </div>
      <div style="padding:0 8px 10px"><div class="hint" style="padding:8px 10px;background:var(--bg-2);border-radius:8px;line-height:1.5">⚠ AI <b>không bao giờ</b> tự ghi vào note evergreen. Mọi đề xuất chờ bạn duyệt ở đây.</div></div>
    </div>
  </div>`;
};

function propKindShort(k){
  return { link_candidate:'link', moc_proposal:'MOC', merge_suggestion:'merge', agent_note:'note' }[k]||k;
}
function propTitle(p){
  if(p.kind==='link_candidate') return `${p.noteTitle} → ${p.targetTitle}`;
  if(p.kind==='merge_suggestion') return `${p.sourceTitle} ⇒ ${p.targetTitle}`;
  return p.title||'(proposal)';
}

// ============================================================
//  W2 — Note View / Edit
// ============================================================
SCREENS.note = function(id){
  id = parseInt(id)||47;
  const n = WIKI.notes[id] || WIKI.notes[47];
  const bl = WIKI.backlinks[n.id] || {linked:[],unlinked:[],outbound:[]};
  const sugg = WIKI.suggestions[n.id] || [];

  const outRow = o => o.isResolved
    ? `<a class="woutlink clickable" data-route="note/${o.id}">${icon('i-link')}<span>${o.title}</span><span class="faint">#${o.id}</span></a>`
    : `<div class="woutlink ghost">${icon('i-link')}<span>${o.ghost}</span><button class="btn sm ghost" style="margin-left:auto;padding:2px 8px">+ tạo note</button></div>`;

  const linkedRow = b => `<div class="wbl-row clickable" data-route="note/${b.id}">
    <div class="wbl-head"><b>${b.title}</b><span class="faint">#${b.id} ${b.anchor||''}</span></div>
    <div class="wbl-snip mut">${b.snippet}</div></div>`;

  const unlinkedRow = b => `<div class="wbl-row unlinked">
    <div class="wbl-head"><b>${b.title}</b><span class="faint">#${b.id}</span>
    <button class="btn sm" style="margin-left:auto;padding:2px 9px" data-wlink="${b.id}">${icon('i-link')} link nó</button></div>
    <div class="wbl-snip mut">${b.snippet}</div></div>`;

  const suggRow = sg => {
    if(sg.state==='rejected') return `<div class="wsugg rejected">
      <div class="wsugg-top"><b style="text-decoration:line-through;color:var(--tx-2)">${sg.title}</b><span class="faint">đã reject</span></div>
      <div class="wsugg-why faint">${sg.why}</div></div>`;
    return `<div class="wsugg" data-sugg="${sg.id}">
      <div class="wsugg-top"><b>${sg.title}</b><span class="wconf">conf ${(sg.confidence*100).toFixed(0)}%</span></div>
      <div class="wsugg-why"><span class="acc">why:</span> ${sg.why}</div>
      <div class="wsugg-acts">
        <button class="btn sm accent" data-acc-sugg="${sg.id}">${icon('i-check')} Accept</button>
        <button class="btn sm" data-rej-sugg="${sg.id}">${icon('i-x')} Reject</button>
        <button class="btn sm ghost" data-pin-sugg="${sg.id}">${icon('i-pin')} Pin</button>
      </div></div>`;
  };

  return `
  <div class="wnote-head">
    <button class="btn sm ghost" data-route="wiki">${icon('i-back')} Vault</button>
    <span class="wnote-id num">#${n.id}</span>
    ${statusPill(n.status)}
    ${typeBadge(n.noteType)}
    ${trustBadge(n.trustTier, n.author)}
    <span class="sp" style="flex:1"></span>
    <button class="btn sm" data-route="graph">${icon('i-graph')} graph quanh note</button>
    <button class="btn sm accent" id="wEditNote">${icon('i-note')} Sửa</button>
  </div>

  <div class="wnote-grid">
    <!-- main column -->
    <div class="wnote-main">
      <div class="panel wnote-body-panel">
        <input class="wnote-title" value="${n.title}" readonly>
        <div class="wnote-meta">
          ${n.aliases.length?`<span class="wmeta-k">aliases:</span> ${n.aliases.map(a=>`<span class="tagchip">${a}</span>`).join(' ')}`:''}
          <span class="wmeta-k" style="margin-left:${n.aliases.length?'10px':'0'}">tags:</span> ${n.tags.map(t=>`<span class="tagchip">#${t}</span>`).join(' ')}
          <span class="sp" style="flex:1"></span>
          <span class="faint" style="font-family:var(--mono);font-size:10.5px">tạo ${n.created} · sửa ${n.updated}</span>
        </div>
        <div class="wnote-body">${renderWikiLinks(n.content)}</div>
        ${n.trustTier==='candidate'?`<div class="wcand-warn">${icon('i-ai')} Note này do agent viết — đang ở trạng thái <b>candidate</b>. Ratify ở Proposal queue để thành verified.</div>`:''}
      </div>

      <!-- outbound -->
      <div class="panel">
        <div class="phead"><span class="kicker">Outbound links</span><span class="hint" style="margin-left:auto">${bl.outbound.length} liên kết ra</span></div>
        <div class="woutlist">${bl.outbound.map(outRow).join('')}</div>
      </div>
    </div>

    <!-- side column -->
    <div class="wnote-side">
      <!-- AI suggestions -->
      <div class="panel wsugg-panel">
        <div class="phead"><span class="kicker">${icon('i-ai')} Link gợi ý · AI candidate</span></div>
        <div class="wsugg-list">${sugg.map(suggRow).join('')}</div>
        <div class="hint" style="padding:0 14px 12px">Chỉ là <b>candidate</b> tới khi accept — không bao giờ tự ghi. Reject được nhớ.</div>
      </div>

      <!-- backlinks -->
      <div class="panel">
        <div class="phead"><span class="kicker">Backlinks</span><span class="hint" style="margin-left:auto">${bl.linked.length} linked · ${bl.unlinked.length} unlinked</span></div>
        <div class="wbl-sec-lbl">Linked mentions</div>
        <div class="wbl-list">${bl.linked.map(linkedRow).join('')||'<div class="wbl-empty">chưa có</div>'}</div>
        <div class="wbl-sec-lbl">Unlinked mentions <span class="faint">— nhắc tên nhưng chưa link</span></div>
        <div class="wbl-list">${bl.unlinked.map(unlinkedRow).join('')||'<div class="wbl-empty">không có</div>'}</div>
      </div>
    </div>
  </div>`;
};

// ============================================================
//  W3 — Inbox / Refine
// ============================================================
let _refineId = null;
SCREENS.inbox = function(){
  const items = WIKI.inbox;
  const active = _refineId ? items.find(i=>i.id===_refineId) : items[0];

  const listRow = it => `<div class="winbox-row ${active&&active.id===it.id?'on':''}" data-refine="${it.id}">
    <span class="wcap-src ${it.captureSource}">${capLabel(it.captureSource)}</span>
    <div class="wlr-body">
      <div class="wlr-t">${it.aiSuggest?it.aiSuggest.titleClaim:'<span class="faint">— chưa title —</span>'}</div>
      <div class="wlr-s mut">${it.rawContent.slice(0,56)}…</div>
    </div>
    ${it.aiSuggest&&it.aiSuggest.dupeOf?`<span class="wdupe-flag" title="Trùng note đã có">dupe</span>`:''}
    <span class="faint" style="font-family:var(--mono);font-size:10px;white-space:nowrap">${it.captured}</span>
  </div>`;

  const ai = active.aiSuggest;
  const hasLink = active.linkCount > 0;

  return `
  <div class="vtitle"><h1>Inbox / Refine</h1><span class="sub">${items.length} fleeting · triage → atomic + ≥1 link</span>
    <span class="sp"></span>
    <span class="winbox-progress"><b class="num">${items.length}</b> → <b class="num pos">0</b></span>
  </div>

  <div class="winbox-grid">
    <!-- list -->
    <div class="panel" style="overflow:hidden;display:flex;flex-direction:column">
      <div class="phead"><span class="kicker">Hàng chờ · cũ → mới</span><span class="hint" style="margin-left:auto">${items.length}</span></div>
      <div class="winbox-list">${items.map(listRow).join('')}</div>
    </div>

    <!-- refine panel -->
    <div class="panel wrefine">
      <div class="phead">
        <span class="kicker">Refine · 1 note</span>
        <span class="wcap-src ${active.captureSource}" style="margin-left:8px">${capLabel(active.captureSource)} · ${active.captured}</span>
      </div>
      <div class="wrefine-body">
        <!-- raw -->
        <div class="wrefine-sec">
          <div class="wrefine-lbl">Raw capture <span class="faint">— giữ nguyên, không sửa lúc capture</span></div>
          <div class="wraw">${active.rawContent}</div>
        </div>

        <!-- AI suggest -->
        ${ai ? `<div class="wrefine-sec wai-box">
          <div class="wrefine-lbl">${icon('i-ai')} AI gợi ý <span class="faint">— async, non-blocking</span></div>
          <div class="wai-row"><span class="wai-k">title-claim</span><span class="wai-v"><b>${ai.titleClaim}</b></span></div>
          <div class="wai-row"><span class="wai-k">summary</span><span class="wai-v">${ai.summary}</span></div>
          <div class="wai-row"><span class="wai-k">atomicity</span><span class="wai-v ${ai.atomicityFlag.includes('✓')?'pos':'amber'}">${ai.atomicityFlag}</span></div>
          ${ai.dupeOf?`<div class="wai-row"><span class="wai-k">dupe</span><span class="wai-v"><span class="neg">⚠ trùng ${(ai.dupeOf.similarity*100).toFixed(0)}% với</span> <a class="wlink" data-route="note/${ai.dupeOf.id}">#${ai.dupeOf.id} ${ai.dupeOf.title}</a>
            <button class="btn sm" style="margin-left:8px;padding:2px 9px" id="wMergeBtn">${icon('i-merge')} merge</button></span></div>`:''}
        </div>` : `<div class="wrefine-sec"><div class="hint" style="padding:10px;background:var(--bg-2);border-radius:8px">${icon('i-clock')} AI đang phân tích… (async)</div></div>`}

        <!-- human edit -->
        <div class="wrefine-sec">
          <div class="wrefine-lbl">Viết lại → atomic prose + claim-title</div>
          <input class="wrefine-title" placeholder="Claim-title (một mệnh đề khẳng định)…" value="${ai?ai.titleClaim:''}">
          <textarea class="wrefine-text" placeholder="Viết lại thành atomic prose…">${active.rawContent}</textarea>
          <div class="wrefine-status">
            <span class="faint" style="font-size:11px">Status:</span>
            <div class="seg"><button>fleeting</button><button class="on">developing</button><button>evergreen</button></div>
          </div>
        </div>

        <!-- hard gate -->
        <div class="wgate ${hasLink?'ok':'blocked'}">
          <div class="wgate-icon">${hasLink?icon('i-check'):icon('i-link')}</div>
          <div class="wgate-body">
            <b>${hasLink?'Cổng link: đã qua':'Cổng cứng: cần ≥1 link'}</b>
            <span class="mut">${hasLink?'Note có liên kết — sẵn sàng rời triage.':'Thêm 1 link (manual [[ ]] hoặc accept gợi ý) trước khi Done.'}</span>
          </div>
          ${!hasLink?`<button class="btn sm" id="wAddLink">${icon('i-link')} + link</button>`:''}
        </div>

        <!-- AI link suggestion inline -->
        <div class="wrefine-sec">
          <div class="wrefine-lbl">${icon('i-ai')} Link gợi ý</div>
          <div class="wsugg" data-sugg="inline">
            <div class="wsugg-top"><b>Concept-orientation beats source-orientation</b><span class="wconf">conf 79%</span></div>
            <div class="wsugg-why"><span class="acc">why:</span> Cùng bàn cách tổ chức tri thức để tái kết hợp.</div>
            <div class="wsugg-acts"><button class="btn sm accent" id="wAcceptInline">${icon('i-check')} Accept link</button><button class="btn sm">${icon('i-x')} Reject</button></div>
          </div>
        </div>

        <div class="wrefine-foot">
          <button class="btn ghost">Bỏ qua</button>
          <button class="btn ${hasLink?'accent':''}" ${hasLink?'':'disabled'} id="wDoneRefine">${icon('i-check')} Done refine ${hasLink?'':'· cần link'}</button>
        </div>
      </div>
    </div>
  </div>`;
};
function capLabel(s){ return { command_bar:'⌘ cmd', quick_add:'+ quick', mcp_agent:'◇ MCP', daily_note:'☷ daily' }[s]||s; }

// expose refine helpers for interactions.js
window._refineSelect = function(id){ _refineId = id; if((location.hash||'').slice(1).startsWith('inbox')) navigate(); };
window._refineForceLink = function(){
  const it = WIKI.inbox.find(i=>i.id===_refineId) || WIKI.inbox[0];
  if(it){ it.linkCount = 1; navigate(); }
};

// ============================================================
//  W4 — Graph Explorer
// ============================================================
SCREENS.graph = function(){
  const g = WIKI.graph;
  const W=760, H=440;
  const statusColor = { evergreen:'var(--green)', developing:'var(--blue)', fleeting:'var(--amber)' };
  const node = g.nodes.find(n=>n.id===g.center);

  // edges
  const edgeSvg = g.edges.map(e=>{
    const a = g.nodes.find(n=>n.id===e.source), b = g.nodes.find(n=>n.id===e.target);
    if(!a||!b) return '';
    const x1=a.x/100*W, y1=a.y/100*H, x2=b.x/100*W, y2=b.y/100*H;
    const mx=(x1+x2)/2, my=(y1+y2)/2;
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${e.isResolved?'var(--line-2)':'var(--amber)'}" stroke-width="1.4" ${e.isResolved?'':'stroke-dasharray="3 3"'}/>
      <text x="${mx}" y="${my-3}" class="wedge-lbl">${e.type}</text>`;
  }).join('');

  // nodes
  const nodeSvg = g.nodes.map(n=>{
    const x=n.x/100*W, y=n.y/100*H, r=8+n.degree*2.4;
    const col = n.ghost?'var(--tx-2)':statusColor[n.status]||'var(--tx-1)';
    const isCenter = n.id===g.center;
    return `<g class="wgnode clickable" data-route="note/${n.id}" transform="translate(${x},${y})">
      ${isCenter?`<circle r="${r+6}" fill="none" stroke="${col}" stroke-width="1.5" stroke-dasharray="2 3" opacity=".6"/>`:''}
      <circle r="${r}" fill="${n.ghost?'transparent':col}" stroke="${col}" stroke-width="${n.ghost?'1.5':'0'}" ${n.ghost?'stroke-dasharray="3 2"':''} fill-opacity="${n.orphan?'.25':'1'}" style="${isCenter?'filter:drop-shadow(0 0 8px '+col+')':''}"/>
      ${n.orphan?`<circle r="${r+3}" fill="none" stroke="var(--red)" stroke-width="1" stroke-dasharray="2 2"/>`:''}
      <text y="${r+13}" class="wgnode-lbl" ${isCenter?'style="font-weight:700;fill:var(--tx-0)"':''}>${n.title.length>22?n.title.slice(0,20)+'…':n.title}</text>
      <text y="3" text-anchor="middle" class="wgnode-id">${n.id}</text>
    </g>`;
  }).join('');

  return `
  <div class="vtitle"><h1>Graph Explorer</h1><span class="sub">ego-graph quanh #${g.center} · depth 2 · ${g.nodes.length} nodes</span>
    <span class="sp"></span>
    <div class="seg"><button>depth 1</button><button class="on">depth 2</button></div>
    <button class="btn">${icon('i-search')} Đổi note tâm</button>
  </div>

  <div class="wgraph-grid">
    <div class="panel wgraph-canvas">
      <div class="phead"><span class="kicker">Ego-graph · #${g.center} ${node?node.title:''}</span>
        <span class="sp" style="flex:1"></span>
        <span class="wgleg"><span class="wgl-dot" style="background:var(--green)"></span>evergreen</span>
        <span class="wgleg"><span class="wgl-dot" style="background:var(--blue)"></span>developing</span>
        <span class="wgleg"><span class="wgl-dot" style="background:var(--amber)"></span>fleeting</span>
        <span class="wgleg"><span class="wgl-dot" style="border:1px dashed var(--red);background:transparent"></span>orphan</span>
      </div>
      <div class="wgraph-stage">
        <svg viewBox="0 0 ${W} ${H}" style="width:100%;height:100%">
          <g class="wedges">${edgeSvg}</g>
          <g class="wnodes">${nodeSvg}</g>
        </svg>
      </div>
    </div>

    <div class="wgraph-side">
      <div class="panel">
        <div class="phead"><span class="kicker">Bộ lọc</span></div>
        <div style="padding:12px 14px;display:flex;flex-direction:column;gap:10px">
          <div class="wfilter-row"><span class="mut">Status</span><div class="seg"><button class="on">all</button><button>ever</button><button>dev</button></div></div>
          <div class="wfilter-row"><span class="mut">Highlight</span>
            <div style="display:flex;gap:6px"><button class="tab on">orphan</button><button class="tab">ghost</button></div>
          </div>
          <div class="wfilter-row"><span class="mut">Tag</span><input class="wfilter-inp" placeholder="#pkm…" readonly></div>
        </div>
      </div>

      <div class="panel wcluster-box">
        <div class="phead"><span class="kicker">${icon('i-ai')} Cluster hint</span></div>
        ${g.clusters.map(c=>`<div class="wcluster">
          <div class="wcluster-top"><b>${c.label}</b><span class="wconf">mật độ ${(c.density*100).toFixed(0)}%</span></div>
          <div class="wcluster-members">${c.noteIds.map(id=>{const nn=g.nodes.find(x=>x.id===id);return `<span class="tagchip clickable" data-route="note/${id}">#${id} ${nn?nn.title.slice(0,14):''}</span>`;}).join('')}</div>
          ${c.mocSuggestion?`<button class="btn sm accent" style="margin-top:10px;width:100%" data-route="moc">${icon('i-moc')} Cụm này → tạo MOC</button>`:''}
        </div>`).join('')}
        <div class="hint" style="padding:0 14px 12px">AI khoanh cụm dày — ứng viên Map of Content.</div>
      </div>
    </div>
  </div>`;
};

// ============================================================
//  W5 — MOC Workspace
// ============================================================
SCREENS.moc = function(){
  const m = WIKI.mocDraft;
  const memberRow = (mem,i)=>`<div class="wmoc-member" draggable="true">
    <span class="wmoc-drag">⠿</span>
    <span class="wmoc-num num">${String(i+1).padStart(2,'0')}</span>
    <div class="wlr-body"><a class="wlr-t wlink" data-route="note/${mem.id}">${mem.title}</a><span class="faint" style="font-family:var(--mono);font-size:10px">#${mem.id}</span></div>
    ${statusPill(mem.status)}
    <button class="btn sm ghost" style="padding:2px 7px">${icon('i-x')}</button>
  </div>`;

  return `
  <div class="vtitle"><h1>MOC Workspace</h1><span class="sub">curate cụm "${m.clusterLabel}" → 1 note MOC</span>
    <span class="sp"></span>
    <button class="btn" data-route="graph">${icon('i-back')} Graph</button>
    <button class="btn accent" id="wRatifyMoc">${icon('i-check')} Ratify → tạo MOC</button>
  </div>

  <div class="wmoc-grid">
    <!-- members -->
    <div class="panel" style="overflow:hidden;display:flex;flex-direction:column">
      <div class="phead"><span class="kicker">Cluster members</span><span class="hint" style="margin-left:auto">${m.members.length} note · kéo để sắp</span></div>
      <div class="wmoc-members">${m.members.map(memberRow).join('')}</div>
      <div style="padding:10px 14px;border-top:1px solid var(--line)"><button class="btn sm ghost" style="width:100%">${icon('i-plus')} thêm note vào cụm</button></div>
    </div>

    <!-- draft + throughline + contradictions -->
    <div class="wmoc-main">
      <div class="panel wmoc-draft">
        <div class="phead"><span class="kicker">${icon('i-ai')} MOC draft · AI scaffold</span>
          <span class="wtrust cand" style="margin-left:auto">candidate</span></div>
        <div class="wmoc-scaffold">${renderWikiLinks(m.draftScaffold)}</div>
        <div class="wmoc-edit-hint hint">AI nháp khung — <b>bạn sửa/ratify</b>. AI propose, human dispose.</div>
      </div>

      <div class="panel wthroughline">
        <div class="phead"><span class="kicker">Throughline · sợi xuyên suốt</span></div>
        <div class="wmoc-through">${m.throughline}</div>
      </div>

      <div class="panel wcontra">
        <div class="phead"><span class="kicker">${icon('i-ai')} Contradiction surface</span><span class="hint" style="margin-left:auto">challenge, không summarize</span></div>
        ${m.contradictions.map(c=>`<div class="wcontra-row">
          <div class="wcontra-pair">
            <a class="wlink" data-route="note/${c.a}">#${c.a} ${c.aTitle}</a>
            <span class="wcontra-vs">⚡ mâu thuẫn</span>
            <a class="wlink" data-route="note/${c.b}">#${c.b} ${c.bTitle}</a>
          </div>
          <div class="wcontra-note mut">${c.note}</div>
          <div class="wcontra-acts"><button class="btn sm">Giữ cả hai</button><button class="btn sm">Note giải quyết</button></div>
        </div>`).join('')}
      </div>
    </div>
  </div>`;
};

// ============================================================
//  P1 — Proposal Queue
// ============================================================
SCREENS.proposals = function(){
  const props = WIKI.proposals;
  const kindMeta = {
    link_candidate:{ lbl:'link candidate', color:'var(--accent)', ic:'i-link' },
    moc_proposal:  { lbl:'MOC proposal', color:'var(--amber)', ic:'i-moc' },
    merge_suggestion:{ lbl:'merge', color:'var(--violet)', ic:'i-merge' },
    agent_note:    { lbl:'agent note', color:'var(--blue)', ic:'i-ai' },
  };

  const propCard = p => {
    const km = kindMeta[p.kind];
    let body = '';
    if(p.kind==='link_candidate') body = `<div class="wprop-link"><a class="wlink" data-route="note/${p.noteId}">#${p.noteId} ${p.noteTitle}</a> <span class="acc">→</span> <a class="wlink" data-route="note/${p.targetId}">#${p.targetId} ${p.targetTitle}</a></div>`;
    else if(p.kind==='merge_suggestion') body = `<div class="wprop-link"><span class="tagchip">${p.sourceTitle}</span> <span class="violet">⇒</span> <a class="wlink" data-route="note/${p.targetId}">#${p.targetId} ${p.targetTitle}</a> <span class="wconf">${(p.confidence*100).toFixed(0)}%</span></div>`;
    else if(p.kind==='moc_proposal') body = `<div class="wprop-link"><b>${p.title}</b> — <span class="mut">${p.memberIds.map(id=>'#'+id).join(' · ')}</span></div>`;
    else if(p.kind==='agent_note') body = `<div class="wprop-link"><b>${p.title}</b> <span class="wtrust cand">candidate</span></div><div class="wprop-content mut">${p.content}</div>`;

    return `<div class="wprop-card" data-prop="${p.id}">
      <div class="wprop-head">
        <span class="wprop-kind-badge" style="color:${km.color};background:color-mix(in oklch,${km.color} 14%,transparent)">${icon(km.ic)} ${km.lbl}</span>
        <span class="wprop-actor">${p.actor.replace('agent:','◇ ')}</span>
        <span class="sp" style="flex:1"></span>
        <span class="faint" style="font-family:var(--mono);font-size:10.5px">${p.created} · ${p.correlationId}</span>
      </div>
      ${body}
      <div class="wprop-why"><span class="acc">why:</span> ${p.why}</div>
      ${p.confidence&&p.confidence>0.85&&p.kind==='merge_suggestion'?`<div class="wprop-warn">⚠ Contradiction-check: trùng cao với note đã có — review kỹ trước khi merge.</div>`:''}
      <div class="wprop-acts">
        <button class="btn sm accent" data-acc-prop="${p.id}">${icon('i-check')} Accept</button>
        <button class="btn sm" data-rej-prop="${p.id}">${icon('i-x')} Reject</button>
        <button class="btn sm ghost" data-pin-prop="${p.id}">${icon('i-pin')} Pin</button>
        <span class="sp" style="flex:1"></span>
        <span class="hint">accept → apply qua op-log → verified</span>
      </div>
    </div>`;
  };

  const counts = {};
  props.forEach(p=>counts[p.kind]=(counts[p.kind]||0)+1);

  return `
  <div class="vtitle"><h1>Proposal Queue</h1><span class="sub">${props.length} mutation AI chờ duyệt · trust boundary</span>
    <span class="sp"></span>
    <div class="seg"><button class="on">tất cả</button><button>link</button><button>MOC</button><button>merge</button></div>
  </div>

  <div class="panel" style="padding:13px 16px;display:flex;gap:12px;align-items:center">
    <span class="dot acc pulse"></span>
    <div style="flex:1;font-size:12.5px;line-height:1.5"><b style="font-family:var(--mono)">AI write-back luôn vào đây trước.</b> <span class="mut">Không bao giờ sửa thân note evergreen tại chỗ. Accept → apply qua changes-queue. Reject → nhớ, không gợi lại.</span></div>
    ${Object.entries(counts).map(([k,n])=>`<span class="tagchip">${kindMeta[k].lbl}: ${n}</span>`).join('')}
  </div>

  <div class="wprop-list">${props.map(propCard).join('')}</div>`;
};

})();
