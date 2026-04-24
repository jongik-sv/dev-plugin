
function escapeHtml(s){
  if(s==null)return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function renderWbsSection(md,source){
  if(!md)return '';
  var heading=(source==='feat')?'&sect; 사양':'&sect; WBS';
  var lines=md.split('\n'),html='<h4>'+heading+'</h4>',inCode=false,lang='';
  for(var i=0;i<lines.length;i++){
    var line=lines[i];
    if(!inCode&&line.match(/^```/)){inCode=true;lang=line.slice(3).trim();html+='<pre><code'+(lang?' class="lang-'+escapeHtml(lang)+'"':'')+'>';continue;}
    if(inCode){if(line.match(/^```/)){inCode=false;html+='</code></pre>\n';}else{html+=escapeHtml(line)+'\n';}continue;}
    var m4=line.match(/^####\s+(.*)/),m3=line.match(/^###\s+(.*)/),m2=line.match(/^##\s+(.*)/),m1=line.match(/^#\s+(.*)/);
    if(m4){html+='<h5>'+escapeHtml(m4[1])+'</h5>\n';continue;}
    if(m3){html+='<h4>'+escapeHtml(m3[1])+'</h4>\n';continue;}
    if(m2){html+='<h3>'+escapeHtml(m2[1])+'</h3>\n';continue;}
    if(m1){html+='<h2>'+escapeHtml(m1[1])+'</h2>\n';continue;}
    var li=line.match(/^\s*[-*]\s+(.*)/);
    if(li){html+='<li>'+escapeHtml(li[1])+'</li>\n';continue;}
    if(line.trim()===''){html+='<br>\n';continue;}
    html+='<p>'+escapeHtml(line)+'</p>\n';
  }
  if(inCode)html+='</code></pre>\n';
  return html;
}
function renderTaskProgressHeader(state){
  if(!state)return '';
  var status=state.status||'[ ]';
  var phase=String(status).replace('[','').replace(']','').trim();
  if(!phase||phase===' ')phase='pending';
  var last=state.last||{};
  var evt=last.event||'';
  var isRunning=/_(start|running)$/.test(evt);
  var elapsed=state.elapsed_seconds;
  var elapsedStr=(elapsed==null)?'-':String(elapsed)+'s';
  var lastAt=last.at||'-';
  var history=state.phase_history||[];
  var historyLen=history.length;
  var spinner=isRunning?'<span class="spinner"></span>':'';
  var html='<header class="progress-header">';
  html+='<div class="ph-row">';
  html+='<span class="ph-badge" data-phase="'+escapeHtml(phase)+'"'
    +(isRunning?' data-running="true"':'')+'>'
    +escapeHtml(phase)+spinner+'</span>';
  html+='<span class="ph-last-event">'+escapeHtml(evt||'-')+'</span>';
  html+='</div>';
  html+='<dl class="ph-meta">'
    +'<dt>status</dt><dd>'+escapeHtml(status)+'</dd>'
    +'<dt>last.at</dt><dd>'+escapeHtml(lastAt)+'</dd>'
    +'<dt>elapsed</dt><dd>'+escapeHtml(elapsedStr)+'</dd>'
    +'<dt>phaseCount</dt><dd>'+escapeHtml(String(historyLen))+'</dd>'
    +'</dl>';
  if(historyLen===0){
    html+='<div class="ph-history-empty">phase_history 없음</div>';
  }else{
    var recent=history.slice(-3).reverse();
    html+='<ul class="ph-history">';
    for(var i=0;i<recent.length;i++){
      var h=recent[i]||{};
      html+='<li><span class="ph-time">'+escapeHtml(h.at||'-')+'</span>'
        +'<span class="ph-evt">'+escapeHtml(h.event||'-')+'</span></li>';
    }
    html+='</ul>';
  }
  html+='</header>';
  return html;
}
function _fmtElapsedSec(sec){
  if(sec==null||sec==='')return '—';
  var n=Number(sec);
  if(!isFinite(n))return String(sec);
  if(n<60)return n+'s';
  var m=Math.floor(n/60),s=n%60;
  return m+'m '+s+'s';
}
function _fmtStateVal(v){
  if(v==null||v==='')return '—';
  if(typeof v==='boolean')return v?'true':'false';
  return String(v);
}
function renderStateJson(state){
  var html='<h4>&sect; state.json</h4>';
  if(!state||typeof state!=='object'||Object.keys(state).length===0){
    return html+'<p class="state-empty">데이터 없음</p>';
  }
  var rows=[];
  var last=(state.last&&typeof state.last==='object')?state.last:null;
  if('name' in state)rows.push(['name',_fmtStateVal(state.name)]);
  rows.push(['status',_fmtStateVal(state.status)]);
  if('started_at' in state)rows.push(['started_at',_fmtStateVal(state.started_at)]);
  if(last){
    rows.push(['last.event',_fmtStateVal(last.event)]);
    rows.push(['last.at',_fmtStateVal(last.at)]);
  }
  if('updated' in state)rows.push(['updated',_fmtStateVal(state.updated)]);
  if('completed_at' in state)rows.push(['completed_at',_fmtStateVal(state.completed_at)]);
  if('elapsed_seconds' in state)rows.push(['elapsed',_fmtElapsedSec(state.elapsed_seconds)]);
  if(state.bypassed)rows.push(['bypassed','true']);
  if(state.bypassed_reason)rows.push(['bypassed_reason',_fmtStateVal(state.bypassed_reason)]);
  html+='<table class="state-table"><tbody>';
  for(var i=0;i<rows.length;i++){
    html+='<tr><th>'+escapeHtml(rows[i][0])+'</th><td>'+escapeHtml(rows[i][1])+'</td></tr>';
  }
  html+='</tbody></table>';
  var history=(state.phase_history&&state.phase_history.length)?state.phase_history:null;
  if(history){
    html+='<h5 class="state-subhead">phase_history ('+history.length+')</h5>';
    html+='<table class="state-history-table"><thead><tr>'
      +'<th>#</th><th>event</th><th>from</th><th>to</th><th>at</th><th>elapsed</th>'
      +'</tr></thead><tbody>';
    for(var j=0;j<history.length;j++){
      var h=history[j]||{};
      html+='<tr>'
        +'<td class="state-idx">'+(j+1)+'</td>'
        +'<td>'+escapeHtml(_fmtStateVal(h.event))+'</td>'
        +'<td>'+escapeHtml(_fmtStateVal(h.from))+'</td>'
        +'<td>'+escapeHtml(_fmtStateVal(h.to))+'</td>'
        +'<td>'+escapeHtml(_fmtStateVal(h.at))+'</td>'
        +'<td>'+escapeHtml(_fmtElapsedSec(h.elapsed_seconds))+'</td>'
        +'</tr>';
    }
    html+='</tbody></table>';
  }
  return html;
}
function renderArtifacts(arts){
  var html='<h4>&sect; 아티팩트</h4>';
  if(!arts||!arts.length)return html+'<p>-</p>';
  html+='<ul>';
  for(var i=0;i<arts.length;i++){
    var a=arts[i];
    if(a.exists)html+='<li><code>'+escapeHtml(a.path)+'</code><span class="size">'+escapeHtml((a.size/1024).toFixed(1))+'KB</span></li>';
    else html+='<li class="disabled"><code>'+escapeHtml(a.path)+'</code></li>';
  }
  return html+'</ul>';
}
function renderLogs(logs){
  var html='<h4>&sect; 로그</h4>';
  if(!logs||!logs.length)return html+'<p>-</p>';
  var sections='';
  for(var i=0;i<logs.length;i++){
    var log=logs[i];
    if(!log.exists){
      sections+='<div class="log-empty">'+escapeHtml(log.name)+' — 보고서 없음</div>';
    }else{
      var truncMsg=log.truncated?'<span class="log-trunc">마지막 200줄 / 전체 '+escapeHtml(String(log.lines_total))+'줄</span>':'';
      sections+='<details class="log-entry" open><summary>'+escapeHtml(log.name)+truncMsg+'</summary>'
        +'<pre class="log-tail">'+escapeHtml(log.tail)+'</pre></details>';
    }
  }
  return html+'<section class="panel-logs">'+sections+'</section>';
}
function openTaskPanel(taskId){
  var sp='all';try{var m=location.search.match(/[?&]subproject=([^&]+)/);if(m)sp=m[1];}catch(e){}
  fetch('/api/task-detail?task='+encodeURIComponent(taskId)+'&subproject='+encodeURIComponent(sp))
    .then(function(r){return r.json();}).then(function(data){
      var t=document.getElementById('task-panel-title');if(t)t.textContent=data.title||taskId;
      var b=document.getElementById('task-panel-body');
      if(b)b.innerHTML=renderTaskProgressHeader(data.state||null)+renderWbsSection(data.wbs_section_md||'',data.source||'')+renderStateJson(data.state||{})+renderArtifacts(data.artifacts||[])+renderLogs(data.logs||[]);
      var p=document.getElementById('task-panel'),o=document.getElementById('task-panel-overlay');
      if(p){p.classList.add('open');p.dataset.panelMode='task';}if(o)o.removeAttribute('hidden');
    }).catch(function(e){console.error('task-panel error',e);});
}
function closeTaskPanel(){
  var p=document.getElementById('task-panel'),o=document.getElementById('task-panel-overlay');
  if(p)p.classList.remove('open');if(o)o.setAttribute('hidden','');
}
function renderMergePreview(ms){
  var html='';
  if(ms.stale){html+='<div class="merge-stale-banner">⚠ 스캔 결과가 30분 이상 경과 — 재스캔 필요</div>';}
  var state=ms.state||'unknown';
  if(state==='ready'){
    html+='<div class="merge-ready-banner">✅ 모든 Task 완료 · 충돌 없음</div>';
  }else if(state==='waiting'){
    html+='<h4>§ 대기 중인 Task</h4><ul>';
    var pts=ms.pending_tasks||[];
    for(var i=0;i<pts.length;i++){html+='<li>'+escapeHtml(pts[i].id||'')+' ('+escapeHtml(pts[i].phase||'')+')</li>';}
    html+='</ul>';
  }else if(state==='conflict'){
    html+='<h4>§ 충돌 파일</h4><ul class="merge-conflict-file">';
    var conflicts=ms.conflicts||[];
    var autoFiles=ms.auto_merge_files||[];
    var hunkCount=0;
    for(var i=0;i<conflicts.length;i++){
      var c=conflicts[i];var fname=c.file||c.path||'';
      var isAuto=autoFiles.indexOf(fname)>=0;
      if(isAuto){
        html+='<li class="disabled"><code>'+escapeHtml(fname)+'</code> <span>auto-merge 드라이버 적용 예정</span></li>';
      }else{
        html+='<li><code>'+escapeHtml(fname)+'</code>';
        if(c.hunks&&hunkCount<5){
          var hunks=c.hunks.slice(0,5-hunkCount);
          for(var j=0;j<hunks.length;j++){
            html+='<pre class="merge-hunk-preview">'+escapeHtml(hunks[j])+'</pre>';
            hunkCount++;
          }
        }
        html+='</li>';
      }
    }
    html+='</ul>';
  }else{
    html+='<p>스캔 데이터 없음 — <code>scripts/merge-preview-scanner.py</code> 를 실행하세요.</p>';
  }
  return html;
}
function openMergePanel(wpId){
  var sp='all';try{var m=location.search.match(/[?&]subproject=([^&]+)/);if(m)sp=m[1];}catch(e){}
  var panel=document.getElementById('task-panel');
  var title=document.getElementById('task-panel-title');
  var body=document.getElementById('task-panel-body');
  var overlay=document.getElementById('task-panel-overlay');
  function _showPanel(contentHtml){
    if(body)body.innerHTML=contentHtml;
    if(panel){panel.dataset.panelMode='merge';panel.classList.add('open');}
    if(overlay)overlay.removeAttribute('hidden');
  }
  fetch('/api/merge-status?wp='+encodeURIComponent(wpId)+'&subproject='+encodeURIComponent(sp))
    .then(function(r){return r.json();})
    .then(function(ms){
      if(title)title.textContent=wpId+' — 머지 프리뷰';
      _showPanel(renderMergePreview(ms));
    })
    .catch(function(err){
      _showPanel('<p>머지 상태 로드 실패: '+escapeHtml(String(err))+'</p>');
    });
}
document.addEventListener('click',function(e){
  var badge=e.target.closest?e.target.closest('.merge-badge'):null;
  if(!badge&&e.target.classList&&e.target.classList.contains('merge-badge'))badge=e.target;
  if(badge){openMergePanel(badge.getAttribute('data-wp')||'');return;}
  var btn=e.target.closest?e.target.closest('.expand-btn'):null;
  if(!btn&&e.target.classList&&e.target.classList.contains('expand-btn'))btn=e.target;
  if(btn){openTaskPanel(btn.getAttribute('data-task-id')||'');return;}
  if(e.target.id==='task-panel-close'){closeTaskPanel();return;}
  if(e.target.id==='task-panel-overlay'){closeTaskPanel();return;}
});
document.addEventListener('keydown',function(e){
  if(e.key==='Escape'){var p=document.getElementById('task-panel');if(p&&p.classList.contains('open'))closeTaskPanel();}
});
(function initSlidePanelResize(){
  var panel=document.getElementById('task-panel');
  if(!panel)return;
  var handle=panel.querySelector('.slide-panel-resize-handle');
  if(!handle)return;
  try{var saved=localStorage.getItem('task-panel-width');if(saved)panel.style.setProperty('--panel-w',saved);}catch(e){}
  var dragging=false,startX=0,startW=0;
  handle.addEventListener('pointerdown',function(e){
    dragging=true;startX=e.clientX;startW=panel.getBoundingClientRect().width;
    handle.classList.add('dragging');panel.classList.add('resizing');
    try{handle.setPointerCapture(e.pointerId);}catch(_){}
    e.preventDefault();
  });
  handle.addEventListener('pointermove',function(e){
    if(!dragging)return;
    var delta=startX-e.clientX;
    var newW=Math.max(320,Math.min(window.innerWidth*0.98,startW+delta));
    panel.style.setProperty('--panel-w',newW+'px');
  });
  function endDrag(e){
    if(!dragging)return;
    dragging=false;handle.classList.remove('dragging');panel.classList.remove('resizing');
    try{handle.releasePointerCapture(e.pointerId);}catch(_){}
    try{var w=panel.style.getPropertyValue('--panel-w');if(w)localStorage.setItem('task-panel-width',w.trim());}catch(_){}
  }
  handle.addEventListener('pointerup',endDrag);
  handle.addEventListener('pointercancel',endDrag);
  handle.addEventListener('dblclick',function(){
    panel.style.removeProperty('--panel-w');
    try{localStorage.removeItem('task-panel-width');}catch(_){}
  });
})();
