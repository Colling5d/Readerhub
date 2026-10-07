#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给阅读器注入「连续滚动（跨章节）」（幂等）。

用法:
    python3 scripts/add_continuous_scroll.py books/<id>/index.html
    python3 scripts/add_continuous_scroll.py books/*/index.html

原阅读器每次只渲染一个章节，滚到底就停住，无法连续阅读，也不能滑到
下一章。本脚本注入一层「连续滚动」实现：

    - 启动时把整本书所有章节一次性渲染进左右两栏（连续长文）
    - 每个段落同时标记 data-sec（章节 id）与 data-i（章内段号）与
      data-gi（全书唯一段号）
    - goTo(id) 改为「滚动到该章锚点」，不再整段重绘
    - 滚动时实时计算当前可见章节，同步目录高亮 / 顶部 HUD / 记忆位置
    - 笔记、划词句级对齐、全文检索、阅读位置记忆全部适配（保持向后兼容；
      旧笔记（无 gi 字段）会按原文文本自动归属到正确章节）
"""
import sys, os

MARK = 'CONTINUOUS-SCROLL'

CSS = '''
  /* ===== 连续滚动 (CONTINUOUS-SCROLL) ===== */
  .sec-anchor{display:block;height:0;margin:0;padding:0;scroll-margin-top:64px}
  .sec-divider{
    margin:64px 0 8px;border:none;border-top:1px dashed var(--line);opacity:.7;
  }
  /* 每章标题增加一点顶部留白，读起来有分章感 */
  .chapter-title{scroll-margin-top:64px}
