(function(){
  'use strict';
  /* shared state — dashboard poll + drawer poll are fully independent */
  var state={
    autoRefresh:true,activeFilter:'all',mainPollId:null,mainAbort:null,
    drawerPaneId:null,drawerPollId:null,clockId:null,
    /* monitor-perf: visibility-aware polling + ETag 캐시 */
    visible:(document.visibilityState!=='hidden'),mainEtag:''
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
  /* monitor-perf (2026-04-24): visible 상태 초기화 + data-anim 토글로 무한 CSS 애니메이션 일괄 정지 */
  state.visible=(document.visibilityState!=='hidden');
  try{document.documentElement.setAttribute('data-anim',state.visible?'on':'off');}catch(_){}
  function onMonitorVisibilityChange(){
    state.visible=(document.visibilityState!=='hidden');
    try{document.documentElement.setAttribute('data-anim',state.visible?'on':'off');}catch(_){}
    if(!state.visible){stopMainPoll();}
    else if(state.autoRefresh){startMainPoll();}
  }
  document.addEventListener('visibilitychange',onMonitorVisibilityChange);
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
    /* monitor-perf (2026-04-24): If-None-Match로 ETag 보낸 뒤 304면 전체 스킵.
       서버 SSR HTML이 변하지 않았을 때 76KB 재전송·DOMParser·patchSection 모두 0. */
    var headers={'If-None-Match':state.mainEtag||''};
    fetch(window.location.search?'/'+window.location.search:'/',{cache:'no-store',signal:signal,headers:headers})
      .then(function(r){
        if(r.status===304)return null;
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
    fetch('/api/pane/'+encodeURIComponent(id),{cache:'no-store'})
      .then(function(r){return r.ok?r.json():null;})
      .then(function(j){if(j)updateDrawerBody(j);})
      .catch(function(){/* silent: retry on next tick */});
  }
  function updateDrawerBody(j){
    var pre=document.querySelector('[data-drawer-pre]');
    if(!pre)return;
    /* Preserve body scroll: some browsers reflow page scroll when a focused
       element's scrollable content changes. Snapshot + restore is cheap. */
    var prevBodyY=window.scrollY||0;
    pre.textContent=(j.lines||[]).join('\n');
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
        /* wp-cards와 live-activity 섹션만 .trow를 포함 — 다른 섹션 patch 후에는 재필터링 불필요. */
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

/* TSK-04-02 FR-01: Task info popover — setupInfoPopover IIFE (click trigger, above-row placement) */
/* TSK-02-05: renderPhaseModels 확장 유지 */
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

function renderInfoPopoverHtml(data){
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
  var pmDl=renderPhaseModels(data.phase_models,data.escalated,data.retry_count);
  var frag=document.createDocumentFragment();
  frag.appendChild(dl);
  if(pmDl){frag.appendChild(pmDl);}
  return frag;
}

function positionPopover(btn,pop){
  /* Position above row by default; flip below on insufficient top space. Uses scrollY/scrollX. */
  var sy=window.scrollY,sx=window.scrollX;
  var row=btn.closest?btn.closest('.trow'):null;
  var anchor=row||btn;
  var r=anchor.getBoundingClientRect();
  var prevHidden=pop.hidden;
  pop.hidden=false;
  pop.style.visibility='hidden';
  var ph=pop.offsetHeight,pw=pop.offsetWidth;
  pop.style.visibility='';
  if(prevHidden){pop.hidden=true;}
  var margin=8;
  var placement=(r.top>=ph+margin)?'above':'below';
  var top=(placement==='above')?(r.top+sy-ph-margin):(r.bottom+sy+margin);
  var left=r.left+sx;
  if(left+pw>sx+window.innerWidth-8){left=sx+window.innerWidth-pw-8;}
  if(left<sx+8){left=sx+8;}
  pop.style.top=top+'px';
  pop.style.left=left+'px';
  pop.setAttribute('data-placement',placement);
}

(function setupInfoPopover(){
  var pop=document.getElementById('trow-info-popover');
  if(!pop)return;
  var openBtn=null;

  function close(){
    if(openBtn){
      try{openBtn.setAttribute('aria-expanded','false');}catch(err){}
    }
    pop.hidden=true;
    openBtn=null;
  }

  function openFor(btn){
    var row=btn.closest?btn.closest('.trow[data-state-summary]'):null;
    if(!row){return;}
    var raw=row.getAttribute('data-state-summary');
    if(!raw){return;}
    var data;
    try{data=JSON.parse(raw);}catch(err){
      if(window.console&&console.warn){console.warn('trow-info-popover: JSON parse failed',err);}
      return;
    }
    pop.innerHTML='';
    pop.appendChild(renderInfoPopoverHtml(data));
    openBtn=btn;
    btn.setAttribute('aria-expanded','true');
    positionPopover(btn,pop);
    pop.hidden=false;
  }

  document.addEventListener('click',function(e){
    var btn=e.target&&e.target.closest?e.target.closest('.info-btn'):null;
    if(btn){
      e.stopPropagation();
      if(openBtn===btn){close();return;}
      if(openBtn){close();}
      openFor(btn);
      return;
    }
    /* Outside click — close if open and click not inside popover */
    if(openBtn){
      var inside=e.target&&e.target.closest?e.target.closest('#trow-info-popover'):null;
      if(!inside){close();}
    }
  },false);

  document.addEventListener('keydown',function(e){
    if(e.key==='Escape'||e.keyCode===27){
      if(openBtn){
        var btn=openBtn;
        close();
        if(btn&&btn.focus){try{btn.focus();}catch(err){}}
      }
    }
  },false);

  window.addEventListener('scroll',function(){if(openBtn){close();}},true);
  window.addEventListener('resize',function(){if(openBtn){close();}},false);
})();