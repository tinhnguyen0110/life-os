/* ============================================================
   WIKI DATA — Knowledge vault (Zettelkasten / Wiki-LLM)
   integer-ID notes · typed links · candidate proposals
   ============================================================ */
window.WIKI = {
  stats: {
    totalNotes: 142,
    byStatus: { fleeting: 8, developing: 31, evergreen: 103 },
    totalLinks: 487,
    orphanCount: 6,
    ghostLinkCount: 3,
    pctWithLink: 94.2,
    asOf: '13.06.2026 · 10:00',
  },

  // ---- full note records (keyed by integer id) ----
  notes: {
    47: { id:47, title:'Knowledge work accretes', aliases:['accretion model of knowledge'],
      status:'evergreen', noteType:'concept', trustTier:'verified', author:'human',
      tags:['learning','pkm'], created:'02.04.2026', updated:'13.06.2026 · 09:55', degree:7,
      content:`Tri thức không đến trong một cú "aha" lớn — nó **bồi đắp** qua thời gian, mỗi note nhỏ kết nối với cái đã có.\n\nCơ chế cốt lõi là **tái kết hợp**: ý A gặp ý B sinh ra ý C. Càng nhiều note atomic được liên kết, càng nhiều tổ hợp khả dĩ. Đây là lý do [[88|MOCs are workstations]] quan trọng — chúng là nơi tái kết hợp diễn ra có chủ đích.\n\nNgược với mô hình "đọc xong là biết", accretion coi hiểu biết như **lãi kép**: đầu tư đều, kết nối đều, giá trị tăng phi tuyến. Xem thêm [[Atomicity principle]].` },
    88: { id:88, title:'MOCs are workstations', aliases:['map of content','MOC'],
      status:'evergreen', noteType:'concept', trustTier:'verified', author:'human',
      tags:['pkm','moc'], created:'15.03.2026', updated:'13.06.2026 · 09:40', degree:4,
      content:`MOC (Map of Content) không phải mục lục thụ động — nó là **bàn làm việc** nơi bạn chủ động gom, sắp, và nối các note rời thành một throughline.\n\nKhác với backlinks (tự sinh, máy đọc), MOC là **note có thể ghi** — con người curate. Như [[47|Knowledge work accretes]] chỉ ra, tái kết hợp cần một không gian vật lý; MOC chính là không gian đó.` },
    31: { id:31, title:'Concept-orientation beats source-orientation', aliases:[],
      status:'evergreen', noteType:'concept', trustTier:'verified', author:'human',
      tags:['pkm','method'], created:'20.03.2026', updated:'01.06.2026', degree:5,
      content:`Tổ chức note theo **khái niệm** (một ý / một note) thắng tổ chức theo **nguồn** (một sách / một note).\n\nLý do: khái niệm tái dùng được across nguồn; nguồn thì khóa cứng. Concept-orientation cho phép [[47|tri thức tích lũy]] qua tái kết hợp.` },
    102:{ id:102, title:'Evergreen notes compound', aliases:[],
      status:'developing', noteType:'concept', trustTier:'verified', author:'human',
      tags:['pkm','learning'], created:'10.05.2026', updated:'09.06.2026', degree:3,
      content:`Note evergreen — viết lại tới khi atomic + tái dùng được — **sinh lãi kép** theo thời gian. Knowledge work accretes over time khi note đủ chín để được nối lại nhiều lần.` },
    12: { id:12, title:'Spaced repetition is interest-driven', aliases:[],
      status:'evergreen', noteType:'concept', trustTier:'verified', author:'human',
      tags:['learning','memory'], created:'01.04.2026', updated:'01.04.2026', degree:0,
      content:`Ôn tập hiệu quả nhất khi **được dẫn dắt bởi hứng thú**, không phải lịch cứng. Khi tò mò, não mã hóa sâu hơn — interval tối ưu là interval bạn *muốn* quay lại.` },
    47.1:{ id:115, title:'Atomicity principle', ghost:true },
  },

  // ---- inbox (fleeting notes awaiting triage) ----
  inbox: [
    { id:47, title:null, status:'fleeting', captured:'08:12 hôm nay', captureSource:'command_bar', linkCount:0,
      rawContent:'dump nhanh: tri thức không đến 1 lần, nó bồi đắp qua các kết nối nhỏ. mỗi note gặp note khác sinh ý mới. giống lãi kép. cần MOC để tái kết hợp có chủ đích.',
      aiSuggest:{ titleClaim:'Knowledge work accretes', summary:'Tri thức tích lũy phi tuyến qua tái kết hợp các note atomic.',
        atomicityFlag:'có vẻ chứa 2 ý: (a) accretion model (b) vai trò của MOC — cân nhắc tách', dupeOf:null } },
    { id:201, title:null, status:'fleeting', captured:'07:48 hôm nay', captureSource:'daily_note', linkCount:0,
      rawContent:'ý: dry powder trong đầu tư = slack trong hệ thống. luôn giữ buffer để phản ứng cơ hội bất ngờ.',
      aiSuggest:{ titleClaim:'Slack enables opportunistic response', summary:'Buffer chưa-dùng cho phép phản ứng nhanh với cơ hội.',
        atomicityFlag:'atomic ✓', dupeOf:null } },
    { id:202, title:null, status:'fleeting', captured:'hôm qua · 21:30', captureSource:'command_bar', linkCount:0,
      rawContent:'spaced repetition nên interest-driven chứ ko phải fixed schedule',
      aiSuggest:{ titleClaim:'Spaced repetition is interest-driven', summary:'Ôn theo hứng thú thắng lịch cứng.',
        atomicityFlag:'atomic ✓', dupeOf:{ id:12, title:'Spaced repetition is interest-driven', similarity:0.91 } } },
    { id:203, title:null, status:'fleeting', captured:'hôm qua · 18:02', captureSource:'mcp_agent', linkCount:0,
      rawContent:'từ session Claude Code: pattern build-to-90 = bỏ dự án ngay trước khi có user. cơ chế: thiếu áp lực ship khi 0 user.',
      aiSuggest:{ titleClaim:'Build-to-90 abandonment pattern', summary:'Xu hướng bỏ dự án ở ~90% vì thiếu áp lực user.',
        atomicityFlag:'atomic ✓', dupeOf:null } },
    { id:204, title:null, status:'fleeting', captured:'2 ngày trước', captureSource:'quick_add', linkCount:0,
      rawContent:'ghi chú thoáng qua về typed links — edge có loại (supports/contradicts/refines) giàu thông tin hơn link trơn.',
      aiSuggest:null },
    { id:205, title:null, status:'fleeting', captured:'2 ngày trước', captureSource:'command_bar', linkCount:0,
      rawContent:'evergreen vs fleeting: fleeting là nháp, evergreen là đã chưng cất. trạng thái mềm, đổi tại chỗ.',
      aiSuggest:{ titleClaim:'Note status is a soft gradient', summary:'fleeting→developing→evergreen là phổ mềm, giữ id.',
        atomicityFlag:'atomic ✓', dupeOf:null } },
    { id:206, title:null, status:'fleeting', captured:'3 ngày trước', captureSource:'daily_note', linkCount:0,
      rawContent:'orphan note = note không link gì. đó là nợ tri thức, cần sweep định kỳ.', aiSuggest:null },
    { id:207, title:null, status:'fleeting', captured:'3 ngày trước', captureSource:'command_bar', linkCount:0,
      rawContent:'citation-safe: khi sửa đoạn có block-id, cảnh báo citation có thể lệch.', aiSuggest:null },
  ],

  // ---- orphans (degree 0 or stale) ----
  orphans: [
    { id:12, title:'Spaced repetition is interest-driven', status:'evergreen', degree:0, lastTouched:'01.04.2026' },
    { id:78, title:'Note typing reduces ambiguity', status:'developing', degree:0, lastTouched:'12.05.2026' },
    { id:90, title:'Capture is separate from refine', status:'evergreen', degree:1, lastTouched:'20.03.2026' },
    { id:133,title:'Slack absorbs variance', status:'developing', degree:0, lastTouched:'02.05.2026' },
    { id:140,title:'ID-redirect tombstones preserve citations', status:'evergreen', degree:1, lastTouched:'28.04.2026' },
    { id:141,title:'FTS5 beats embedding for recall', status:'fleeting', degree:0, lastTouched:'10.06.2026' },
  ],

  // ---- recent op-log activity ----
  recentActivity: [
    { ts:'09:55', op:'edit', actor:'human', noteId:88, noteTitle:'MOCs are workstations', detail:'sửa thân note' },
    { ts:'09:40', op:'link_candidate', actor:'agent', noteId:47, noteTitle:'Knowledge work accretes', detail:'đề xuất [[47]] → [[31]]' },
    { ts:'09:22', op:'create', actor:'human', noteId:47, noteTitle:'Knowledge work accretes', detail:'capture vào inbox' },
    { ts:'08:50', op:'refine', actor:'human', noteId:102, noteTitle:'Evergreen notes compound', detail:'fleeting → developing' },
    { ts:'08:30', op:'moc_proposal', actor:'agent', noteId:null, noteTitle:'PKM Methodology', detail:'cụm 4 note → đề xuất MOC' },
    { ts:'02:14', op:'agent_note', actor:'agent', noteId:208, noteTitle:'Distilled: spaced repetition debate', detail:'MCP viết note candidate' },
    { ts:'hôm qua', op:'link', actor:'human', noteId:31, noteTitle:'Concept-orientation...', detail:'nối [[31]] → [[47]]' },
    { ts:'hôm qua', op:'merge', actor:'human', noteId:55, noteTitle:'(merged)', detail:'gộp #55 → #12, tạo tombstone' },
  ],

  // ---- backlinks per note ----
  backlinks: {
    47: {
      linked: [
        { id:88, title:'MOCs are workstations', snippet:'…như <b>[[47]]</b> chỉ ra, tái kết hợp cần một không gian vật lý…', anchor:'^b3' },
        { id:31, title:'Concept-orientation beats source-orientation', snippet:'…cho phép <b>[[47|tri thức tích lũy]]</b> qua tái kết hợp…', anchor:'^a1' },
      ],
      unlinked: [
        { id:102, title:'Evergreen notes compound', snippet:'…<b>knowledge work accretes</b> over time khi note đủ chín…' },
      ],
      outbound: [
        { id:88, title:'MOCs are workstations', isResolved:true },
        { ghost:'Atomicity principle', isResolved:false },
      ],
    },
  },

  // ---- AI link suggestions per note ----
  suggestions: {
    47: [
      { id:31, title:'Concept-orientation beats source-orientation', state:'candidate', confidence:0.82,
        why:'Cả hai bàn cách tri thức tích lũy qua tái kết hợp ý — chia sẻ 3 inbound chung (#88, #102, #115).' },
      { id:102, title:'Evergreen notes compound', state:'candidate', confidence:0.76,
        why:'"compound" và "accretes" cùng mô tả tăng trưởng phi tuyến của hiểu biết — gần như đồng nghĩa ở tầng ý.' },
      { id:12, title:'Spaced repetition is interest-driven', state:'rejected', confidence:0.41,
        why:'Liên quan yếu qua "learning" tag — đã reject trước đó.' },
    ],
  },

  // ---- proposal queue (P1) ----
  proposals: [
    { id:'p_1', kind:'link_candidate', actor:'agent:claude-code', noteId:47, noteTitle:'Knowledge work accretes',
      targetId:31, targetTitle:'Concept-orientation beats source-orientation', confidence:0.82,
      why:'Chia sẻ 3 inbound chung, cùng bàn tái kết hợp ý.', created:'09:40', correlationId:'mcp-abc123', state:'pending' },
    { id:'p_2', kind:'agent_note', actor:'agent:claude-code', title:'Distilled: spaced repetition debate', status:'candidate',
      why:'Tổng hợp từ session 13.06 — gom 3 note rời về ôn tập.', content:'Tranh luận: lịch cố định (Anki) vs interest-driven…', created:'02:14', correlationId:'mcp-def456', state:'pending' },
    { id:'p_3', kind:'moc_proposal', actor:'agent:claude-code', title:'PKM Methodology', memberIds:[47,88,31,102],
      why:'Cụm 4 note mật độ 0.7 — ứng viên MOC rõ ràng.', created:'08:30', correlationId:'mcp-ghi789', state:'pending' },
    { id:'p_4', kind:'merge_suggestion', actor:'agent:claude-code', sourceId:202, sourceTitle:'(fleeting) spaced repetition…',
      targetId:12, targetTitle:'Spaced repetition is interest-driven', confidence:0.91,
      why:'Trùng 91% với note evergreen #12 — đề xuất merge + tombstone.', created:'07:48', correlationId:'mcp-jkl012', state:'pending' },
  ],

  // ---- ego graph (center 47, depth 2) ----
  graph: {
    center: 47,
    nodes: [
      { id:47, title:'Knowledge work accretes', status:'evergreen', degree:7, x:50, y:50 },
      { id:88, title:'MOCs are workstations', status:'evergreen', degree:4, x:74, y:30 },
      { id:31, title:'Concept-orientation beats source', status:'evergreen', degree:5, x:78, y:66 },
      { id:102,title:'Evergreen notes compound', status:'developing', degree:3, x:30, y:28 },
      { id:115,title:'Atomicity principle', status:'fleeting', degree:1, x:24, y:62, ghost:true },
      { id:12, title:'Spaced repetition is interest-driven', status:'evergreen', degree:0, x:52, y:84, orphan:true },
      { id:90, title:'Capture is separate from refine', status:'evergreen', degree:2, x:14, y:44 },
      { id:78, title:'Note typing reduces ambiguity', status:'developing', degree:2, x:88, y:48 },
    ],
    edges: [
      { source:47, target:88, type:'relates', isResolved:true },
      { source:47, target:31, type:'supports', isResolved:true },
      { source:47, target:102, type:'refines', isResolved:true },
      { source:47, target:115, type:'example_of', isResolved:false },
      { source:88, target:31, type:'relates', isResolved:true },
      { source:102,target:90, type:'relates', isResolved:true },
      { source:88, target:78, type:'supports', isResolved:true },
    ],
    clusters: [
      { label:'PKM methodology', noteIds:[47,88,31,102], density:0.7, mocSuggestion:true },
    ],
  },

  // ---- MOC draft (W5) ----
  mocDraft: {
    clusterLabel: 'PKM Methodology',
    members: [
      { id:47, title:'Knowledge work accretes', status:'evergreen' },
      { id:88, title:'MOCs are workstations', status:'evergreen' },
      { id:31, title:'Concept-orientation beats source-orientation', status:'evergreen' },
      { id:102,title:'Evergreen notes compound', status:'developing' },
    ],
    draftScaffold: `## PKM Methodology\n\nCác note này tạo thành một phương pháp luận mạch lạc về quản lý tri thức cá nhân:\n\n- [[47|Knowledge work accretes]] — nền tảng: tri thức tích lũy qua tái kết hợp\n- [[31|Concept-orientation beats source-orientation]] — cách tổ chức để tái kết hợp được\n- [[88|MOCs are workstations]] — không gian nơi tái kết hợp diễn ra\n- [[102|Evergreen notes compound]] — kết quả: lãi kép theo thời gian`,
    throughline: 'Tri thức tích lũy qua tái kết hợp; tổ chức theo khái niệm làm tái kết hợp khả thi; MOC là nơi nó diễn ra; note evergreen là lãi kép thu được.',
    contradictions: [
      { a:12, aTitle:'Spaced repetition is interest-driven', b:88, bTitle:'MOCs are workstations',
        note:'#12 nói review nên interest-driven (linh hoạt); #88 ngụ ý curate có cấu trúc cố định. Căng thẳng: linh hoạt vs cấu trúc.' },
    ],
  },
};

// op metadata for rendering
window.WIKI_OP = {
  create:        { lbl:'tạo',        color:'var(--green)' },
  edit:          { lbl:'sửa',        color:'var(--blue)' },
  link:          { lbl:'nối',        color:'var(--accent)' },
  link_candidate:{ lbl:'đề xuất nối', color:'var(--amber)' },
  refine:        { lbl:'tinh chỉnh', color:'var(--violet)' },
  merge:         { lbl:'gộp',        color:'var(--tx-1)' },
  moc_proposal:  { lbl:'đề xuất MOC', color:'var(--amber)' },
  agent_note:    { lbl:'note AI',    color:'var(--amber)' },
  delete:        { lbl:'xoá',        color:'var(--red)' },
};
window.STATUS_META = {
  fleeting:  { lbl:'fleeting',  color:'var(--amber)', dim:'var(--amber-dim)' },
  developing:{ lbl:'developing',color:'var(--blue)',  dim:'#11314f' },
  evergreen: { lbl:'evergreen', color:'var(--green)', dim:'var(--green-dim)' },
};
