#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给阅读器注入「脚注悬浮提示 + 高亮保留脚注」（幂等）。

用法:
    python3 scripts/add_footnote_tooltips.py books/<id>/index.html
    python3 scripts/add_footnote_tooltips.py books/*/index.html

背景:
    正文里以 <sup>6</sup>（新书）或明文 ^{6}（旧书）形式嵌入脚注编号；注释正文集中在
    每本书的 `notes` 章节，按「章」分组、每章从 1 重新编号。本脚本：

    1) 运行时从 EN/ZH 的 `notes` 章节解析出「章节 -> {编号: 注释文本}」映射；
    2) 把正文里的脚注统一成 <sup class="fnmark" data-fn="N">N</sup>：
       支持 <sup>N</sup>、被转义的 &lt;sup&gt;、明文 ^{N}、以及 $^{N}$ 四种写法；
    3) 悬停 / 点击标记时浮层显示注释（同语言优先，缺失回退另一语言）；
    4) 【修复】高亮笔记重绘时会把 <sup>N</sup> 拍平成纯文本 "N"，导致脚注失效。
       这里包裹 renderMarks：重绘前把 .fnmark 换成哨兵文本（不可见字符包裹数字，
       偏移与 textContent 一致），重绘后再还原为 <sup>，脚注与高亮可共存。
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

JS = r'''/* ============ 脚注悬浮提示 (FOOTNOTE-TOOLTIP) ============ */
(function(){
  if(typeof EN === 'undefined') return;

  /* ---------- 1) 解析 notes 章节 -> 章节脚注映射 ---------- */
  var FN = {};   // FN[secId] = { en:{num:text}, zh:{num:text} }

  function normTitle(t){
    return String(t||'').toLowerCase()
      .replace(/^\s*\d+\s*\/\s*/, '')       // "274 / Notes to Introduction" -> notes to introduction
      .replace(/notes?\s+to\s+/, '')         // notes to introduction -> introduction
      .replace(/^\s*(chapter|ch\.?)\s*/,'')  // chapter 1 -> 1
      .replace(/[^a-z0-9\u4e00-\u9fa5]+/g,' ').trim();
  }
  // 从一段文本里抽出「编号 -> 注释文本」（宽松：编号可出现于行首或行中）
  function extractNotes(t){
    var out = [];
    var s = String(t||'');
    var marks = [];
    var r2 = /(?:^|[\s.。])(\d{1,3})\s*[.、]\s*/g, m2;
    while((m2 = r2.exec(s))){
      var lead = m2[0].length - m2[0].replace(/^[\s.。]/,'').length;
      marks.push({ n: parseInt(m2[1],10), at: m2.index + lead, end: r2.lastIndex });
    }
    for(var i=0;i<marks.length;i++){
      var chunkStart = marks[i].end;
      var chunkEnd = (i+1<marks.length) ? marks[i+1].at : s.length;
      out.push({ n: marks[i].n, text: s.slice(chunkStart, chunkEnd).trim() });
    }
    return out;
  }
  function stripNum(t){
    return String(t || '').replace(/^\s*\d{1,3}[.、\s]\s*/, '').trim();
  }
  function hasSup(t){
    t = t || '';
    return /<sup\b/i.test(t) || /\\\^\{|\\\^\{|\\\^\\\{/.test(t) || /\^\{/.test(t);
  }
  function footnoteSections(ARR){
    return ARR.filter(function(s){
      if(s.id === 'notes') return false;
      return (s.paras || []).some(function(p){ return hasSup(p.text); });
    });
  }
  function noteSec(ARR){
    for(var i=0;i<ARR.length;i++){ if(ARR[i].id === 'notes') return ARR[i]; }
    return null;
  }
  // 收集某章节正文里出现过的脚注编号
  function numbersIn(sec){
    var nums = {};
    (sec.paras||[]).forEach(function(p){
      var t = p.text||''; var m;
      var r1=/<sup[^>]*data-fn=["']?(\d{1,3})/g; while((m=r1.exec(t))) nums[+m[1]]=1;
      var r1b=/<sup[^>]*>(\d{1,3})<\/sup>/g; while((m=r1b.exec(t))) nums[+m[1]]=1;
      var r2=/\^\{(\[?\d{1,3}\]?)\}/g; while((m=r2.exec(t))) nums[+m[1].replace(/[\[\]]/g,'')]=1;
    });
    return nums;
  }
  /* 组注释：优先用 notes 里的 title 切章（多数书标题清晰）；
     title 缺失/错位时退回「编号回落到 1」切分。 */
  function buildFragGroups(nsec){
    var groups = [], cur = null;
    (nsec.paras||[]).forEach(function(p){
      if(p.type === 'title'){
        cur = { title: p.text||'', nums:{} };
        groups.push(cur); return;
      }
      if(!cur){ cur = { title:'', nums:{} }; groups.push(cur); }
      extractNotes(p.text).forEach(function(x){
        if(!x.n) return;
        if(!(x.n in cur.nums) && x.text) cur.nums[x.n] = x.text;
      });
    });
    return groups;
  }
  function matchGroup(groups, sec, used){
    var st = normTitle(sec.title || sec.id), sid = normTitle(sec.id);
    for(var i=0;i<groups.length;i++){
      if(used[i]) continue;
      var gt = normTitle(groups[i].title);
      if(!gt) continue;
      if(gt===st || gt===sid || (sid && gt.indexOf(sid)>=0) || (st && gt.indexOf(st)>=0)) return i;
    }
    return -1;
  }
  /* 分派：先按 title 对齐各章节；对仍未覆盖的编号，用「整体片段池」按序回填。 */
  function assignNotes(nsec, secs){
    var groups = buildFragGroups(nsec);
    var result = secs.map(function(){ return {}; });
    var usedG = {};
    secs.forEach(function(sec, si){
      var gi = matchGroup(groups, sec, usedG);
      if(gi >= 0){
        usedG[gi] = 1;
        var nums = groups[gi].nums, want = numbersIn(sec);
        Object.keys(want).forEach(function(n){ if(nums[n]) result[si][n] = nums[n]; });
      }
    });
    // 回填：把所有片段按编号收集（保序），给缺失的章节补
    var pool = {};
    groups.forEach(function(g){ Object.keys(g.nums).forEach(function(n){ (pool[n]=pool[n]||[]).push(g.nums[n]); }); });
    var poolIdx = {};
    secs.forEach(function(sec, si){
      Object.keys(numbersIn(sec)).forEach(function(n){
        if(result[si][n]) return;
        var arr = pool[n]; if(!arr || !arr.length) return;
        var k = poolIdx[n]||0;
        if(k < arr.length){ result[si][n] = arr[k]; poolIdx[n] = k+1; }
      });
    });
    return result;
  }
  ['en','zh'].forEach(function(lang){
    var ARR = (lang === 'en') ? EN : ((typeof ZH !== 'undefined') ? ZH : []);
    var nsec = noteSec(ARR);
    if(!nsec) return;
    var secs = footnoteSections(ARR);
    var assigned = assignNotes(nsec, secs);
    secs.forEach(function(sec, idx){
      var sid = sec.id;
      FN[sid] = FN[sid] || {en:{}, zh:{}};
      FN[sid][lang] = assigned[idx] || {};
    });
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

  /* ---------- 3) 统一脚注表示 ----------
     正文里可能出现的脚注写法：
        a) <sup>14</sup>             （新书）
        b) ^{14}  / ${}^{14}$        （旧书，明文）
     二者统一为：
        <sup class="fnmark" data-fn="14">14</sup>
     关键点：其 textContent 恰为 "14"，与用户阅读所见一致，偏移稳定。 */
  function markHTML(n){ return '<sup class="fnmark" data-fn="' + n + '">' + n + '</sup>'; }

  function normalizeHTML(html){
    // a) 真正的 <sup>（含已有 fnmark，保持不动）
    html = html.replace(/<sup\b([^>]*)>(\s*\d{1,3}\s*)<\/sup>/g, function(m, attrs, n){
      if(/data-fn=/.test(attrs)) return m;                 // 已标注
      return markHTML(String(n).replace(/\s/g,''));
    });
    // a2) 被转义的 &lt;sup&gt;
    html = html.replace(/&lt;sup\b[^&]*?&gt;(\s*\d{1,3}\s*)&lt;\/sup&gt;/g, function(m, n){
      return markHTML(String(n).replace(/\s/g,''));
    });
    // b2) $^{N}$ / ${}^{N}$（先处理，避免 $ 包壳被下面的 ^{N} 规则拆坏）
    html = html.replace(/\$\s*\{?\s*\}\s*\^?\s*\{\s*(\[?\d{1,3}\]?)\s*\}\s*\$/g, function(m, n){
      var v = String(n).replace(/[\[\]]/g,'');
      return v ? markHTML(v) : m;
    });
    // b) ^{N}
    html = html.replace(/\^\{\s*(\[?\d{1,3}\]?)\s*\}/g, function(m, n){
      return markHTML(String(n).replace(/[\[\]]/g,''));
    });
    return html;
  }

  function annotateEl(el){
    if(!el || !el.getAttribute) return;
    if(el.getAttribute('data-fn-done')) return;
    var html = el.innerHTML;
    var out = normalizeHTML(html);
    if(out !== html) el.innerHTML = out;
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

  /* ---------- 4) 让 renderMarks 保留脚注（核心修复） ----------
     renderMarks 以 el.textContent 计算偏移，再用 escText 重建 innerHTML，
     于是 <sup>14</sup> 被拍平成纯文本 "14"（旧书的 "^{14}" 同理），
     导致「高亮一旦覆盖脚注，脚注标记就失效」。

     做法：在调用原 renderMarks 之前，把段落里每个 .fnmark 临时替换成
     一段「哨兵文本」\u2063N\u2063（不可见字符包裹数字），使 textContent/偏移
     完全一致、且不会与普通数字混淆；原 renderMarks 重建完成后，
     再把 HTML 里的 \u2063N\u2063 还原为 <sup class="fnmark" data-fn="N">。 */
  var SEPS = '\u2063';   // invisible separator (哨兵)

  function encloseSups(el){
    // DOM -> 用哨兵文本替换 .fnmark 元素；返回是否替换过
    var sups = el.querySelectorAll('sup.fnmark');
    if(!sups.length) return false;
    for(var i=0;i<sups.length;i++){
      var s = sups[i];
      var n = s.getAttribute('data-fn') || (s.textContent||'').replace(/[\[\]]/g,'');
      s.replaceWith(document.createTextNode(SEPS + n + SEPS));
    }
    return true;
  }
  function restoreSups(el){
    // HTML -> 把哨兵还原为 <sup>（escText 不会改动 \u2063）
    var html = el.innerHTML;
    if(html.indexOf(SEPS) < 0) return;
    // 正常情况：⁣N⁣
    html = html.replace(new RegExp(SEPS + '(\\d{1,3})' + SEPS, 'g'), function(m, n){
      return markHTML(n);
    });
    // 兜底：若高亮边界把数字切开（⁣2</mark>2⁣），合并后再还原
    html = html.replace(new RegExp(SEPS + '([\\s\\S]{1,120}?)' + SEPS, 'g'), function(m, mid){
      var digits = mid.replace(/<[^>]+>/g,'').replace(/\D/g,'');
      return digits ? markHTML(digits) : m;
    });
    el.innerHTML = html;
  }

  /* 让高亮/划线选区「吸附」到整枚脚注：from/to 落在某枚脚注范围内则扩展为整枚，
     避免把脚注数字切成两半，从而与 renderMarks 的哨兵法配合、脚注始终完整。 */
  function snapToFootnotes(el, from, to){
    var sups = el.querySelectorAll('sup.fnmark');
    if(!sups.length) return [from, to];
    for(var i=0;i<sups.length;i++){
      var s = sups[i];
      try{
        var r = document.createRange();
        r.selectNodeContents(el);
        r.setEndBefore(s);
        var sStart = r.toString().length;
        var sLen = (s.textContent || '').length;
        var sEnd = sStart + sLen;
        if(from > sStart && from < sEnd) from = sStart;
        if(to   > sStart && to   < sEnd) to   = sEnd;
      }catch(e){}
    }
    return [from, to];
  }

  if(typeof window.renderMarks === 'function'){
    var __rm = window.renderMarks;
    window.renderMarks = function(el){
      if(el && el.querySelectorAll){
        var had = encloseSups(el);
        var r = __rm.apply(this, arguments);
        if(had) restoreSups(el);
        el.removeAttribute('data-fn-done');
        annotateEl(el);
        return r;
      }
      var r2 = __rm.apply(this, arguments);
      if(el){ el.removeAttribute('data-fn-done'); annotateEl(el); }
      return r2;
    };
    try{ renderMarks = window.renderMarks; }catch(e){}
  }

  /* 包裹 buildNote：把选区偏移吸附到完整脚注，避免切碎脚注数字 */
  if(typeof window.buildNote === 'function'){
    var __bn = window.buildNote;
    window.buildNote = function(){
      var n = __bn.apply(this, arguments);
      if(!n) return n;
      try{
        var el = document.querySelector('p[data-gi="' + n.gi + '"][data-lang="' + n.lang + '"]');
        if(el){
          var snapped = snapToFootnotes(el, n.from, n.to);
          if(snapped[0] !== n.from || snapped[1] !== n.to){
            n.from = snapped[0]; n.to = snapped[1];
            n.text = el.textContent.slice(n.from, n.to);
          }
        }
      }catch(e){}
      return n;
    };
    try{ buildNote = window.buildNote; }catch(e){}
  }

  /* ---------- 5) 事件委托 ---------- */
  function markOf(t){ return (t && t.closest) ? t.closest('.fnmark') : null; }
  function recOf(m){
    var p = m.closest('[data-gi]') || m.closest('[data-sec]') || m.closest('[data-lang]');
    var sid = null, lang = null;
    if(p){
      sid = p.getAttribute('data-sec');
      lang = p.getAttribute('data-lang');
    }
    if(!sid){
      // 兜底：用当前章节
      sid = (typeof current !== 'undefined') ? current : null;
    }
    if(!lang){
      lang = m.closest('#article-zh') ? 'zh' : 'en';
    }
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
