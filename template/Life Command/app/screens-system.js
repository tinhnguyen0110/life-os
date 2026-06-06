/* ============================================================
   SCREENS — System (S9 Claude · S10 Notes · S11 AI · S12 Settings)
   ============================================================ */
(function(){

// ---------- S9 Claude Usage ----------
SCREENS.claude = function(){
  const c = DB.claude;
  const days = [['T2',48],['T3',62],['T4',55],['T5',71],['T6',71],['T7',0],['CN',0]];
  return `
  <div class="vtitle"><h1>Claude Usage</h1><span class="sub">${c.model} · cửa sổ 5 giờ</span>
    <span class="sp"></span>
    <div class="seg"><button class="on">5H</button><button>Tuần</button><button>Tháng</button></div>
  </div>

  <div class="grid" style="grid-template-columns:300px 1fr;align-items:start">
    <div class="card" style="align-items:center;gap:10px">
      <div class="kicker" style="align-self:flex-start">Quota hiện tại</div>
      <div class="gauge" style="width:150px;height:150px">${gauge(c.pct, accent(), 150, 12)}<div class="lab"><b style="font-size:34px;color:${accent()}">${c.pct}%</b><span style="font-size:10px">đã đốt</span></div></div>
      <div class="num" style="color:var(--accent-soft);font-size:12.5px">↻ reset trong ${c.resetIn}</div>
      <div class="num faint" style="font-size:11px">${(c.used/1000).toFixed(1)}k / ${c.cap/1000}k tokens</div>
      <div class="divider" style="width:100%;margin:4px 0"></div>
      <div style="width:100%;display:flex;flex-direction:column;gap:7px">
        <div class="mrow"><span class="k">Còn lại</span><span class="v num">${((c.cap-c.used)/1000).toFixed(1)}k</span></div>
        <div class="mrow"><span class="k">Weekly</span><span class="v num">${c.weekly}%</span></div>
        <div class="mrow"><span class="k">~ session sâu</span><span class="v num pos">1</span></div>
      </div>
    </div>
    <div class="grid" style="grid-template-rows:auto 1fr;gap:14px;align-content:start">
      <div class="grid g-3">
        <div class="stat"><span class="sl">Hôm nay</span><span class="sv">${(c.used/1000).toFixed(0)}k</span><span class="sd faint">tokens đốt</span></div>
        <div class="stat"><span class="sl">Trung bình/ngày</span><span class="sv">118k</span><span class="sd faint">7 ngày qua</span></div>
        <div class="stat"><span class="sl">Đỉnh</span><span class="sv">186k</span><span class="sd faint">T5 tuần này</span></div>
      </div>
      <div class="card" style="min-height:200px">
        <div class="kicker">Token đốt theo ngày</div>
        <div style="display:flex;align-items:flex-end;gap:16px;flex:1;padding:18px 4px 0">
          ${days.map(d=>`<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:8px;justify-content:flex-end;height:100%">
            <div style="width:100%;max-width:46px;height:${d[1]?d[1]*1.7:2}px;background:${d[1]>65?'var(--accent)':d[1]?'var(--accent-dim)':'var(--bg-3)'};border-radius:5px 5px 0 0;${d[1]>65?'box-shadow:0 0 14px -3px var(--accent)':''}"></div>
            <span class="num faint" style="font-size:10px">${d[0]}</span></div>`).join('')}
        </div>
      </div>
    </div>
  </div>

  <div class="panel">
    <div class="phead"><span class="kicker">Đốt token theo dự án / routine</span></div>
    <div style="padding:8px 16px 14px">
      ${[['life-command (dev)',64,'var(--accent)'],['mcp-wrapper (dev)',18,'var(--blue)'],['morning-brief',9,'var(--green)'],['pattern-check',5,'var(--violet)'],['khác',4,'var(--tx-2)']].map(r=>`
        <div class="usebar-row"><span class="ul">${r[0]}</span><span class="ub"><i style="width:${r[1]}%;background:${r[2]}"></i></span><span class="uv">${r[1]}%</span></div>`).join('')}
    </div>
  </div>`;
};

// ---------- S10 Notes ----------
SCREENS.notes = function(){
  const tagColor = {idea:'var(--accent)',insight:'var(--violet)',finance:'var(--green)',project:'var(--blue)'};
  const pinned = DB.notes.filter(n=>n.pinned), rest = DB.notes.filter(n=>!n.pinned);
  const card = n=>`<div class="note-card">
    <div class="nt">${n.pinned?icon('i-pin'):''}${n.title}</div>
    <div class="nb">${n.body}</div>
    <div class="nm"><span class="tagchip" style="color:${tagColor[n.tag]};border-color:${tagColor[n.tag]}40">${n.tag}</span><span style="margin-left:auto">${n.updated}</span></div>
  </div>`;
  return `
  <div class="vtitle"><h1>Ghi chú</h1><span class="sub">${DB.notes.length} note · ${pinned.length} ghim</span>
    <span class="sp"></span>
    <div class="pill" style="cursor:text">${icon('i-search')}<span class="faint">tìm note…</span></div>
    <button class="btn accent">${icon('i-plus')} Note mới</button>
  </div>

  ${pinned.length?`<div><div class="kicker" style="margin-bottom:10px">📌 Đã ghim</div>
  <div class="grid g-2" style="align-items:start">${pinned.map(card).join('')}</div></div>`:''}

  <div><div class="kicker" style="margin:6px 0 10px">Tất cả</div>
  <div style="columns:3;column-gap:14px">${rest.map(n=>`<div style="margin-bottom:14px">${card(n)}</div>`).join('')}</div></div>`;
};

// ---------- S11 AI Brain / Chat ----------
SCREENS.ai = function(){
  const suggestions = ['Vì sao portfolio-reader chững?','Tôi nên DCA BTC bao nhiêu?','Dự án nào nên bỏ?','Tóm tắt tuần này','Token Claude đang đốt vào đâu?'];
  return `
  <div class="vtitle"><h1>AI Brain</h1><span class="sub">đọc state thật: dự án · finance · activity · notes</span>
    <span class="sp"></span>
    <div class="pill"><span class="dot g"></span>MCP <b>connected</b></div>
    <button class="btn">Lịch sử</button>
  </div>

  <div style="flex:1;display:flex;flex-direction:column;gap:14px;min-height:0">
    <div class="chat-wrap" style="flex:1">
      ${DB.chat.map(m=>`<div class="msg ${m.role}">
        <div class="mav">${m.role==='ai'?'✦':'CH'}</div>
        <div class="mbody"><div class="who">${m.role==='ai'?'AI Brain':'Bạn'}</div><div class="mtext">${m.text.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>')}</div></div>
      </div>`).join('')}
    </div>
    <div class="chat-wrap" style="flex:none">
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:4px">
        ${suggestions.map(s=>`<span class="tab" data-suggest="${s}">${s}</span>`).join('')}
      </div>
      <div class="cmdbar" style="height:50px">
        <span class="pr">&gt;</span>
        <input placeholder="hỏi bất cứ điều gì về đế chế của bạn…" id="aiInput">
        <button class="btn accent sm" id="aiSend">Gửi</button>
      </div>
    </div>
  </div>`;
};

// ---------- S12 Settings ----------
SCREENS.settings = function(){
  const row = (t,d,ctrl)=>`<div class="set-row"><div class="sr-info"><div class="sr-t">${t}</div><div class="sr-d">${d}</div></div>${ctrl}</div>`;
  const tog = on=>`<div class="toggle ${on?'on':''}"></div>`;
  return `
  <div class="vtitle"><h1>Cài đặt</h1><span class="sub">tài khoản · automation · tích hợp</span></div>

  <div class="grid g-2" style="align-items:start">
    <div style="display:flex;flex-direction:column;gap:14px">
      <div><div class="kicker" style="margin-bottom:10px">Automation toàn cục</div>
        <div class="set-group">
          ${row('Master automation','Bật/tắt toàn bộ routine cùng lúc',tog(true))}
          ${row('Giờ chạy brief','Morning brief mỗi ngày lúc 8:00','<span class="pill">08:00</span>')}
          ${row('Kênh báo lỗi','Khi routine lỗi, báo qua đâu','<span class="pill">In-app + Email</span>')}
          ${row('Ngưỡng idle hunter','Cảnh báo dự án đứng quá N ngày','<span class="pill">7 ngày</span>')}
        </div>
      </div>
      <div><div class="kicker" style="margin-bottom:10px">Tài khoản</div>
        <div class="set-group">
          ${row('Tên hiển thị','Chỉ huy','<button class="btn sm">Sửa</button>')}
          ${row('Gói','Pro · vira','<span class="sbadge sb-act">active</span>')}
          ${row('Múi giờ','Asia/Ho_Chi_Minh (GMT+7)','<button class="btn sm">Đổi</button>')}
        </div>
      </div>
    </div>
    <div style="display:flex;flex-direction:column;gap:14px">
      <div><div class="kicker" style="margin-bottom:10px">Tích hợp & MCP</div>
        <div class="set-group">
          ${row('Claude Code (MCP)','AI đọc data + kích hoạt routine',tog(true))}
          ${row('GitHub','4 repo đang đồng bộ',tog(true))}
          ${row('Market data feed','Crypto + chứng khoán, mỗi 10 phút',tog(true))}
          ${row('Webhook','Nhận event commit/giá từ ngoài',tog(false))}
        </div>
      </div>
      <div><div class="kicker" style="margin-bottom:10px">API endpoints</div>
        <div class="set-group">
          ${['GET /routines','POST /routines/{id}/run','PATCH /routines/{id}','GET /activity'].map(e=>`<div class="set-row"><span class="num" style="font-size:12px;color:var(--tx-1);flex:1">${e}</span><span class="sbadge sb-act">live</span></div>`).join('')}
        </div>
      </div>
      <div><div class="kicker" style="margin-bottom:10px">Giao diện</div>
        <div class="set-group">${row('Tweaks (màu / nền / hiệu ứng)','Mở panel Tweaks ở góc dưới phải','<button class="btn sm" onclick="document.getElementById(\'tweaksFab\').click()">Mở Tweaks</button>')}</div>
      </div>
    </div>
  </div>`;
};
})();
