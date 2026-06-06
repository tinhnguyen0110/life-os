/* ============================================================
   SHELL — helpers, icons, render chrome, router, tweaks
   ============================================================ */

// ---------- icons ----------
const ICONS = {
  'i-home':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/></svg>',
  'i-proj':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
  'i-grave':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M5 21V11a7 7 0 0 1 14 0v10z"/><path d="M9 21v-4h6v4"/></svg>',
  'i-fin':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 19h16"/><path d="M6 16l4-5 3 3 5-7"/></svg>',
  'i-pie':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 3v9l7 5"/><circle cx="12" cy="12" r="9"/></svg>',
  'i-journal':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M5 4h11l3 3v13H5z"/><path d="M9 9h7M9 13h7M9 17h4"/></svg>',
  'i-mkt':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 12h4l2 6 4-14 2 8h6"/></svg>',
  'i-cpu':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="7" y="7" width="10" height="10" rx="1.5"/><path d="M10 2v3M14 2v3M10 19v3M14 19v3M2 10h3M2 14h3M19 10h3M19 14h3"/></svg>',
  'i-note':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 3h9l5 5v13H6z"/><path d="M14 3v6h6M9 13h6M9 17h6"/></svg>',
  'i-ai':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 3l1.8 4.2L18 9l-4.2 1.8L12 15l-1.8-4.2L6 9l4.2-1.8z"/><circle cx="18" cy="17" r="2.2"/></svg>',
  'i-set':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/></svg>',
  'i-bolt':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M13 2L4 14h7l-1 8 9-12h-7z"/></svg>',
  'i-pulse':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 12h4l2-7 4 16 2-9h6"/></svg>',
  'i-refresh':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 4v4h-4"/></svg>',
  'i-chevron':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 6l-6 6 6 6"/></svg>',
  'i-bell':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>',
  'i-play':'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>',
  'i-plus':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>',
  'i-clock':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  'i-event':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M13 2L4 14h7l-1 8 9-12h-7z"/></svg>',
  'i-hand':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M8 13V5a1.5 1.5 0 0 1 3 0v6m0-1V4a1.5 1.5 0 0 1 3 0v7m0-2a1.5 1.5 0 0 1 3 0v6a5 5 0 0 1-5 5h-2a4 4 0 0 1-3-1.5L5 16a1.5 1.5 0 0 1 2.3-2z"/></svg>',
  'i-back':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 6l-6 6 6 6"/></svg>',
  'i-git':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="6" cy="6" r="2.5"/><circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="9" r="2.5"/><path d="M6 8.5v7M6 15.5a6 6 0 0 0 6-6h3.5"/></svg>',
  'i-star':'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.9 6.6 7.1.6-5.4 4.7 1.6 7L12 17.8 5.8 21l1.6-7L2 9.2l7.1-.6z"/></svg>',
  'i-pin':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 4h6l-1 6 3 3H7l3-3z"/><path d="M12 16v5"/></svg>',
  'i-search':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4-4"/></svg>',
};
function icon(k){ return ICONS[k]||''; }
function accent(){ return (THEMES[TWEAKS.theme]||THEMES.copper).primary; }

// ---------- formatters ----------
const fmtUSD = n => '$'+Math.round(n).toLocaleString('en-US');
const fmtSign = n => (n>=0?'+':'−')+'$'+Math.abs(n).toLocaleString('en-US');

