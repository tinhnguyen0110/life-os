/* ============================================================
   SCREENS — Active layer (S13 Automation · S14 Activity Feed)
   ============================================================ */
(function(){
const trigIcon = { scheduled:'i-clock', event:'i-bolt', ondemand:'i-hand' };
const trigLabel = { scheduled:'Theo lịch', event:'Theo sự kiện', ondemand:'On-demand' };

// ---------- S13 Automation / Routines ----------
SCREENS.automation = function(){
  const active = DB.routines.filter(r=>r.on).length;
  const card = r=>`
    <div class="routine-card ${r.on?'':'off'}" ${r.on?'style="box-shadow:0 0 0 1px color-mix(in oklch, var(--accent) 14%, transparent)"':''}>
      <div class="rc-top">
        <div class="rc-ic">${icon(trigIcon[r.trigger])}</div>
        <div style="flex:1">
          <div class="rc-name">${r.name}</div>
          <div class="rc-trig"><span class="trigpill ${r.trigger}">${trigLabel[r.trigger]}</span> ${r.triggerLbl}</div>
        </div>
        <div class="toggle ${r.on?'on':''}" data-routine="${r.id}"></div>
      </div>
      <div class="rc-desc">${r.desc}</div>
      <div class="rc-action"><span class="faint">→ </span>${r.action}</div>
      <div class="rc-foot">
        <span class="runi ${r.lastResult}" style="width:15px;height:15px;font-size:9px">${r.lastResult==='ok'?'✓':'✗'}</span>
        <span>chạy cuối ${r.lastRun}</span>
        <span style="margin-left:auto">${r.runs.toLocaleString()} lần</span>
        <span class="link" data-route="activity" style="font-family:var(--mono);font-size:10.5px">lịch sử →</span>
        <button class="btn sm ghost" style="padding:3px 9px" data-run="${r.id}">${icon('i-play')} Chạy</button>
      </div>
    </div>`;
  return `
  <div class="vtitle"><h1>Automation / Routines</h1><span class="sub">${active}/${DB.routines.length} active · bạn ra luật, AI thực thi</span>
    <span class="sp"></span>
    <button class="btn accent" id="newRoutine">${icon('i-plus')} Routine mới</button>
  </div>

  <div class="grid g-4">
    <div class="stat"><span class="sl">Routine active</span><span class="sv pos">${active}</span><span class="sd faint">trên ${DB.routines.length} đã định nghĩa</span></div>
    <div class="stat"><span class="sl">Chạy hôm nay</span><span class="sv">${DB.activity.length}</span><span class="sd faint">7 ok · 1 lỗi</span></div>
    <div class="stat"><span class="sl">Lần chạy gần nhất</span><span class="sv" style="font-size:18px">09:00</span><span class="sd faint">pattern-check · ok</span></div>
    <div class="stat"><span class="sl">Đang chạy</span><span class="sv acc">0</span><span class="sd faint">scheduler idle</span></div>
  </div>

  <div class="panel" style="padding:13px 16px;display:flex;gap:12px;align-items:center">
    <span class="dot g pulse"></span>
    <div style="flex:1;font-size:12.5px;color:var(--tx-0)"><b style="font-family:var(--mono)">Scheduler online.</b> <span class="mut">Cron + event listener (commit · giá · idle) đang lắng nghe. AI có thể kích hoạt routine on-demand qua MCP — nhưng chỉ những routine bạn đã định nghĩa.</span></div>
    <div class="seg"><button class="on">Tất cả</button><button>Lịch</button><button>Sự kiện</button></div>
  </div>

  <div class="grid g-2" style="align-items:start">${DB.routines.map(card).join('')}</div>

  <div class="panel" style="padding:15px 17px;display:flex;gap:13px;align-items:center;opacity:.85">
    <div style="font-size:13px;color:var(--tx-1);flex:1;line-height:1.5"><b style="color:var(--tx-0)">Giới hạn có chủ đích:</b> ~6 routine có mục đích rõ. Mỗi routine mới phải qua test <span class="acc">"tiết kiệm thời gian thật, hay chỉ đẩy ra cho có?"</span> — không xây marketplace 54 skill.</div>
    <button class="btn sm" id="newRoutine2">${icon('i-plus')} Thêm có chủ đích</button>
  </div>`;
};

// ---------- S14 Activity Feed / Run Log ----------
SCREENS.activity = function(){
  const ok = DB.activity.filter(a=>a.status==='ok').length;
  const err = DB.activity.filter(a=>a.status==='err').length;
  const feedRow = a=>`
    <div class="feed-row" data-feed="${a.id}">
      <span class="runi ${a.status} fr-ic">${a.status==='ok'?'✓':a.status==='err'?'✗':'●'}</span>
      <div class="fr-body">
        <div class="fr-t"><b>${a.name}</b>${a.desc}</div>
        <div class="fr-s"><span>${a.time}</span><span>${a.ago} trước</span><span>${a.dur}</span><span class="${a.status==='ok'?'pos':'neg'}">${a.status==='ok'?'thành công':'lỗi'}</span></div>
        <div class="fr-out">${a.output}</div>
      </div>
      <span class="fr-chev">${icon('i-chevron')}</span>
    </div>`;
  return `
  <div class="vtitle"><h1>Activity Feed</h1><span class="sub">run log · minh bạch mọi hành động tự động</span>
    <span class="sp"></span>
    <div class="tabs" id="feedTabs"><span class="tab on" data-f="all">Tất cả</span><span class="tab" data-f="ok">Thành công</span><span class="tab" data-f="err">Lỗi</span></div>
    <div class="seg"><button class="on">Hôm nay</button><button>Tuần</button></div>
  </div>

  <div class="grid g-4">
    <div class="stat"><span class="sl">Run hôm nay</span><span class="sv">${DB.activity.length}</span><span class="sd faint">qua ${new Set(DB.activity.map(a=>a.routine)).size} routine</span></div>
    <div class="stat"><span class="sl">Thành công</span><span class="sv pos">${ok}</span><span class="sd faint">${Math.round(ok/DB.activity.length*100)}% tỉ lệ</span></div>
    <div class="stat"><span class="sl">Lỗi</span><span class="sv neg">${err}</span><span class="sd faint">market-poll · đã retry</span></div>
    <div class="stat"><span class="sl">Thời gian TB</span><span class="sv" style="font-size:20px">3.1s</span><span class="sd faint">mỗi run</span></div>
  </div>

  <div class="panel" style="overflow:hidden">
    <div class="phead"><span class="kicker">Run log</span><span class="dot g pulse"></span><span class="hint">live · tail -f</span><span class="link" data-route="automation" style="margin-left:auto">quản lý routine →</span></div>
    <div class="feed" id="feed">${DB.activity.map(feedRow).join('')}</div>
  </div>

  <div class="hint" style="text-align:center;padding:4px">Bấm vào một dòng để xem log đầy đủ + output của run đó.</div>`;
};
})();
