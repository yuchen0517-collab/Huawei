(function(){
  'use strict';
  if(window.NegotiationEventCard)return;
  var pending=[],active=false,lastFocus=null,overlay=null;
  var KIND={technology:'技术突变',scandal:'舆论风暴',conflict:'地缘危机',diplomacy:'外交动向',economy:'经济冲击',disaster:'突发灾难',interlude:'会场花絮'};
  var INDEX={interest:'利益',image:'形象',trust:'信任'};
  function esc(value){return String(value==null?'':value).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function icon(){return'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13 2L4 14h7l-1 8 10-13h-7z"/></svg>';}
  function art(kind){
    var known=['technology','scandal','conflict','diplomacy','economy'];
    if(kind==='interlude'||kind==='disaster'||known.indexOf(kind)<0)kind='diplomacy';
    return '<div class="ec-art-img ec-art-'+kind+'"></div>';
  }
  function deltaChip(number,label){
    return'<span class="ec-delta '+(number>0?'up':'down')+'">'+(number>0?'+':'')+esc(number)+' <small>'+esc(label)+'</small></span>';
  }
  function effectSide(label,values){
    var deltas=[];
    Object.keys(INDEX).forEach(function(key){
      var raw=values&&values[key+'_delta'];
      var number=Number(raw);
      if(!Number.isFinite(number)||number===0)return;
      deltas.push(deltaChip(number,INDEX[key]));
    });
    if(!deltas.length)return'';
    return'<div class="ec-effect-side"><span class="ec-side-name">'+esc(label)+'</span><div class="ec-deltas">'+deltas.join('')+'</div></div>';
  }
  /* 观战九方场：后端已按「受影响方」解析好，事件卡只展示这些代表团 */
  function impactRow(imp){
    if(!imp)return'';
    var deltas=[],values=imp.deltas||{};
    Object.keys(INDEX).forEach(function(key){
      var number=Number(values[key]);
      if(!Number.isFinite(number)||number===0)return;
      deltas.push(deltaChip(number,INDEX[key]));
    });
    if(!deltas.length)return'';
    var count=Number(imp.count)||0;
    var sub=count>1?(count+' 方'):(imp.role||'');
    return'<div class="ec-effect-side"><span class="ec-side-name">'+esc(imp.label||'各方')+(sub?'<small>'+esc(sub)+'</small>':'')+'</span><div class="ec-deltas">'+deltas.join('')+'</div></div>';
  }
  function ensure(){
    if(overlay)return overlay;
    overlay=document.createElement('div');
    overlay.className='ec-overlay';
    overlay.setAttribute('aria-hidden','true');
    document.body.appendChild(overlay);
    overlay.addEventListener('click',function(e){
      if(e.target===overlay)close();
      if(e.target.closest&&e.target.closest('[data-ec-close]'))close();
    });
    return overlay;
  }
  function render(event){
    var kind=KIND[event.kind]?event.kind:'disaster';
    var effects=event.effects||{};
    var hasImpacts=Array.isArray(event.impacts);
    var noEffect=!!event.noEffect;
    var effectHtml=hasImpacts
      ? event.impacts.map(impactRow).join('')
      : effectSide(event.playerLabel||'我方',effects.player)+effectSide(event.agentLabel||'对方',effects.agent);
    if(noEffect)effectHtml='<div class="ec-no-impact"><b>NO INDEX CHANGE</b><span>会场花絮，不改变任何代表团指数</span></div>';
    var serial=String(event.id||'EVENT').toUpperCase();
    ensure().innerHTML='<div class="ec-stage"><article class="ec-card" role="dialog" aria-modal="true" aria-labelledby="ecEventTitle"><header class="ec-top"><span class="ec-suit">'+icon()+'</span><div class="ec-top-text"><div class="ec-eyebrow">NEGOTIATION EVENT</div><div class="ec-top-title">突发事件卡</div></div><span class="ec-serial">'+esc(serial)+'</span><button class="ec-close" type="button" data-ec-close aria-label="关闭事件卡"><svg viewBox="0 0 24 24"><path d="M5 5l14 14M19 5L5 19"/></svg></button></header><div class="ec-art">'+art(kind)+'<span class="ec-art-label">'+esc(KIND[kind])+'</span></div><div class="ec-body"><div class="ec-round">ROUND '+esc(event.round||'—')+' · '+(noEffect?'花絮':'突发')+'</div><h2 class="ec-title" id="ecEventTitle">'+esc(event.title||'突发事件')+'</h2><p class="ec-text">'+esc(event.text||event.description||'会场出现新的变化，各方需要重新评估局势。')+'</p><p class="ec-flavor">'+esc(event.flavor||'会场风向正在改变，接下来的每一次表态都可能付出新的代价。')+'</p>'+((noEffect||effectHtml)?'<section class="ec-effects"><div class="ec-effects-title"><span>局势影响</span><span>INDEX CHANGE</span></div>'+(hasImpacts&&!noEffect?'<div class="ec-effects-note">只结算受影响方，未列入的代表团本轮指数不变</div>':'')+effectHtml+'</section>':'')+'</div><footer class="ec-bottom"><span class="ec-hint">EVENT CARD<br>KEEP THE TURN MOVING</span><button class="ec-continue" type="button" data-ec-close>继续谈判<svg viewBox="0 0 24 24"><path d="M5 12h13M13 6l6 6-6 6"/></svg></button></footer></article></div>';
    overlay.setAttribute('aria-hidden','false');
    overlay.classList.remove('closing');
    requestAnimationFrame(function(){overlay.classList.add('open');var button=overlay.querySelector('.ec-continue');if(button)button.focus();});
  }
  function show(event){
    if(!event)return;
    if(active){pending.push(event);return;}
    active=true;
    lastFocus=document.activeElement;
    try {
      render(event);
    } catch (err) {
      active=false;
      try { if(overlay){overlay.setAttribute('aria-hidden','true');overlay.classList.remove('open');} } catch(e2){}
      if (window.console && console.warn) console.warn('[event-card] render failed', err, event);
      throw err;
    }
  }
  function close(){
    if(!active||!overlay)return;
    overlay.classList.add('closing');
    overlay.classList.remove('open');
    overlay.setAttribute('aria-hidden','true');
    setTimeout(function(){
      overlay.classList.remove('closing');
      active=false;
      if(lastFocus&&lastFocus.focus)lastFocus.focus();
      if(pending.length)show(pending.shift());
    },240);
  }
  document.addEventListener('keydown',function(e){if(e.key==='Escape'&&active)close();});
  window.NegotiationEventCard={show:show,close:close,queue:function(events){(events||[]).forEach(show);},isOpen:function(){return active;}};
})();
