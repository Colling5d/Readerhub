#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给阅读器注入「脚注悬浮提示」（幂等）。

用法:
    python3 scripts/add_footnote_tooltips.py books/<id>/index.html
    python3 scripts/add_footnote_tooltips.py books/*/index.html

背景:
    正文里以 <sup>6</sup> 形式嵌入了脚注编号；注释正文集中在每本书的
    `notes` 章节，并按「章」分组、每章从 1 重新编号。本脚本：

    1) 运行时从 EN/ZH 的 `notes` 章节重新解析出「章节 -> {编号: 注释文本}」映射；
    2) 保留正文中**原有**的 <sup>N</sup> 标记（不删除、不改编号），只在其上
       补一个 data-fn 属性（编号的副本）作为查表键；
    3) 鼠标悬停标记时，浮层显示对应注释内容（同语言优先，缺失则回退到另一语言）；
    4) 顺带修复中文栏：中文正文里的 <sup>N</sup> 之前被 esc() 转义成字面文本，
       这里在渲染后把字面 `&lt;sup&gt;N&lt;/sup&gt;` 还原为真正的上标标记。

    原有的注释章节、正文标记全部保留（「复制一份、不删除之前的」）。
"""
import sys, os

MARK = 'FOOTNOTE-TOOLTIP'

CSS = '''
  /* ===== 脚注悬浮提示 (FOOTNOTE-TOOLTIP) ===== */
  .fnmark{cursor:help;color:var(--accent);font-weight:600;padding:0 1px}
  .fnmark:hover{text-decoration:underline;text-underline-offset:2px}
  #fn-tip{
    position:fixed;z-index:10060;max-width:min(440px,82vw);
    background:var(--panel);color:var(--ink);border:1px solid var(--line);
    border-radius:10px;box-shadow:0 12px 36px rgba(0,0,0,.28);
    padding:10px 13px;font-size:13px;line-height:1.65;
    font-family:var(--reader-font,inherit);
    display:none;pointer-events:none;
  }
  #fn-tip.on{display:block}
  #fn-tip .fn-tip-num{font-size:11px;color:var(--accent);font-weight:700;
    letter-spacing:.6px;margin-bottom:5px}
  #fn-tip .fn-tip-body{max-height:42vh;overflow:auto;white-space:pre-wrap;word-break:break-word}
  #fn-tip .fn-tip-alt{color:var(--ink-soft,#8a8a8a);font-style:italic}