'''

JS = r'''
/* ============ 连续滚动（跨章节）(CONTINUOUS-SCROLL) ============ */
(function(){
  if(typeof EN === 'undefined') return;

  var enEl = document.getElementById('article-en');
  var zhEl = document.getElementById('article-zh');
  var scE  = document.getElementById('scroll-en');
  var scZ  = document.getElementById('scroll-zh');
  if(!enEl || !zhEl || !scE || !scZ) return;

  // 章节顺序：优先 tocOrder，其次 EN 顺序
  var ORDER = (typeof tocOrder !== 'undefined' && tocOrder)
    ? tocOrder.filter(function(id){ return EN.some(function(s){ return s.id===id; }); })
    : EN.map(function(s){ return s.id; });
  // 补上不在 ORDER 里的章节
  EN.forEach(function(s){ if(ORDER.indexOf(s.id)<0) ORDER.push(s.id); });

  // 书本脚本启动时已渲染过单章，这里清空后重绘为「整本连续长文」
  enEl.innerHTML = '';
  zhEl.innerHTML = '';

  var ENMAP = {}; EN.forEach(function(s){ ENMAP[s.id]=s; });
  var ZHMMAP = {}; (typeof ZH!=='undefined'?ZH:[]).forEach(function(s){ ZHMMAP[s.id]=s; });

  // 章节标题（短名 + 英文原名）：从已生成的目录按钮文本推断
  function labelsFor(id){
    var btn = document.querySelector('.toc-item[data-sec-id="'+id+'"]');
    var cn = '', en = '';
    if(btn){
      var span = btn.querySelector('span');
      cn = (span ? span.textContent : btn.textContent) || '';
      cn = cn.replace(/\s+/g,' ').trim();
    }
    var s = ENMAP[id];
    en = s ? s.title : id;
    return {cn: cn, en: en};
  }

  // ------- 渲染所有章节（一次） -------
  var gi = 0;
  ORDER.forEach(function(id, si){
    var sec = ENMAP[id]; if(!sec) return;
    var zsec = ZHMMAP[id] || {paras:[]};
    var zmap = {}; zsec.paras.forEach(function(z,k){ zmap[k] = z && z.text ? z.text : ''; });

    [enEl, zhEl].forEach(function(root){
      var anchor = document.createElement('span');
      anchor.className = 'sec-anchor';
      anchor.setAttribute('data-sec-anchor', id);
      root.appendChild(anchor);

      if(si > 0){
        var hr = document.createElement('hr');
        hr.className = 'sec-divider';
        root.appendChild(hr);
      }
      var lb = labelsFor(id);
      var head = document.createElement('div');
      head.innerHTML = '<p class="chapter-title" data-sec="'+id+'">'+ lb.cn +'</p>'
                     + '<p class="chapter-sub" data-sec="'+id+'">'+ esc(lb.en) +'</p>';
      root.appendChild(head);
    });

    sec.paras.forEach(function(p, i){
      var myGi = gi++;
      var enCls = p.type==='title' ? 'p title' : (p.type==='note' ? 'note' : 'p');
      var enHtml = '<p class="'+enCls+'" data-lang="en" data-sec="'+id+'" data-i="'+i+'" data-gi="'+myGi+'">'+(p.text||'')+'</p>';
      enEl.insertAdjacentHTML('beforeend', enHtml);

      var zt = zmap[i];
      var zhHtml;
      if(p.type==='title'){
        zhHtml = '<p class="p title" data-lang="zh" data-sec="'+id+'" data-i="'+i+'" data-gi="'+myGi+'">'+esc(zt||'')+'</p>';
      } else if(p.type==='note'){
        zhHtml = '<p class="note" data-lang="zh" data-sec="'+id+'" data-i="'+i+'" data-gi="'+myGi+'">'+esc(zt||'')+'</p>';
      } else if(zt){
        zhHtml = '<p class="p" data-lang="zh" data-sec="'+id+'" data-i="'+i+'" data-gi="'+myGi+'">'+esc(zt)+'</p>';
      } else {
        var mirror = (id==='notes' || id==='backmatter' || id==='biblio' || id==='index') ? (p.text||'') : '';
        if(mirror){
          zhHtml = '<p class="p" style="color:#3a3a3a" data-lang="zh" data-sec="'+id+'" data-i="'+i+'" data-gi="'+myGi+'">'+esc(mirror)+'</p>';
        } else {
          zhHtml = '<p class="p" style="color:#b6b0a6" data-lang="zh" data-sec="'+id+'" data-i="'+i+'" data-gi="'+myGi+'">（尚未翻译）</p>';
        }
      }
      zhEl.insertAdjacentHTML('beforeend', zhHtml);
    });
  });

  var TOTAL_GI = gi;

  // ------- 滚动定位 / 当前章节 -------
  var giToSec = {};   // gi -> section id
  enEl.querySelectorAll('[data-gi]').forEach(function(el){
    var g = +el.getAttribute('data-gi');
    if(!(g in giToSec)) giToSec[g] = el.getAttribute('data-sec');
  });
  enEl.querySelectorAll('[data-sec-anchor]').forEach(function(el){});
  var secEls = {};    // section id -> anchor element (en column)
  enEl.querySelectorAll('[data-sec-anchor]').forEach(function(a){
    secEls[a.getAttribute('data-sec-anchor')] = a;
  });

  function headerOff(scrollEl){
    var h = scrollEl.querySelector('.col-head');
    if(!h) return 0;
    try{ var cs=getComputedStyle(h).position; if(cs==='sticky'||cs==='fixed') return h.offsetHeight; }catch(e){}
    return 0;
  }
  function anchorTop(scrollEl, contentEl, id){
    var a = contentEl.querySelector('[data-sec-anchor="'+id+'"]');
    if(!a) return null;
    var sRect = scrollEl.getBoundingClientRect();
    var aRect = a.getBoundingClientRect();
    return (aRect.top - sRect.top) + scrollEl.scrollTop - headerOff(scrollEl) - 8;
  }
  function paraTop(scrollEl, contentEl, g){
    var t = contentEl.querySelector('[data-gi="'+g+'"]');
    if(!t) return null;
    var sRect = scrollEl.getBoundingClientRect();
    var tRect = t.getBoundingClientRect();
    return (tRect.top - sRect.top) + scrollEl.scrollTop - headerOff(scrollEl);
  }

  // 当前可见章节（各栏顶部下方第一个段落所属章节），以 EN 栏为准
  function topSection(scrollEl, contentEl){
    var y = scrollEl.scrollTop + headerOff(scrollEl) + 12;
    var cur = null;
    var anchors = contentEl.querySelectorAll('[data-sec-anchor]');
    for(var k=0;k<anchors.length;k++){
      var aTop = (anchors[k].getBoundingClientRect().top - scrollEl.getBoundingClientRect().top) + scrollEl.scrollTop;
      if(aTop <= y + 2) cur = anchors[k].getAttribute('data-sec-anchor');
      else break;
    }
    return cur || (ORDER[0]||null);
  }

  function setCurrent(id){
    var changed = (id && id !== window.__csCurrent);
    window.__csCurrent = id;
    if(typeof current !== 'undefined'){ try{ current = id; }catch(e){} }
    // 目录高亮
    if(window.__markChapterActive) window.__markChapterActive(id);
    if(window.__updateChapterHud) window.__updateChapterHud();
    // 滚动到新章节时，短暂浮现章节药丸提醒
    if(changed && window.__flashChapterHud) window.__flashChapterHud();
  }

  var raf = null;
  function onScroll(){
    if(raf) return;
    raf = requestAnimationFrame(function(){
      raf = null;
      var id = topSection(scE, enEl);
      setCurrent(id);
    });
  }
  scE.addEventListener('scroll', onScroll, {passive:true});

  // ------- 左右两栏滚动同步（按段落锚点对齐）-------
  // 中英文段落一一对应（同 gi），把「来源栏顶部可见的那一段」在目标栏也对齐到
  // 相同相对位置，使两栏始终并排对应。用锁避免回弹循环。
  var syncLock = false;
  var syncPending = {en:false, zh:false};
  function topAnchorGi(scrollEl, contentEl){
    var y = scrollEl.scrollTop + headerOff(scrollEl) + 8;
    var ps = contentEl.querySelectorAll('[data-gi]');
    if(!ps.length) return null;
    var best = null;
    // 二分查找最后一个 offsetTop <= y 的段落
    var lo = 0, hi = ps.length - 1;
    while(lo <= hi){
      var mid = (lo + hi) >> 1;
      if(ps[mid].offsetTop <= y){ best = ps[mid]; lo = mid + 1; }
      else hi = mid - 1;
    }
    if(!best) best = ps[0];
    return best;
  }
  function syncFrom(srcScroll, srcContent, dstScroll, dstContent){
    var srcEl = topAnchorGi(srcScroll, srcContent);
    if(!srcEl) return;
    var g = srcEl.getAttribute('data-gi');
    var dstEl = dstContent.querySelector('[data-gi="'+g+'"]');
    if(!dstEl) return;
    // 源栏内「视口顶端相对该段的偏移」
    var srcOff = (srcScroll.scrollTop + headerOff(srcScroll)) - srcEl.offsetTop;
    // 目标栏中把同一段也放在同样的相对位置
    var dstTop = dstEl.offsetTop + srcOff;
    var maxTop = dstScroll.scrollHeight - dstScroll.clientHeight;
    dstTop = Math.max(0, Math.min(maxTop, dstTop));
    if(Math.abs(dstScroll.scrollTop - dstTop) < 2) return;
    syncLock = true;
    dstScroll.scrollTop = dstTop;
    // 下一帧释放锁（等浏览器应用滚动）
    requestAnimationFrame(function(){ requestAnimationFrame(function(){ syncLock = false; }); });
  }
  // 尾随重同步：快速滚动时每帧跟进，直到对齐
  var syncRafE = null, syncRafZ = null;
  var settleTimer = null;
  function scheduleSync(which){
    if(which==='en'){
      if(syncRafE) return;
      syncRafE = requestAnimationFrame(function(){ syncRafE = null;
        if(syncLock) return;
        syncFrom(scE, enEl, scZ, zhEl);
        bumpSettle('en');
      });
    } else {
      if(syncRafZ) return;
      syncRafZ = requestAnimationFrame(function(){ syncRafZ = null;
        if(syncLock) return;
        syncFrom(scZ, zhEl, scE, enEl);
        bumpSettle('zh');
      });
    }
  }
  // 停止滚动后再补一次同步（保证最终完全对齐）
  window.__csLastSrc = 'en';
  function bumpSettle(which){
    window.__csLastSrc = which;
    clearTimeout(settleTimer);
    settleTimer = setTimeout(function(){
      if(syncLock){ bumpSettle(window.__csLastSrc); return; }
      if(window.__csLastSrc==='zh') syncFrom(scZ, zhEl, scE, enEl);
      else syncFrom(scE, enEl, scZ, zhEl);
    }, 90);
  }
  scE.addEventListener('scroll', function(){
    if(syncLock){ syncPending.en = true; return; }
    scheduleSync('en');
  }, {passive:true});
  scZ.addEventListener('scroll', function(){
    if(syncLock){ syncPending.zh = true; return; }
    scheduleSync('zh');
  }, {passive:true});

  // goTo -> 滚动到章节
  var __prevGoTo = window.goTo;
  window.goTo = function(id){
    if(!ENMAP[id]) id = ORDER[0];
    // 同步两栏滚到该章顶部
    var tE = anchorTop(scE, enEl, id);
    var tZ = anchorTop(scZ, zhEl, id);
    if(tE !== null) scE.scrollTop = Math.max(0, tE);
    if(tZ !== null) scZ.scrollTop = Math.max(0, tZ);
    setCurrent(id);
    return undefined;
  };
  // 覆盖全局 goTo（书本脚本用全局名调用）
  try{ goTo = window.goTo; }catch(e){}

  // 覆盖 paraScrollTop（原函数按 data-i 查找，现在需按 data-gi）
  try{
    paraScrollTop = function(pair, g){
      var isEn = pair.scroll === scE || pair.content === enEl;
      return paraTop(pair.scroll, pair.content, g);
    };
  }catch(e){}

  // 覆盖 openResult（检索结果跳转）：按 章节 + 章内段号定位
  window.openResult = function(sectionId, paraIdx){
    try{ closeSearch && closeSearch(true); }catch(e){}
    // 找到该章该段的 gi
    var el = enEl.querySelector('[data-sec="'+sectionId+'"][data-i="'+paraIdx+'"]');
    if(!el){ window.goTo(sectionId); return; }
    var g = +el.getAttribute('data-gi');
    var tE = paraTop(scE, enEl, g), tZ = paraTop(scZ, zhEl, g);
    if(tE !== null) scE.scrollTop = Math.max(0, tE);
    if(tZ !== null) scZ.scrollTop = Math.max(0, tZ);
    setCurrent(sectionId);
  };
  try{ openResult = window.openResult; }catch(e){}

  // ------- 笔记：改用 data-gi 定位 + 兼容旧数据 -------
  // 旧笔记只有 {lang,i,from,to,text}（i 为章内段号，无章节信息）。
  // 迁移：优先匹配「章内段号 i 相同 + 文本包含」的段落（最可靠），
  // 其次退回到纯文本匹配。
  (function migrateNotes(){
    if(typeof NOTES === 'undefined' || !NOTES) return;
    var changed = false;
    NOTES.forEach(function(n){
      if(n.gi != null) return;
      var root = (n.lang==='zh') ? zhEl : enEl;
      var cands = root.querySelectorAll(n.lang==='zh' ? '[data-lang="zh"]' : '[data-lang="en"]');
      var el = null;
      // 1) 段号 i 相同 且 包含片段
      if(n.i != null){
        var byI = root.querySelectorAll('[data-i="'+n.i+'"]');
        for(var k=0;k<byI.length;k++){
          if(!n.text || byI[k].textContent.indexOf(n.text)>=0){ el = byI[k]; break; }
        }
      }
      // 2) 纯文本匹配
      if(!el && n.text){
        for(var j=0;j<cands.length;j++){
          if(cands[j].textContent.indexOf(n.text) >= 0){ el = cands[j]; break; }
        }
      }
      if(el){
        n.gi = +el.getAttribute('data-gi');
        n.sec = el.getAttribute('data-sec');
        changed = true;
      }
    });
    if(changed && typeof saveNotes === 'function'){ try{ saveNotes(); }catch(e){} }
  })();

  function paraByGi(lang, g){
    var root = (lang==='zh') ? zhEl : enEl;
    return root.querySelector('[data-gi="'+g+'"]');
  }

  // renderMarks：按 gi 找笔记
  window.renderMarks = function(el){
    if(!el || el.getAttribute('data-gi')==null) return;
    var lang = el.getAttribute('data-lang'), g = el.getAttribute('data-gi');
    var list = NOTES.filter(function(n){ return n.lang===lang && +n.gi===+g; })
                   .sort(function(a,b){ return a.from-b.from; });
    var text = el.textContent, html='', pos=0;
    list.forEach(function(n){
      var f=Math.max(pos,n.from), t=Math.min(text.length,n.to);
      if(f>pos) html += escText(text.slice(pos,f));
      if(t>f){
        if(n.type==='hl') html += '<mark class="hlmark" style="background:'+n.color+'">'+escText(text.slice(f,t))+'</mark>';
        else html += '<u class="ulnote">'+escText(text.slice(f,t))+'</u>';
      }
      pos=Math.max(pos,t);
    });
    if(typeof TEMP!=='undefined' && TEMP && TEMP.lang===lang && +TEMP.gi===+g){
      var f=Math.max(pos,TEMP.from), t=Math.min(text.length,TEMP.to);
      if(f>pos) html += escText(text.slice(pos,f));
      if(t>f) html += '<mark class="senthl">'+escText(text.slice(f,t))+'</mark>';
      pos=Math.max(pos,t);
    }
    if(typeof PEER!=='undefined' && PEER && PEER.lang===lang && +PEER.gi===+g){
      var pr = PEER.ranges.slice().sort(function(a,b){ return a[0]-b[0]; });
      pr.forEach(function(rg){
        var f=Math.max(pos,rg[0]), t=Math.min(text.length,rg[1]);
        if(f>pos) html += escText(text.slice(pos,f));
        if(t>f) html += '<mark class="peer-sent">'+escText(text.slice(f,t))+'</mark>';
        pos=Math.max(pos,t);
      });
    }
    if(pos<text.length) html += escText(text.slice(pos));
    el.innerHTML = html;
  };
  try{ renderMarks = window.renderMarks; }catch(e){}

  // clearTempHL：用 [data-gi] 查找段落
  window.clearTempHL = function(){
    try{ TEMP = null; PEER = null; }catch(e){}
    var marks = document.querySelectorAll('.senthl,.peer-sent');
    for(var k=0;k<marks.length;k++){
      var p = marks[k].closest('[data-gi]');
      if(p) window.renderMarks(p);
    }
  };
  try{ clearTempHL = window.clearTempHL; }catch(e){}

  window.renderAllMarks = function(){
    ['en','zh'].forEach(function(lang){
      var root = (lang==='zh') ? zhEl : enEl;
      var set = {};
      NOTES.forEach(function(n){ if(n.lang===lang && n.gi!=null) set[n.gi]=1; });
      for(var g in set){ var el = root.querySelector('[data-gi="'+g+'"]'); if(el) window.renderMarks(el); }
    });
  };
  try{ renderAllMarks = window.renderAllMarks; }catch(e){}

  // applyNote：原实现用 [data-i] 重绘，改为按 gi 重绘
  window.applyNote = function(type, color){
    var note = window.buildNote();
    try{ window.getSelection().removeAllRanges(); }catch(e){}
    hideToolbar();
    if(!note){ showToast('请在同一段内选择文字'); return; }
    if(type==='ul'){ note.type='ul'; note.color=null; }
    else { note.type='hl'; note.color=color||HL_COLORS[0].hex; }
    var idx = window.findNoteIndex(note);
    if(idx>=0) NOTES.splice(idx,1);
    NOTES.push(note);
    saveNotes();
    var el = paraByGi(note.lang, note.gi);
    if(el) window.renderMarks(el);
    showToast((type==='ul'?'已划线':'已高亮'+(colorName(note.color)||''))+'，已保存到笔记');
    refreshPanel();
  };
  try{ applyNote = window.applyNote; }catch(e){}

  // refreshPanel：笔记列表按 gi/sec 定位
  window.refreshPanel = function(){
    var p = document.getElementById('note-panel');
    var html = '<div class="np-head"><b>📝 我的笔记 ('+NOTES.length+')</b><span>';
    html += '<button id="np-clear" style="color:#c0392b">清除全部</button> <button id="np-close" style="color:var(--accent)">关闭</button></span></div>';
    if(!NOTES.length) html += '<div class="np-empty">还没有笔记。<br>在正文里选中文字，即可「高亮」或「划线」。</div>';
    else{
      var shown = {};
      for(var i=NOTES.length-1;i>=0;i--){
        var n = NOTES[i];
        var key = n.lang+':'+n.gi;
        shown[key] = (shown[key]||0)+1;
        if(shown[key]>1) continue;
        var t = window.noteText(n) || '…';
        var lang = n.lang==='en' ? '英' : '中';
        var mark = n.type==='hl'
          ? '<span style="background:'+n.color+'">&nbsp;&nbsp;&nbsp;</span>'
          : '<span style="text-decoration:underline;text-decoration-thickness:2px;text-decoration-color:#e8504a">&nbsp;&nbsp;&nbsp;</span>';
        html += '<div class="np-item" data-lang="'+n.lang+'" data-gi="'+n.gi+'">'
             +  '<div class="np-meta"><b>'+(n.sec||'')+' · '+(n.i+1)+'</b><span style="color:var(--mute)">'+lang+'</span>'+mark
             +  (n.type==='ul'?'<span style="font-size:10px;color:#888">划线</span>':'<span style="font-size:10px;color:#888">高亮</span>')
             +  '</div><div class="np-text">'+escText(t)+'</div></div>';
      }
    }
    p.innerHTML = html;
  };
  try{ refreshPanel = window.refreshPanel; }catch(e){}

  // 笔记面板点击：接管 .np-item 跳转（按 gi）、np-close 关闭
  var npEl = document.getElementById('note-panel');
  if(npEl){
    npEl.addEventListener('click', function(e){
      var item = e.target.closest && e.target.closest('.np-item');
      if(item){
        e.stopImmediatePropagation();
        var g = +item.getAttribute('data-gi');
        var lang = item.getAttribute('data-lang')==='zh' ? 'zh' : 'en';
        var tE = paraTop(scE, enEl, g), tZ = paraTop(scZ, zhEl, g);
        if(tE!==null) scE.scrollTop = Math.max(0, tE-40);
        if(tZ!==null) scZ.scrollTop = Math.max(0, tZ-40);
        var el = paraByGi('en', g);
        if(el) setCurrent(el.getAttribute('data-sec'));
        e.stopPropagation();
        hideToolbar();
        return;
      }
      var closeBtn = e.target.closest && e.target.closest('#np-close');
      if(closeBtn){
        e.stopImmediatePropagation();
        document.getElementById('note-panel').classList.remove('np-open');
      }
    }, true);
  }

  // buildNote：记录 gi + sec
  window.buildNote = function(){
    var sel = window.getSelection();
    if(!sel || sel.rangeCount===0 || sel.isCollapsed) return null;
    var r = sel.getRangeAt(0);
    var root = r.commonAncestorContainer.nodeType===1 ? r.commonAncestorContainer : r.commonAncestorContainer.parentElement;
    var lang = root.closest('#article-en') ? 'en' : (root.closest('#article-zh') ? 'zh' : null);
    if(!lang) return null;
    var startPara = r.startContainer.nodeType===3 ? r.startContainer.parentElement : r.startContainer.closest('[data-gi]');
    var endPara = r.endContainer.nodeType===3 ? r.endContainer.parentElement : r.endContainer.closest('[data-gi]');
    if(!startPara || !endPara || startPara!==endPara) return null;
    var a = pointOffsetInPara(startPara, r.startContainer, r.startOffset);
    var b = pointOffsetInPara(endPara, r.endContainer, r.endOffset);
    var from = Math.min(a,b), to = Math.max(a,b);
    if(to-from<=0) return null;
    return {lang:lang, gi:+startPara.getAttribute('data-gi'), sec:startPara.getAttribute('data-sec'),
            i:+startPara.getAttribute('data-i'), from:from, to:to,
            text:startPara.textContent.slice(from,to)};
  };
  try{ buildNote = window.buildNote; }catch(e){}

  window.findNoteIndex = function(n){
    for(var k=0;k<NOTES.length;k++){ var x=NOTES[k];
      if(x.lang===n.lang && +x.gi===+n.gi && x.from===n.from && x.to===n.to) return k; }
    return -1;
  };
  try{ findNoteIndex = window.findNoteIndex; }catch(e){}

  window.noteText = function(n){
    var el = paraByGi(n.lang, n.gi);
    return el ? el.textContent.slice(n.from, n.to) : '';
  };
  try{ noteText = window.noteText; }catch(e){}

  // sentsFor：按 gi 取段落文本
  window.sentsFor = function(lang, g){
    var key = lang+':'+g;
    if(__SENT_CACHE[key]) return __SENT_CACHE[key];
    var el = paraByGi(lang, g);
    var list = el ? splitSentences(el.textContent) : [];
    __SENT_CACHE[key] = list;
    return list;
  };
  try{ sentsFor = window.sentsFor; }catch(e){}

  // applyNote 里用 articleFor(...).querySelector('[data-i=..]') 重绘，
  // 用 gi 覆盖：直接在此重新实现 applyNote 的收尾（已通过 renderMarks 覆盖）。
  // applySentenceSel 需要按 gi 找对侧段落，使用章内 i 访问 SENT_ALIGN。
  window.applySentenceSel = function(){
    var sel = window.getSelection();
    try{ clearTempHL(); }catch(e){}
    if(!sel || sel.rangeCount===0 || sel.isCollapsed) return;
    var r = sel.getRangeAt(0);
    var node = r.startContainer, startPara = node.nodeType===3 ? node.parentElement : node.closest('[data-gi]');
    var endNode = r.endContainer, endPara = endNode.nodeType===3 ? endNode.parentElement : endNode.closest('[data-gi]');
    if(!startPara || !endPara || startPara!==endPara) return;
    var lang = startPara.getAttribute('data-lang');
    if(lang!=='en' && lang!=='zh') return;
    var g = +startPara.getAttribute('data-gi');
    var i = +startPara.getAttribute('data-i');
    var sec = startPara.getAttribute('data-sec');
    var a = pointOffsetInPara(startPara, r.startContainer, r.startOffset);
    var b = pointOffsetInPara(startPara, r.endContainer, r.endOffset);
    var from = Math.min(a,b), to = Math.max(a,b);
    var peerLang = lang==='en' ? 'zh' : 'en';
    var peerPara = paraByGi(peerLang, g);   // 左右两栏 gi 一一对应
    var entry = (typeof SENT_ALIGN!=='undefined' && SENT_ALIGN) ? SENT_ALIGN[sec+'/'+i] : null;
    if(entry && entry[lang] && entry[peerLang] && peerPara){
      var si = sentIdxAt(entry[lang], from);
      if(si!==-1){
        TEMP = {lang:lang, gi:g, from:entry[lang][si][0], to:entry[lang][si][1]};
        var tr = [];
        var m = entry.m || [];
        for(var k=0;k<m.length;k++){
          var src = (lang==='en') ? m[k][0] : m[k][1];
          var dst = (lang==='en') ? m[k][1] : m[k][0];
          if(src===si && entry[peerLang][dst]) tr.push(entry[peerLang][dst]);
        }
        if(!tr.length && entry[peerLang][si]) tr.push(entry[peerLang][si]);
        if(tr.length){
          PEER = {lang:peerLang, gi:g, ranges:tr};
          window.renderMarks(peerPara);
          // 平滑滚动对侧栏到对应段
          var t = paraTop(peerLang==='zh'?scZ:scE, peerLang==='zh'?zhEl:enEl, g);
          if(t!==null) smoothGoto(peerLang==='zh'?scZ:scE, t);
        }
        return;
      }
    }
  };
  try{ applySentenceSel = window.applySentenceSel; }catch(e){}

  // ------- 阅读位置记忆：连续滚动直接存 scrollTop -------
  function savePos(){
    var id = window.__csCurrent || ORDER[0];
    try{
      localStorage.setItem(POS_KEY, JSON.stringify({
        section: id, en: scE.scrollTop, zh: scZ.scrollTop, at: Date.now()
      }));
    }catch(e){}
  }
  scE.addEventListener('scroll', function(){ clearTimeout(window.__csPosT); window.__csPosT=setTimeout(savePos,200); }, {passive:true});
  scZ.addEventListener('scroll', function(){ clearTimeout(window.__csPosT); window.__csPosT=setTimeout(savePos,200); }, {passive:true});

  // ------- 恢复上次位置 -------
  var saved = null;
  try{ saved = JSON.parse(localStorage.getItem(POS_KEY) || 'null'); }catch(e){}
  var startSec = (saved && saved.section) ? saved.section : (ORDER.indexOf('introduction')>=0 ? 'introduction' : ORDER[0]);
  window.goTo(startSec);
  if(saved){
    requestAnimationFrame(function(){ requestAnimationFrame(function(){
      // 连续滚动下直接用像素位置恢复更准确；若还原偏差过大再退回章节顶部
      if(saved.en) scE.scrollTop = saved.en;
      if(saved.zh) scZ.scrollTop = saved.zh;
      var id = topSection(scE, enEl); setCurrent(id);
    });});
  }
  setTimeout(function(){ window.__csCurrent = window.__csCurrent || startSec; }, 0);

  // 首次渲染后套用笔记标记
  if(window.renderAllMarks) window.renderAllMarks();
  if(window.__updateChapterHud) window.__updateChapterHud();
})();
'''

def patch(html):
    if MARK in html:
        return html, False
    if '</style>' not in html:
        raise RuntimeError('未找到 </style>')
    html = html.replace('</style>', CSS + '</style>', 1)
    if '</body>' not in html:
        raise RuntimeError('未找到 </body>')
    # 需要在 add_theme_and_hud 的脚本之后运行，确保 __markChapterActive 等已就绪
    html = html.replace('</body>', '<script>' + JS + '</script>\n</body>', 1)
    return html, True

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    for path in sys.argv[1:]:
        if not os.path.isfile(path):
            print('!! 找不到', path); continue
        html = open(path, encoding='utf-8').read()
        out, changed = patch(html)
        if changed:
            open(path, 'w', encoding='utf-8').write(out)
            print('✓ 已注入', path)
        else:
            print('= 已存在，跳过', path)

if __name__ == '__main__':
    main()
