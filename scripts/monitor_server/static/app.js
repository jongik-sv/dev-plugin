(function(){
  'use strict';
  /* shared state — dashboard poll + drawer poll are fully independent */
  var state={
    autoRefresh:true,activeFilter:'all',mainPollId:null,mainAbort:null,
    drawerPaneId:null,drawerPollId:null,clockId:null,
    /* monitor-perf: visibility-aware polling */
    visible:(document.visibilityState!=='hidden'),
    mainEtag:'',drawerEtagByPane:{}
  };
  /* ---- clock (v3) ---- */
  function startClock(){
    var clock=document.getElementById('clock');
    if(!clock)return;
    state.clockId=setInterval(function(){
      var now=new Date();
      clock.textContent=now.toISOString().slice(0,19).replace('T',' ')+'Z';
    },1000);
  }
  /* ---- fold persistence (TSK-00-01 generic + TSK-05-01/TSK-01-02 data-wp 호환) ---- */
  var FOLD_KEY_PREFIX='dev-monitor:fold:';
  function readFold(key, defaultOpen){
    try{
      var v=localStorage.getItem(FOLD_KEY_PREFIX+key);
      if(v==='open')return true;
      if(v==='closed')return false;
      return defaultOpen===undefined?false:defaultOpen;
    }catch(e){return defaultOpen===undefined?false:defaultOpen;}
  }
  function writeFold(key, open){
    try{localStorage.setItem(FOLD_KEY_PREFIX+key,open?'open':'closed');}catch(e){}
  }
  function _foldKeyOf(el){
    /* data-fold-key 우선, 하위 호환으로 data-wp도 지원 */
    return el.getAttribute('data-fold-key')||el.getAttribute('data-wp');
  }
  function applyFoldStates(container){
    container.querySelectorAll('[data-fold-key],[data-wp]').forEach(function(el){
      var key=_foldKeyOf(el);
      if(!key)return;
      var defaultOpen=el.hasAttribute('data-fold-default-open');
      var isOpen=readFold(key, defaultOpen);
      if(isOpen){el.setAttribute('open','');}
      else{el.removeAttribute('open');}
    });
  }
  function bindFoldListeners(container){
    container.querySelectorAll('[data-fold-key],[data-wp]').forEach(function(el){
      if(el.__foldBound)return;
      el.__foldBound=true;
      el.addEventListener('toggle',function(){
        var key=_foldKeyOf(el);
        if(key)writeFold(key, el.open);
      });
    });
  }
  /* ---- body[data-filter] CSS-driven filter (v3) ---- */
  function applyFilter(){
    var f=state.activeFilter;
    document.body.setAttribute('data-filter',f);
    /* legacy: also patch chip aria-pressed */
    document.querySelectorAll('.chip[data-filter]').forEach(function(c){
      c.setAttribute('aria-pressed',c.dataset.filter===f?'true':'false');
    });
  }
  /* ---- filter chips (TSK-02-02) — event delegation survives DOM replacement ---- */
  document.addEventListener('click',function(e){
    var chip=e.target.closest?e.target.closest('.chip'):null;
    if(!chip)return;
    state.activeFilter=chip.dataset.filter||'all';
    applyFilter();
  });
  /* ---- auto-refresh toggle (TSK-02-02) ---- */
  document.addEventListener('click',function(e){
    var tog=e.target.closest?e.target.closest('.refresh-toggle'):null;
    if(!tog)return;
    state.autoRefresh=!state.autoRefresh;
    tog.setAttribute('aria-pressed',String(state.autoRefresh));
    tog.textContent=state.autoRefresh?'◐ auto':'○ paused';
    if(!state.autoRefresh){stopMainPoll();}else{startMainPoll();}
  });
  /* ---- dashboard polling (TSK-02-01, monitor-perf: visibility-aware) ---- */
  function stopMainPoll(){
    if(state.mainPollId!==null){clearInterval(state.mainPollId);state.mainPollId=null;}
    if(state.mainAbort){try{state.mainAbort.abort();}catch(e){} state.mainAbort=null;}
  }
  function startMainPoll(){
    stopMainPoll();
    /* monitor-perf: hidden 탭에서는 폴링 시작 안 함 */
    if(!state.visible)return;
    tick();
    state.mainPollId=setInterval(tick,5000);
  }
  function tick(){
    if(!state.autoRefresh)return;
    /* monitor-perf: visibilityState hidden이면 폴링 스킵 */
    if(!state.visible)return;
    if(state.mainAbort){try{state.mainAbort.abort();}catch(e){}}
    state.mainAbort=new AbortController();
    fetchAndPatch(state.mainAbort.signal);
  }
  function fetchAndPatch(signal){
    /* monitor-perf: If-None-Match 헤더로 ETag 캐싱 — 304면 DOM 교체 스킵 */
    var headers={'If-None-Match':state.mainEtag||''};
    fetch(window.location.search?'/'+window.location.search:'/',{cache:'no-store',signal:signal,headers:headers})
      .then(function(r){
        /* 304: 서버 상태 미변경 — DOM 교체 불필요 */
        if(r.status===304)return null;
        /* 200: ETag 갱신 후 본문 파싱 */
        var etag=r.headers.get('ETag');
        if(etag)state.mainEtag=etag;
        return r.ok?r.text():null;
      })
      .then(function(text){
        if(!text)return;
        var parser=new DOMParser();
        var newDoc=parser.parseFromString(text,'text/html');
        var newSections=newDoc.querySelectorAll('[data-section]');
        newSections.forEach(function(newEl){
          var name=newEl.getAttribute('data-section');
          patchSection(name,newEl.innerHTML);
        });
        /* TSK-02-02: DOM 교체 후 필터 재적용 */
        applyFilter();
      })
      .catch(function(){/* silent: retry on next tick */});
  }
  /* monitor-perf: visibility 변경 핸들러 */
  function onVisibilityChange(){
    state.visible=(document.visibilityState!=='hidden');
    /* monitor-perf (2026-04-24): 무한 CSS 애니메이션을 visibility 전환 시 일괄 on/off.
       hidden 탭은 브라우저가 rAF만 throttle할 뿐 CSS 애니메이션 compositor 작업은 계속 —
       data-anim="off"로 명시 정지해 GPU/compositor 완전 idle. */
    try{document.documentElement.setAttribute('data-anim',state.visible?'on':'off');}catch(_){}
    if(!state.visible){
      /* 탭 hidden → 폴링 즉시 정지 */
      stopMainPoll();
      stopDrawerPoll();
    }else if(state.autoRefresh){
      /* 탭 visible 복귀 → startMainPoll이 내부적으로 tick() 즉시 호출 + interval 설정 */
      startMainPoll();
    }
  }
  document.addEventListener('visibilitychange',onVisibilityChange);
  /* 초기 로드 직후에도 visibility 상태를 즉시 반영 */
  try{document.documentElement.setAttribute('data-anim',(document.visibilityState!=='hidden')?'on':'off');}catch(_){}
  function patchSection(name,newHtml){
    var current=document.querySelector('[data-section="'+name+'"]');
    if(!current)return;
    /* dep-graph is managed autonomously by graph-client.js; skip DOM replacement
       to prevent cytoscape canvas destruction on every 5-second dashboard poll. */
    if(name==='dep-graph')return;
    /* TSK-05-01: filter-bar controls must survive auto-refresh DOM replacement.
       The filter-bar section is static SSR content — inputs hold client state.
       Replacing its innerHTML would lose user-typed query/select values. */
    if(name==='filter-bar')return;
    if(name==='hdr'){
      /* Preserve chip aria-pressed states and refresh-toggle visual state
         across DOM replacement so client-side filter/toggle survive server push. */
      var chipStates={};
      current.querySelectorAll('.chip[data-filter]').forEach(function(c){
        chipStates[c.dataset.filter]=c.getAttribute('aria-pressed');
      });
      var togEl=current.querySelector('.refresh-toggle');
      var togPressed=togEl?togEl.getAttribute('aria-pressed'):null;
      var togText=togEl?togEl.textContent:null;
      if(current.innerHTML!==newHtml){current.innerHTML=newHtml;}
      /* Restore chip states */
      current.querySelectorAll('.chip[data-filter]').forEach(function(c){
        var saved=chipStates[c.dataset.filter];
        if(saved!==null&&saved!==undefined){c.setAttribute('aria-pressed',saved);}
      });
      /* Restore refresh-toggle state */
      var tog2=current.querySelector('.refresh-toggle');
      if(tog2&&togPressed!==null){
        tog2.setAttribute('aria-pressed',togPressed);
        if(togText){tog2.textContent=togText;}
      }
      return;
    }
    /* TSK-05-01 / TSK-01-02: fold 상태 복원이 필요한 섹션 집합.
       새 섹션 추가 시 이 집합에만 추가하면 된다. */
    var _FOLD_SECTIONS={'wp-cards':1,'live-activity':1};
    if(_FOLD_SECTIONS[name]){
      if(current.innerHTML!==newHtml){current.innerHTML=newHtml;}
      applyFoldStates(current);
      bindFoldListeners(current);
      return;
    }
    if(current.innerHTML!==newHtml){current.innerHTML=newHtml;}
  }
  /* ---- drawer control (v3: aria-hidden="false" + focus trap) ---- */
  function _setDrawerOpen(open){
    var backdrop=document.querySelector('[data-drawer-backdrop]');
    var panel=document.querySelector('[data-drawer]');
    if(backdrop){backdrop.setAttribute('aria-hidden',open?'false':'true');}
    if(panel){
      panel.setAttribute('aria-hidden',open?'false':'true');
      /* focus-trap: set tabindex=-1 on focusables when closed */
      panel.querySelectorAll('[tabindex]').forEach(function(el){
        el.setAttribute('tabindex',open?'0':'-1');
      });
      if(open){
        var first=panel.querySelector('[tabindex="0"]');
        /* preventScroll: drawer is position:fixed; without this Chromium will
           scroll the page body to "reveal" the focused element, landing the
           user at the very bottom of the dashboard with only one line visible. */
        if(first){try{first.focus({preventScroll:true});}catch(_){first.focus();}}
      }
    }
  }
  function openDrawer(paneId){
    state.drawerPaneId=paneId;
    var titleEl=document.querySelector('[data-drawer-title]');
    if(titleEl){titleEl.textContent='Pane: '+paneId;}
    _setDrawerOpen(true);
    startDrawerPoll();
  }
  function closeDrawer(){
    state.drawerPaneId=null;
    stopDrawerPoll();
    _setDrawerOpen(false);
  }
  function stopDrawerPoll(){
    if(state.drawerPollId!==null){clearInterval(state.drawerPollId);state.drawerPollId=null;}
  }
  function startDrawerPoll(){
    stopDrawerPoll();
    tickDrawer();
    state.drawerPollId=setInterval(tickDrawer,2000);
  }
  function tickDrawer(){
    var id=state.drawerPaneId;
    if(!id)return;
    /* monitor-perf: visibilityState hidden이면 drawer 폴링 스킵 */
    if(!state.visible)return;
    /* monitor-perf: per-pane ETag 캐싱 */
    if(!state.drawerEtagByPane){state.drawerEtagByPane={};}
    var drawerEtag=state.drawerEtagByPane[id]||'';
    fetch('/api/pane/'+encodeURIComponent(id),{cache:'no-store',headers:{'If-None-Match':drawerEtag}})
      .then(function(r){
        if(r.status===304)return null;
        var etag=r.headers.get('ETag');
        if(etag)state.drawerEtagByPane[id]=etag;
        return r.ok?r.json():null;
      })
      .then(function(j){if(j)updateDrawerBody(j);})
      .catch(function(){/* silent: retry on next tick */});
  }
  function updateDrawerBody(j){
    var pre=document.querySelector('[data-drawer-pre]');
    if(!pre)return;
    /* Preserve body scroll: some browsers reflow page scroll when a focused
       element's scrollable content changes. Snapshot + restore is cheap. */
    var prevBodyY=window.scrollY||0;
    pre.textContent=(j.lines||[]).join('\\n');
    /* rAF ensures layout has computed scrollHeight/clientHeight for the new
       text before we seek. Clamp explicitly so we land at "bottom minus one
       viewport" — the last clientHeight worth of lines stays visible. */
    requestAnimationFrame(function(){
      var sh=pre.scrollHeight||0;
      var ch=pre.clientHeight||0;
      pre.scrollTop=Math.max(0,sh-ch);
      if(window.scrollY!==prevBodyY){window.scrollTo(0,prevBodyY);}
    });
    var meta=document.querySelector('[data-drawer-meta]');
    if(meta){meta.textContent=j.captured_at||'';}
  }
  /* ---- event delegation (click + keydown) ---- */
  function _hasAttr(el,attr){return el&&el.hasAttribute&&el.hasAttribute(attr);}
  document.addEventListener('click',function(e){
    var t=e.target;
    var exp=t.closest?t.closest('[data-pane-expand]'):(_hasAttr(t,'data-pane-expand')?t:null);
    if(exp){openDrawer(exp.getAttribute('data-pane-expand'));return;}
    if(_hasAttr(t,'data-drawer-close')||_hasAttr(t,'data-drawer-backdrop')){closeDrawer();}
  });
  document.addEventListener('keydown',function(e){
    if(e.key==='Escape'&&state.drawerPaneId){closeDrawer();}
  });
  /* ---- init ---- */
  function init(){
    /* v3: start clock */
    startClock();
    /* v3: apply initial body[data-filter] */
    applyFilter();
    /* TSK-02-02: refresh-toggle 버튼 초기 상태 동기화 */
    var tog=document.querySelector('.refresh-toggle');
    if(tog){
      state.autoRefresh=(tog.getAttribute('aria-pressed')!=='false');
      tog.textContent=state.autoRefresh?'◐ auto':'○ paused';
    }
    /* TSK-05-01: fold 상태 복원 (startMainPoll 직전) */
    applyFoldStates(document);
    bindFoldListeners(document);
    startMainPoll();
  }
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',init);
  }else{
    init();
  }
})();

