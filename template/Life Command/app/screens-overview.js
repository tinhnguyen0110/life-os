/* ============================================================
   SCREENS — Overview (S1 Home)
   ============================================================ */
(function(){
const healthDot = { act:'var(--green)', slow:'var(--amber)', stall:'var(--red)', dead:'var(--tx-2)' };
const healthBadge = { act:'sb-act', slow:'sb-slow', stall:'sb-stall', dead:'sb-dead' };

function projRow(p){
  return `<tr class="clickable" data-route="project/${p.id}">
    <td class="pn">${p.name}</td>
    <td><span class="hd"><span class="d" style="background:${healthDot[p.health]}"></span>${p.healthLbl}</span></td>
    <td><span class="barc"><i style="width:${p.progress}%;background:${healthDot[p.health]}"></i></span>${p.progress}%</td>
    <td class="${p.users>0?'pos':'faint'}">${p.users}</td>
    <td class="faint">${p.last}</td>
    <td class="mut">${p.next}</td>
  </tr>`;
}

function alertRow(a){
  const c = {r:'var(--red)',a:'var(--amber)',g:'var(--green)'}[a.level];
  return `<div class="al"><span class="ad" style="background:${c}"></span><div><div class="at">${a.text}</div><div class="as">${a.src} · ${a.ago}</div></div></div>`;
}

function actRow(a){
  return `<div class="actmini clickable" data-route="activity">
    <span class="runi ${a.status}">${a.status==='ok'?'✓':a.status==='err'?'✗':'●'}</span>
    <div class="am-body"><div class="am-t"><b>${a.name}</b> ${a.desc}</div><div class="am-s">${a.ago} trước · ${a.dur}</div></div>
  </div>`;
}

SCREENS.home = function(){
  const n = DB.net, c = DB.claude;
  return `
  <div class="cmdbar">
    <span class="pr">&gt;</span>
    <input placeholder="dca btc 2000 · open portfolio-reader · run morning-brief · ask 'vì sao reader chững?'" id="homeCmd">
    <kbd>⌘K</kbd>
  </div>

  <!-- KPI strip -->
  <div class="grid" style="grid-template-columns:2fr 1fr 1fr;height:192px">
    <div class="card glowcard nwc">
      <div class="chartbg">${spark(n.series, accent(), 640, 120)}</div>
      <div class="kicker">Tổng tài sản · USD</div>
      <div class="nwnum num">${fmtUSD(n.total)}</div>
      <div class="nwd"><span class="pos num">▲ ${fmtSign(n.day)} · +${n.dayPct}% hôm nay</span><span class="pos num">+${n.weekPct}% tuần</span></div>
      <div class="allocbar">${n.alloc.map(a=>`<div class="s" style="width:${a.pct}%;background:${a.color}"></div>`).join('')}</div>
      <div class="alleg">${n.alloc.map(a=>`<span><i style="background:${a.color}"></i>${a.k} ${a.pct}%</span>`).join('')}</div>
    </div>
    <div class="card">
      <div class="kicker" style="margin-bottom:4px">P&L theo kênh</div>
      ${n.alloc.map(a=>`<div class="mrow"><span class="k">${a.k}</span><span class="v num ${a.pnl>0?'pos':a.pnl<0?'neg':''}" style="${a.pnl===0?'color:var(--tx-0)':''}">${a.pnl===0?fmtUSD(a.val):fmtSign(a.pnl)}</span></div>`).join('')}
    </div>
    <div class="card quotacard" data-route="claude" style="cursor:pointer">
      <div class="kicker" style="align-self:flex-start">Claude · quota</div>
      <div class="gauge" style="width:104px;height:104px">${gauge(c.pct, accent(), 104)}<div class="lab"><b style="font-size:23px;color:${accent()}">${c.pct}%</b><span style="font-size:9px">đã đốt</span></div></div>
      <div class="num" style="font-size:11px;color:var(--accent-soft)">↻ reset ${c.resetIn}</div>
      <div class="num" style="font-size:10px;color:var(--tx-2)">${(c.used/1000).toFixed(1)}k / ${c.cap/1000}k · weekly ${c.weekly}%</div>
    </div>
  </div>

  <!-- mid -->
  <div class="grid" style="grid-template-columns:1.7fr 1fr;align-items:start">
    <div class="panel" style="overflow:hidden">
      <div class="phead"><span class="kicker">Dự án đang chạy</span><span class="link" data-route="projects">+ thêm / xem tất cả</span></div>
      <table class="dtable">
        <thead><tr><th>Dự án</th><th>Sức khỏe</th><th>Tiến độ</th><th>Users</th><th>Hoạt động</th><th>Next</th></tr></thead>
        <tbody>${DB.projects.map(projRow).join('')}</tbody>
      </table>
      <div style="padding:11px 16px;border-top:1px solid var(--line);font-family:var(--mono);font-size:11px;color:var(--tx-2);display:flex;gap:16px">
        <span>4 dự án · <span class="pos">2 active</span> · <span class="mid">1 chậm</span> · <span class="neg">1 đứng</span></span>
        <span style="margin-left:auto">tổng <span class="pos">4 user thật</span></span>
      </div>
    </div>
    <div class="card briefcard">
      <div class="bh"><div class="ic">✦</div><b>Brief hôm nay</b><span class="t">08:42 · opus</span></div>
      ${DB.brief.map(b=>`<div class="pr"><span class="n">${b.n}</span><span>${b.html}</span></div>`).join('')}
      <div class="ask" data-route="ai"><span style="color:var(--green)">&gt;</span> hỏi sâu: <b>"vì sao portfolio-reader chững?"</b></div>
    </div>
  </div>

  <!-- bottom: alerts + activity feed widget -->
  <div class="grid g-2" style="align-items:start">
    <div class="panel alertpanel">
      <div class="phead"><span class="kicker">Cảnh báo</span><span class="dot r"></span><span class="hint">${DB.alerts.length} mới</span><span class="link" data-route="market" style="margin-left:auto">xem tất cả →</span></div>
      <div class="alist">${DB.alerts.slice(0,4).map(alertRow).join('')}</div>
    </div>
    <div class="panel">
      <div class="phead"><span class="kicker">Activity Feed</span><span class="dot g pulse"></span><span class="hint">automation đang chạy</span><span class="link" data-route="activity" style="margin-left:auto">${DB.activity.length} runs hôm nay →</span></div>
      <div class="actlist">${DB.activity.slice(0,4).map(actRow).join('')}</div>
    </div>
  </div>
  `;
};

// command input → fake parse
window._afterRender = null;
})();
