#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给阅读器注入「笔记删除 + 批量导出」（幂等）。

用法:
    python3 scripts/add_notes_export.py books/<id>/index.html
    python3 scripts/add_notes_export.py books/*/index.html

背景:
    阅读器原本只能「清除全部」笔记，无法单条删除，也没有导出功能。本脚本：

    1) 单条删除（两种方式）：
       a) 直接点击正文里已经高亮/划线的文字 → 删除这一条
          （拖拽选词不会误删；误删后可按 Ctrl/⌘+Z 恢复）；
       b) 笔记面板每一项右侧的「✕」按钮，逐条列出、点哪条删哪条
          （同段落的多条按 gi+from+to 精确定位删除，其余保留）；
    2) 批量导出：面板头部加「导出」，把全部笔记导出为 Markdown / 纯文本 /
       JSON，按「章 -> 段」顺序排列；每条附「出处」引文行，格式为

           引文正文……
           ——作者：《书名》，出版社，年份

       中文笔记用中文格式，英文笔记用英文格式（Author, *Title* (Publisher, Year).），
       其他语言的书可在 metadata.json 里补 publisher / publisherEn / publishYear。

    书目标题/作者/出版社信息通过注入的 window.BOOK_META 提供（读取 metadata.json）。

    与既有脚本一致：幂等、只注入、不删除原有逻辑。
"""
import sys, os, json, re

MARK = 'NOTES-EXPORT'

CSS = '''
  /* ===== 笔记删除 + 批量导出 (NOTES-EXPORT) ===== */
  #note-panel .np-tools{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
  #note-panel .np-tools button{background:none;border:none;cursor:pointer;font-size:13px;
    padding:2px 6px;font-family:inherit}
  #note-panel .np-tools button.exp{color:var(--accent)}
  #note-panel .np-tools button.clr{color:#c0392b}
  #note-panel .np-meta .np-del{margin-left:auto;flex:0 0 auto;border:none;background:none;
    color:#b9b3a8;cursor:pointer;font-size:13px;line-height:1;padding:0 4px;font-family:inherit}
  #note-panel .np-meta .np-del:hover{color:#c0392b}
  /* 导出选择浮层 */
  #np-export{position:fixed;z-index:10030;background:var(--panel,#fff);color:var(--ink,#2b2b2b);
    border:1px solid var(--line,#e6e1d6);border-radius:10px;box-shadow:0 12px 36px rgba(0,0,0,.24);
    padding:6px;display:none;font-family:var(--reader-font,inherit)}
  #np-export.on{display:block}
  #np-export button{display:block;width:100%;text-align:left;background:none;border:none;
    cursor:pointer;padding:8px 12px;border-radius:7px;font-size:13px;color:inherit;font-family:inherit;
    white-space:nowrap}
  #np-export button:hover{background:var(--accent-soft,rgba(138,68,34,.09))}
  #np-export .np-exp-sep{height:1px;background:var(--line,#e6e1d6);margin:5px 4px}
