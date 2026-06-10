/**
 * NO_FLASH_SCRIPT (S13) — exportable for parity unit tests.
 *
 * The script is inlined in layout.tsx <head> to apply saved theme vars BEFORE
 * first paint (avoids warm-flash on cold load). Because an inline <script>
 * cannot import TS modules, THEMES/BG hex values are duplicated here in raw JS.
 * The parity test (lib/__tests__/no-flash-parity.test.ts) imports this constant
 * alongside lib/tweaks.ts THEMES/BG to assert they never drift apart.
 *
 * KEEP IN SYNC with lib/tweaks.ts THEMES / BG whenever you change hex values.
 */
export const NO_FLASH_SCRIPT = `(function(){try{
var THEMES={copper:{primary:'#FF6A33',soft:'#ffb088',dim:'#5a2c14',grad:'linear-gradient(140deg,#ff9a5c,#e8451a)'},amber:{primary:'#F5A623',soft:'#ffce7a',dim:'#5c4318',grad:'linear-gradient(140deg,#FFB452,#ef7d22)'},solar:{primary:'#FFC53D',soft:'#ffe199',dim:'#5c4a12',grad:'linear-gradient(140deg,#ffe08a,#f0a818)'},cyan:{primary:'#38BDF8',soft:'#a5e4ff',dim:'#11414f',grad:'linear-gradient(140deg,#7ad6ff,#1f9fe0)'},violet:{primary:'#A879FF',soft:'#d4baff',dim:'#3a2a5c',grad:'linear-gradient(140deg,#c7a3ff,#8b54f0)'},rose:{primary:'#FF5C7A',soft:'#ffaebd',dim:'#5a1f2c',grad:'linear-gradient(140deg,#ff8aa0,#e8324f)'}};
var BG={cool:{'--bg-0':'#0a0a0c','--bg-1':'#0f0f13','--bg-2':'#16161c','--bg-3':'#1e1e26','--line':'#23232c','--line-2':'#30303a','--tx-1':'#9b988e','--tx-2':'#66645c'},warm:{'--bg-0':'#0f0a07','--bg-1':'#15100b','--bg-2':'#1c150e','--bg-3':'#241a11','--line':'#2c2319','--line-2':'#392d20','--tx-1':'#a39c8e','--tx-2':'#6e665a'}};
var t={theme:'copper',bg:'cool',glow:true,scanline:false};
try{var raw=localStorage.getItem('lifeos.tweaks');if(raw){var p=JSON.parse(raw);if(p&&typeof p==='object'){if(p.theme&&THEMES[p.theme])t.theme=p.theme;if(p.bg==='cool'||p.bg==='warm')t.bg=p.bg;if(typeof p.glow==='boolean')t.glow=p.glow;if(typeof p.scanline==='boolean')t.scanline=p.scanline;}}}catch(e){}
var th=THEMES[t.theme],r=document.documentElement.style;
r.setProperty('--accent',th.primary);r.setProperty('--accent-soft',th.soft);r.setProperty('--accent-dim',th.dim);r.setProperty('--accent-grad',th.grad);
r.setProperty('--glow',t.glow?('0 0 0 1px '+th.primary+'52, 0 0 22px -6px '+th.primary):('0 0 0 1px '+th.primary+'30'));
var bg=BG[t.bg];for(var k in bg)r.setProperty(k,bg[k]);
if(t.scanline)document.documentElement.setAttribute('data-scanline','1');
}catch(e){}})();`;