// ---------- sparkline / area ----------
function spark(points, color, w=560, h=70, fill=true){
  const max=Math.max(...points), min=Math.min(...points), range=(max-min)||1, step=w/(points.length-1);
  const pts=points.map((p,i)=>`${(i*step).toFixed(1)},${(h-((p-min)/range)*h).toFixed(1)}`);
  const id='sg'+Math.random().toString(36).slice(2,7);
  const area=`M0,${h} L${pts.join(' L')} L${w},${h} Z`;
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="width:100%;height:100%;display:block">
    ${fill?`<defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="${color}" stop-opacity=".24"/><stop offset="100%" stop-color="${color}" stop-opacity="0"/></linearGradient></defs><path d="${area}" fill="url(#${id})"/>`:''}
    <polyline points="${pts.join(' ')}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}
function gauge(pct, color, size=108, sw=9, track='var(--bg-3)'){
  const r=(size/2)-sw, c=2*Math.PI*r, off=c*(1-pct/100), cx=size/2;
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
    <circle cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="${track}" stroke-width="${sw}"/>
    <circle cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="${color}" stroke-width="${sw}" stroke-linecap="round"
      stroke-dasharray="${c}" stroke-dashoffset="${off}" transform="rotate(-90 ${cx} ${cx})" style="filter:drop-shadow(0 0 5px ${color}90)"/></svg>`;
}

// ---------- ticker ----------
function tickerHTML(){
  const one = DB.market.map(t=>`<span class="ti"><span class="sym">${t.sym}</span><b>${t.px}</b><span class="${t.dir}">${t.chg}</span></span>`).join('');
  return one+one;
}

// ---------- shell ----------
function renderShell(){
  const navHTML = NAV.map(g=>`
    <div class="sb-sec">${g.sec}</div>
    ${g.items.map(([id,lbl,ic,opt])=>`<div class="sb-item" data-route="${id}" title="${lbl}">${icon(ic)}<span class="lbl">${lbl}</span>${opt&&opt.badge?`<span class="badge ${opt.cls}">${opt.badge}</span>`:''}</div>`).join('')}
  `).join('');

  document.getElementById('app').innerHTML = `
    <aside class="sidebar">
      <div class="sb-top">
        <div class="sb-logo">L</div>
        <div class="sb-word">LIFE·<b>CMD</b></div>
        <div class="sb-collapse" id="collapseBtn" title="Thu gọn">${icon('i-chevron')}</div>
      </div>
      <nav class="sb-nav" id="sbNav">${navHTML}</nav>
      <div class="sb-user" data-route="settings">
        <div class="avatar">${DB.user.initials}</div>
        <div class="uinfo"><b>${DB.user.name}</b><span>${DB.user.handle}</span></div>
      </div>
    </aside>
    <div class="main">
      <div class="topbar">
        <div class="crumb"><span class="c0">Life Command</span><span class="sep">/</span><span class="c1" id="crumb">Home</span></div>
        <div class="sp"></div>
        <div class="pill"><span class="dot g"></span>API <b>live</b></div>
        <div class="pill"><span class="dot g"></span>5 routine <b>active</b></div>
        <div class="pill">Sync <b>2 phút trước</b></div>
        <div class="icbtn" id="refreshBtn" title="Refresh data">${icon('i-refresh')}</div>
        <div class="icbtn" data-route="market" title="Cảnh báo">${icon('i-bell')}<span class="bdg">2</span></div>
        <button class="btn accent" data-route="ai">${icon('i-ai')} Hỏi AI</button>
      </div>
      <div class="view" id="view"></div>
      <div class="tape"><div class="tk" id="tape"></div></div>
    </div>`;

  document.getElementById('tape').innerHTML = tickerHTML();
  document.getElementById('collapseBtn').addEventListener('click', ()=>document.getElementById('app').classList.toggle('collapsed'));
  document.getElementById('refreshBtn').addEventListener('click', e=>{
    e.currentTarget.classList.add('spinning'); setTimeout(()=>e.currentTarget.classList.remove('spinning'),800);
    toast('g','Đã pull data mới · 9 mã thị trường · 4 dự án');
  });
  // delegated routing
  document.getElementById('app').addEventListener('click', e=>{
    const el = e.target.closest('[data-route]');
    if(el){ location.hash = '#'+el.dataset.route; }
  });
}

// ---------- router ----------
function setActiveNav(route){
  document.querySelectorAll('.sb-item').forEach(i=>i.classList.toggle('on', i.dataset.route===route));
  const cr = document.getElementById('crumb'); if(cr) cr.textContent = CRUMB[route]||route;
}
function navigate(){
  let route = (location.hash||'#home').slice(1);
  // sub-routes like project/<id>
  let param = null;
  if(route.includes('/')){ [route, param] = route.split('/'); }
  const fn = SCREENS[route] || SCREENS.home;
  const view = document.getElementById('view');
  view.innerHTML = fn(param);
  view.scrollTop = 0;
  setActiveNav(route);
  if(route==='project' && param){
    const p = DB.projects.find(x=>x.id===param);
    const cr = document.getElementById('crumb'); if(cr) cr.textContent = p?p.name:'Dự án';
    document.querySelectorAll('.sb-item').forEach(i=>i.classList.toggle('on', i.dataset.route==='projects'));
  }
  if(window._afterRender) { const cb=window._afterRender; window._afterRender=null; cb(); }
}

// ---------- toast ----------
let toastT;
function toast(level, msg){
  let t = document.getElementById('toast');
  if(!t){ t=document.createElement('div'); t.id='toast'; document.body.appendChild(t); }
  t.innerHTML = `<span class="dot ${level}"></span>${msg}`;
  t.classList.add('show'); clearTimeout(toastT);
  toastT = setTimeout(()=>t.classList.remove('show'), 2600);
}
window.toast = toast;

// ============================================================
//  TWEAKS
// ============================================================
const TWEAKS = /*EDITMODE-BEGIN*/{
  "theme": "copper",
  "bg": "warm",
  "glow": true,
  "scanline": false
}/*EDITMODE-END*/;

const THEMES = {
  copper:{name:'Copper Glow',primary:'#FF6A33',soft:'#ffb088',dim:'#5a2c14',grad:'linear-gradient(140deg,#ff9a5c,#e8451a)'},
  amber: {name:'Amber',      primary:'#F5A623',soft:'#ffce7a',dim:'#5c4318',grad:'linear-gradient(140deg,#FFB452,#ef7d22)'},
  solar: {name:'Solar Gold', primary:'#FFC53D',soft:'#ffe199',dim:'#5c4a12',grad:'linear-gradient(140deg,#ffe08a,#f0a818)'},
  cyan:  {name:'Cyan Tech',  primary:'#38BDF8',soft:'#a5e4ff',dim:'#11414f',grad:'linear-gradient(140deg,#7ad6ff,#1f9fe0)'},
  violet:{name:'Violet',     primary:'#A879FF',soft:'#d4baff',dim:'#3a2a5c',grad:'linear-gradient(140deg,#c7a3ff,#8b54f0)'},
  rose:  {name:'Crimson',    primary:'#FF5C7A',soft:'#ffaebd',dim:'#5a1f2c',grad:'linear-gradient(140deg,#ff8aa0,#e8324f)'},
};
const BG = {
  cool:{'--bg-0':'#0a0a0c','--bg-1':'#0f0f13','--bg-2':'#16161c','--bg-3':'#1e1e26','--line':'#23232c','--line-2':'#30303a','--tx-1':'#9b988e','--tx-2':'#66645c'},
  warm:{'--bg-0':'#0f0a07','--bg-1':'#15100b','--bg-2':'#1c150e','--bg-3':'#241a11','--line':'#2c2319','--line-2':'#392d20','--tx-1':'#a39c8e','--tx-2':'#6e665a'},
};
function applyTweaks(){
  const t = THEMES[TWEAKS.theme]||THEMES.copper, r=document.documentElement.style;
  r.setProperty('--accent',t.primary); r.setProperty('--accent-soft',t.soft);
  r.setProperty('--accent-dim',t.dim); r.setProperty('--accent-grad',t.grad);
  r.setProperty('--glow', TWEAKS.glow?`0 0 0 1px ${t.primary}52, 0 0 22px -6px ${t.primary}`:`0 0 0 1px ${t.primary}30`);
  const bg = BG[TWEAKS.bg]||BG.warm; for(const k in bg) r.setProperty(k,bg[k]);
  document.body.classList.toggle('scanline', TWEAKS.scanline);
  // re-render current screen so baked SVG colors update
  if(document.getElementById('view')) navigate();
  // panel state
  document.querySelectorAll('#twSwatches .sw').forEach(s=>s.classList.toggle('on', s.dataset.k===TWEAKS.theme));
  document.querySelectorAll('#twBg button').forEach(b=>b.classList.toggle('on', b.dataset.bg===TWEAKS.bg));
  const g=document.getElementById('twGlow'); if(g) g.classList.toggle('on',TWEAKS.glow);
  const sc=document.getElementById('twScan'); if(sc) sc.classList.toggle('on',TWEAKS.scanline);
  const f=document.getElementById('twFoot'); if(f) f.innerHTML=`Đang dùng: <b style="color:${t.primary}">${t.name}</b> · nền ${TWEAKS.bg==='warm'?'ấm':'trung tính'}`;
}
function persistTweaks(){ try{ window.parent.postMessage({type:'__edit_mode_set_keys',edits:TWEAKS},'*'); }catch(e){} }

function buildTweaksPanel(){
  const p=document.createElement('div'); p.id='tweaks';
  p.innerHTML=`
    <div class="tw-head"><span class="dotlogo"></span><b>Tweaks</b><div class="x" id="twClose">✕</div></div>
    <div class="tw-body">
      <div class="tw-sec">Tông màu thương hiệu</div>
      <div class="swatches" id="twSwatches">${Object.entries(THEMES).map(([k,t])=>`<div class="sw" data-k="${k}"><div class="chip" style="background:${t.grad}"></div><div class="nm">${t.name}</div></div>`).join('')}</div>
      <div class="tw-sec">Nền</div>
      <div class="seg2" id="twBg"><button data-bg="cool">Trung tính</button><button data-bg="warm">Ấm (warm)</button></div>
      <div class="tw-sec">Hiệu ứng</div>
      <div class="togrow"><span class="lbl">Glow accent</span><div class="toggle on" id="twGlow"></div></div>
      <div class="togrow"><span class="lbl">Scanline (console)</span><div class="toggle" id="twScan"></div></div>
      <div class="tw-foot" id="twFoot"></div>
    </div>`;
  document.body.appendChild(p);
  const fab=document.createElement('div'); fab.id='tweaksFab'; fab.innerHTML='<span class="dotlogo"></span>Tweaks';
  document.body.appendChild(fab);

  const open=()=>{p.classList.add('show'); fab.style.display='none';};
  const close=()=>{p.classList.remove('show'); fab.style.display='flex'; try{window.parent.postMessage({type:'__edit_mode_dismissed'},'*');}catch(e){}};
  fab.addEventListener('click',open);
  p.querySelector('#twClose').addEventListener('click',close);
  p.querySelectorAll('#twSwatches .sw').forEach(s=>s.addEventListener('click',()=>{TWEAKS.theme=s.dataset.k;applyTweaks();persistTweaks();}));
  p.querySelectorAll('#twBg button').forEach(b=>b.addEventListener('click',()=>{TWEAKS.bg=b.dataset.bg;applyTweaks();persistTweaks();}));
  p.querySelector('#twGlow').addEventListener('click',()=>{TWEAKS.glow=!TWEAKS.glow;applyTweaks();persistTweaks();});
  p.querySelector('#twScan').addEventListener('click',()=>{TWEAKS.scanline=!TWEAKS.scanline;applyTweaks();persistTweaks();});
  window.addEventListener('message',e=>{const t=e.data&&e.data.type; if(t==='__activate_edit_mode')open(); else if(t==='__deactivate_edit_mode')close();});
  try{window.parent.postMessage({type:'__edit_mode_available'},'*');}catch(e){}
}

// ---------- boot ----------
window.SCREENS = window.SCREENS || {};
function boot(){
  renderShell();
  buildTweaksPanel();
  window.addEventListener('hashchange', navigate);
  applyTweaks();      // also triggers first navigate()
}
document.addEventListener('DOMContentLoaded', boot);