/* TSK-05-01: Filter bar — currentFilters / matchesRow / applyFilters / syncUrl / loadFiltersFromUrl */
/* patchSection monkey-patch for filter survival across 5-second auto-refresh */
(function setupFilterBar(){
  'use strict';
  /* ---- 5 core filter functions ---- */
  function currentFilters(){
    var q      =(document.getElementById('fb-q')||{value:''}).value.trim().toLowerCase();
    var status =(document.getElementById('fb-status')||{value:''}).value;
    var domain =(document.getElementById('fb-domain')||{value:''}).value;
    var model  =(document.getElementById('fb-model')||{value:''}).value;
    return {q:q,status:status,domain:domain,model:model};
  }
  function matchesRow(trow,f){
    /* q: substring match on task-id OR .ttitle text, case-insensitive */
    if(f.q){
      var taskId=(trow.dataset.taskId||'').toLowerCase();
      var titleEl=trow.querySelector('.ttitle');
      var titleText=titleEl?titleEl.textContent.toLowerCase():'';
      if(taskId.indexOf(f.q)===-1&&titleText.indexOf(f.q)===-1)return false;
    }
    /* status: exact match on data-status OR data-phase */
    if(f.status){
      var ds=trow.dataset.status||'';
      var dp=trow.dataset.phase||'';
      if(ds!==f.status&&dp!==f.status)return false;
    }
    /* domain: exact match on data-domain */
    if(f.domain){
      if((trow.dataset.domain||'')!==f.domain)return false;
    }
    /* model: exact match on .model-chip data-model */
    if(f.model){
      var chip=trow.querySelector('.model-chip');
      if((chip?chip.dataset.model||'':'')!==f.model)return false;
    }
    return true;
  }
  function applyFilters(){
    var f=currentFilters();
    /* .trow[data-task-id] — task rows carry data-task-id on the outer div. */
    document.querySelectorAll('.trow[data-task-id]').forEach(function(trow){
      trow.style.display=matchesRow(trow,f)?'':'none';
    });
    /* Dep-Graph filter — optional, guard for missing depGraph */
    if(window.depGraph&&typeof window.depGraph.applyFilter==='function'){
      window.depGraph.applyFilter(function(nodeId){
        /* nodeId matches task id — show node if no q filter or task matches */
        if(!f.q&&!f.domain&&!f.model&&!f.status)return true;
        var trow=document.querySelector('.trow[data-task-id="'+nodeId+'"]');
        if(!trow)return true;/* unknown node — keep visible */
        return matchesRow(trow,f);
      });
    }
  }
  /* Apply filters and sync URL — shared by all event handlers */
  function applyAndSync(){applyFilters();syncUrl(currentFilters());}
  function syncUrl(f){
    var url=new URL(window.location.href);
    var sp=url.searchParams;
    /* Set or delete each filter param; preserve subproject/lang/other params */
    if(f.q){sp.set('q',f.q);}else{sp.delete('q');}
    if(f.status){sp.set('status',f.status);}else{sp.delete('status');}
    if(f.domain){sp.set('domain',f.domain);}else{sp.delete('domain');}
    if(f.model){sp.set('model',f.model);}else{sp.delete('model');}
    history.replaceState(null,'',url.toString());
  }
  /* Get the 4 filter control DOM elements */
  function _fbEls(){
    return {
      q:document.getElementById('fb-q'),
      st:document.getElementById('fb-status'),
      dm:document.getElementById('fb-domain'),
      md:document.getElementById('fb-model')
    };
  }
  function loadFiltersFromUrl(){
    var sp=new URLSearchParams(window.location.search);
    var els=_fbEls();
    if(els.q&&sp.has('q')){els.q.value=sp.get('q');}
    if(els.st&&sp.has('status')){els.st.value=sp.get('status');}
    if(els.dm&&sp.has('domain')){els.dm.value=sp.get('domain');}
    if(els.md&&sp.has('model')){els.md.value=sp.get('model');}
  }
  /* ---- event bindings (document-level delegation — survives DOM replacement) ---- */
  document.addEventListener('input',function(e){
    if(e.target&&e.target.id==='fb-q'){applyAndSync();}
  });
  document.addEventListener('change',function(e){
    var id=e.target&&e.target.id;
    if(id==='fb-status'||id==='fb-domain'||id==='fb-model'){applyAndSync();}
  });
  document.addEventListener('click',function(e){
    if(e.target&&e.target.id==='fb-reset'){
      var els=_fbEls();
      if(els.q)els.q.value='';
      if(els.st)els.st.value='';
      if(els.dm)els.dm.value='';
      if(els.md)els.md.value='';
      applyAndSync();
    }
  });
  /* ---- patchSection monkey-patch — filter survival across auto-refresh ---- */
  /* Extract helper: registers monkey-patch once (sentinel guard). */
  function _registerPatchWrap(){
    if(window.patchSection&&!window.patchSection.__filterWrapped){
      var _orig=window.patchSection;
      window.patchSection=function(name,html){
        _orig.call(this,name,html);
        /* wp-cards and live-activity may contain .trow[data-task-id] rows.
           Live-activity rows have no data-task-id so applyFilters() is harmless. */
        if(name==='wp-cards'||name==='live-activity'){applyFilters();}
      };
      window.patchSection.__filterWrapped=true;
    }
  }
  _registerPatchWrap();
  /* ---- initial load sequence (DOMContentLoaded) ---- */
  function initFilterBar(){
    loadFiltersFromUrl();
    applyFilters();
    /* Re-register monkey-patch here if patchSection was not yet available at IIFE run time. */
    _registerPatchWrap();
  }
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',initFilterBar);
  }else{
    initFilterBar();
  }
  /* Expose for external access (e.g. dev-test verification) */
  window.filterBar={currentFilters:currentFilters,matchesRow:matchesRow,applyFilters:applyFilters,syncUrl:syncUrl,loadFiltersFromUrl:loadFiltersFromUrl};
})();

