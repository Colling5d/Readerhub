#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给「首页 / 在线阅读馆」注入多风格主题切换（幂等，自包含，零外部资源）。

用法:
    python3 scripts/add_home_theme.py                # 默认作用于根目录 index.html
    python3 scripts/add_home_theme.py index.html     # 指定文件
    python3 scripts/add_home_theme.py --remove [files...]

设计:
    - 复用阅读器自带主题的 4 套配色（亮色 / 护眼 / 深色 / 夜间）与字体、字号，
      通过 <html data-theme="..."> 覆盖 CSS 变量实现，金色齿轮按钮固定在左下角。
    - 主题 / 字体 / 字号写入与书页**同一组** localStorage key
      (readerhub_theme / readerhub_font / readerhub_scale)，
      因此主页选一次，进入任何书页都会自动沿用。
    - 与 scripts/add_theme_and_hud.py 保持视觉一致（同一套变量名与控件样式）。
"""
import sys, os, re, argparse

MARK = 'HOME-THEME'

CSS = '''
  /* ===== 首页多风格主题 (HOME-THEME) ===== */
  :root{
    --bg:#faf8f4;--card:#fff;--panel:#fff;--ink:#2b2b2b;--mute:#7a766c;
    --ink-soft:#6f6a60;--accent:#8a4422;--accent-soft:#efe5df;--line:#e6e1d6;
    --reader-font:"Source Serif Pro",Georgia,"Songti SC","Noto Serif CJK SC",serif;
    --reader-scale:1;
  }
  html[data-theme="sepia"]{
    --bg:#f3ead8;--card:#faf3e3;--panel:#faf3e3;--ink:#43382a;--mute:#7d6f58;
    --ink-soft:#7d6f58;--accent:#8a5a2b;--accent-soft:#ece0c6;--line:#ddcfb0;
  }
  html[data-theme="dark"]{
    --bg:#1d2024;--card:#26292e;--panel:#26292e;--ink:#dfe3e8;--mute:#98a0aa;
    --ink-soft:#98a0aa;--accent:#c98b6b;--accent-soft:#33383f;--line:#3a3f46;
    color-scheme:dark;
  }
  html[data-theme="night"]{
    --bg:#0e0f11;--card:#16181b;--panel:#16181b;--ink:#c9ccd1;--mute:#7d838c;
    --ink-soft:#7d838c;--accent:#b0785c;--accent-soft:#202327;--line:#26292e;
    color-scheme:dark;
  }
  html[data-theme="dark"] .tag,html[data-theme="night"] .tag{background:var(--accent-soft);color:var(--ink)}
  html[data-theme="dark"] .tag.lang,html[data-theme="night"] .tag.lang{background:var(--accent);color:#1d2024;font-weight:600}
  html[data-theme="dark"] header,html[data-theme="night"] header{
    background:linear-gradient(180deg,var(--card),var(--bg))}
  html[data-theme="dark"] .card:hover,html[data-theme="night"] .card:hover{
    box-shadow:0 8px 22px rgba(0,0,0,.45)}
  /* 作者行用更深的强调色，保证浅色主题下的可读性 */
  .card .author{color:#6d3419}
  html[data-theme="sepia"] .card .author{color:#6b4319}
  html[data-theme="dark"] .card .author{color:#e0a98a}
  html[data-theme="night"] .card .author{color:#c89074}
  body{font-family:var(--reader-font);font-size:calc(15px * var(--reader-scale,1))}
  body[data-font="sans"]{font-family:"PingFang SC","Microsoft YaHei","Helvetica Neue",Arial,sans-serif}
  #grid{font-size:calc(14px * var(--reader-scale,1))}

  /* --- 主题按钮与面板 --- */
  .home-settings-btn{
    position:fixed;z-index:9991;bottom:22px;left:22px;
    padding:10px 14px;border-radius:999px;border:1px solid var(--line);
    background:var(--card);color:var(--accent);cursor:pointer;font-family:inherit;
    font-size:13px;box-shadow:0 6px 18px rgba(0,0,0,.18);
  }
  .home-settings-btn:hover{filter:brightness(1.06)}
  .home-settings{
    position:fixed;z-index:10002;bottom:70px;left:22px;width:270px;
    background:var(--card);color:var(--ink);border:1px solid var(--line);
    border-radius:12px;box-shadow:0 14px 44px rgba(0,0,0,.28);
    padding:14px 16px 16px;display:none;font-family:inherit;font-size:13px;
  }
  .home-settings.open{display:block}
  .home-settings h4{margin:0 0 10px;font-size:13px;letter-spacing:1px;color:var(--accent);
    text-transform:uppercase}
  .home-settings .rs-row{margin-bottom:14px}
  .home-settings .rs-row:last-child{margin-bottom:0}
  .home-settings .rs-label{font-size:11px;color:var(--mute);margin-bottom:6px;letter-spacing:.5px}
  .home-settings .rs-opts{display:flex;flex-wrap:wrap;gap:6px}
  .home-settings .rs-opt{
    padding:5px 10px;border:1px solid var(--line);border-radius:7px;cursor:pointer;
    background:var(--bg);color:var(--ink);font-size:12.5px;font-family:inherit;line-height:1.2;
  }
  .home-settings .rs-opt:hover{border-color:var(--accent)}
  .home-settings .rs-opt.on{background:var(--accent);color:#fff;border-color:var(--accent)}
  .home-settings .rs-swatches{display:flex;gap:8px;flex-wrap:wrap;padding-bottom:14px}
  .home-settings .rs-sw{width:34px;height:34px;border-radius:8px;border:2px solid var(--line);
    cursor:pointer;position:relative}
  .home-settings .rs-sw.on{border-color:var(--accent);box-shadow:0 0 0 2px var(--accent-soft)}
  .home-settings .rs-sw span{position:absolute;bottom:-15px;left:0;right:0;text-align:center;
    font-size:10px;color:var(--mute)}
  @media (max-width:560px){
    .home-settings-btn{bottom:14px;left:14px;padding:8px 12px;font-size:12px}
    .home-settings{left:14px;right:14px;width:auto;bottom:60px}
  }
'''

BTNS = ('  <button class="home-settings-btn" id="home-settings-btn" '
        'title="切换主题与字体" aria-label="切换主题与字体">&#9881; 主题</button>\n'
        '  <div class="home-settings" id="home-settings" role="dialog" aria-label="主题设置"></div>\n')

JS = r'''
/* ============ 首页多风格主题 (HOME-THEME) ============ */
(function(){
  // 与书页共用同一组 key：主页设置后进入书页自动沿用，反之亦然
  var THEME_KEY = 'readerhub_theme';
  var FONT_KEY  = 'readerhub_font';
  var SCALE_KEY = 'readerhub_scale';

  var THEMES = [
    {id:'light',  name:'亮色',  bg:'#f7f5f0', ink:'#2b2b2b'},
    {id:'sepia',  name:'护眼',  bg:'#f3ead8', ink:'#43382a'},
    {id:'dark',   name:'深色',  bg:'#1d2024', ink:'#dfe3e8'},
    {id:'night',  name:'夜间',  bg:'#0e0f11', ink:'#c9ccd1'}
  ];
  var FONTS = [
    {id:'serif',   name:'宋体', css:'"Source Han Serif SC","Noto Serif SC","Songti SC","SimSun",Georgia,serif'},
    {id:'kai',     name:'楷体', css:'"Kaiti SC","STKaiti","KaiTi","Source Han Serif SC",serif'},
    {id:'sans',    name:'黑体', css:'"PingFang SC","Microsoft YaHei","Helvetica Neue",Arial,sans-serif'},
    {id:'system',  name:'系统', css:'-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif'}
  ];
  var SCALES = [
    {id:'0.9',  name:'小'},
    {id:'1',    name:'中'},
    {id:'1.15', name:'大'},
    {id:'1.3',  name:'特大'}
  ];

  function get(k, d){ try{ return localStorage.getItem(k) || d; }catch(e){ return d; } }
  function set(k, v){ try{ localStorage.setItem(k, v); }catch(e){} }
  function meta(list, id){ for(var i=0;i<list.length;i++) if(list[i].id===id) return list[i]; return list[0]; }

  var curTheme = get(THEME_KEY, 'light');
  var curFont  = get(FONT_KEY,  'serif');
  var curScale = get(SCALE_KEY, '1');

  function applyTheme(id){
    curTheme = id;
    if(id === 'light') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', id);
    try{
      var m = document.querySelector('meta[name="theme-color"]');
      if(!m){ m = document.createElement('meta'); m.name='theme-color'; document.head.appendChild(m); }
      m.content = meta(THEMES, id).bg;
    }catch(e){}
    set(THEME_KEY, id);
  }
  function applyFont(id){
    curFont = id;
    document.documentElement.style.setProperty('--reader-font', meta(FONTS, id).css);
    document.body.setAttribute('data-font', id);
    set(FONT_KEY, id);
  }
  function applyScale(id){
    curScale = String(id);
    document.documentElement.style.setProperty('--reader-scale', curScale);
    set(SCALE_KEY, curScale);
  }

  // 尽早应用，避免闪烁（脚本位于 </body> 前，此处即刻生效）
  applyTheme(curTheme); applyFont(curFont); applyScale(curScale);

  var panel = document.getElementById('home-settings');
  var btn = document.getElementById('home-settings-btn');

  function render(){
    var h = '<h4>显示设置</h4>';
    h += '<div class="rs-row"><div class="rs-label">主题</div><div class="rs-swatches">';
    THEMES.forEach(function(t){
      h += '<div class="rs-sw'+(t.id===curTheme?' on':'')+'" data-theme-pick="'+t.id+'" '
        +  'style="background:'+t.bg+'"><span style="color:'+((t.id==='dark'||t.id==='night')?'#bbb':'#666')+'">'+t.name+'</span></div>';
    });
    h += '</div></div>';
    h += '<div class="rs-row"><div class="rs-label">字体</div><div class="rs-opts">';
    FONTS.forEach(function(f){
      h += '<button class="rs-opt'+(f.id===curFont?' on':'')+'" data-font-pick="'+f.id+'" style="font-family:'+f.css+'">'+f.name+'</button>';
    });
    h += '</div></div>';
    h += '<div class="rs-row"><div class="rs-label">字号</div><div class="rs-opts">';
    SCALES.forEach(function(s){
      h += '<button class="rs-opt'+(s.id===curScale?' on':'')+'" data-scale-pick="'+s.id+'">'+s.name+'</button>';
    });
    h += '</div></div>';
    panel.innerHTML = h;
  }
  function toggle(force){
    var open = (typeof force==='boolean') ? force : !panel.classList.contains('open');
    if(open) render();
    panel.classList.toggle('open', open);
  }
  btn.addEventListener('click', function(e){ e.stopPropagation(); toggle(); });
  panel.addEventListener('click', function(e){
    e.stopPropagation();
    var sw = e.target.closest('[data-theme-pick]');
    if(sw){ applyTheme(sw.getAttribute('data-theme-pick')); render(); return; }
    var fo = e.target.closest('[data-font-pick]');
    if(fo){ applyFont(fo.getAttribute('data-font-pick')); render(); return; }
    var sc = e.target.closest('[data-scale-pick]');
    if(sc){ applyScale(sc.getAttribute('data-scale-pick')); render(); return; }
  });
  document.addEventListener('click', function(e){
    if(panel.classList.contains('open') && !e.target.closest('#home-settings') && !e.target.closest('#home-settings-btn'))
      toggle(false);
  });
  document.addEventListener('keydown', function(e){ if(e.key === 'Escape') toggle(false); });
})();
'''


def strip_old(html):
    # 旧 CSS 块
    html = re.sub(r'\n\s*/\* ===== 首页多风格主题 \(HOME-THEME\) ===== \*/.*?(?=</style>)', '\n', html, flags=re.S)
    # 旧按钮 + 面板
    html = re.sub(r'\n?\s*<button class="home-settings-btn".*?</div>\n?', '\n', html, flags=re.S)
    # 旧脚本
    html = re.sub(r'\n?<script>\s*/\* ============ 首页多风格主题 \(HOME-THEME\) ============ \*/.*?</script>\n?', '\n', html, flags=re.S)
    return html


def patch(html):
    html = strip_old(html)
    if '</style>' not in html:
        raise RuntimeError('未找到 </style>')
    html = html.replace('</style>', CSS + '</style>', 1)
    if '</body>' not in html:
        raise RuntimeError('未找到 </body>')
    html = html.replace('</body>', BTNS + '<script>' + JS + '</script>\n</body>', 1)
    return html


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('--remove', action='store_true')
    ap.add_argument('files', nargs='*')
    a = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    targets = a.files or [os.path.join(root, 'index.html')]

    for f in targets:
        if not os.path.isfile(f):
            print('!! 找不到', f); continue
        src = open(f, encoding='utf-8').read()
        if a.remove:
            open(f, 'w', encoding='utf-8').write(strip_old(src))
            print('✓ 已移除主题注入', os.path.relpath(f, root))
            continue
        open(f, 'w', encoding='utf-8').write(patch(src))
        print('✓ 已注入主题', os.path.relpath(f, root))


if __name__ == '__main__':
    main()