'''

JS = r'''
/* ============ 脚注悬浮提示 (FOOTNOTE-TOOLTIP) ============ */
(function(){
  if(typeof EN === 'undefined') return;

  /* ---------- 1) 解析 notes 章节 -> 章节脚注映射 ---------- */
  var FN = {};   // FN[secId] = { en:{num:text}, zh:{num:text} }

  function numAtStart(t){
    var m = /^\s*(\d{1,3})[.\s]/.exec(t || '');
    return m ? parseInt(m[1], 10) : 0;
  }
  function stripNum(t){
    return String(t || '').replace(/^\s*\d{1,3}[.\s]\s*/, '').trim();
  }
  // 按标题切组，并在「编号回落到 1」处再切一刀（处理缺失的章标题）
  function buildGroups(nsec){
    var groups = [], cur = null;
    (nsec.paras || []).forEach(function(p){
      if(p.type === 'title'){ cur = null; return; }
      var n = numAtStart(p.text);
      if(!n) return;
      if(cur === null || (n === 1 && cur.last > 1)){ cur = {nums:{}, last:0}; groups.push(cur); }
      if(!(n in cur.nums)) cur.nums[n] = p.text;   // 同号重复时保留首个
      if(n > cur.last) cur.last = n;
    });
    return groups.map(function(g){ return g.nums; });
  }
  function footnoteSections(ARR){
    return ARR.filter(function(s){
      if(s.id === 'notes') return false;
      return (s.paras || []).some(function(p){ return /<sup>\d+<\/sup>/.test(p.text || ''); });
    });
  }
  function noteSec(ARR){
    for(var i=0;i<ARR.length;i++){ if(ARR[i].id === 'notes') return ARR[i]; }
    return null;
  }
  ['en','zh'].forEach(function(lang){
    var ARR = (lang === 'en') ? EN : ((typeof ZH !== 'undefined') ? ZH : []);
    var nsec = noteSec(ARR);
    if(!nsec) return;
    var groups = buildGroups(nsec);
    var secs = footnoteSections(ARR);
    for(var k=0;k<secs.length && k<groups.length;k++){
      var sid = secs[k].id;
      FN[sid] = FN[sid] || {en:{}, zh:{}};
      FN[sid][lang] = groups[k];
    }
  });

  /* ---------- 2) 浮层 ---------- */
  var tip = document.getElementById('fn-tip');
  if(!tip){ tip = document.createElement('div'); tip.id = 'fn-tip'; document.body.appendChild(tip); }

  function showTip(el, text, num, alt){
    tip.innerHTML = '';
    var h = document.createElement('div'); h.className = 'fn-tip-num';
    h.textContent = '注释 ' + num + (alt ? '（原文）' : '');
    var b = document.createElement('div'); b.className = 'fn-tip-body';
    b.textContent = text;
    tip.appendChild(h); tip.appendChild(b);
    tip.classList.add('on');
    var r = el.getBoundingClientRect();
    var tw = tip.offsetWidth, th = tip.offsetHeight;
    var left = r.left + r.width/2 - tw/2;
    left = Math.max(8, Math.min(window.innerWidth - tw - 8, left));
    var top = r.top - th - 10;
    if(top < 8) top = r.bottom + 10;
    top = Math.max(8, Math.min(window.innerHeight - th - 8, top));
    tip.style.left = left + 'px';
    tip.style.top = top + 'px';
  }
  function hideTip(){ tip.classList.remove('on'); tip.removeAttribute('data-for'); }

  function lookup(sid, lang, n){
    var rec = FN[sid];
    if(!rec) return null;
    if(rec[lang] && rec[lang][n]) return {text: stripNum(rec[lang][n]), alt:false};
    var other = (lang === 'en') ? 'zh' : 'en';
    if(rec[other] && rec[other][n]) return {text: stripNum(rec[other][n]), alt:true};
    return null;
  }

  /* ---------- 3) 标注正文（保留原标记，仅补 data-fn；并修复中文栏转义） ---------- */
  function annotateEl(el){
    var sid = el.getAttribute('data-sec');
    if(!FN[sid]) return;
    if(el.getAttribute('data-fn-done')) return;
    var html = el.innerHTML, changed = false;
    html = html.replace(/<sup(?:\s[^>]*)?>(\d{1,3})<\/sup>/g, function(m, n){
      changed = true; return '<sup class="fnmark" data-fn="' + n + '">' + n + '</sup>';
    });
    html = html.replace(/&lt;sup&gt;(\d{1,3})&lt;\/sup&gt;/g, function(m, n){
      changed = true; return '<sup class="fnmark" data-fn="' + n + '">' + n + '</sup>';
    });
    if(changed) el.innerHTML = html;
    el.setAttribute('data-fn-done', '1');
  }
  function annotateAll(){
    ['article-en','article-zh'].forEach(function(aid){
      var root = document.getElementById(aid);
      if(!root) return;
      var ps = root.querySelectorAll('[data-gi]');
      for(var i=0;i<ps.length;i++) annotateEl(ps[i]);
    });
  }
  annotateAll();

  // 笔记重绘（renderMarks 会用 textContent 重建 innerHTML）后重新标注
  if(typeof window.renderMarks === 'function'){
    var __rm = window.renderMarks;
    window.renderMarks = function(el){
      var r = __rm.apply(this, arguments);
      if(el){ el.removeAttribute('data-fn-done'); annotateEl(el); }
      return r;
    };
    try{ renderMarks = window.renderMarks; }catch(e){}
  }

  /* ---------- 4) 事件委托 ---------- */
  function markOf(t){ return (t && t.closest) ? t.closest('.fnmark') : null; }
  function recOf(m){
    var p = m.closest('[data-gi]'); if(!p) return null;
    var sid = p.getAttribute('data-sec'), lang = p.getAttribute('data-lang');
    var n = parseInt(m.getAttribute('data-fn'), 10);
    var rec = lookup(sid, lang, n);
    return rec ? {rec:rec, n:n, key:sid + ':' + lang + ':' + n} : null;
  }
  document.addEventListener('mouseover', function(e){
    var m = markOf(e.target); if(!m) return;
    var info = recOf(m); if(!info) return;
    showTip(m, info.rec.text, info.n, info.rec.alt);
  });
  document.addEventListener('mouseout', function(e){
    var m = markOf(e.target); if(!m) return;
    hideTip();
  });
  document.addEventListener('click', function(e){
    var m = markOf(e.target); if(!m) return;
    var info = recOf(m); if(!info) return;
    if(tip.classList.contains('on') && tip.getAttribute('data-for') === info.key){ hideTip(); }
    else { showTip(m, info.rec.text, info.n, info.rec.alt); tip.setAttribute('data-for', info.key); }
  });
  document.addEventListener('keydown', function(e){ if(e.key === 'Escape') hideTip(); });
  window.addEventListener('scroll', hideTip, true);
  window.addEventListener('resize', hideTip);

  window.__annotateFootnotes = annotateAll;
  window.__fnLookup = lookup;
  window.__fnMap = FN;
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
