#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给阅读器 index.html 注入「隐藏 / 显示 原文栏 & 中文栏」交互（幂等）。

适用两种版面：
    1) 书籍/文档双栏版面：<section class="col en"> / <section class="col zh">
    2) 图文三栏版面（如 hyland-lyon）：#imgpane / #enpane / #zhpane

用法:
    python3 scripts/add_lang_toggle.py books/<id>/index.html
    python3 scripts/add_lang_toggle.py books/*/index.html docs/*/index.html

特性:
    - 底部居中悬浮胶囊按钮组：「隐藏英文 / 隐藏中文」，点击即在
      「双语对照 / 仅中文 / 仅原文」三种视图间切换
    - 按钮文案随状态变化（隐藏英文 ⇄ 显示英文），高亮表示当前已隐藏
    - 栏目标签自动从栏头读取，俄文书显示「俄文」、英文书显示「英文」
    - 状态记忆在 localStorage（各书共用）
    - 键盘快捷键：E 切换原文栏，C 切换中文栏
    - 内容为空的一栏（单语书）自动隐藏对应按钮
    - 若原页面已有旧版「隐藏英文」顶栏按钮（#toggle-en），会自动接管并隐藏它
"""
import sys, os, re

MARK = 'LANG-TOGGLE'  # 幂等标记

CSS = '''
  /* ===== 语言栏显示切换 (LANG-TOGGLE) ===== */
  .lang-toggle{
    position:fixed;z-index:9993;bottom:22px;left:50%;transform:translateX(-50%);
    display:inline-flex;align-items:center;gap:2px;padding:3px;
    border-radius:999px;
    background:var(--panel,#fbfaf7);border:1px solid var(--line,#e6e1d6);
    box-shadow:0 6px 18px rgba(0,0,0,.18);
    font-family:var(--reader-font,inherit);
  }
  .lang-toggle .lt-btn{
    border:0;background:transparent;color:var(--ink,#2b2b2b);
    font-family:inherit;font-size:12.5px;line-height:1;white-space:nowrap;
    padding:6px 13px;border-radius:999px;cursor:pointer;
    transition:background .15s ease,color .15s ease;
  }
  .lang-toggle .lt-btn:hover{background:rgba(180,160,120,.20)}
  .lang-toggle .lt-btn.on{background:var(--accent,#b99a5b);color:#fff}
  .lang-toggle .lt-sep{width:1px;height:14px;background:var(--line,#e6e1d6);opacity:.7}

  /* 栏头右上角常驻的「隐藏 / 显示」小按钮（最容易发现的位置） */
  .lt-head-btn{
    float:right;margin:-1px 0 0 12px;padding:2px 11px;
    border:1px solid var(--line,#e6e1d6);border-radius:999px;
    background:var(--panel,#fbfaf7);color:var(--ink,#2b2b2b);
    font-family:inherit;font-size:11px;line-height:1.7;
    letter-spacing:0;text-transform:none;white-space:nowrap;cursor:pointer;
    transition:background .15s ease,color .15s ease;
  }
  .lt-head-btn:hover{background:var(--accent,#b99a5b);color:#fff;border-color:transparent}
  .lt-head-btn.on{background:var(--accent,#b99a5b);color:#fff;border-color:transparent}

  /* 隐藏某一栏：display:none 用 !important 压过 #enpane 之类的 id 选择器 */
  body.rh-hide-en #scroll-en,
  body.rh-hide-en .col.en,
  body.rh-hide-en #enpane{display:none !important}
  body.rh-hide-zh #scroll-zh,
  body.rh-hide-zh .col.zh,
  body.rh-hide-zh #zhpane{display:none !important}

  /* 三栏版面：隐藏一栏后另一栏自动放宽 */
  body.rh-hide-en #zhpane,
  body.rh-hide-zh #enpane{flex:1 1 46%}
  body.rh-hide-en #enpane,
  body.rh-hide-zh #zhpane{flex:0 0 0}

  @media (max-width:900px){
    .lang-toggle{bottom:14px;padding:2px;gap:1px}
    .lang-toggle .lt-btn{font-size:11.5px;padding:5px 9px}
  }
'''

BAR = '''<div class="lang-toggle" id="lang-toggle" role="group" aria-label="语言栏显示切换">
    <button type="button" class="lt-btn" id="lt-en" title="隐藏 / 显示原文栏（快捷键 E）">隐藏英文</button>
    <span class="lt-sep"></span>
    <button type="button" class="lt-btn" id="lt-zh" title="隐藏 / 显示中文栏（快捷键 C）">隐藏中文</button>
  </div>
'''

JS = r'''
/* ============ 语言栏显示切换 (LANG-TOGGLE) ============ */
(function(){
  var KEY = 'readerhub_lang_view';
  var body = document.body;
  var enEls = document.querySelectorAll('#scroll-en, #enpane, .col.en');
  var zhEls = document.querySelectorAll('#scroll-zh, #zhpane, .col.zh');
  if(!enEls.length && !zhEls.length) return;

  var bar = document.getElementById('lang-toggle');
  var bEn = document.getElementById('lt-en');
  var bZh = document.getElementById('lt-zh');

  /* ---- 接管旧版顶栏「隐藏英文」按钮，避免两套状态打架 ---- */
  var legacyBtn = document.getElementById('toggle-en');
  if(legacyBtn){
    legacyBtn.style.display = 'none';
    var wrap = document.getElementById('wrap');
    if(wrap) wrap.classList.remove('hide-en');
    try{ localStorage.removeItem('readerhub_bilingual_hide_en'); }catch(e){}
  }

  /* ---- 从栏头文案推断语言名（英文 / 俄文 / 中文 …） ---- */
  function headText(els){
    for(var i=0;i<els.length;i++){
      var h = els[i].querySelector('.col-head, .panehead, header');
      if(h && h.textContent) return h.textContent;
    }
    return '';
  }
  function bodyText(els){
    var s = '';
    for(var i=0;i<els.length;i++){
      var a = els[i].querySelector('.article') || els[i];
      if(a && a.textContent){ s += a.textContent; if(s.length > 8000) break; }
    }
    return s;
  }
  function cjkRatio(s){
    var m = String(s||'').match(/[\u4e00-\u9fa5]/g);
    return (m && s.length) ? (m.length / s.length) : 0;
  }
  function guess(txt, preferCjk, fallback){
    var seg = String(txt||'').split(/[·•|｜]/);
    var cjk = [], lat = [];
    seg.forEach(function(s){
      s = s.trim(); if(!s) return;
      (/[\u4e00-\u9fa5]/.test(s) ? cjk : lat).push(s);
    });
    var pick = preferCjk ? (cjk[0] || lat[0]) : (lat[0] || cjk[0]);
    pick = String(pick || '');
    pick = pick.replace(/原文|翻译|译文|对照|版|栏/g, '').replace(/[（(].*?[)）]/g, '').trim();
    if(!pick) return fallback;
    if(!/[\u4e00-\u9fa5]/.test(pick)) return fallback;
    return pick.length > 6 ? fallback : pick;
  }
  var enLabel = guess(headText(enEls), true, '英文');
  var zhLabel = guess(headText(zhEls), true, '中文');

  /* ---- 在每一栏的栏头（sticky 顶部）挂一个「隐藏」小按钮 ---- */
  function headBtn(els, which){
    if(!els.length) return null;
    var head = els[0].querySelector('.col-head, .panehead, header');
    if(!head) return null;
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'lt-head-btn';
    b.textContent = '隐藏';
    b.title = '隐藏这一栏（底部「' + (which === 'en' ? '隐藏' + enLabel : '隐藏' + zhLabel)
            + '」按钮可再次显示）';
    b.addEventListener('click', function(e){ e.stopPropagation(); toggle(which); });
    head.appendChild(b);
    return b;
  }
  var hEn = headBtn(enEls, 'en');
  var hZh = headBtn(zhEls, 'zh');

  /* ---- 空栏（单语书）自动藏起对应按钮 ---- */
  function hasContent(els){
    for(var i=0;i<els.length;i++){
      var a = els[i].querySelector('.article') || els[i];
      if(a && a.textContent && a.textContent.replace(/\s+/g,'').length > 40) return true;
    }
    return false;
  }
  function refreshAvailability(){
    // 空栏（单语书）藏起对应按钮
    var cEn = hasContent(enEls), cZh = hasContent(zhEls);
    if(bEn) bEn.style.display = cEn ? '' : 'none';
    if(bZh) bZh.style.display = cZh ? '' : 'none';
    if(hEn) hEn.style.display = cEn ? '' : 'none';
    if(hZh) hZh.style.display = cZh ? '' : 'none';
    // 栏头标题未必靠谱（有的书把中文原文放在“英文栏”），按实际内容语言校正标签
    if(cEn && cjkRatio(bodyText(enEls)) > 0.15) enLabel = '原文';
    if(cZh && cjkRatio(bodyText(zhEls)) < 0.15) zhLabel = '译文';
    paint(false);
  }

  /* ---- 状态 ---- */
  var hideEn = false, hideZh = false;

  function toast(msg){
    if(typeof window.showToast === 'function'){ try{ window.showToast(msg); return; }catch(e){} }
    var t = document.getElementById('note-toast');
    if(t){
      t.textContent = msg; t.style.opacity = '1';
      clearTimeout(t._lt); t._lt = setTimeout(function(){ t.style.opacity = '0'; }, 1400);
    }
  }

  function paint(save){
    body.classList.toggle('rh-hide-en', hideEn);
    body.classList.toggle('rh-hide-zh', hideZh);
    if(bEn){
      bEn.classList.toggle('on', hideEn);
      bEn.textContent = (hideEn ? '显示' : '隐藏') + enLabel;
      bEn.title = (hideEn ? '显示' : '隐藏') + '原文栏（快捷键 E）';
    }
    if(bZh){
      bZh.classList.toggle('on', hideZh);
      bZh.textContent = (hideZh ? '显示' : '隐藏') + zhLabel;
      bZh.title = (hideZh ? '显示' : '隐藏') + '中文栏（快捷键 C）';
    }
    if(hEn) hEn.textContent = hideEn ? '显示' : '隐藏';
    if(hZh) hZh.textContent = hideZh ? '显示' : '隐藏';
    if(save){
      try{ localStorage.setItem(KEY, JSON.stringify({en: hideEn, zh: hideZh})); }catch(e){}
    }
    try{ window.dispatchEvent(new Event('resize')); }catch(e){}
  }

  function toggle(which){
    if(which === 'en'){
      // 不允许两栏同时隐藏：隐藏原文时若中文已隐藏，则自动切回中文
      if(!hideEn && hideZh) hideZh = false;
      hideEn = !hideEn;
    }else{
      if(!hideZh && hideEn) hideEn = false;
      hideZh = !hideZh;
    }
    paint(true);
    if(hideEn) toast('已隐藏' + enLabel + ' · 仅看' + zhLabel);
    else if(hideZh) toast('已隐藏' + zhLabel + ' · 仅看' + enLabel);
    else toast('双语对照');
  }

  if(bEn) bEn.addEventListener('click', function(){ toggle('en'); });
  if(bZh) bZh.addEventListener('click', function(){ toggle('zh'); });

  document.addEventListener('keydown', function(e){
    if(e.ctrlKey || e.metaKey || e.altKey) return;
    var t = e.target;
    if(t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
    var k = (e.key || '').toLowerCase();
    if(k === 'e'){ e.preventDefault(); toggle('en'); }
    else if(k === 'c'){ e.preventDefault(); toggle('zh'); }
  });

  /* ---- 恢复上次偏好 ---- */
  var st = null;
  try{ st = JSON.parse(localStorage.getItem(KEY) || 'null'); }catch(e){}
  if(st && typeof st === 'object'){
    hideEn = !!st.en; hideZh = !!st.zh;
    if(hideEn && hideZh){ hideEn = false; hideZh = false; }  // 脏数据兜底
  }
  paint(false);
  refreshAvailability();
  window.addEventListener('load', function(){
    refreshAvailability();
    setTimeout(refreshAvailability, 600);
  });
})();
'''


def strip_old(html):
    """移除旧的 LANG-TOGGLE 注入块，便于升级重写（返回是否已有旧块）。"""
    had = MARK in html
    if not had:
        return html, False
    html = re.sub(r'\n\s*/\* ===== 语言栏显示切换 \(LANG-TOGGLE\).*?</style>',
                  '\n</style>', html, flags=re.S)
    html = re.sub(r'<div class="lang-toggle".*?</div>\s*', '', html, flags=re.S)
    # 注意：<script> 与注释之间有一个换行，须用 \s* 吸纳
    html = re.sub(r'<script>\s*/\* =+ 语言栏显示切换 \(LANG-TOGGLE\)\s*=+ \*/.*?</script>\n?',
                  '', html, flags=re.S)
    return html, True


def patch(html):
    html, had = strip_old(html)
    if '</style>' not in html:
        raise RuntimeError('未找到 </style>')
    html = html.replace('</style>', CSS + '</style>', 1)
    if '</body>' not in html:
        raise RuntimeError('未找到 </body>')
    html = html.replace('</body>', BAR + '<script>' + JS + '</script>\n</body>', 1)
    return html, ('updated' if had else 'new')


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    ok = upd = err = 0
    for path in sys.argv[1:]:
        if not os.path.isfile(path):
            print('!! 找不到', path); err += 1; continue
        html = open(path, encoding='utf-8').read()
        try:
            out, kind = patch(html)
        except Exception as e:
            print('!! 失败', path, e); err += 1; continue
        open(path, 'w', encoding='utf-8').write(out)
        if kind == 'new':
            print('✓ 已注入', path); ok += 1
        else:
            print('↻ 已更新', path); upd += 1
    print('\n完成：新注入 %d，更新 %d，失败 %d' % (ok, upd, err))


if __name__ == '__main__':
    main()
