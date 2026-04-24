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
        pre.textContent = (j.lines || []).join('\n');
        if (ftr) ftr.textContent = 'captured at ' + j.captured_at;
      })
      .catch(function(){ /* silent: loop continues on next tick */ });
  }
  setInterval(tick, 2000);
})();