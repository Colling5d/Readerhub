#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给阅读器 index.html 注入「折叠/隐藏左侧目录」交互（幂等）。

用法:
    python3 scripts/add_sidebar_toggle.py books/<id>/index.html
    python3 scripts/add_sidebar_toggle.py books/*/index.html
    python3 scripts/add_sidebar_toggle.py scripts/templates/reader_base.html

特性:
    - 左上角悬浮按钮「☰ 目录」点击折叠/展开侧栏
    - 折叠后正文占满全宽；按钮始终可见
    - 状态记忆在 localStorage（所有书共用）
    - 键盘快捷键：反斜杠 \\  切换
    - 手机端（<=900px）顶栏同样可折叠
"""
import sys, os, re

MARK = 'SIDEBAR-TOGGLE'  # 幂等标记

CSS = '''
  /* ===== 目录折叠交互 (SIDEBAR-TOGGLE) ===== */
  /* 贴在侧栏右缘的竖向把手（经典折叠面板样式），不会遮挡任何内容 */
  .sidebar-toggle{
    position:fixed;z-index:9990;top:50%;
    left:calc(var(--sidebar-w) - 15px);transform:translateY(-50%);
    width:22px;height:52px;border-radius:0 8px 8px 0;
    border:1px solid var(--line);border-left:none;
    background:#fbfaf7;color:var(--accent);cursor:pointer;
    display:inline-flex;align-items:center;justify-content:center;
    font-size:11px;line-height:1;padding:0;
    box-shadow:2px 0 6px rgba(0,0,0,.06);
    transition:left .22s ease, background .15s ease, color .15s ease;
  }
  .sidebar-toggle:hover{background:var(--accent);color:#fff}
  /* 折叠后把手贴到最左 */
  .app.sidebar-collapsed .sidebar-toggle{left:0}

  /* 侧栏折叠动画 */
  .sidebar{transition:margin-left .22s ease}
  .app.sidebar-collapsed .sidebar{margin-left:calc(-1 * var(--sidebar-w))}

  /* 手机端：顶栏折叠，把手改为右上角小圆钮 */
  @media (max-width:900px){
    .sidebar-toggle{
      top:8px;right:8px;left:auto;transform:none;
      width:30px;height:30px;border-radius:7px;border:1px solid rgba(255,255,255,.4);
      background:rgba(0,0,0,.2);color:#fff;box-shadow:none;font-size:14px;
    }
    .sidebar-toggle:hover{background:rgba(0,0,0,.35);color:#fff}
    .app.sidebar-collapsed .sidebar-toggle{left:auto;right:8px;background:var(--accent);border-color:transparent}
    /* 手机上折叠=顶栏收起 */
    .app.sidebar-collapsed .sidebar{max-height:0;min-height:0;border-bottom:none;overflow:hidden}
  }
'''

BUTTON = '''  <button class="sidebar-toggle" id="sidebar-toggle" title="隐藏 / 显示目录（快捷键 \\\\）" aria-label="隐藏或显示目录">&#9776;</button>
'''

JS = '''
/* ============ 目录折叠交互 (SIDEBAR-TOGGLE) ============ */
(function(){
  var KEY = 'readerhub_sidebar_collapsed';
  var app = document.querySelector('.app');
  if(!app) return;
  function getCollapsed(){
    try{ return localStorage.getItem(KEY) === '1'; }catch(e){ return false; }
  }
  function setCollapsed(v){
    app.classList.toggle('sidebar-collapsed', !!v);
    try{ localStorage.setItem(KEY, v ? '1' : '0'); }catch(e){}
    var btn = document.getElementById('sidebar-toggle');
    if(btn){
      btn.innerHTML = v ? '&#10095;' : '&#10094;';   // 折叠时 ›（展开），展开时 ‹（收起）
      btn.setAttribute('aria-expanded', String(!v));
    }
  }
  // 初始
  setCollapsed(getCollapsed());
  var btn = document.getElementById('sidebar-toggle');
  if(btn){
    btn.addEventListener('click', function(e){ e.stopPropagation(); setCollapsed(!app.classList.contains('sidebar-collapsed')); });
  }
  // 快捷键：反斜杠 \  切换
  document.addEventListener('keydown', function(e){
    if(e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable)) return;
    if(e.key === '\\\\' || e.key === '|'){ setCollapsed(!app.classList.contains('sidebar-collapsed')); }
  });
})();
'''

def patch(html):
    if MARK in html:
        return html, False
    # 1) CSS 注入到 </style> 前
    if '</style>' not in html:
        raise RuntimeError('未找到 </style>')
    html = html.replace('</style>', CSS + '</style>', 1)
    # 2) 按钮注入到 <div class="app"> 之后
    m = re.search(r'(<div class="app">\s*)', html)
    if not m:
        raise RuntimeError('未找到 <div class="app">')
    html = html[:m.end()] + BUTTON + html[m.end():]
    # 3) JS 注入到 </body> 前
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
