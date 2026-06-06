/* ============================================================
   DATA — mock store for Life Command OS
   ============================================================ */
window.DB = {
  user: { name:'Chỉ huy', handle:'pro · vira', initials:'CH' },
  now: 'THỨ SÁU · 06.06.2026 · 08:42',

  net: {
    total: 247850, day: 3420, dayPct: 1.4, week: 11200, weekPct: 4.7,
    dryPowder: 49570,
    series: [218,221,219,224,222,220,226,224,229,227,232,230,228,235,233,240,238,236,242,247.85],
    alloc: [
      { k:'Crypto', pct:38, color:'var(--accent)', val:94183, pnl:8420 },
      { k:'ETF',    pct:24, color:'#4DA6FF',       val:59484, pnl:2180 },
      { k:'VN equities', pct:18, color:'#a877ff',  val:44613, pnl:-640 },
      { k:'Dry powder',  pct:20, color:'#4a3a2a',  val:49570, pnl:0 },
    ],
  },

  claude: { pct:71, used:142300, cap:200000, resetIn:'2h 47m', weekly:64,
    series:[12,28,35,30,48,52,44,60,55,71], model:'claude-opus-4' },

  market: [
    { sym:'BTC', name:'Bitcoin', px:'68,240', chg:'+3.1%', dir:'pos' },
    { sym:'ETH', name:'Ethereum', px:'3,820', chg:'+5.2%', dir:'pos' },
    { sym:'SOL', name:'Solana', px:'164.2', chg:'+2.4%', dir:'pos' },
    { sym:'SPY', name:'S&P 500 ETF', px:'612.4', chg:'+0.4%', dir:'pos' },
    { sym:'QQQ', name:'Nasdaq 100', px:'528.1', chg:'+0.6%', dir:'pos' },
    { sym:'VNINDEX', name:'VN-Index', px:'1,284', chg:'-0.6%', dir:'neg' },
    { sym:'USDT/VND', name:'Tether', px:'24,180', chg:'+0.1%', dir:'pos' },
    { sym:'BRENT', name:'Brent Oil', px:'78.4', chg:'-1.2%', dir:'neg' },
    { sym:'GOLD', name:'Gold', px:'2,418', chg:'+0.3%', dir:'pos' },
  ],

  projects: [
    { id:'life-command', name:'life-command', desc:'Trung tâm điều hành — bạn đang ở đây', health:'act', healthLbl:'healthy',
      progress:87, users:3, last:'2h trước', lastDays:0, next:'ship S6', repo:'vira/life-command', commits:412, stars:48,
      lang:'TypeScript', routines:['morning-brief','wiki-refresh'], lastAuto:'08:00 sáng nay',
      desc2:'Personal AI OS — dashboard tổng hợp dự án, tài chính, automation. Bạn define rule, AI thực thi.' },
    { id:'mcp-wrapper', name:'mcp-wrapper', desc:'Bọc REST → tool MCP cho AI', health:'act', healthLbl:'healthy',
      progress:92, users:1, last:'6h trước', lastDays:0, next:'deploy', repo:'vira/mcp-wrapper', commits:188, stars:23,
      lang:'Python', routines:['wiki-refresh'], lastAuto:'02:14 sáng nay',
      desc2:'Wrapper biến REST API bất kỳ thành MCP tools để Claude Code cắm vào.' },
    { id:'vira-bot', name:'vira-bot', desc:'Bot giao dịch ladder tự động', health:'slow', healthLbl:'chậm',
      progress:64, users:0, last:'4d trước', lastDays:4, next:'backtest', repo:'vira/vira-bot', commits:96, stars:7,
      lang:'Rust', routines:['market-poll'], lastAuto:'08:35 sáng nay',
      desc2:'Bot DCA + ladder cho crypto. Đang dừng ở giai đoạn backtest 4 ngày.' },
    { id:'portfolio-reader', name:'portfolio-reader', desc:'Reader đọc git/log cập nhật metadata', health:'stall', healthLbl:'đứng',
      progress:41, users:0, last:'14d trước', lastDays:14, next:'quyết bỏ?', repo:'vira/portfolio-reader', commits:34, stars:1,
      lang:'Go', routines:['idle-hunter','pattern-check'], lastAuto:'—',
      desc2:'Reader quét git/log để tự cập nhật metadata dự án. Đứng yên 14 ngày @41% — khớp pattern build-to-90.' },
  ],

  graveyard: [
    { name:'auto-blogger', reason:'Mất hứng sau khi xong 78%', died:'03/2026', peak:78, lesson:'Build-to-90 rồi bỏ — y như pattern hiện tại.' },
    { name:'crypto-screener', reason:'Trùng tool có sẵn', died:'01/2026', peak:55, lesson:'Không validate "đã có ai làm chưa" trước khi code.' },
    { name:'note-sync', reason:'Scope phình to', died:'11/2025', peak:62, lesson:'Bắt đầu nhỏ, đừng ôm đồm sync 5 nền tảng.' },
    { name:'habit-tracker-v1', reason:'Không ai dùng (kể cả tôi)', died:'09/2025', peak:90, lesson:'90% xong, 0 user — cảnh báo lớn nhất.' },
  ],

  // ===== ACTIVE LAYER =====
  routines: [
    { id:'morning-brief', name:'Morning brief', trigger:'scheduled', triggerLbl:'8:00 hằng ngày',
      action:'Pull data mọi dự án + finance → sinh brief', on:true, lastRun:'08:00 hôm nay', lastResult:'ok', runs:142,
      desc:'Tổng hợp toàn bộ state buổi sáng thành 3 ưu tiên.' },
    { id:'wiki-refresh', name:'Refresh wiki', trigger:'event', triggerLbl:'commit mới ở repo',
      action:'Đọc lại repo → cập nhật wiki + status dự án', on:true, lastRun:'02:14 hôm nay', lastResult:'ok', runs:318,
      desc:'Mỗi commit, đọc diff và cập nhật trang wiki + tiến độ.' },
    { id:'market-poll', name:'Market poll', trigger:'scheduled', triggerLbl:'mỗi 10 phút',
      action:'Fetch giá → check trigger ladder → alert', on:true, lastRun:'08:35 hôm nay', lastResult:'err', runs:4126,
      desc:'Poll giá, so với ladder rung, bắn cảnh báo khi chạm.' },
    { id:'idle-hunter', name:'Idle hunter', trigger:'scheduled', triggerLbl:'22:00 mỗi tối',
      action:'Quét dự án đứng yên >7 ngày → cảnh báo', on:true, lastRun:'22:00 hôm qua', lastResult:'ok', runs:64,
      desc:'Tìm dự án bị bỏ quên, nhắc bạn quyết định.' },
    { id:'pattern-check', name:'Pattern check', trigger:'scheduled', triggerLbl:'9:00 hằng ngày',
      action:'Quét dự án 90%-0-user → cảnh báo + câu hỏi khó', on:true, lastRun:'09:00 hôm nay', lastResult:'ok', runs:58,
      desc:'Phát hiện pattern build-to-90 rồi bỏ, hỏi thẳng.' },
    { id:'journal-nudge', name:'Journal nudge', trigger:'event', triggerLbl:'khi giá chạm rung',
      action:'Nhắc ghi quyết định vào journal', on:false, lastRun:'2d trước', lastResult:'ok', runs:21,
      desc:'Mỗi lần ladder hit, nhắc ghi lại lý do vào nhật ký lệnh.' },
  ],

  activity: [
    { id:1, routine:'morning-brief', name:'MORNING-BRIEF', status:'ok', desc:'Sinh brief 06/06 — 3 ưu tiên, đọc 4 dự án + finance', time:'08:00', ago:'42 phút', dur:'4.2s',
      output:'Brief tạo thành công. 3 ưu tiên: DCA BTC $2k · quyết portfolio-reader · 1 session Claude. Đọc 4 dự án, 9 mã thị trường.' },
    { id:2, routine:'market-poll', name:'MARKET-POLL', status:'err', desc:'Lỗi fetch giá BRENT — timeout, đã retry 2 lần', time:'08:35', ago:'7 phút', dur:'10.0s',
      output:'ERROR: fetch https://api.market/brent → ETIMEDOUT sau 10s. Retry 1/2 lỗi. Retry 2/2 lỗi. Các mã khác OK (8/9).' },
    { id:3, routine:'pattern-check', name:'PATTERN-CHECK', status:'ok', desc:'portfolio-reader khớp build-to-90 → đẩy cảnh báo', time:'09:00', ago:'vừa xong', dur:'1.8s',
      output:'Phát hiện 1 match: portfolio-reader (41%, 0 user, idle 14d). Đẩy alert + câu hỏi: "Quyết bỏ hay đẩy tiếp?"' },
    { id:4, routine:'wiki-refresh', name:'WIKI-REFRESH', status:'ok', desc:'Cập nhật life-command từ 3 commit mới', time:'08:12', ago:'30 phút', dur:'3.1s',
      output:'Đọc 3 commit (a3f2, b81c, c44e). Cập nhật wiki: "S5–S8 Finance done". Tiến độ 84% → 87%.' },
    { id:5, routine:'market-poll', name:'MARKET-POLL', status:'ok', desc:'BTC chạm $68,200 → ladder rung 2 active → alert', time:'08:36', ago:'6 phút', dur:'2.4s',
      output:'BTC $68,240 ≥ trigger $68,200. Ladder rung_2 ACTIVE. Bắn alert MARKET + đề xuất DCA $2,000.' },
    { id:6, routine:'idle-hunter', name:'IDLE-HUNTER', status:'ok', desc:'Quét 4 dự án → 1 đứng yên >7d (portfolio-reader)', time:'22:00', ago:'10 giờ', dur:'1.2s',
      output:'Scan 4 dự án. portfolio-reader idle 14d > ngưỡng 7d. Đẩy cảnh báo PROJECT.' },
    { id:7, routine:'wiki-refresh', name:'WIKI-REFRESH', status:'ok', desc:'Cập nhật mcp-wrapper từ 1 commit', time:'02:14', ago:'6 giờ', dur:'2.0s',
      output:'Đọc commit d99a. Cập nhật wiki mcp-wrapper. Tiến độ 90% → 92%.' },
    { id:8, routine:'morning-brief', name:'MORNING-BRIEF', status:'ok', desc:'Brief 05/06 — 3 ưu tiên', time:'08:00', ago:'1 ngày', dur:'3.9s',
      output:'Brief 05/06 OK. Ưu tiên: ship Finance screens · backtest vira-bot · review portfolio.' },
  ],

  alerts: [
    { level:'r', text:'BTC chạm trigger $68,200 — rung 2 ladder active', src:'MARKET', ago:'6 phút trước' },
    { level:'a', text:'portfolio-reader đứng yên 14 ngày', src:'PROJECT', ago:'sáng nay' },
    { level:'a', text:'Claude quota 71% đã đốt — reset 2h47m', src:'CLAUDE', ago:'20 phút trước' },
    { level:'g', text:'ETH +5.2% — vượt ngưỡng theo dõi $3,800', src:'MARKET', ago:'1 giờ trước' },
    { level:'r', text:'MARKET-POLL lỗi fetch giá BRENT — đã retry', src:'SYSTEM', ago:'7 phút trước' },
  ],

  brief: [
    { n:'01', html:'BTC chạm rung 2 <b class="acc">$68.2k</b> — cân nhắc DCA <b style="color:var(--tx-0)">$2k</b>, dry powder 20% đủ dư địa.' },
    { n:'02', html:'<b style="color:var(--tx-0)">portfolio-reader</b> đứng 14d @41% — khớp pattern <span class="mid">build-to-90</span>. Quyết bỏ / đẩy?' },
    { n:'03', html:'Quota còn <b style="color:var(--tx-0)">2h47m</b> ~58k token — đủ 1 session sâu. Ưu tiên mcp-wrapper.' },
  ],

  journal: [
    { date:'06/06', action:'BUY', asset:'BTC', size:'$2,000', px:'$68,240', reason:'Rung 2 ladder hit. DCA theo kế hoạch.', pnl:null, tag:'ladder' },
    { date:'02/06', action:'BUY', asset:'ETH', size:'$1,500', px:'$3,620', reason:'Dưới MA200, tích lũy.', pnl:'+5.5%', tag:'dca' },
    { date:'28/05', action:'SELL', asset:'SOL', size:'$1,200', px:'$172', reason:'Chốt lời một phần, rebalance.', pnl:'+18%', tag:'rebalance' },
    { date:'21/05', action:'BUY', asset:'VNM', size:'$800', px:'62,000đ', reason:'Định giá rẻ, cổ tức cao.', pnl:'-4.1%', tag:'value' },
    { date:'14/05', action:'BUY', asset:'BTC', size:'$2,000', px:'$64,100', reason:'Rung 1 ladder hit.', pnl:'+6.5%', tag:'ladder' },
  ],

  notes: [
    { id:1, title:'Ý tưởng: AI OS tự vận hành', tag:'idea', pinned:true, updated:'hôm nay', body:'Tôi define rule + goal, AI thực thi. Activity Feed để minh bạch. Không build marketplace skill — mỗi routine phải tiết kiệm thời gian thật.' },
    { id:2, title:'Pattern build-to-90', tag:'insight', pinned:true, updated:'hôm nay', body:'Mình hay build tới 90% rồi bỏ trước khi có user. auto-blogger, habit-tracker, giờ là portfolio-reader. Cần cơ chế ép ship ở 70%.' },
    { id:3, title:'Ladder BTC plan', tag:'finance', pinned:false, updated:'2 ngày trước', body:'Rung 1 $64k ✓ · Rung 2 $68.2k (active) · Rung 3 $72k · Rung 4 $76k. Mỗi rung DCA $2k. Dry powder giữ ≥15%.' },
    { id:4, title:'MCP wrapper — backlog', tag:'project', pinned:false, updated:'4 ngày trước', body:'- Auth pass-through\n- Rate limit\n- Tool schema từ OpenAPI tự sinh\n- Deploy lên fly.io' },
    { id:5, title:'Câu hỏi tuần này', tag:'idea', pinned:false, updated:'5 ngày trước', body:'Nếu chỉ giữ được 1 dự án trong 3 tháng tới, đó là dự án nào? → life-command.' },
  ],

  chat: [
    { role:'user', text:'Vì sao portfolio-reader chững lại?' },
    { role:'ai', text:'Mình đọc git + activity của portfolio-reader: commit cuối 14 ngày trước, dừng ở 41%. Pattern khớp **build-to-90 / abandon-before-user** — cùng dấu vết với auto-blogger (78%) và habit-tracker (90%, 0 user).\n\n3 lý do khả dĩ:\n1. **Scope mơ hồ** — "đọc git/log cập nhật metadata" chưa có định nghĩa "xong".\n2. **Không user chờ** — 0 user nên không có áp lực ship.\n3. **Mới hơn, sexy hơn** — life-command hút hết năng lượng.\n\nĐề xuất: cắt scope xuống 1 việc (chỉ đọc commit → cập nhật %), ship trong 1 session Claude còn lại hôm nay, hoặc đưa vào Graveyard có chủ đích.' },
  ],
};

