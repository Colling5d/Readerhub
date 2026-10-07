#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给阅读器 index.html 注入「阅读主题 / 字体设置」与「当前章节 HUD」（幂等）。

用法:
    python3 scripts/add_theme_and_hud.py books/<id>/index.html
    python3 scripts/add_theme_and_hud.py books/*/index.html

特性:
    1) 主题（与首页 add_home_theme.py 完全一致的 15 套）
       - 阅读主题：亮色 / 护眼米黄 / 深色 / 夜间黑
       - 趣味主题：动漫 / 像素 / 赛博朋克 / 水墨 / 森林 / 海洋 /
                  复古报纸 / 糖果 / 热血漫画 / 樱花夜 / 蒸汽波
       - 通过 <html data-theme="..."> 切换，全部用 CSS 变量覆盖实现；
         趣味主题附带纹样背景（纯 CSS 渐变，零外部资源）
       - 选择记忆在 localStorage（所有书与首页共用同一 key，双向同步）
    2) 字体设置
       - 字体族：宋体衬线 / 楷体 / 黑体无衬线 / 系统默认
       - 字号：小 / 中 / 大 / 特大（CSS 变量 --reader-scale 缩放正文）
       - 选择记忆在 localStorage
    3) 当前章节提示（HUD）
       - 显示阅读器右上角的浮动章节药丸；折叠侧栏时自动出现
       - 目录栏展开时，当前章节项高亮为强调色（原有 .active 强化并加深）
       - 随 goTo() 实时更新，并可点击展开目录
"""
import sys, os, re

MARK = 'READER-THEME-HUD'  # 幂等标记

# ---------------------------------------------------------------------------
# 1) CSS
# ---------------------------------------------------------------------------
CSS = '''
  /* ===== 阅读主题 / 字体 / 章节 HUD (READER-THEME-HUD) ===== */

  /* --- 主题：通过 data-theme 覆盖 CSS 变量 --- */
  html[data-theme="sepia"]{
    --bg:#f3ead8;
    --panel:#faf3e3;
    --ink:#43382a;
    --ink-soft:#7d6f58;
    --accent:#8a5a2b;
    --accent-soft:#ece0c6;
    --line:#ddcfb0;
    --lang-head:#ebdfc5;
    --zh:#7a3a13;
    --en:#3a4a2f;
  }
  html[data-theme="dark"]{
    --bg:#1d2024;
    --panel:#26292e;
    --ink:#dfe3e8;
    --ink-soft:#98a0aa;
    --accent:#c98b6b;
    --accent-soft:#33383f;
    --line:#3a3f46;
    --lang-head:#2b2f35;
    --zh:#e6a08a;
    --en:#8fb6e8;
  }
  html[data-theme="night"]{
    --bg:#0e0f11;
    --panel:#16181b;
    --ink:#c9ccd1;
    --ink-soft:#7d838c;
    --accent:#b0785c;
    --accent-soft:#202327;
    --line:#26292e;
    --lang-head:#181a1d;
    --zh:#d99a84;
    --en:#84a9d6;
  }
  html[data-theme="dark"],html[data-theme="night"]{color-scheme:dark}
  html[data-theme="dark"] body,html[data-theme="night"] body{background:var(--bg);color:var(--ink)}
  html[data-theme="dark"] .sidebar,html[data-theme="night"] .sidebar{background:var(--panel)}
  html[data-theme="dark"] .sidebar .brand,html[data-theme="night"] .sidebar .brand{color:#fff}
  html[data-theme="dark"] .search-box #search-input,
  html[data-theme="night"] .search-box #search-input{background:var(--bg);color:var(--ink);border-color:var(--line)}
  html[data-theme="dark"] .search-results,
  html[data-theme="night"] .search-results{background:var(--panel);border-color:var(--line)}
  html[data-theme="dark"] .sr-item,html[data-theme="night"] .sr-item{border-bottom-color:var(--line)}
  html[data-theme="dark"] .sr-item:hover,html[data-theme="night"] .sr-item:hover{background:var(--accent-soft)}
  html[data-theme="dark"] .col.en,html[data-theme="night"] .col.en{color:var(--ink)}
  html[data-theme="dark"] .note,html[data-theme="night"] .note{color:var(--ink-soft)}
  html[data-theme="dark"] #note-toolbar,html[data-theme="dark"] #note-panel,
  html[data-theme="night"] #note-toolbar,html[data-theme="night"] #note-panel{background:var(--panel);color:var(--ink);border-color:var(--line)}
  html[data-theme="dark"] #note-panel .np-head,html[data-theme="night"] #note-panel .np-head{background:var(--panel);border-bottom-color:var(--line)}
  html[data-theme="dark"] #note-panel .np-item:hover,html[data-theme="night"] #note-panel .np-item:hover{background:var(--accent-soft)}
  html[data-theme="dark"] #note-toolbar .nt,html[data-theme="night"] #note-toolbar .nt{background:var(--bg);color:var(--ink);border-color:var(--line)}
  html[data-theme="dark"] .sidebar-toggle,html[data-theme="night"] .sidebar-toggle{background:var(--panel);color:var(--accent)}
  html[data-theme="dark"] ::-webkit-scrollbar-thumb,html[data-theme="night"] ::-webkit-scrollbar-thumb{background:#4a4f57}
  html[data-theme="sepia"] .sidebar{background:#faf3e3}

  /* ===================================================================
     趣味主题（与首页 add_home_theme.py 保持一致）：配色 + 纹样 + 装饰
     阅读器变量集：--bg --panel --ink --ink-soft --accent --accent-soft
                   --line --lang-head --zh --en
     =================================================================== */

  /* 动漫 */
  html[data-theme="anime"]{
    --bg:#fdf2f6;--panel:#ffffff;--ink:#3b2c3a;--ink-soft:#6f5266;
    --accent:#e26d9c;--accent-soft:#fbe0ec;--line:#f3d3e0;
    --lang-head:#fbe7f0;--zh:#a83a66;--en:#255f80;
    --rv-radius:18px;
    --rv-pattern:
      radial-gradient(circle at 12% 18%, rgba(255,183,206,.55) 0 6px, transparent 7px),
      radial-gradient(circle at 82% 62%, rgba(170,208,255,.5) 0 5px, transparent 6px),
      radial-gradient(circle at 40% 84%, rgba(255,214,102,.45) 0 4px, transparent 5px),
      radial-gradient(circle at 66% 12%, rgba(255,183,206,.4) 0 4px, transparent 5px);
    --rv-pattern-size:520px 520px,460px 460px,600px 600px,480px 480px;
  }
  /* 像素 */
  html[data-theme="pixel"]{
    --bg:#1a1c2c;--panel:#2b2d42;--ink:#f4f4f4;--ink-soft:#a7acce;
    --accent:#41e0a0;--accent-soft:#22303a;--line:#3b3f5c;
    --lang-head:#222436;--zh:#86f0c2;--en:#8fb6e8;
    --rv-radius:0px;--rv-font:"Courier New",ui-monospace,monospace;
    --rv-pattern:
      linear-gradient(rgba(65,224,160,.09) 1px, transparent 1px),
      linear-gradient(90deg, rgba(65,224,160,.09) 1px, transparent 1px);
    --rv-pattern-size:22px 22px;color-scheme:dark;
  }
  /* 赛博朋克 */
  html[data-theme="cyber"]{
    --bg:#07070f;--panel:#101024;--ink:#d8e6ff;--ink-soft:#95a2d0;
    --accent:#00e5ff;--accent-soft:#161a3a;--line:#2a2f5c;
    --lang-head:#131634;--zh:#7df3ff;--en:#ff9ce8;
    --rv-radius:6px;--rv-font:ui-monospace,"SFMono-Regular",Menlo,monospace;
    --rv-pattern:
      repeating-linear-gradient(0deg, rgba(0,229,255,.07) 0 1px, transparent 1px 42px),
      repeating-linear-gradient(90deg, rgba(255,0,200,.07) 0 1px, transparent 1px 42px);
    --rv-pattern-size:auto;color-scheme:dark;
  }
  /* 水墨 */
  html[data-theme="ink"]{
    --bg:#f6f3ec;--panel:#fbf9f3;--ink:#20201d;--ink-soft:#57544b;
    --accent:#9c2b25;--accent-soft:#ece5d8;--line:#d8d2c4;
    --lang-head:#efe9dc;--zh:#8a2a22;--en:#3f4a55;
    --rv-radius:4px;--rv-font:"STKaiti","Kaiti SC","KaiTi",serif;
    --rv-pattern:
      radial-gradient(ellipse 55% 38% at 8% 12%, rgba(40,40,40,.07), transparent 70%),
      radial-gradient(ellipse 42% 30% at 92% 82%, rgba(40,40,40,.055), transparent 72%),
      radial-gradient(ellipse 30% 22% at 72% 22%, rgba(156,43,37,.05), transparent 70%);
    --rv-pattern-size:auto;
  }
  /* 森林 */
  html[data-theme="forest"]{
    --bg:#f1f5ee;--panel:#ffffff;--ink:#243024;--ink-soft:#5b6a55;
    --accent:#3f7d4f;--accent-soft:#e0eede;--line:#cfe0cb;
    --lang-head:#e8f2e5;--zh:#2f6a3c;--en:#4a5f7a;
    --rv-radius:14px;--rv-font:"Yuanti SC","PingFang SC",serif;
    --rv-pattern:
      radial-gradient(circle at 20% 30%, rgba(104,160,104,.14) 0 14px, transparent 15px),
      radial-gradient(circle at 70% 70%, rgba(104,160,104,.1) 0 20px, transparent 21px),
      radial-gradient(circle at 88% 18%, rgba(160,140,90,.12) 0 10px, transparent 11px);
    --rv-pattern-size:600px 600px,700px 700px,500px 500px;
  }
  /* 海洋 */
  html[data-theme="ocean"]{
    --bg:#eef6fb;--panel:#ffffff;--ink:#14313f;--ink-soft:#4d7183;
    --accent:#1273a8;--accent-soft:#dcecf6;--line:#c9e0ee;
    --lang-head:#e3f1f9;--zh:#0d5f8a;--en:#2b6a8f;
    --rv-radius:16px;--rv-font:"Yuanti SC","PingFang SC",serif;
    --rv-pattern:
      repeating-radial-gradient(circle at 50% 120%, rgba(18,115,168,.07) 0 2px, transparent 2px 26px);
    --rv-pattern-size:auto;
  }
  /* 复古报纸 */
  html[data-theme="news"]{
    --bg:#f2ede1;--panel:#fbf7ec;--ink:#23211c;--ink-soft:#5c5849;
    --accent:#8c2d22;--accent-soft:#e7e0d1;--line:#cbc3b0;
    --lang-head:#eee8da;--zh:#8c2d22;--en:#3f4a55;
    --rv-radius:2px;--rv-font:"Times New Roman",Georgia,serif;
    --rv-pattern:
      repeating-linear-gradient(90deg, rgba(60,55,40,.05) 0 1px, transparent 1px 4px),
      repeating-linear-gradient(0deg, rgba(60,55,40,.05) 0 1px, transparent 1px 4px);
    --rv-pattern-size:auto;
  }
  /* 糖果 */
  html[data-theme="candy"]{
    --bg:#fff7f0;--panel:#ffffff;--ink:#3d2f3a;--ink-soft:#6f5866;
    --accent:#e85c37;--accent-soft:#ffe6de;--line:#ffd0bf;
    --lang-head:#fff0ea;--zh:#b23a1a;--en:#255f80;
    --rv-radius:20px;--rv-font:"Yuanti SC","PingFang SC",serif;
    --rv-pattern:
      repeating-conic-gradient(from 0deg at 20% 25%, rgba(255,196,102,.16) 0deg 8deg, transparent 8deg 45deg),
      repeating-conic-gradient(from 0deg at 78% 72%, rgba(120,200,255,.14) 0deg 10deg, transparent 10deg 50deg);
    --rv-pattern-size:auto;
  }
  /* 热血漫画 */
  html[data-theme="manga"]{
    --bg:#fbfbfb;--panel:#ffffff;--ink:#111111;--ink-soft:#4a4a4a;
    --accent:#e0a800;--accent-soft:#f5eccd;--line:#d8d8d8;
    --lang-head:#f2f2f2;--zh:#8a5f00;--en:#333333;
    --rv-radius:4px;--rv-font:"Impact","Haettenschweiler","Arial Black",sans-serif;
    --rv-pattern:radial-gradient(circle at 1px 1px, rgba(0,0,0,.16) 1.2px, transparent 0);
    --rv-pattern-size:13px 13px;
  }
  /* 樱花夜 */
  html[data-theme="sakura"]{
    --bg:#1b1430;--panel:#241a3d;--ink:#f0e6ff;--ink-soft:#b3a5d6;
    --accent:#ff9ecb;--accent-soft:#312348;--line:#3a2c58;
    --lang-head:#211838;--zh:#ffb6d5;--en:#b9a7ff;
    --rv-radius:16px;
    --rv-pattern:
      radial-gradient(circle at 16% 22%, rgba(255,158,203,.22) 0 5px, transparent 6px),
      radial-gradient(circle at 68% 58%, rgba(180,160,255,.2) 0 4px, transparent 5px),
      radial-gradient(circle at 42% 82%, rgba(255,158,203,.16) 0 6px, transparent 7px);
    --rv-pattern-size:420px 420px,520px 520px,600px 600px;color-scheme:dark;
  }
  /* 蒸汽波 */
  html[data-theme="vapor"]{
    --bg:#241b4a;--panel:#2e2360;--ink:#f7e9ff;--ink-soft:#c3b3f0;
    --accent:#ff77e1;--accent-soft:#3a2a6b;--line:#453678;
    --lang-head:#2a1f57;--zh:#ffa4ec;--en:#8fd8ff;
    --rv-radius:8px;--rv-font:"Trebuchet MS","PingFang SC",sans-serif;
    --rv-pattern:
      repeating-linear-gradient(0deg, rgba(0,229,255,.13) 0 1px, transparent 1px 34px),
      repeating-linear-gradient(90deg, rgba(255,119,225,.13) 0 1px, transparent 1px 34px);
    --rv-pattern-size:auto;color-scheme:dark;
  }

  /* --- 侧栏跟随主题面板色（原书硬编码 #fbfaf7，这里统一改为 --panel） --- */
  html[data-theme] .sidebar{background:var(--panel)}

  /* --- 趣味主题：所有暗色系通用覆盖（保持正文可读） --- */
  html[data-theme="pixel"] body,html[data-theme="cyber"] body,
  html[data-theme="sakura"] body,html[data-theme="vapor"] body{background:var(--bg);color:var(--ink)}
  html[data-theme="pixel"] .sidebar,html[data-theme="cyber"] .sidebar,
  html[data-theme="sakura"] .sidebar,html[data-theme="vapor"] .sidebar{background:var(--panel)}
  html[data-theme="pixel"] .sidebar .brand,html[data-theme="cyber"] .sidebar .brand,
  html[data-theme="sakura"] .sidebar .brand,html[data-theme="vapor"] .sidebar .brand{color:var(--ink)}
  html[data-theme="pixel"] .search-box #search-input,html[data-theme="cyber"] .search-box #search-input,
  html[data-theme="sakura"] .search-box #search-input,html[data-theme="vapor"] .search-box #search-input{
    background:var(--bg);color:var(--ink);border-color:var(--line)}
  html[data-theme="pixel"] .search-results,html[data-theme="cyber"] .search-results,
  html[data-theme="sakura"] .search-results,html[data-theme="vapor"] .search-results{
    background:var(--panel);border-color:var(--line)}
  html[data-theme="pixel"] .sr-item:hover,html[data-theme="cyber"] .sr-item:hover,
  html[data-theme="sakura"] .sr-item:hover,html[data-theme="vapor"] .sr-item:hover{background:var(--accent-soft)}
  html[data-theme="pixel"] #note-toolbar,html[data-theme="cyber"] #note-toolbar,
  html[data-theme="sakura"] #note-toolbar,html[data-theme="vapor"] #note-toolbar,
  html[data-theme="pixel"] #note-panel,html[data-theme="cyber"] #note-panel,
  html[data-theme="sakura"] #note-panel,html[data-theme="vapor"] #note-panel{
    background:var(--panel);color:var(--ink);border-color:var(--line)}
  html[data-theme="pixel"] #note-panel .np-item:hover,html[data-theme="cyber"] #note-panel .np-item:hover,
  html[data-theme="sakura"] #note-panel .np-item:hover,html[data-theme="vapor"] #note-panel .np-item:hover{
    background:var(--accent-soft)}
  html[data-theme="pixel"] .sidebar-toggle,html[data-theme="cyber"] .sidebar-toggle,
  html[data-theme="sakura"] .sidebar-toggle,html[data-theme="vapor"] .sidebar-toggle{
    background:var(--panel);color:var(--accent)}
  html[data-theme="pixel"] ::-webkit-scrollbar-thumb,html[data-theme="cyber"] ::-webkit-scrollbar-thumb,
  html[data-theme="sakura"] ::-webkit-scrollbar-thumb,html[data-theme="vapor"] ::-webkit-scrollbar-thumb{
    background:#4a4f57}
  html[data-theme="pixel"] .col.en,html[data-theme="cyber"] .col.en,
  html[data-theme="sakura"] .col.en,html[data-theme="vapor"] .col.en{color:var(--ink)}

  /* --- 趣味主题：纹样背景层（固定在正文之后） --- */
  body::before{
    content:"";position:fixed;inset:0;z-index:0;pointer-events:none;
    background:var(--rv-pattern,none);background-size:var(--rv-pattern-size,auto);
    opacity:.95;
  }
  /* 保证正文在纹样之上 */
  .app,.sidebar,.main,.article{position:relative;z-index:1}

  /* --- 趣味主题：装饰（圆角 / 字体族 / 阴影） --- */
  html[data-theme="anime"] .sidebar,html[data-theme="forest"] .sidebar,
  html[data-theme="ocean"] .sidebar,html[data-theme="candy"] .sidebar,
  html[data-theme="sakura"] .sidebar{box-shadow:inset -1px 0 0 var(--line)}
  html[data-theme="pixel"] body{font-family:"Courier New",ui-monospace,monospace}
  html[data-theme="ink"] .chapter-title,html[data-theme="ink"] .p.title{letter-spacing:3px}
  html[data-theme="news"] .chapter-title{letter-spacing:1px;text-transform:uppercase}
  html[data-theme="manga"] .hlmark,html[data-theme="manga"] .senthl{box-shadow:0 0 0 1px #111}
  html[data-theme="cyber"] .chapter-title{text-shadow:0 0 10px rgba(0,229,255,.55),0 0 20px rgba(255,0,200,.35)}
  html[data-theme="cyber"] .reader-settings-btn{background:var(--accent);color:#07070f;border-color:var(--accent);
    box-shadow:0 0 14px rgba(0,229,255,.6)}
  html[data-theme="pixel"] .reader-settings-btn,html[data-theme="pixel"] .reader-settings .rs-opt,
  html[data-theme="pixel"] .reader-settings .rs-sw{border-radius:0}
  html[data-theme="pixel"] .reader-settings-btn{box-shadow:3px 3px 0 #0f1020}
  html[data-theme="manga"] .reader-settings-btn{box-shadow:3px 3px 0 #111}

  /* --- 字体族切换：--reader-font 由 JS 设置 --- */
  body{font-family:var(--reader-font, "Source Han Serif SC","Noto Serif SC","Songti SC","SimSun",Georgia,serif)}
  .chapter-title,.chapter-sub,#note-panel,.makenote,.toc-item,.search-box{font-family:var(--reader-font, inherit)}
  /* EN 栏保留衬线，但跟随所选字体族（楷/黑体时也统一） */
  body[data-font="sans"] .col.en{font-family:"Helvetica Neue",Arial,"PingFang SC","Microsoft YaHei",sans-serif}

  /* --- 字号：--reader-scale 缩放两栏正文 --- */
  .col{font-size:calc(17px * var(--reader-scale,1))}
  .col.en{font-size:calc(16.5px * var(--reader-scale,1))}
  .col.en .p{font-family:inherit}
  .chapter-title{font-size:calc(28px * var(--reader-scale,1))}
  .chapter-sub{font-size:calc(16px * var(--reader-scale,1))}
  .p.title{font-size:calc(22px * var(--reader-scale,1))}
  .note{font-size:calc(15px * var(--reader-scale,1))}

  /* --- 目录当前章节：强化高亮 --- */
  .toc-item.active{background:var(--accent-soft)!important;border-left-color:var(--accent)!important;
    color:var(--accent);font-weight:700}

  /* --- 设置面板（齿轮） --- */
  .reader-settings-btn{
    position:fixed;z-index:9991;bottom:22px;left:22px;
    width:auto;padding:10px 14px;border-radius:999px;border:1px solid var(--line);
    background:var(--panel);color:var(--accent);cursor:pointer;font-family:inherit;
    font-size:13px;box-shadow:0 6px 18px rgba(0,0,0,.18);
  }
  .reader-settings-btn:hover{filter:brightness(1.06)}
  .reader-settings{
    position:fixed;z-index:10002;bottom:70px;left:22px;width:340px;
    max-height:78vh;overflow:auto;
    background:var(--panel);color:var(--ink);border:1px solid var(--line);
    border-radius:12px;box-shadow:0 14px 44px rgba(0,0,0,.28);
    padding:14px 16px 16px;display:none;font-family:var(--reader-font,inherit);font-size:13px;
  }
  .reader-settings.open{display:block}
  .reader-settings h4{margin:0 0 10px;font-size:13px;letter-spacing:1px;color:var(--accent);
    text-transform:uppercase}
  .reader-settings .rs-row{margin-bottom:14px}
  .reader-settings .rs-row:last-child{margin-bottom:0}
  .reader-settings .rs-label{font-size:11px;color:var(--ink-soft);margin-bottom:6px;letter-spacing:.5px}
  .reader-settings .rs-opts{display:flex;flex-wrap:wrap;gap:6px}
  .reader-settings .rs-opt{
    padding:5px 10px;border:1px solid var(--line);border-radius:7px;cursor:pointer;
    background:var(--bg);color:var(--ink);font-size:12.5px;font-family:inherit;line-height:1.2;
  }
  .reader-settings .rs-opt:hover{border-color:var(--accent)}
  .reader-settings .rs-opt.on{background:var(--accent);color:#fff;border-color:var(--accent)}
  .reader-settings .rs-swatches{display:flex;gap:8px;flex-wrap:wrap;padding-bottom:15px}
  .reader-settings .rs-sw{width:34px;height:34px;border-radius:8px;border:2px solid var(--line);
    cursor:pointer;position:relative;overflow:hidden}
  .reader-settings .rs-sw.on{border-color:var(--accent);box-shadow:0 0 0 2px var(--accent-soft)}
  .reader-settings .rs-sw span{position:absolute;bottom:-15px;left:-4px;right:-4px;text-align:center;
    font-size:10px;color:var(--ink-soft);white-space:nowrap}
  .reader-settings .rs-sw .ico{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
    font-size:16px;line-height:1}

  /* --- 当前章节 HUD（侧栏折叠时出现）：紧凑、自动隐去、不遮挡 --- */
  .chapter-hud{
    position:fixed;z-index:9992;top:10px;right:14px;transform:translateY(-10px);
    max-width:min(60vw,420px);
    background:color-mix(in srgb, var(--panel) 82%, transparent);
    -webkit-backdrop-filter:saturate(1.2) blur(6px);backdrop-filter:saturate(1.2) blur(6px);
    color:var(--ink-soft);border:1px solid var(--line);
    border-radius:999px;padding:3px 12px;font-size:12px;line-height:1.5;
    font-family:var(--reader-font,inherit);
    box-shadow:0 3px 12px rgba(0,0,0,.10);cursor:pointer;
    display:inline-flex;align-items:center;gap:6px;
    opacity:0;pointer-events:none;transition:opacity .35s ease,transform .35s ease;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  }
  .chapter-hud .ch-hud-tag{color:var(--accent);font-weight:600;flex:none;opacity:.85}
  .chapter-hud .ch-hud-name{overflow:hidden;text-overflow:ellipsis;max-width:42vw}
  /* 仅在侧栏折叠时可见/可交互 */
  .app.sidebar-collapsed ~ .chapter-hud{pointer-events:auto}
  .app.sidebar-collapsed ~ .chapter-hud.ch-hud-show{opacity:1;transform:translateY(0)}
  .chapter-hud:hover{opacity:1!important;color:var(--ink);border-color:var(--accent)}

  /* 手机端：设置按钮与 HUD 适配 */
  @media (max-width:900px){
    .reader-settings-btn{bottom:14px;left:14px;padding:8px 12px;font-size:12px}
    .reader-settings{left:10px;right:10px;width:auto;bottom:58px}
    .chapter-hud{top:8px;right:10px;bottom:auto;max-width:calc(100vw - 100px);font-size:11px;padding:3px 10px}
    .chapter-hud .ch-hud-name{max-width:52vw}
  }
'''

# ---------------------------------------------------------------------------
# 2) HTML: 设置按钮 + 面板 + HUD
# ---------------------------------------------------------------------------
BUTTONS = '''  <button class="reader-settings-btn" id="reader-settings-btn" title="阅读主题与字体" aria-label="阅读主题与字体">&#9881; 主题</button>
  <div class="reader-settings" id="reader-settings" role="dialog" aria-label="阅读设置"></div>
  <div class="chapter-hud" id="chapter-hud" title="点击展开目录"><span class="ch-hud-tag">当前位置</span><span class="ch-hud-name"></span></div>
'''

# ---------------------------------------------------------------------------
# 3) JS
# ---------------------------------------------------------------------------
JS = r'''
/* ============ 阅读主题 / 字体 / 章节 HUD (READER-THEME-HUD) ============ */
(function(){
  var THEME_KEY = 'readerhub_theme';        // 共用
  var FONT_KEY  = 'readerhub_font';         // 共用
  var SCALE_KEY = 'readerhub_scale';        // 共用

  // group: reading = 阅读主题；fun = 趣味主题（与首页一致）
  var THEMES = [
    {id:'light',  name:'亮色',   bg:'#f7f5f0', ink:'#2b2b2b', group:'reading', ico:'☀'},
    {id:'sepia',  name:'护眼',   bg:'#f3ead8', ink:'#43382a', group:'reading', ico:'📖'},
    {id:'dark',   name:'深色',   bg:'#1d2024', ink:'#dfe3e8', group:'reading', ico:'🌙'},
    {id:'night',  name:'夜间',   bg:'#0e0f11', ink:'#c9ccd1', group:'reading', ico:'🌑'},
    {id:'anime',  name:'动漫',   bg:'#fdf2f6', ink:'#3b2c3a', group:'fun', ico:'🌸'},
    {id:'pixel',  name:'像素',   bg:'#1a1c2c', ink:'#f4f4f4', group:'fun', ico:'👾'},
    {id:'cyber',  name:'赛博朋克', bg:'#07070f', ink:'#d8e6ff', group:'fun', ico:'🛰'},
    {id:'ink',    name:'水墨',   bg:'#f6f3ec', ink:'#20201d', group:'fun', ico:'🖌'},
    {id:'forest', name:'森林',   bg:'#f1f5ee', ink:'#243024', group:'fun', ico:'🌲'},
    {id:'ocean',  name:'海洋',   bg:'#eef6fb', ink:'#14313f', group:'fun', ico:'🌊'},
    {id:'news',   name:'报纸',   bg:'#f2ede1', ink:'#23211c', group:'fun', ico:'📰'},
    {id:'candy',  name:'糖果',   bg:'#fff7f0', ink:'#3d2f3a', group:'fun', ico:'🍬'},
    {id:'manga',  name:'漫画',   bg:'#fbfbfb', ink:'#111111', group:'fun', ico:'💥'},
    {id:'sakura', name:'樱花夜', bg:'#1b1430', ink:'#f0e6ff', group:'fun', ico:'🌸'},
    {id:'vapor',  name:'蒸汽波', bg:'#241b4a', ink:'#f7e9ff', group:'fun', ico:'🎴'}
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

  var curTheme = get(THEME_KEY, 'light');
  var curFont  = get(FONT_KEY,  'serif');
  var curScale = get(SCALE_KEY, '1');

  // 书页现已支持全部 15 套主题（4 阅读 + 11 趣味），与首页完全一致。
  // 兼容旧数据：若 localStorage 里是未知/已废弃的主题 id，回退到亮色。
  function themeMeta(id){ for(var i=0;i<THEMES.length;i++) if(THEMES[i].id===id) return THEMES[i]; return THEMES[0]; }
  function normalizeTheme(id){ for(var i=0;i<THEMES.length;i++) if(THEMES[i].id===id) return id; return 'light'; }
  function fontMeta(id){ for(var i=0;i<FONTS.length;i++) if(FONTS[i].id===id) return FONTS[i]; return FONTS[0]; }

  function applyTheme(id, persist){
    // 书页支持全部 15 套主题。
    // persist=true 时才写回 THEME_KEY（用户手动选择时）。
    id = normalizeTheme(id);
    curTheme = id;
    if(id === 'light'){ document.documentElement.removeAttribute('data-theme'); }
    else{ document.documentElement.setAttribute('data-theme', id); }
    // 顶部/lang-head 品牌色仍用 accent；手机端状态栏色调（支持的浏览器）
    try{
      var m = document.querySelector('meta[name="theme-color"]');
      if(!m){ m = document.createElement('meta'); m.name='theme-color'; document.head.appendChild(m); }
      m.content = themeMeta(id).bg;
    }catch(e){}
    // 用户手动选择时覆盖共用 key；首屏回退应用时不写，保留主页的趣味主题。
    if(persist) set(THEME_KEY, id);
  }
  function applyFont(id){
    curFont = id;
    var f = fontMeta(id);
    document.documentElement.style.setProperty('--reader-font', f.css);
    document.body.setAttribute('data-font', id);
    set(FONT_KEY, id);
  }
  function applyScale(id){
    curScale = String(id);
    document.documentElement.style.setProperty('--reader-scale', curScale);
    set(SCALE_KEY, curScale);
  }

  // ---- 首屏尽早应用（避免闪烁）----
  applyTheme(curTheme, false);  // 首屏不写回 key（避免无谓写入）
  applyFont(curFont);
  applyScale(curScale);

  // ---- 设置面板 ----
  var panel = document.getElementById('reader-settings');
  var btn = document.getElementById('reader-settings-btn');

  function swatch(t){
    var light = (t.ink === '#2b2b2b' || t.ink === '#43382a' || t.ink === '#20201d' ||
                 t.ink === '#243024' || t.ink === '#14313f' || t.ink === '#23211c' ||
                 t.ink === '#3d2f3a' || t.ink === '#3b2c3a' || t.ink === '#111111');
    return '<div class="rs-sw'+(t.id===curTheme?' on':'')+'" data-theme-pick="'+t.id+'" '
      +  'title="'+t.name+'" style="background:'+t.bg+'">'
      +  '<span style="color:'+(light?'#666':'#bbb')+'">'+t.name+'</span>'
      +  '<i class="ico" style="font-style:normal">'+t.ico+'</i></div>';
  }
  function renderPanel(){
    var html = '<h4>阅读设置</h4>';
    html += '<div class="rs-row"><div class="rs-label">阅读主题</div><div class="rs-swatches">';
    THEMES.filter(function(t){return t.group==='reading';}).forEach(function(t){ html += swatch(t); });
    html += '</div></div>';
    html += '<div class="rs-row"><div class="rs-label">趣味主题</div><div class="rs-swatches">';
    THEMES.filter(function(t){return t.group==='fun';}).forEach(function(t){ html += swatch(t); });
    html += '</div></div>';
    html += '<div class="rs-row"><div class="rs-label">字体</div><div class="rs-opts">';
    FONTS.forEach(function(f){
      html += '<button class="rs-opt'+(f.id===curFont?' on':'')+'" data-font-pick="'+f.id+'" style="font-family:'+f.css+'">'+f.name+'</button>';
    });
    html += '</div></div>';
    html += '<div class="rs-row"><div class="rs-label">字号</div><div class="rs-opts">';
    SCALES.forEach(function(s){
      html += '<button class="rs-opt'+(s.id===curScale?' on':'')+'" data-scale-pick="'+s.id+'">'+s.name+'</button>';
    });
    html += '</div></div>';
    panel.innerHTML = html;
  }

  function togglePanel(force){
    var open = (typeof force==='boolean') ? force : !panel.classList.contains('open');
    if(open) renderPanel();
    panel.classList.toggle('open', open);
  }

  btn.addEventListener('click', function(e){ e.stopPropagation(); togglePanel(); });
  panel.addEventListener('click', function(e){
    e.stopPropagation();
    var sw = e.target.closest('[data-theme-pick]');
    if(sw){ applyTheme(sw.getAttribute('data-theme-pick'), true); renderPanel(); return; }
    var fo = e.target.closest('[data-font-pick]');
    if(fo){ applyFont(fo.getAttribute('data-font-pick')); renderPanel(); return; }
    var sc = e.target.closest('[data-scale-pick]');
    if(sc){ applyScale(sc.getAttribute('data-scale-pick')); renderPanel(); return; }
  });
  document.addEventListener('click', function(e){
    if(panel.classList.contains('open') && !e.target.closest('#reader-settings') && !e.target.closest('#reader-settings-btn'))
      togglePanel(false);
  });
  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape') togglePanel(false);
  });

  // ---- 目录项与章节 id 建立映射，修正高亮 + 供 HUD 使用 ----
  // 原书用 `el.textContent.includes(labelOf(id))` 判断高亮，对多数章节失效。
  // 这里改用「TOC 生成顺序 = tocOrder」建立 data-sec-id，按 id 精确高亮。
  var SEC_IDS = [];
  (function stampTocIds(){
    var order = (typeof tocOrder !== 'undefined' && tocOrder) ? tocOrder : null;
    var items = [].slice.call(document.querySelectorAll('.toc-item'));
    if(order && typeof EN !== 'undefined'){
      var ids = order.filter(function(id){ return EN.some(function(s){ return s.id === id; }); });
      if(ids.length === items.length){
        for(var k=0;k<items.length;k++){
          items[k].setAttribute('data-sec-id', ids[k]);
          SEC_IDS.push(ids[k]);
        }
        return;
      }
    }
    // 兜底：没有 tocOrder 时按 EN 顺序
    if(typeof EN !== 'undefined'){
      EN.forEach(function(s, idx){
        if(items[idx]){ items[idx].setAttribute('data-sec-id', s.id); SEC_IDS.push(s.id); }
      });
    }
  })();

  function markActive(id){
    var items = document.querySelectorAll('.toc-item');
    var hit = null;
    for(var k=0;k<items.length;k++){
      var on = items[k].getAttribute('data-sec-id') === id;
      items[k].classList.toggle('active', on);
      if(on) hit = items[k];
    }
    // 让当前章节在目录中保持可见（侧栏未折叠时）
    if(hit && hit.scrollIntoView){ /* 仅在目录自身可滚动时轻推，不移动正文 */ }
    return hit;
  }

  // ---- 当前章节 HUD ----
  var hud = document.getElementById('chapter-hud');
  var hudName = hud.querySelector('.ch-hud-name');
  var hudTimer = null;
  function activeTocLabel(){
    var el = document.querySelector('.toc-item.active');
    if(!el) return '';
    var sub = el.querySelector('.sub');
    var main = el.querySelector('span');
    var t = (main ? main.textContent : el.textContent) || '';
    if(sub && sub.textContent) t = t + ' · ' + sub.textContent;
    return t.replace(/\s+/g,' ').trim();
  }
  function flashHud(){
    hud.classList.add('ch-hud-show');
    clearTimeout(hudTimer);
    hudTimer = setTimeout(function(){ hud.classList.remove('ch-hud-show'); }, 2600);
  }
  function updateHud(){
    hudName.textContent = activeTocLabel();
  }
  window.__updateChapterHud = updateHud;
  window.__flashChapterHud = flashHud;
  window.__markChapterActive = markActive;
  hud.addEventListener('click', function(){
    var app = document.querySelector('.app');
    if(app && app.classList.contains('sidebar-collapsed')){
      var tgl = document.getElementById('sidebar-toggle');
      if(tgl) tgl.click();
    }
  });
  setTimeout(updateHud, 60);

  // goTo() 之后：按 id 精确高亮 + 同步 HUD（兼容原有 __origGoTo 包装）
  function afterGoTo(id){
    if(id) markActive(id);
    updateHud();
    flashHud();
  }
  var __prevGoTo = window.goTo;
  if(typeof __prevGoTo === 'function'){
    window.goTo = function(id){
      var r = __prevGoTo.apply(null, arguments);
      setTimeout(function(){ afterGoTo(id); }, 0);
      return r;
    };
    // 折叠状态变化时短暂展示当前章节（让用户知道现在读到哪）
    var tgl = document.getElementById('sidebar-toggle');
    if(tgl) tgl.addEventListener('click', function(){ setTimeout(function(){ updateHud(); flashHud(); }, 60); });
    // 确定初始章节：优先 localStorage 记忆的位置，其次当前 active 项
    setTimeout(function(){
      var initId = null;
      try{
        for(var k=0;k<localStorage.length;k++){
          var key = localStorage.key(k);
          if(key && key.indexOf('readerhub_pos_') === 0){
            var v = JSON.parse(localStorage.getItem(key) || 'null');
            if(v && v.section){ initId = v.section; break; }
          }
        }
      }catch(e){}
      if(!initId){
        var cur = document.querySelector('.toc-item.active');
        initId = cur ? cur.getAttribute('data-sec-id') : null;
      }
      if(initId) markActive(initId);
      else if(SEC_IDS.length) markActive(SEC_IDS[0]);
      updateHud();
    }, 0);
  }
})();
'''

def strip_old(html):
    """移除旧的注入内容，保证脚本可反复运行、升级版本时能覆盖旧 JS/CSS。"""
    html = re.sub(r'\n\s*/\* ===== 阅读主题 / 字体 / 章节 HUD \(READER-THEME-HUD\) ===== \*/.*?(?=</style>)',
                  '\n', html, flags=re.S)
    # 按钮 + 设置面板 + 章节 HUD（即 BUTTONS 整块）
    html = re.sub(r'\n?\s*<button class="reader-settings-btn".*?<div class="chapter-hud"[^>]*>.*?</div>\s*\n?',
                  '\n', html, flags=re.S)
    html = re.sub(r'\n?<script>\s*/\* ============ 阅读主题 / 字体 / 章节 HUD \(READER-THEME-HUD\) ============ \*/.*?</script>\n?',
                  '\n', html, flags=re.S)
    return html


def patch(html):
    had = MARK in html
    html = strip_old(html)
    if '</style>' not in html:
        raise RuntimeError('未找到 </style>')
    html = html.replace('</style>', CSS + '</style>', 1)
    if '</body>' not in html:
        raise RuntimeError('未找到 </body>')
    html = html.replace('</body>', BUTTONS + '<script>' + JS + '</script>\n</body>', 1)
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
