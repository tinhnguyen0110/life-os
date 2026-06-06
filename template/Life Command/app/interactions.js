/* ============================================================
   INTERACTIONS — delegated handlers (run once)
   ============================================================ */
(function(){
document.addEventListener('click', e=>{
  // ----- routine on/off toggle -----
  const rtog = e.target.closest('[data-routine]');
  if(rtog){ e.stopPropagation();
    const id = rtog.dataset.routine; const r = DB.routines.find(x=>x.id===id);
    if(r){ r.on=!r.on; rtog.classList.toggle('on', r.on);
      rtog.closest('.routine-card')?.classList.toggle('off', !r.on);
      toast(r.on?'g':'a', `${r.name} đã ${r.on?'bật':'tắt'}`);
    }
    return;
  }
  // ----- run a routine on-demand -----
  const run = e.target.closest('[data-run]');
  if(run){ e.stopPropagation();
    const r = DB.routines.find(x=>x.id===run.dataset.run);
    toast('acc', `▶ Đang chạy ${r?r.name:'routine'}… xem Activity Feed`);
    return;
  }
  // ----- generic toggles (settings etc.) -----
  const tog = e.target.closest('.toggle:not([data-routine])');
  if(tog){ e.stopPropagation(); tog.classList.toggle('on'); return; }
  // ----- expand feed row -----
  const feed = e.target.closest('[data-feed]');
  if(feed){ feed.classList.toggle('open'); return; }
  // ----- ai suggestion chip -----
  const sug = e.target.closest('[data-suggest]');
  if(sug){ const inp=document.getElementById('aiInput'); if(inp){ inp.value=sug.dataset.suggest; inp.focus(); } return; }
  // ----- ai send -----
  const send = e.target.closest('#aiSend');
  if(send){ aiSend(); return; }
  // ----- tabs (visual) -----
  const tab = e.target.closest('.tab');
  if(tab && tab.parentElement){ tab.parentElement.querySelectorAll('.tab').forEach(t=>t.classList.remove('on')); tab.classList.add('on');
    // feed filter
    if(tab.dataset.f){ filterFeed(tab.dataset.f); }
    return;
  }
  // ----- seg buttons (visual) -----
  const seg = e.target.closest('.seg button');
  if(seg && seg.parentElement){ seg.parentElement.querySelectorAll('button').forEach(b=>b.classList.remove('on')); seg.classList.add('on'); return; }
  // ----- new routine -----
  if(e.target.closest('#newRoutine')||e.target.closest('#newRoutine2')){ toast('acc','Form routine mới — chọn trigger + hành động (demo)'); return; }
});

// command-bar / ai enter
document.addEventListener('keydown', e=>{
  if(e.key!=='Enter') return;
  if(e.target.id==='homeCmd'){ runCommand(e.target.value); e.target.value=''; }
  else if(e.target.id==='aiInput'){ aiSend(); }
});

function runCommand(v){
  v=(v||'').trim(); if(!v) return;
  const low=v.toLowerCase();
  if(low.startsWith('open ')){ const id=low.slice(5).trim(); const p=DB.projects.find(x=>x.id.includes(id)); if(p){ location.hash='#project/'+p.id; return; } }
  if(low.startsWith('dca')){ toast('g','✓ Ghi nhận lệnh DCA — mở Nhật ký để xác nhận'); location.hash='#journal'; return; }
  if(low.startsWith('run')){ toast('acc','▶ Kích hoạt routine — xem Activity Feed'); location.hash='#activity'; return; }
  if(low.startsWith('ask')||low.startsWith('hỏi')){ location.hash='#ai'; return; }
  if(low.startsWith('note')){ location.hash='#notes'; return; }
  toast('a','Lệnh chưa rõ — thử: open <dự án> · dca btc 2000 · run morning-brief · ask …');
}

function aiSend(){
  const inp=document.getElementById('aiInput'); if(!inp||!inp.value.trim()) return;
  const wrap=document.querySelector('.chat-wrap'); if(!wrap) return;
  const q=inp.value.trim(); inp.value='';
  wrap.insertAdjacentHTML('beforeend', `<div class="msg user"><div class="mav">CH</div><div class="mbody"><div class="who">Bạn</div><div class="mtext">${q}</div></div></div>`);
  const thinking=document.createElement('div'); thinking.className='msg ai';
  thinking.innerHTML=`<div class="mav">✦</div><div class="mbody"><div class="who">AI Brain</div><div class="mtext faint">đang đọc state…</div></div>`;
  wrap.appendChild(thinking);
  const view=document.getElementById('view'); view.scrollTop=view.scrollHeight;
  setTimeout(()=>{
    thinking.querySelector('.mtext').classList.remove('faint');
    thinking.querySelector('.mtext').innerHTML='Mình đã đọc dự án, finance và activity feed. Đây là góc nhìn dựa trên state thật của bạn — chi tiết hơn cần mình đào sâu vào dữ liệu cụ thể nào?';
    view.scrollTop=view.scrollHeight;
  }, 700);
}

function filterFeed(f){
  document.querySelectorAll('#feed .feed-row').forEach(row=>{
    const a=DB.activity.find(x=>x.id==row.dataset.feed);
    row.style.display = (f==='all'||(a&&a.status===f))?'':'none';
  });
}
})();