'''

JS = r'''
/* ============ 笔记删除 + 批量导出 (NOTES-EXPORT) ============ */
(function(){
  if(typeof EN === 'undefined') return;

  var META = window.BOOK_META || {};
  function bookTitle(){ return META.title || ''; }
  function bookAuthor(){ return META.author || ''; }

  /* 引文行：中文与英文两套格式 */
  function citation(lang){
    var t, a;
    if(lang === 'zh'){
      t = META.titleZh || META.title || '';
      a = META.author || '';
      var pub = META.publisher || '';
      var yr  = META.publishYear || '';
      // ——作者：《书名》，出版社，年份
      var tail = [];
      if(pub) tail.push(pub);
      if(yr)  tail.push(yr);
      var s = '——' + a;
      s += '：《' + t + '》';
      if(tail.length) s += '，' + tail.join('，');
      return s;
    }
    // 英文：Author, *Title* (Publisher, Year).
    t = META.titleEn || META.title || '';
    a = META.authorEn || META.author || '';
    var pubE = META.publisherEn || META.publisher || '';
    var yrE  = META.publishYear || '';
    var s2 = (a ? a + ', ' : '') + (t ? '*' + t + '*' : '');
    if(pubE || yrE){
      var par = [];
      if(pubE) par.push(pubE);
      if(yrE)  par.push(yrE);
      s2 += ' (' + par.join(', ') + ')';
    }
    s2 = s2.replace(/^\s+|\s+$/g,'');
    if(s2) s2 += '.';
    return s2;
  }

  /* 每条笔记：正文 + 出处（去重后的引文行） */
  function noteBlock(n, ordinal){
    var txt = (window.noteText ? (window.noteText(n) || '') : '').replace(/\s+$/,'');
    var head = (n.sec || '') + (n.i != null ? (' · 段 ' + (n.i + 1)) : '');
    var kind = (n.type === 'ul') ? '划线' : '高亮';
    var lang = (n.lang === 'en') ? 'en' : 'zh';
    var cite = citation(lang);
    var out = '';
    out += '### ' + ordinal + '. ' + head + '（' + kind + '）\n\n';
    out += '> ' + txt.replace(/\n/g, '\n> ') + '\n\n';
    if(cite) out += '> ' + cite + '\n\n';
    return out;
  }

  function sortedNotes(){
    // 按 章（sec 出现顺序）-> 段 -> 起始偏移 排序；同段同偏移合并为一条
    var secOrder = {};
    (typeof EN !== 'undefined' ? EN : []).forEach(function(s, k){ secOrder[s.id] = k; });
    var arr = NOTES.slice();
    // 去重：同 lang+gi+from+to 只保留一条（笔记模型本身可含重复）
    var seen = {};
    arr = arr.filter(function(n){
      var k = n.lang + '|' + n.gi + '|' + n.from + '|' + n.to;
      if(seen[k]) return false; seen[k] = 1; return true;
    });
    arr.sort(function(a, b){
      var oa = (secOrder[a.sec] != null) ? secOrder[a.sec] : 9999;
      var ob = (secOrder[b.sec] != null) ? secOrder[b.sec] : 9999;
      if(oa !== ob) return oa - ob;
      if((a.gi||0) !== (b.gi||0)) return (a.gi||0) - (b.gi||0);
      return (a.from||0) - (b.from||0);
    });
    return arr;
  }

  function buildMarkdown(){
    var arr = sortedNotes();
    if(!arr.length) return '';
    var out = '# ' + (bookTitle() || '阅读笔记') + ' · 高亮笔记\n\n';
    var c0 = citation('zh');
    if(c0) out += c0.replace(/^——/, '') + '\n\n';
    out += '共 ' + arr.length + ' 条\n\n---\n\n';
    // 按章分组
    var lastSec = null, idx = 0;
    arr.forEach(function(n){
      if(n.sec !== lastSec){
        lastSec = n.sec;
        out += '## ' + (n.sec || '（未分章）') + '\n\n';
      }
      idx++;
      out += noteBlock(n, idx);
    });
    return out;
  }

  function buildText(){
    var arr = sortedNotes();
    if(!arr.length) return '';
    var out = (bookTitle() || '阅读笔记') + ' · 高亮笔记\n';
    var c0 = citation('zh');
    if(c0) out += c0 + '\n';
    out += '共 ' + arr.length + ' 条\n\n';
    var lastSec = null, idx = 0;
    arr.forEach(function(n){
      if(n.sec !== lastSec){ lastSec = n.sec; out += '\n【' + (n.sec || '（未分章）') + '】\n'; }
      idx++;
      var txt = (window.noteText ? (window.noteText(n) || '') : '').replace(/\s+$/,'');
      var kind = (n.type === 'ul') ? '划线' : '高亮';
      out += '\n' + idx + '. ' + txt + '\n';
      var lang = (n.lang === 'en') ? 'en' : 'zh';
      var cite = citation(lang);
      if(cite) out += '   ' + cite + '\n';
    });
    return out;
  }

  function buildJSON(){
    var arr = sortedNotes().map(function(n){
      var lang = (n.lang === 'en') ? 'en' : 'zh';
      return {
        section: n.sec || null,
        paraIndex: (n.i != null ? n.i : null),
        globalIndex: (n.gi != null ? n.gi : null),
        lang: lang,
        type: (n.type === 'ul') ? 'underline' : 'highlight',
        color: n.color || null,
        text: (window.noteText ? (window.noteText(n) || '') : ''),
        citation: citation(lang)
      };
    });
    return JSON.stringify({
      book: { title: bookTitle(), author: bookAuthor(),
              publisher: META.publisher || '', publisherEn: META.publisherEn || '',
              year: META.publishYear || '' },
      exportedAt: new Date().toISOString(),
      count: arr.length,
      notes: arr
    }, null, 2);
  }

  /* ---------- 下载 ---------- */
  function download(filename, content, mime){
    try{
      var blob = new Blob([content], {type: (mime || 'text/plain') + ';charset=utf-8'});
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url; a.download = filename;
      document.body.appendChild(a); a.click();
      setTimeout(function(){ document.body.removeChild(a); URL.revokeObjectURL(url); }, 120);
      return true;
    }catch(e){ return false; }
  }
  function safeName(){
    var t = (bookTitle() || 'notes').replace(/[\\/:*?"<>|]+/g, '_').trim();
    var d = new Date();
    function p(x){ return (x<10?'0':'') + x; }
    return t + '_笔记_' + d.getFullYear() + p(d.getMonth()+1) + p(d.getDate()) + '.md';
  }
  function doExport(kind){
    var arr = sortedNotes();
    if(!arr.length){ if(window.showToast) showToast('还没有笔记可导出'); hideExport(); return; }
    var ok = false;
    if(kind === 'md')   ok = download(safeName(), buildMarkdown(), 'text/markdown');
    if(kind === 'txt')  ok = download(safeName().replace(/\.md$/, '.txt'), buildText(), 'text/plain');
    if(kind === 'json') ok = download(safeName().replace(/\.md$/, '.json'), buildJSON(), 'application/json');
    if(kind === 'copy' || !ok){
      // 兜底：复制到剪贴板
      var txt = (kind === 'json') ? buildJSON() : buildMarkdown();
      copyText(txt);
    } else {
      if(window.showToast) showToast('已导出 ' + arr.length + ' 条笔记');
    }
    hideExport();
  }
  function copyText(txt){
    if(navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(txt).then(function(){
        if(window.showToast) showToast('已复制到剪贴板');
      }, function(){ fallback(txt); });
    } else fallback(txt);
  }
  function fallback(txt){
    try{
      var ta = document.createElement('textarea');
      ta.value = txt; ta.style.position='fixed'; ta.style.opacity='0';
      document.body.appendChild(ta); ta.select(); document.execCommand('copy');
      document.body.removeChild(ta);
      if(window.showToast) showToast('已复制到剪贴板');
    }catch(e){ if(window.showToast) showToast('导出失败'); }
  }

  /* ---------- 导出浮层 ---------- */
  function ensureExportMenu(){
    var m = document.getElementById('np-export');
    if(m) return m;
    m = document.createElement('div');
    m.id = 'np-export';
    m.innerHTML =
      '<button data-k="md">导出 Markdown（.md）</button>' +
      '<button data-k="txt">导出纯文本（.txt）</button>' +
      '<button data-k="json">导出 JSON（.json）</button>' +
      '<div class="np-exp-sep"></div>' +
      '<button data-k="copy">复制全部（含出处）</button>';
    document.body.appendChild(m);
    m.addEventListener('click', function(e){
      var b = e.target.closest && e.target.closest('button[data-k]');
      if(!b) return;
      e.stopPropagation();
      doExport(b.getAttribute('data-k'));
    });
    return m;
  }
  function showExport(anchor){
    var m = ensureExportMenu();
    m.classList.add('on');
    var r = anchor.getBoundingClientRect();
    var mw = m.offsetWidth, mh = m.offsetHeight;
    var left = Math.min(window.innerWidth - mw - 8, Math.max(8, r.right - mw));
    var top = r.bottom + 6;
    if(top + mh > window.innerHeight - 8) top = Math.max(8, r.top - mh - 6);
    m.style.left = left + 'px';
    m.style.top = top + 'px';
  }
  function hideExport(){ var m = document.getElementById('np-export'); if(m) m.classList.remove('on'); }
  document.addEventListener('click', function(e){
    var m = document.getElementById('np-export');
    if(!m || !m.classList.contains('on')) return;
    if(e.target.closest && e.target.closest('#np-export')) return;
    if(e.target.closest && e.target.closest('.np-exp')) return;
    hideExport();
  });
  window.addEventListener('scroll', hideExport, true);
  window.addEventListener('resize', hideExport);

  /* ---------- 单条删除 ---------- */
  function deleteNote(n){
    // 精确定位：lang + gi + from + to；移除所有匹配项
    var removed = 0;
    for(var k = NOTES.length - 1; k >= 0; k--){
      var x = NOTES[k];
      if(x.lang === n.lang && +x.gi === +n.gi && x.from === n.from && x.to === n.to){
        NOTES.splice(k, 1); removed++;
      }
    }
    if(!removed) return false;
    try{ saveNotes(); }catch(e){}
    try{ renderAllMarks(); }catch(e){}
    // 该段可能已无任何笔记：renderAllMarks 不会重绘它，导致残留 <mark>。
    // 因此这里显式重绘被删除笔记所在的那一段（清掉标记）。
    try{
      var root = (n.lang==='zh') ? document.getElementById('article-zh') : document.getElementById('article-en');
      var el = root && root.querySelector('[data-gi="'+n.gi+'"]');
      if(el && typeof window.renderMarks === 'function') window.renderMarks(el);
    }catch(e){}
    try{ refreshPanel(); }catch(e){}
    if(window.showToast) showToast('已删除该条笔记');
    return true;
  }
  /* ---------- 点击正文里的高亮/划线 → 直接删除 ----------
     需求：不用打开「笔记」面板，直接点那段彩色文字就能删掉这条高亮。
     做法：
       1) 包裹 renderMarks，在每枚 mark.hlmark / u.ulnote 上写入 data-nf/data-nt
          （段内起止偏移），使「被点的标记 → 对应笔记」可精确对应；
       2) 在 document 上监听 click，命中标记则按 lang+gi+from+to 删除该条；
       3) 区分「单击」与「拖选」：按下与抬起位置基本重合、且没有选中文字时才算点击，
          避免用户拖拽选词时误删。
     同时提供一个可选开关（默认开启）：window.__clickDeleteHighlight。 */
  window.__clickDeleteHighlight = (window.__clickDeleteHighlight !== false);

  // 1) 包裹 renderMarks：给高亮/划线标记打上偏移信息
  function tagMarks(root){
    if(!root || !root.querySelectorAll) root = document;
    var ms = root.querySelectorAll('mark.hlmark, u.ulnote');
    for(var i=0;i<ms.length;i++){
      var m = ms[i];
      if(m.getAttribute('data-nf')!=null) continue;
      // 该标记在段落纯文本中的起止偏移（跳过已处理的其它标记，逐枚累加）
      var para = m.closest('[data-gi]');
      if(!para) continue;
      var off = textOffsetWithin(para, m);
      var len = (m.textContent||'').length;
      m.setAttribute('data-nf', off);
      m.setAttribute('data-nt', off+len);
    }
  }
  function textOffsetWithin(para, node){
    // 用一个 Range 测 node 起点相对 para 内容的字符偏移
    try{
      var r = document.createRange();
      r.selectNodeContents(para);
      r.setEndBefore(node);
      return r.toString().length;
    }catch(e){ return 0; }
  }
  if(typeof window.renderMarks === 'function'){
    var __rm2 = window.renderMarks;
    window.renderMarks = function(el){
      var r = __rm2.apply(this, arguments);
      try{ tagMarks(el); }catch(e){}
      return r;
    };
    try{ renderMarks = window.renderMarks; }catch(e){}
  }
  // 全文重绘后再补标一次
  if(typeof window.renderAllMarks === 'function'){
    var __ram = window.renderAllMarks;
    window.renderAllMarks = function(){ var r=__ram.apply(this,arguments); try{ tagMarks(document); }catch(e){} return r; };
    try{ renderAllMarks = window.renderAllMarks; }catch(e){}
  }
  // 首屏已有标记也补标
  setTimeout(function(){ try{ tagMarks(document); }catch(e){} }, 400);

  // 2) 点击删除（含拖选保护）
  var _downX=0,_downY=0,_downT=0;
  document.addEventListener('mousedown', function(e){
    _downX=e.clientX; _downY=e.clientY; _downT=Date.now();
  }, true);
  document.addEventListener('click', function(e){
    if(window.__clickDeleteHighlight === false) return;
    var t = e.target;
    if(!t || !t.closest) return;
    var m = t.closest('mark.hlmark, u.ulnote');
    if(!m) return;
    var para = m.closest('[data-gi]');
    if(!para) return;
    // 拖选保护：位移过大 / 耗时过长 → 视为选词，不删
    var dist = Math.abs(e.clientX-_downX) + Math.abs(e.clientY-_downY);
    var dt = Date.now() - _downT;
    var sel = window.getSelection && window.getSelection();
    var hasSel = sel && !sel.isCollapsed && String(sel).length>0;
    if(dist > 6 || hasSel && dt > 120) return;
    var lang = para.getAttribute('data-lang') || (para.closest('#article-zh') ? 'zh' : 'en');
    var gi = +para.getAttribute('data-gi');
    var from = +m.getAttribute('data-nf');
    var to = +m.getAttribute('data-nt');
    var target = findNoteByKey(lang, gi, from, to);
    if(!target){
      // 兜底：同段内取包含点击位置的最近一条
      var cands = NOTES.filter(function(x){ return x.lang===lang && +x.gi===gi; });
      target = cands.sort(function(a,b){ return Math.abs(a.from-from)-Math.abs(b.from-from); })[0];
    }
    if(!target) return;
    e.preventDefault();
    e.stopPropagation();
    if(e.stopImmediatePropagation) e.stopImmediatePropagation();
    var removed = target;
    lastDeleted = JSON.parse(JSON.stringify(removed));
    deleteNote(target);
    if(window.showToast) showToast('已删除这条' + (removed.type==='ul' ? '划线' : '高亮') + '（按 Ctrl/⌘+Z 撤销）');
  }, true);

  // 误删保护：记录最近一次删除，支持 Ctrl/⌘+Z 恢复
  var lastDeleted = null;
  document.addEventListener('keydown', function(e){
    if(!lastDeleted) return;
    if((e.ctrlKey || e.metaKey) && (e.key==='z' || e.key==='Z')){
      var n = lastDeleted; lastDeleted = null;
      // 避免重复恢复
      var dup = NOTES.some(function(x){ return x.lang===n.lang && +x.gi===+n.gi && x.from===n.from && x.to===n.to; });
      if(!dup){
        NOTES.push(n);
        try{ saveNotes(); }catch(e2){}
        try{ renderAllMarks(); }catch(e2){}
        try{
          var root=(n.lang==='zh')?document.getElementById('article-zh'):document.getElementById('article-en');
          var el=root&&root.querySelector('[data-gi="'+n.gi+'"]');
          if(el) window.renderMarks(el);
        }catch(e2){}
        try{ refreshPanel(); }catch(e2){}
        if(window.showToast) showToast('已恢复刚才删除的笔记');
      }
      e.preventDefault();
    }
  }, true);

  // 供面板构建时取到「当前显示的这条」：用 data 属性和 noteText 反查
  function findNoteByKey(lang, gi, from, to){
    for(var k=0;k<NOTES.length;k++){
      var x=NOTES[k];
      if(x.lang===lang && +x.gi===+gi && x.from===+from && x.to===+to) return x;
    }
    return null;
  }

  /* ---------- 面板重建 ----------
     原阅读器 refreshPanel 同一段（lang+gi）只渲染“最新一条”，
     导致同段多条高亮时：列表里看不到其余条目、✕ 删的也不是显示的那条。
     这里整段重写：逐条列出每一枚高亮/划线，各自带 ✕，
     并用索引精确定位要删的笔记（不依赖 gi/from/to 去猜）。 */
  function hexOf(n){ return n.color || '#ffe58a'; }

  function buildPanel(){
    var p = document.getElementById('note-panel');
    if(!p) return;
    // 按「章 -> 段 -> 段内位置」排序，列表更稳
    var order = NOTES.map(function(n,i){ return i; });
    order.sort(function(a,b){
      var A=NOTES[a], B=NOTES[b];
      if((A.sec||'') !== (B.sec||'')) return (A.sec||'') < (B.sec||'') ? -1 : 1;
      if(+A.gi !== +B.gi) return +A.gi - +B.gi;
      if(A.lang !== B.lang) return A.lang < B.lang ? -1 : 1;
      return (A.from||0) - (B.from||0);
    });

    var html = '<div class="np-head"><b>📝 我的笔记 ('+NOTES.length+')</b>'
             + '<span class="np-tools">'
             + '<button class="np-exp">导出</button>'
             + '<button id="np-clear" class="clr">清除全部</button>'
             + '<button id="np-close">关闭</button></span></div>';

    if(!NOTES.length){
      html += '<div class="np-empty">还没有笔记。<br>在正文里选中文字，即可「高亮」或「划线」。</div>';
    }else{
      for(var k=0;k<order.length;k++){
        var idx = order[k];
        var n = NOTES[idx];
        var t = '';
        try{ t = window.noteText ? window.noteText(n) : ''; }catch(e){}
        if(!t) t = '…';
        var lang = n.lang==='en' ? '英' : '中';
        var mark = n.type==='hl'
          ? '<span style="background:'+hexOf(n)+'">&nbsp;&nbsp;&nbsp;</span>'
          : '<span style="text-decoration:underline;text-decoration-thickness:2px;text-decoration-color:#e8504a">&nbsp;&nbsp;&nbsp;</span>';
        html += '<div class="np-item" data-idx="'+idx+'" data-lang="'+n.lang+'" data-gi="'+n.gi+'" data-from="'+(n.from||0)+'" data-to="'+(n.to||0)+'">'
             +  '<div class="np-meta"><b>'+escText(n.sec||'')+' · '+((+n.i||0)+1)+'</b>'
             +  '<span style="color:var(--mute)">'+lang+'</span>'+mark
             +  (n.type==='ul'?'<span style="font-size:10px;color:var(--mute)">划线</span>':'<span style="font-size:10px;color:var(--mute)">高亮</span>')
             +  '<button class="np-del" data-idx="'+idx+'" title="删除这条笔记">✕</button>'
             +  '</div><div class="np-text">'+escText(t)+'</div></div>';
      }
    }
    p.innerHTML = html;

    var exp = p.querySelector('.np-exp');
    if(exp) exp.addEventListener('click', function(e){ e.stopPropagation(); showExport(exp); });
    var clr = p.querySelector('#np-clear');
    if(clr) clr.addEventListener('click', function(e){ e.stopPropagation(); clearAll(); });
    var cls = p.querySelector('#np-close');
    if(cls) cls.addEventListener('click', function(e){ e.stopPropagation(); closePanel(); });
  }

  function escText(s){
    return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function clearAll(){
    if(!NOTES.length) return;
    if(!window.confirm('确定清除全部 '+NOTES.length+' 条笔记？')) return;
    NOTES.length = 0;
    try{ saveNotes(); }catch(e){}
    try{ renderAllMarks(); }catch(e){}
    try{ refreshPanel(); }catch(e){}
    if(window.showToast) showToast('已清除全部笔记');
  }

  function closePanel(){
    var p = document.getElementById('note-panel');
    if(p) p.style.display = 'none';
    if(typeof window.hidePanel === 'function'){ try{ window.hidePanel(); }catch(e){} }
  }

  /* ✕ 删除：document 捕获阶段监听，抢在面板自身的 .np-item 跳转
     （捕获 + stopImmediatePropagation）之前处理。 */
  document.addEventListener('click', function(e){
    var del = e.target && e.target.closest && e.target.closest('#note-panel .np-del');
    if(!del) return;
    e.preventDefault();
    e.stopPropagation();
    if(e.stopImmediatePropagation) e.stopImmediatePropagation();
    var idx = +del.getAttribute('data-idx');
    if(isNaN(idx) || idx<0 || idx>=NOTES.length){
      // 兜底：用 data 属性反查
      var item = del.closest('.np-item');
      if(item){
        var lang = item.getAttribute('data-lang')==='zh'?'zh':'en';
        var gi = +item.getAttribute('data-gi');
        var from = +item.getAttribute('data-from');
        var to = +item.getAttribute('data-to');
        idx = -1;
        for(var k=0;k<NOTES.length;k++){
          var x=NOTES[k];
          if(x.lang===lang && +x.gi===gi && (+x.from||0)===from && (+x.to||0)===to){ idx=k; break; }
        }
      }
    }
    if(idx<0 || idx>=NOTES.length){ if(window.showToast) showToast('未找到该笔记'); return; }
    deleteNote(NOTES[idx]);
  }, true);

  /* 覆盖 refreshPanel：改为逐条列出全部笔记 */
  window.refreshPanel = buildPanel;
  try{ refreshPanel = window.refreshPanel; }catch(e){}

  // 初始化时若面板已存在也重建一次
  buildPanel();

  window.__notesExport = { markdown: buildMarkdown, text: buildText, json: buildJSON, citation: citation };
})();
'''

def load_meta(book_html_path):
    """读取同目录 metadata.json，生成注入用的 BOOK_META 对象。"""
    d = os.path.dirname(os.path.abspath(book_html_path))
    mp = os.path.join(d, 'metadata.json')
    meta = {}
    if os.path.isfile(mp):
        try:
            meta = json.load(open(mp, encoding='utf-8'))
        except Exception:
            meta = {}
    title = meta.get('title', '')
    subtitle = meta.get('subtitle', '')
    author = meta.get('author', '')
    # 中英书名：优先显式 titleZh；否则 subtitle 若为《...》则视为中文书名
    title_zh = meta.get('titleZh', '')
    if not title_zh and subtitle and subtitle.strip().startswith('《') and subtitle.strip().endswith('》'):
        title_zh = subtitle.strip()[1:-1]
    # 中英作者：优先显式 authorZh/authorEn；否则从 "Hongshan Li 李洪山" 拆分
    author_en = meta.get('authorEn', '') or author
    author_zh = meta.get('authorZh', '')
    # 若 authorEn 仍混入中文，尝试剥离出纯英文部分
    if author_en and re.search(r'[\u4e00-\u9fff]', author_en):
        mm = re.match(r'^([A-Za-z\.\-\s]+)', author_en)
        if mm and mm.group(1).strip():
            author_en = mm.group(1).strip()
    if not author_zh:
        m = re.match(r'^([A-Za-z\.\-\s]+?)\s+([\u4e00-\u9fff·]+)$', author.strip()) if author else None
        if m:
            author_en = m.group(1).strip()
            author_zh = m.group(2).strip()
    out = {
        'id': meta.get('id', ''),
        'title': title,
        'titleZh': title_zh,
        'titleEn': meta.get('titleEn', '') or title,
        'subtitle': subtitle,
        'author': author_zh or author,
        'authorZh': author_zh,
        'authorEn': author_en,
        'publisher': meta.get('publisher', ''),
        'publisherEn': meta.get('publisherEn', ''),
        'publishYear': meta.get('publishYear', ''),
    }
    return out

def strip_old(html):
    """移除旧的注入内容，保证脚本可反复运行、升级版本时能覆盖旧 JS/CSS。"""
    html = re.sub(r'\n\s*/\* ===== 笔记删除 \+ 批量导出 \(NOTES-EXPORT\) ===== \*/.*?(?=</style>)',
                  '\n', html, flags=re.S)
    html = re.sub(r'\n?<script>\s*window\.BOOK_META=.*?</script>\n?', '\n', html, flags=re.S)
    html = re.sub(r'\n?<script>\s*/\* ============ 笔记删除 \+ 批量导出 \(NOTES-EXPORT\) ============ \*/.*?</script>\n?',
                  '\n', html, flags=re.S)
    return html


def patch(html, book_html_path):
    had = MARK in html
    html = strip_old(html)
    meta = load_meta(book_html_path)
    meta_js = '<script>window.BOOK_META=' + json.dumps(meta, ensure_ascii=False) + ';</script>\n'
    if '</style>' not in html:
        raise RuntimeError('未找到 </style>')
    html = html.replace('</style>', CSS + '</style>', 1)
    if '</body>' not in html:
        raise RuntimeError('未找到 </body>')
    html = html.replace('</body>', meta_js + '<script>' + JS + '</script>\n</body>', 1)
    return html, True

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    for path in sys.argv[1:]:
        if not os.path.isfile(path):
            print('!! 找不到', path); continue
        html = open(path, encoding='utf-8').read()
        out, changed = patch(html, path)
        if changed:
            open(path, 'w', encoding='utf-8').write(out)
            print('✓ 已注入', path)
        else:
            print('= 已存在，跳过', path)

if __name__ == '__main__':
    main()
