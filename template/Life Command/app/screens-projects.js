/* ============================================================
   SCREENS — Projects (S2 list · S3 detail · S4 graveyard)
   ============================================================ */
(function(){
const healthDot = { act:'var(--green)', slow:'var(--amber)', stall:'var(--red)', dead:'var(--tx-2)' };
const healthSb = { act:'sb-act', slow:'sb-slow', stall:'sb-stall', dead:'sb-dead' };

// ---------- S2 Projects list ----------
SCREENS.projects = function(){
  const counts = { act:0, slow:0, stall:0 };
  DB.projects.forEach(p=>counts[p.health]++);
  return `
  <div class="vtitle">
    <h1>Dự án</h1><span class="sub">${DB.projects.length} đang theo dõi</span>
    <span class="sp"></span>
    <div class="tabs"><span class="tab on">Tất cả</span><span class="tab">Active</span><span class="tab">Chậm</span><span class="tab">Đứng</span></div>
    <button class="btn accent">${icon('i-plus')} Dự án mới</button>
  </div>

  <div class="grid g-4">
    <div class="stat"><span class="sl">Tổng dự án</span><span class="sv">${DB.projects.length}</span><span class="sd faint">1 trong nghĩa địa tuần này</span></div>
    <div class="stat"><span class="sl">Active</span><span class="sv pos">${counts.act}</span><span class="sd faint">commit trong 24h</span></div>
    <div class="stat"><span class="sl">Cần chú ý</span><span class="sv mid">${counts.slow+counts.stall}</span><span class="sd faint">${counts.stall} đứng · ${counts.slow} chậm</span></div>
    <div class="stat"><span class="sl">User thật</span><span class="sv pos">${DB.projects.reduce((s,p)=>s+p.users,0)}</span><span class="sd faint">trên 4 dự án</span></div>
  </div>

  <div class="panel" style="overflow:hidden">
    <div class="phead"><span class="kicker">Tất cả dự án</span><span class="hint" style="margin-left:auto">sắp theo idle ↓</span></div>
    <table class="dtable">
      <thead><tr><th>Dự án</th><th>Mô tả</th><th>Sức khỏe</th><th>Tiến độ</th><th>Users</th><th>Lần cuối</th><th>Routine</th><th>Next</th></tr></thead>
      <tbody>${DB.projects.map(p=>`
        <tr class="clickable" data-route="project/${p.id}">
          <td class="pn">${p.name}</td>
          <td class="mut" style="font-family:var(--sans);max-width:220px">${p.desc}</td>
          <td><span class="sbadge ${healthSb[p.health]}"><span class="dot" style="width:5px;height:5px;background:currentColor"></span>${p.healthLbl}</span></td>
          <td><span class="barc"><i style="width:${p.progress}%;background:${healthDot[p.health]}"></i></span>${p.progress}%</td>
          <td class="${p.users>0?'pos':'faint'}">${p.users}</td>
          <td class="faint">${p.last}</td>
          <td class="faint">${p.routines.length}</td>
          <td class="mut">${p.next}</td>
        </tr>`).join('')}</tbody>
    </table>
  </div>

  <div class="panel" style="padding:14px 16px;display:flex;gap:13px;align-items:center">
    <span class="runi run">⚠</span>
    <div style="flex:1">
      <div style="font-size:12.5px;color:var(--tx-0)"><b style="font-family:var(--mono)">Pattern detector:</b> portfolio-reader đạt 41% rồi đứng 14 ngày — khớp <span class="mid">build-to-90 / abandon-before-user</span>.</div>
      <div class="hint" style="margin-top:3px">Trung bình bạn bỏ dự án ở 68%. 3 dự án trong nghĩa địa cùng dấu vết.</div>
    </div>
    <button class="btn sm" data-route="graveyard">Xem nghĩa địa →</button>
  </div>`;
};

// ---------- S3 Project detail ----------
SCREENS.project = function(id){
  const p = DB.projects.find(x=>x.id===id) || DB.projects[0];
  const rs = p.routines.map(rid=>DB.routines.find(r=>r.id===rid)).filter(Boolean);
  const acts = DB.activity.filter(a=>p.routines.includes(a.routine)).slice(0,4);
  const series = [30,34,32,38,36,42,40,46,44,50,48,54,52,p.progress];
  return `
  <div class="detail-head">
    <div class="backbtn" data-route="projects">${icon('i-back')}</div>
    <div class="detail-title">
      <h1>${p.name} <span class="sbadge ${healthSb[p.health]}"><span class="dot" style="width:5px;height:5px;background:currentColor"></span>${p.healthLbl}</span></h1>
      <div class="meta">
        <span>${icon('i-git')} ${p.repo}</span>
        <span>${p.commits} commits</span>
        <span>${icon('i-star')} ${p.stars}</span>
        <span>${p.lang}</span>
        <span>${icon('i-clock')} cập nhật ${p.last}</span>
      </div>
    </div>
    <button class="btn">${icon('i-git')} Mở repo</button>
    <button class="btn accent">${icon('i-play')} Chạy refresh</button>
  </div>

  <div class="grid" style="grid-template-columns:2fr 1fr">
    <div class="card glowcard" style="min-height:150px">
      <div class="chartbg" style="position:absolute;left:0;right:0;bottom:0;height:55%;opacity:.45">${spark(series, accent(), 600, 110)}</div>
      <div class="kicker">Tiến độ</div>
      <div class="num" style="font-size:40px;font-weight:700;color:var(--accent);position:relative">${p.progress}%</div>
      <div class="mut" style="font-size:12.5px;position:relative;max-width:60%;line-height:1.5">${p.desc2}</div>
    </div>
    <div class="grid" style="grid-template-rows:1fr 1fr;gap:14px">
      <div class="stat"><span class="sl">Users thật</span><span class="sv ${p.users>0?'pos':'neg'}">${p.users}</span><span class="sd faint">${p.users>0?'đang dùng':'chưa có ai dùng'}</span></div>
      <div class="stat"><span class="sl">Auto-refresh cuối</span><span class="sv" style="font-size:18px">${p.lastAuto}</span><span class="sd faint">qua routine wiki-refresh</span></div>
    </div>
  </div>

  <div class="grid" style="grid-template-columns:1fr 1fr;align-items:start">
    <div class="panel" style="overflow:hidden">
      <div class="phead"><span class="kicker">Routine gắn với dự án</span><span class="link" data-route="automation" style="margin-left:auto">quản lý →</span></div>
      ${rs.length? rs.map(r=>`
        <div class="set-row">
          <span class="runi ${r.lastResult}">${r.lastResult==='ok'?'✓':'✗'}</span>
          <div class="sr-info"><div class="sr-t">${r.name}</div><div class="sr-d">${r.triggerLbl} · chạy cuối ${r.lastRun}</div></div>
          <div class="toggle ${r.on?'on':''}"></div>
        </div>`).join('') : '<div style="padding:18px 16px" class="hint">Chưa gắn routine nào.</div>'}
    </div>
    <div class="panel" style="overflow:hidden">
      <div class="phead"><span class="kicker">Hoạt động tự động gần đây</span><span class="link" data-route="activity" style="margin-left:auto">feed đầy đủ →</span></div>
      <div class="actlist">${acts.length? acts.map(a=>`
        <div class="actmini clickable" data-route="activity">
          <span class="runi ${a.status}">${a.status==='ok'?'✓':'✗'}</span>
          <div><div class="am-t"><b>${a.name}</b> ${a.desc}</div><div class="am-s">${a.ago} trước · ${a.dur}</div></div>
        </div>`).join('') : '<div style="padding:18px 16px" class="hint">Chưa có hoạt động.</div>'}</div>
    </div>
  </div>

  ${p.health==='stall'?`<div class="panel" style="padding:15px 17px;display:flex;gap:13px;align-items:flex-start;box-shadow:var(--glow);border-color:transparent">
    <div class="ic" style="width:28px;height:28px;border-radius:7px;background:var(--accent-grad);display:grid;place-items:center;color:#180f04;flex-shrink:0;font-weight:700">✦</div>
    <div style="flex:1">
      <div style="font-size:13px;color:var(--tx-0);line-height:1.5">AI hỏi thẳng: dự án này đứng <b class="acc">14 ngày @41%</b>, 0 user — khớp pattern build-to-90 của bạn (auto-blogger 78%, habit-tracker 90%). <b style="color:var(--tx-0)">Quyết: cắt scope ship trong 1 session hôm nay, hay đưa vào nghĩa địa có chủ đích?</b></div>
      <div class="row" style="margin-top:11px;gap:8px">
        <button class="btn sm accent">Cắt scope & ship</button>
        <button class="btn sm" data-route="graveyard">Đưa vào nghĩa địa</button>
        <button class="btn sm ghost" data-route="ai">Hỏi AI thêm</button>
      </div>
    </div>
  </div>`:''}`;
};

// ---------- S4 Graveyard ----------
SCREENS.graveyard = function(){
  return `
  <div class="vtitle">
    <h1>Nghĩa địa dự án</h1><span class="sub">${DB.graveyard.length} dự án đã chôn · honest mirror</span>
    <span class="sp"></span>
    <button class="btn">Xuất bài học</button>
  </div>

  <div class="panel" style="padding:15px 17px;display:flex;gap:14px;align-items:center">
    <div style="font-family:var(--mono);font-size:30px;font-weight:700;color:var(--accent)">68%</div>
    <div style="flex:1">
      <div style="font-size:13px;color:var(--tx-0)">Bạn thường bỏ dự án ở mức <b class="acc">68% hoàn thành</b>, trước khi có user đầu tiên.</div>
      <div class="hint" style="margin-top:3px">Pattern lặp lại: build-to-90 → mất hứng → bỏ. Đây là tấm gương thật, không phải để trách.</div>
    </div>
    <div class="seg"><button class="on">Lưới</button><button>Dòng thời gian</button></div>
  </div>

  <div class="grid g-4">${DB.graveyard.map(g=>`
    <div class="grave-card">
      <div class="gname">${g.name}</div>
      <div class="bar" style="opacity:.5"><i style="width:${g.peak}%;background:var(--tx-2)"></i></div>
      <div class="greason">${g.reason}</div>
      <div class="glesson">💡 ${g.lesson}</div>
      <div class="gmeta"><span>peak ${g.peak}%</span><span>† ${g.died}</span></div>
    </div>`).join('')}</div>

  <div class="panel">
    <div class="phead"><span class="kicker">Bài học rút ra</span></div>
    <div style="padding:6px 8px 12px">
      ${['Validate "đã có ai làm chưa" TRƯỚC khi code.','Bắt đầu nhỏ — đừng để scope phình to.','Ship ở 70%, đừng đợi 90%.','90% xong + 0 user = cảnh báo lớn nhất, không phải thành tựu.'].map((l,i)=>`
        <div class="al"><span class="ad" style="background:var(--accent)"></span><div class="at">${l}</div></div>`).join('')}
    </div>
  </div>`;
};
})();