// ----- nav structure (14 screens, 6 groups) -----
window.NAV = [
  { sec:'Tổng quan', items:[ ['home','Home','i-home'] ] },
  { sec:'Dự án', items:[ ['projects','Dự án','i-proj',{badge:'4',cls:'acc'}], ['graveyard','Nghĩa địa','i-grave'] ] },
  { sec:'Tài chính', items:[ ['finance','Tổng quan','i-fin'], ['portfolio','Danh mục','i-pie'], ['journal','Nhật ký lệnh','i-journal'], ['market','Thị trường','i-mkt',{badge:'2',cls:'r'}] ] },
  { sec:'Hằng ngày', items:[ ['claude','Claude Usage','i-cpu',{badge:'71%',cls:'r'}], ['notes','Ghi chú','i-note'] ] },
  { sec:'AI & Config', items:[ ['ai','AI Brain','i-ai'], ['settings','Cài đặt','i-set'] ] },
  { sec:'Active', items:[ ['automation','Automation','i-bolt',{badge:'5',cls:'g'}], ['activity','Activity Feed','i-pulse'] ] },
];

window.CRUMB = {
  home:'Home', projects:'Dự án', graveyard:'Nghĩa địa dự án', finance:'Tài chính', portfolio:'Danh mục',
  journal:'Nhật ký lệnh', market:'Thị trường & Cảnh báo', claude:'Claude Usage', notes:'Ghi chú',
  ai:'AI Brain', settings:'Cài đặt', automation:'Automation / Routines', activity:'Activity Feed',
};