/* TSK-02-03: Task hover tooltip — setupTaskTooltip IIFE */
/* TSK-02-05: renderPhaseModels 확장 추가 */
(function setupTaskTooltip(){
  var tip=document.getElementById('trow-tooltip');
  if(!tip)return;
  var _timer=null;
  var _current=null;

  /* TSK-02-05: phase model 4행 <dl> 렌더러 */
  function renderPhaseModels(pm,escalated,retry_count){
    if(!pm)return null;
    var dl=document.createElement('dl');
    dl.className='phase-models';
    function pmrow(label,value){
      var dt=document.createElement('dt');dt.textContent=label;
      var dd=document.createElement('dd');dd.textContent=value||'—';
      dl.appendChild(dt);dl.appendChild(dd);
    }
    pmrow('Design',pm.design);
    pmrow('Build',pm.build);
    var testLine=escalated
      ?'haiku → '+pm.test+' (retry #'+retry_count+') ⚡'
      :pm.test;
    pmrow('Test',testLine);
    pmrow('Refactor',pm.refactor);
    return dl;
  }

  function renderTooltipHtml(data){
    var dl=document.createElement('dl');
    function row(label,value){
      var dt=document.createElement('dt');dt.textContent=label;
      var dd=document.createElement('dd');dd.textContent=(value===null||value===undefined)?'—':String(value);
      dl.appendChild(dt);dl.appendChild(dd);
    }
    row('status',data.status);
    row('last event',data.last_event);
    row('at',data.last_event_at);
    row('elapsed',data.elapsed!=null?data.elapsed+'s':null);
    if(data.phase_tail&&data.phase_tail.length){
      var dt2=document.createElement('dt');dt2.textContent='recent phases';
      dl.appendChild(dt2);
      data.phase_tail.forEach(function(p){
        var dd2=document.createElement('dd');
        dd2.textContent=(p.event||'')+(p.from?' '+p.from+' → ':'')+( p.to||'');
        dl.appendChild(dd2);
      });
    }
    /* TSK-02-05: phase models section */
    var pmDl=renderPhaseModels(data.phase_models,data.escalated,data.retry_count);
    var frag=document.createDocumentFragment();
    frag.appendChild(dl);
    if(pmDl){frag.appendChild(pmDl);}
    return frag;
  }

  function show(el,data){
    tip.innerHTML='';
    tip.appendChild(renderTooltipHtml(data));
    var r=el.getBoundingClientRect();
    var left=r.right+8;
    if(left+420>window.innerWidth){left=r.left-428;}
    tip.style.top=(r.top+window.scrollY)+'px';
    tip.style.left=left+'px';
    tip.hidden=false;
  }

  function hide(){
    clearTimeout(_timer);
    _timer=null;
    _current=null;
    tip.hidden=true;
  }

  document.addEventListener('mouseenter',function(e){
    var el=e.target&&e.target.closest?e.target.closest('.trow[data-state-summary]'):null;
    if(!el){return;}
    if(el===_current){return;}
    clearTimeout(_timer);
    _current=el;
    _timer=setTimeout(function(){
      var raw=el.getAttribute('data-state-summary');
      if(!raw){return;}
      try{var data=JSON.parse(raw);}catch(err){return;}
      show(el,data);
    },300);
  },true);

  document.addEventListener('mouseleave',function(e){
    var el=e.target&&e.target.closest?e.target.closest('.trow[data-state-summary]'):null;
    if(!el){return;}
    hide();
  },true);

  window.addEventListener('scroll',function(){hide();},true);
})();

(function(){
  var pre = document.querySelector('pre.pane-capture');
  var ftr = document.querySelector('.footer');
  if (!pre) return;
  var paneId = pre.getAttribute('data-pane');
  function tick(){
    fetch('/api/pane/' + encodeURIComponent(paneId), {cache:'no-store'})
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(j){
        if (!j) return;
        pre.textContent = (j.lines || []).join('\\n');
        if (ftr) ftr.textContent = 'captured at ' + j.captured_at;
      })
      .catch(function(){ /* silent: loop continues on next tick */ });
  }
  setInterval(tick, 2000);
})();

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
      if(b)b.innerHTML=renderWbsSection(data.wbs_section_md||'',data.source||'')+renderStateJson(data.state||{})+renderArtifacts(data.artifacts||[])+renderLogs(data.logs||[]);
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
