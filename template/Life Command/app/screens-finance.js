/* ============================================================
   SCREENS — Finance (S5 · S6 · S7 · S8)
   ============================================================ */
(function(){

// ---------- S5 Finance overview ----------
SCREENS.finance = function(){
  const n = DB.net;
  return `
  <div class="vtitle"><h1>Tài chính</h1><span class="sub">cập nhật 2 phút trước</span>
    <span class="sp"></span>
    <div class="seg"><button>1D</button><button class="on">1W</button><button>1M</button><button>1Y</button><button>ALL</button></div>
  </div>

  <div class="grid" style="grid-template-columns:2fr 1fr 1fr;height:200px">
    <div class="card glowcard nwc">
      <div class="chartbg">${spark(n.series, accent(), 640, 130)}</div>
      <div class="kicker">Tổng tài sản</div>
      <div class="nwnum num">${fmtUSD(n.total)}</div>
      <div class="nwd"><span class="pos num">▲ ${fmtSign(n.day)} hôm nay</span><span class="pos num">▲ ${fmtSign(n.week)} · +${n.weekPct}% tuần</span></div>
    </div>
    <div class="stat"><span class="sl">Dry powder</span><span class="sv">${fmtUSD(n.dryPowder)}</span><span class="sd faint">20% danh mục · sẵn sàng DCA</span></div>
    <div class="stat"><span class="sl">P&L mở</span><span class="sv pos">+$9,960</span><span class="sd pos">+4.2% trên vốn</span></div>
  </div>

  <div class="grid" style="grid-template-columns:1fr 1fr;align-items:start">
    <div class="panel">
      <div class="phead"><span class="kicker">P&L theo kênh</span><span class="link" data-route="portfolio" style="margin-left:auto">danh mục →</span></div>
      <div style="padding:6px 16px 14px">
        ${n.alloc.map(a=>`<div class="usebar-row"><span class="ul">${a.k}</span><span class="ub"><i style="width:${a.pct*2}%;background:${a.color}"></i></span><span class="uv ${a.pnl>0?'pos':a.pnl<0?'neg':''}">${a.pnl===0?'—':((a.pnl>0?'+':'−')+'$'+Math.abs(a.pnl).toLocaleString())}</span></div>`).join('')}
      </div>
    </div>
    <div class="panel">
      <div class="phead"><span class="kicker">Ladder BTC đang chạy</span><span class="dot acc pulse" style="margin-left:auto"></span><span class="hint">rung 2 active</span></div>
      <div style="padding:8px 16px 14px">
        ${[['Rung 1','$64,000','hit ✓','done'],['Rung 2','$68,200','ACTIVE','active'],['Rung 3','$72,000','chờ','wait'],['Rung 4','$76,000','chờ','wait']].map(r=>`
          <div class="usebar-row"><span class="ul">${r[0]}</span><span class="num" style="width:80px;color:var(--tx-0)">${r[1]}</span><span class="ub"><i style="width:${r[3]==='done'?100:r[3]==='active'?60:8}%;background:${r[3]==='active'?'var(--accent)':r[3]==='done'?'var(--green)':'var(--tx-2)'}"></i></span><span class="uv ${r[3]==='active'?'acc':r[3]==='done'?'pos':'faint'}" style="width:60px">${r[2]}</span></div>`).join('')}
        <div class="hint" style="margin-top:8px">Mỗi rung DCA $2,000 · giữ dry powder ≥15%.</div>
      </div>
    </div>
  </div>

  <div class="panel" style="overflow:hidden">
    <div class="phead"><span class="kicker">Lệnh gần đây</span><span class="link" data-route="journal" style="margin-left:auto">nhật ký đầy đủ →</span></div>
    <table class="dtable">
      <thead><tr><th>Ngày</th><th>Lệnh</th><th>Tài sản</th><th>Khối lượng</th><th>Giá</th><th>P&L</th><th>Lý do</th></tr></thead>
      <tbody>${DB.journal.slice(0,4).map(j=>`<tr>
        <td class="faint">${j.date}</td>
        <td><span class="tradechip ${j.action.toLowerCase()}">${j.action}</span></td>
        <td class="pn">${j.asset}</td><td>${j.size}</td><td class="mut">${j.px}</td>
        <td class="${j.pnl?(j.pnl[0]==='+'?'pos':'neg'):'faint'}">${j.pnl||'—'}</td>
        <td class="mut" style="font-family:var(--sans);max-width:240px">${j.reason}</td></tr>`).join('')}</tbody>
    </table>
  </div>`;
};

// ---------- S6 Portfolio ----------
SCREENS.portfolio = function(){
  const n = DB.net;
  const donut = ()=>{
    let acc=0; const segs = n.alloc.map(a=>{const start=acc; acc+=a.pct; return {a, start, end:acc};});
    const R=70, C=2*Math.PI*R;
    return `<svg width="180" height="180" viewBox="0 0 180 180">${segs.map(s=>{
      const len=(s.a.pct/100)*C, off=C-(s.start/100)*C;
      return `<circle cx="90" cy="90" r="${R}" fill="none" stroke="${s.a.color}" stroke-width="22" stroke-dasharray="${len} ${C-len}" stroke-dashoffset="${off}" transform="rotate(-90 90 90)"/>`;
    }).join('')}<circle cx="90" cy="90" r="48" fill="var(--bg-1)"/></svg>`;
  };
  const holdings = [
    ['BTC','Bitcoin','0.92','$62,800','$68,240','+8.7%','pos'],
    ['ETH','Ethereum','12.4','$3,420','$3,820','+11.7%','pos'],
    ['SOL','Solana','84','$148','$164','+10.8%','pos'],
    ['SPY','S&P 500 ETF','96','$598','$612','+2.3%','pos'],
    ['QQQ','Nasdaq 100','42','$521','$528','+1.3%','pos'],
    ['VNM','Vinamilk','1,200','64,500đ','62,000đ','-3.9%','neg'],
  ];
  return `
  <div class="vtitle"><h1>Danh mục</h1><span class="sub">6 vị thế · 4 kênh</span>
    <span class="sp"></span>
    <div class="tabs"><span class="tab on">Tất cả</span><span class="tab">Crypto</span><span class="tab">ETF</span><span class="tab">VN</span></div>
    <button class="btn accent">${icon('i-plus')} Thêm vị thế</button>
  </div>

  <div class="grid" style="grid-template-columns:300px 1fr;align-items:start">
    <div class="card" style="align-items:center;gap:14px">
      <div class="kicker" style="align-self:flex-start">Phân bổ</div>
      <div style="position:relative;display:grid;place-items:center">${donut()}<div style="position:absolute;text-align:center"><div class="num" style="font-size:20px;font-weight:700">${fmtUSD(n.total)}</div><div class="hint">tổng</div></div></div>
      <div style="width:100%;display:flex;flex-direction:column;gap:7px">
        ${n.alloc.map(a=>`<div style="display:flex;align-items:center;gap:8px;font-family:var(--mono);font-size:11.5px"><i style="width:9px;height:9px;border-radius:2px;background:${a.color}"></i><span class="mut">${a.k}</span><span style="margin-left:auto;color:var(--tx-0)">${a.pct}%</span><span class="faint" style="width:64px;text-align:right">${fmtUSD(a.val)}</span></div>`).join('')}
      </div>
    </div>
    <div class="panel" style="overflow:hidden">
      <div class="phead"><span class="kicker">Vị thế</span><span class="hint" style="margin-left:auto">sắp theo % P&L ↓</span></div>
      <table class="dtable">
        <thead><tr><th>Mã</th><th>Tên</th><th>Số lượng</th><th>Giá vốn</th><th>Giá hiện tại</th><th>P&L %</th><th></th></tr></thead>
        <tbody>${holdings.map(h=>`<tr>
          <td class="pn">${h[0]}</td><td class="mut" style="font-family:var(--sans)">${h[1]}</td>
          <td>${h[2]}</td><td class="faint">${h[3]}</td><td class="mut">${h[4]}</td>
          <td class="${h[6]}">${h[5]}</td>
          <td style="width:70px">${spark(h[6]==='pos'?[3,4,3,5,6,5,7,8]:[8,7,8,6,5,6,4,3], h[6]==='pos'?'var(--green)':'var(--red)', 60, 22, false)}</td>
        </tr>`).join('')}</tbody>
      </table>
    </div>
  </div>

  <div class="panel" style="padding:14px 17px;display:flex;gap:13px;align-items:center;box-shadow:var(--glow);border-color:transparent">
    <span class="dot acc pulse"></span>
    <div style="flex:1;font-size:12.5px;color:var(--tx-0)"><b>Rebalance gợi ý:</b> Crypto đang <b class="acc">38% &gt; trần 35%</b> sau khi BTC/ETH tăng. Cân nhắc chốt một phần về dry powder.</div>
    <button class="btn sm accent">Xem đề xuất</button>
  </div>`;
};

// ---------- S7 Journal ----------
SCREENS.journal = function(){
  return `
  <div class="vtitle"><h1>Nhật ký lệnh</h1><span class="sub">${DB.journal.length} lệnh · ghi lại lý do, không chỉ con số</span>
    <span class="sp"></span>
    <div class="tabs"><span class="tab on">Tất cả</span><span class="tab">Mua</span><span class="tab">Bán</span><span class="tab">Ladder</span></div>
    <button class="btn accent">${icon('i-plus')} Ghi lệnh</button>
  </div>

  <div class="grid g-4">
    <div class="stat"><span class="sl">Win rate</span><span class="sv pos">72%</span><span class="sd faint">18/25 lệnh xanh</span></div>
    <div class="stat"><span class="sl">P&L trung bình</span><span class="sv pos">+6.8%</span><span class="sd faint">mỗi lệnh đóng</span></div>
    <div class="stat"><span class="sl">Kỷ luật ladder</span><span class="sv acc">94%</span><span class="sd faint">theo đúng kế hoạch</span></div>
    <div class="stat"><span class="sl">Lệnh tháng này</span><span class="sv">5</span><span class="sd faint">3 mua · 1 bán · 1 ladder</span></div>
  </div>

  <div class="panel" style="overflow:hidden">
    <div class="phead"><span class="kicker">Mọi lệnh</span><span class="hint" style="margin-left:auto">mới nhất trước</span></div>
    <table class="dtable">
      <thead><tr><th>Ngày</th><th>Lệnh</th><th>Tài sản</th><th>Khối lượng</th><th>Giá</th><th>Loại</th><th>P&L</th><th>Lý do quyết định</th></tr></thead>
      <tbody>${DB.journal.map(j=>`<tr>
        <td class="faint">${j.date}</td>
        <td><span class="tradechip ${j.action.toLowerCase()}">${j.action}</span></td>
        <td class="pn">${j.asset}</td><td>${j.size}</td><td class="mut">${j.px}</td>
        <td><span class="tagchip">${j.tag}</span></td>
        <td class="${j.pnl?(j.pnl[0]==='+'?'pos':'neg'):'faint'}">${j.pnl||'mở'}</td>
        <td class="mut" style="font-family:var(--sans);max-width:280px">${j.reason}</td></tr>`).join('')}</tbody>
    </table>
  </div>`;
};

// ---------- S8 Market & Alerts ----------
SCREENS.market = function(){
  const alertColor = {r:'var(--red)',a:'var(--amber)',g:'var(--green)'};
  return `
  <div class="vtitle"><h1>Thị trường & Cảnh báo</h1><span class="sub">${DB.market.length} mã theo dõi · ${DB.alerts.length} cảnh báo</span>
    <span class="sp"></span>
    <button class="btn">${icon('i-plus')} Thêm trigger</button>
    <button class="btn accent">${icon('i-refresh')} Poll ngay</button>
  </div>

  <div class="grid" style="grid-template-columns:1.4fr 1fr;align-items:start">
    <div class="panel" style="overflow:hidden">
      <div class="phead"><span class="kicker">Watchlist</span><span class="dot g" style="margin-left:auto"></span><span class="hint">market-poll mỗi 10 phút</span></div>
      <table class="dtable">
        <thead><tr><th>Mã</th><th>Tên</th><th>Giá</th><th>24h</th><th>7d</th><th></th></tr></thead>
        <tbody>${DB.market.map(m=>`<tr>
          <td class="pn">${m.sym}</td><td class="mut" style="font-family:var(--sans)">${m.name}</td>
          <td class="num" style="color:var(--tx-0)">${m.px}</td>
          <td class="${m.dir}">${m.chg}</td>
          <td class="${m.dir}">${m.dir==='pos'?'+':'−'}${(Math.random()*12+1).toFixed(1)}%</td>
          <td style="width:74px">${spark(m.dir==='pos'?[2,3,2,4,5,4,6,7,8]:[8,7,8,6,5,6,4,3,2], m.dir==='pos'?'var(--green)':'var(--red)', 64, 22, false)}</td>
        </tr>`).join('')}</tbody>
      </table>
    </div>
    <div class="grid" style="grid-template-rows:auto auto;gap:14px;align-content:start">
      <div class="panel alertpanel">
        <div class="phead"><span class="kicker">Cảnh báo</span><span class="dot r"></span><span class="hint">${DB.alerts.length} mới</span></div>
        <div class="alist">${DB.alerts.map(a=>`<div class="al"><span class="ad" style="background:${alertColor[a.level]}"></span><div><div class="at">${a.text}</div><div class="as">${a.src} · ${a.ago}</div></div></div>`).join('')}</div>
      </div>
      <div class="panel">
        <div class="phead"><span class="kicker">Trigger đang đặt</span><span class="link" data-route="automation" style="margin-left:auto">routine →</span></div>
        <div style="padding:8px 16px 14px">
          ${[['BTC ≥ $72,000','rung 3 ladder','wait'],['BTC ≤ $60,000','dừng lỗ','wait'],['ETH ≥ $4,000','chốt một phần','wait'],['VNINDEX ≤ 1,200','mua thêm','wait']].map(t=>`
            <div class="mrow"><span class="k">${t[0]}</span><span class="v mut" style="font-weight:400;font-size:11px">${t[1]}</span></div>`).join('')}
        </div>
      </div>
    </div>
  </div>`;
};
})();
