#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给「首页 / 在线阅读馆」注入多风格主题切换（幂等，自包含，零外部资源）。

用法:
    python3 scripts/add_home_theme.py                # 默认作用于根目录 index.html
    python3 scripts/add_home_theme.py index.html     # 指定文件
    python3 scripts/add_home_theme.py --remove [files...]

设计:
    - 在阅读器自带的 4 套「阅读主题」（亮色 / 护眼 / 深色 / 夜间）之外，
      追加一组「趣味主题」：动漫 / 像素 / 赛博朋克 / 水墨 / 森林 / 海洋 /
      复古报纸 / 糖果 / 热血漫画 等，每套都带独立配色与纹样。
    - 通过 <html data-theme="..."> 覆盖 CSS 变量实现；纹样用内联 SVG / 渐变
      作为 body 背景，零外部资源。
    - 主题 / 字体 / 字号写入与书页**同一组** localStorage key
      (readerhub_theme / readerhub_font / readerhub_scale)；
      书页只认识 4 套阅读主题，遇到趣味主题时回退为最接近的一套（见映射），
      因此主页选一次，进入任何书页都不会崩。
    - 与 scripts/add_theme_and_hud.py 保持变量名一致。
"""
import sys, os, re, argparse

MARK = 'HOME-THEME'

# ---------------------------------------------------------------------------
# 主题配色 + 纹样
#   每套主题：CSS 变量覆盖（背景/卡片/文字/强调色）+ body 纹样背景
#   pattern: 用作 body::before 的 background 值（可为多层渐变或 SVG data-uri）
#   deco:    额外装饰（如卡片圆角、阴影、字体）
# ---------------------------------------------------------------------------
THEMES_CSS = r'''
  /* ===== 首页多风格主题 (HOME-THEME) ===== */
  :root{
    --bg:#faf8f4;--card:#fff;--panel:#fff;--ink:#2b2b2b;--mute:#7a766c;
    --ink-soft:#6f6a60;--accent:#8a4422;--accent-soft:#efe5df;--line:#e6e1d6;
    --reader-font:"Source Serif Pro",Georgia,"Songti SC","Noto Serif CJK SC",serif;
    --reader-scale:1;
    --radius:12px;
    --pattern:none;
    --pattern-op:0;
    --pattern-size:auto;
    --card-shadow:0 8px 22px rgba(0,0,0,.08);
    --h1-font:var(--reader-font);
  }

  /* ---------- 阅读主题（与书页一致） ---------- */
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

  /* ---------- 趣味主题 ---------- */

  /* 动漫风：樱粉 + 天蓝，圆润柔和 */
  html[data-theme="anime"]{
    --bg:#fdf2f6;--card:#ffffff;--panel:#fff7fb;--ink:#3b2c3a;--mute:#7a5c72;
    --ink-soft:#6f5266;--accent:#e26d9c;--accent-soft:#fbe0ec;--line:#f3d3e0;
    --radius:18px;
    --card-shadow:0 10px 28px rgba(226,109,156,.18);
    --pattern:
      radial-gradient(circle at 12% 18%, rgba(255,183,206,.55) 0 6px, transparent 7px),
      radial-gradient(circle at 82% 62%, rgba(170,208,255,.5) 0 5px, transparent 6px),
      radial-gradient(circle at 40% 84%, rgba(255,214,102,.45) 0 4px, transparent 5px),
      radial-gradient(circle at 66% 12%, rgba(255,183,206,.4) 0 4px, transparent 5px),
      linear-gradient(135deg,#fdf2f6,#eef5ff);
    --pattern-op:1;--pattern-size:520px 520px,460px 460px,600px 600px,480px 480px,auto;
    --h1-font:"Yuanti SC","PingFang SC","Hiragino Sans GB",var(--reader-font);
  }

  /* 像素风：8-bit 调色板，硬边缘、方块阴影 */
  html[data-theme="pixel"]{
    --bg:#1a1c2c;--card:#2b2d42;--panel:#2b2d42;--ink:#f4f4f4;--mute:#8b90b5;
    --ink-soft:#a7acce;--accent:#41e0a0;--accent-soft:#22303a;--line:#3b3f5c;
    --radius:0px;
    --card-shadow:4px 4px 0 #0f1020;
    --pattern:
      linear-gradient(rgba(65,224,160,.09) 1px, transparent 1px),
      linear-gradient(90deg, rgba(65,224,160,.09) 1px, transparent 1px);
    --pattern-op:1;--pattern-size:22px 22px;
    --h1-font:"Courier New",ui-monospace,monospace;
    color-scheme:dark;
  }

  /* 赛博朋克：霓虹青 + 品红，暗底色、发光感 */
  html[data-theme="cyber"]{
    --bg:#07070f;--card:#101024;--panel:#101024;--ink:#d8e6ff;--mute:#7b86b8;
    --ink-soft:#95a2d0;--accent:#00e5ff;--accent-soft:#161a3a;--line:#2a2f5c;
    --radius:6px;
    --card-shadow:0 0 0 1px rgba(0,229,255,.35), 0 0 22px rgba(255,0,200,.25);
    --pattern:
      repeating-linear-gradient(0deg, rgba(0,229,255,.07) 0 1px, transparent 1px 42px),
      repeating-linear-gradient(90deg, rgba(255,0,200,.07) 0 1px, transparent 1px 42px);
    --pattern-op:1;--pattern-size:auto;
    --h1-font:ui-monospace,"SFMono-Regular",Menlo,monospace;
    color-scheme:dark;
  }

  /* 水墨风：宣纸底、墨色字、朱红印 */
  html[data-theme="ink"]{
    --bg:#f6f3ec;--card:#fbf9f3;--panel:#fbf9f3;--ink:#20201d;--mute:#6d6a60;
    --ink-soft:#57544b;--accent:#9c2b25;--accent-soft:#ece5d8;--line:#d8d2c4;
    --radius:4px;
    --card-shadow:0 4px 16px rgba(30,30,20,.1);
    --pattern:
      radial-gradient(ellipse 55% 38% at 8% 12%, rgba(40,40,40,.07), transparent 70%),
      radial-gradient(ellipse 42% 30% at 92% 82%, rgba(40,40,40,.055), transparent 72%),
      radial-gradient(ellipse 30% 22% at 72% 22%, rgba(156,43,37,.05), transparent 70%),
      linear-gradient(180deg,#f7f4ed,#efeadd);
    --pattern-op:1;--pattern-size:auto;
    --h1-font:"STKaiti","Kaiti SC","KaiTi",var(--reader-font);
  }

  /* 森林：墨绿 + 苔藓 + 木色 */
  html[data-theme="forest"]{
    --bg:#f1f5ee;--card:#ffffff;--panel:#f6faf3;--ink:#243024;--mute:#6d7c66;
    --ink-soft:#5b6a55;--accent:#3f7d4f;--accent-soft:#e0eede;--line:#cfe0cb;
    --radius:14px;
    --card-shadow:0 8px 24px rgba(63,125,79,.14);
    --pattern:
      radial-gradient(circle at 20% 30%, rgba(104,160,104,.14) 0 14px, transparent 15px),
      radial-gradient(circle at 70% 70%, rgba(104,160,104,.1) 0 20px, transparent 21px),
      radial-gradient(circle at 88% 18%, rgba(160,140,90,.12) 0 10px, transparent 11px),
      linear-gradient(160deg,#f2f7ef,#e8f1e4);
    --pattern-op:1;--pattern-size:600px 600px,700px 700px,500px 500px,auto;
    --h1-font:"Yuanti SC","PingFang SC",var(--reader-font);
  }

  /* 海洋：深海蓝 + 浪花白 */
  html[data-theme="ocean"]{
    --bg:#eef6fb;--card:#ffffff;--panel:#f4fafd;--ink:#14313f;--mute:#5f7f90;
    --ink-soft:#4d7183;--accent:#1273a8;--accent-soft:#dcecf6;--line:#c9e0ee;
    --radius:16px;
    --card-shadow:0 10px 26px rgba(18,115,168,.16);
    --pattern:
      repeating-radial-gradient(circle at 50% 120%, rgba(18,115,168,.07) 0 2px, transparent 2px 26px),
      linear-gradient(180deg,#f0f8fd,#e2f0f8);
    --pattern-op:1;--pattern-size:auto;
    --h1-font:"Yuanti SC","PingFang SC",var(--reader-font);
  }

  /* 复古报纸：新闻纸 + 墨黑 + 单色 */
  html[data-theme="news"]{
    --bg:#f2ede1;--card:#fbf7ec;--panel:#fbf7ec;--ink:#23211c;--mute:#6f6a5c;
    --ink-soft:#5c5849;--accent:#8c2d22;--accent-soft:#e7e0d1;--line:#cbc3b0;
    --radius:2px;
    --card-shadow:0 2px 0 rgba(0,0,0,.12);
    --pattern:
      repeating-linear-gradient(90deg, rgba(60,55,40,.05) 0 1px, transparent 1px 4px),
      repeating-linear-gradient(0deg, rgba(60,55,40,.05) 0 1px, transparent 1px 4px),
      linear-gradient(180deg,#f3eee2,#ece5d6);
    --pattern-op:1;--pattern-size:auto;
    --h1-font:"Times New Roman",Georgia,serif;
  }

  /* 糖果：奶油底 + 高饱和点缀，俏皮 */
  html[data-theme="candy"]{
    --bg:#fff7f0;--card:#ffffff;--panel:#fff9f4;--ink:#3d2f3a;--mute:#7d6673;
    --ink-soft:#6f5866;--accent:#e85c37;--accent-soft:#ffe6de;--line:#ffd0bf;
    --radius:20px;
    --card-shadow:0 12px 30px rgba(255,122,89,.2);
    --pattern:
      repeating-conic-gradient(from 0deg at 20% 25%, rgba(255,196,102,.16) 0deg 8deg, transparent 8deg 45deg),
      repeating-conic-gradient(from 0deg at 78% 72%, rgba(120,200,255,.14) 0deg 10deg, transparent 10deg 50deg),
      linear-gradient(135deg,#fff8f1,#fff0f4 60%,#eef8ff);
    --pattern-op:1;--pattern-size:auto;
    --h1-font:"Yuanti SC","PingFang SC",var(--reader-font);
  }

  /* 热血漫画：黑白网点 + 冲击黄 */
  html[data-theme="manga"]{
    --bg:#fbfbfb;--card:#ffffff;--panel:#ffffff;--ink:#111111;--mute:#6b6b6b;
    --ink-soft:#4a4a4a;--accent:#e0a800;--accent-soft:#f5eccd;--line:#d8d8d8;
    --radius:4px;
    --card-shadow:5px 5px 0 #111111;
    --pattern:
      radial-gradient(circle at 1px 1px, rgba(0,0,0,.16) 1.2px, transparent 0);
    --pattern-op:1;--pattern-size:13px 13px;
    --h1-font:"Impact","Haettenschweiler","Arial Black",sans-serif;
  }

  /* 樱花夜：深紫底 + 粉色花瓣 */
  html[data-theme="sakura"]{
    --bg:#1b1430;--card:#241a3d;--panel:#241a3d;--ink:#f0e6ff;--mute:#9a8cc0;
    --ink-soft:#b3a5d6;--accent:#ff9ecb;--accent-soft:#312348;--line:#3a2c58;
    --radius:16px;
    --card-shadow:0 10px 30px rgba(255,158,203,.18);
    --pattern:
      radial-gradient(circle at 16% 22%, rgba(255,158,203,.22) 0 5px, transparent 6px),
      radial-gradient(circle at 68% 58%, rgba(180,160,255,.2) 0 4px, transparent 5px),
      radial-gradient(circle at 42% 82%, rgba(255,158,203,.16) 0 6px, transparent 7px),
      linear-gradient(160deg,#1b1430,#221838 60%,#1a1230);
    --pattern-op:1;--pattern-size:420px 420px,520px 520px,600px 600px,auto;
    color-scheme:dark;
  }

  /* 蒸汽波：紫粉青渐变 + 网格地平线 */
  html[data-theme="vapor"]{
    --bg:#241b4a;--card:#2e2360;--panel:#2e2360;--ink:#f7e9ff;--mute:#a99bd8;
    --ink-soft:#c3b3f0;--accent:#ff77e1;--accent-soft:#3a2a6b;--line:#453678;
    --radius:8px;
    --card-shadow:0 0 24px rgba(255,119,225,.28), inset 0 0 0 1px rgba(0,229,255,.25);
    --pattern:
      repeating-linear-gradient(0deg, rgba(0,229,255,.13) 0 1px, transparent 1px 34px),
      repeating-linear-gradient(90deg, rgba(255,119,225,.13) 0 1px, transparent 1px 34px),
      linear-gradient(180deg,#241b4a,#2a1d55 60%,#1e1740);
    --pattern-op:1;--pattern-size:auto;
    --h1-font:"Trebuchet MS","PingFang SC",sans-serif;
    color-scheme:dark;
  }

  /* ---------- 通用：纹样背景层 ---------- */
  body::before{
    content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;
    background:var(--pattern);background-size:var(--pattern-size);
    opacity:var(--pattern-op);
  }
  /* ---------- 通用：结构/装饰随主题变化 ---------- */
  header{background:linear-gradient(180deg,var(--card),var(--bg))}
  .card{border-radius:var(--radius);box-shadow:none}
  .card:hover{box-shadow:var(--card-shadow)}
  header h1{font-family:var(--h1-font)}
  .tag{border-radius:calc(var(--radius) * .6)}
  .tag.lang{background:var(--accent);border-color:var(--accent);color:#fff}
  /* 浅色强调色的主题：徽章改用深色字，保证对比度 */
  html[data-theme="anime"] .tag.lang,html[data-theme="candy"] .tag.lang,
  html[data-theme="manga"] .tag.lang,html[data-theme="pixel"] .tag.lang,
  html[data-theme="cyber"] .tag.lang,html[data-theme="sakura"] .tag.lang,
  html[data-theme="vapor"] .tag.lang{color:#14141a}
  html[data-theme="forest"] .tag.lang,html[data-theme="ocean"] .tag.lang{color:#fff}
  /* 浅色主题下弱对比的普通标签用更深字色 */
  html[data-theme="light"] .tag,html[data-theme="forest"] .tag,
  html[data-theme="ocean"] .tag{color:var(--ink)}
  html[data-theme="light"] .tag:not(.lang),html[data-theme="sepia"] .tag:not(.lang){color:#4a463c}
  #grid{font-size:calc(14px * var(--reader-scale,1))}

  /* 深色系主题下的全局微调 */
  html[data-theme="dark"] .tag,html[data-theme="night"] .tag,
  html[data-theme="pixel"] .tag,html[data-theme="cyber"] .tag,
  html[data-theme="sakura"] .tag,html[data-theme="vapor"] .tag{background:var(--accent-soft);color:var(--ink)}
  html[data-theme="dark"] .tag.lang,html[data-theme="night"] .tag.lang,
  html[data-theme="pixel"] .tag.lang,html[data-theme="cyber"] .tag.lang,
  html[data-theme="sakura"] .tag.lang,html[data-theme="vapor"] .tag.lang{background:var(--accent);color:#1d2024;font-weight:600}
  html[data-theme="pixel"] .tag.lang,html[data-theme="cyber"] .tag.lang,html[data-theme="sakura"] .tag.lang{color:#0b0b14}
  html[data-theme="dark"] .card:hover,html[data-theme="night"] .card:hover,
  html[data-theme="pixel"] .card:hover,html[data-theme="cyber"] .card:hover,
  html[data-theme="sakura"] .card:hover,html[data-theme="vapor"] .card:hover{
    box-shadow:var(--card-shadow)}

  /* 作者行可读性 */
  .card .author{color:#6d3419}
  html[data-theme="sepia"] .card .author{color:#6b4319}
  html[data-theme="dark"] .card .author{color:#e0a98a}
  html[data-theme="night"] .card .author{color:#c89074}
  html[data-theme="anime"] .card .author{color:#c2487a}
  html[data-theme="pixel"] .card .author{color:#41e0a0}
  html[data-theme="cyber"] .card .author{color:#00e5ff}
  html[data-theme="ink"] .card .author{color:#9c2b25}
  html[data-theme="forest"] .card .author{color:#2f6a3c}
  html[data-theme="ocean"] .card .author{color:#0d5f8a}
  html[data-theme="news"] .card .author{color:#8c2d22}
  html[data-theme="candy"] .card .author{color:#c0401f}
  html[data-theme="manga"] .card .author{color:#8a6a00}
  html[data-theme="sakura"] .card .author{color:#ff9ecb}
  html[data-theme="vapor"] .card .author{color:#ff77e1}

  /* 像素风：字体与直角按钮 */
  html[data-theme="pixel"] body{font-family:"Courier New",ui-monospace,monospace}
  html[data-theme="pixel"] .home-settings-btn,
  html[data-theme="pixel"] .home-settings .rs-opt,
  html[data-theme="pixel"] .home-settings .rs-sw{border-radius:0}
  html[data-theme="pixel"] .home-settings-btn{box-shadow:3px 3px 0 #0f1020}

  /* 赛博朋克：按钮霓虹描边 */
  html[data-theme="cyber"] .home-settings-btn{
    background:var(--accent);color:#07070f;border-color:var(--accent);
    box-shadow:0 0 14px rgba(0,229,255,.6)}
  html[data-theme="cyber"] header h1{
    text-shadow:0 0 10px rgba(0,229,255,.7),0 0 22px rgba(255,0,200,.5)}

  /* 水墨：标题楷体 + 印章感强调 */
  html[data-theme="ink"] header h1{letter-spacing:4px}
  html[data-theme="ink"] .card{border-width:1px}

  /* 复古报纸：标题大写间距 */
  html[data-theme="news"] header h1{letter-spacing:2px;text-transform:uppercase}
  html[data-theme="news"] .card{border:1px solid var(--line);border-top:3px double var(--ink)}

  /* 热血漫画：粗描边 */
  html[data-theme="manga"] .card{border:2px solid #111}
  html[data-theme="manga"] .card:hover{transform:translate(-2px,-2px) scale(1.005)}

  /* 糖果 / 动漫：hover 上浮更多一点 */
  html[data-theme="candy"] .card:hover,
  html[data-theme="anime"] .card:hover{transform:translateY(-5px)}

  /* ---------- 主题按钮与面板 ---------- */
  .home-settings-btn{
    position:fixed;z-index:9991;bottom:22px;left:22px;
    padding:10px 14px;border-radius:999px;border:1px solid var(--line);
    background:var(--card);color:var(--accent);cursor:pointer;font-family:inherit;
    font-size:13px;box-shadow:0 6px 18px rgba(0,0,0,.18);
  }
  .home-settings-btn:hover{filter:brightness(1.06)}
  .home-settings{
    position:fixed;z-index:10002;bottom:70px;left:22px;width:330px;
    max-height:78vh;overflow:auto;
    background:var(--card);color:var(--ink);border:1px solid var(--line);
    border-radius:12px;box-shadow:0 14px 44px rgba(0,0,0,.28);
    padding:14px 16px 16px;display:none;font-family:inherit;font-size:13px;
  }
  .home-settings.open{display:block}
  .home-settings h4{margin:0 0 10px;font-size:13px;letter-spacing:1px;color:var(--accent);
    text-transform:uppercase}
  .home-settings .rs-row{margin-bottom:16px}
  .home-settings .rs-row:last-child{margin-bottom:0}
  .home-settings .rs-label{font-size:11px;color:var(--mute);margin-bottom:8px;letter-spacing:.5px}
  .home-settings .rs-opts{display:flex;flex-wrap:wrap;gap:6px}
  .home-settings .rs-opt{
    padding:5px 10px;border:1px solid var(--line);border-radius:7px;cursor:pointer;
    background:var(--bg);color:var(--ink);font-size:12.5px;font-family:inherit;line-height:1.2;
  }
  .home-settings .rs-opt:hover{border-color:var(--accent)}
  .home-settings .rs-opt.on{background:var(--accent);color:#fff;border-color:var(--accent)}
  .home-settings .rs-swatches{display:flex;gap:8px;flex-wrap:wrap;padding-bottom:16px}
  .home-settings .rs-sw{width:34px;height:34px;border-radius:calc(var(--radius) * .5);
    border:2px solid var(--line);cursor:pointer;position:relative;overflow:hidden}
  .home-settings .rs-sw.on{border-color:var(--accent);box-shadow:0 0 0 2px var(--accent-soft)}
  .home-settings .rs-sw span{position:absolute;bottom:-16px;left:-4px;right:-4px;text-align:center;
    font-size:10px;color:var(--mute);white-space:nowrap}
  .home-settings .rs-sw .ico{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
    font-size:16px;line-height:1}
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

  // group: reading = 阅读主题（书页也支持）；fun = 趣味主题（书页回退）
  var THEMES = [
    {id:'light',  name:'亮色',   bg:'#faf8f4', ink:'#2b2b2b', group:'reading', ico:'☀'},
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

  // 趣味主题 -> 书页支持的阅读主题（书页只认识 4 套，遇到趣味主题时回退）
  var FALLBACK = {
    anime:'light', pixel:'dark', cyber:'dark', ink:'light', forest:'light',
    ocean:'light', news:'sepia', candy:'light', manga:'light', sakura:'night', vapor:'dark'
  };

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

  // 书页进入时读取同一 key；若为趣味主题，书页端会自行回退到最接近的阅读主题
  // （见 add_theme_and_hud.py 的 toReading），因此此处无需额外处理。
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

  function swatch(t){
    var light = (t.ink === '#2b2b2b' || t.ink === '#43382a' || t.ink === '#20201d' ||
                 t.ink === '#243024' || t.ink === '#14313f' || t.ink === '#23211c' ||
                 t.ink === '#3d2f3a' || t.ink === '#3b2c3a' || t.ink === '#111111');
    // 用主题的主色与强调色拼一个小样
    return '<div class="rs-sw'+(t.id===curTheme?' on':'')+'" data-theme-pick="'+t.id+'" '
      +  'title="'+t.name+'" style="background:'+t.bg+'">'
      +  '<span style="color:'+(light?'#666':'#bbb')+'">'+t.name+'</span>'
      +  '<i class="ico" style="font-style:normal">'+t.ico+'</i>'
      +  '</div>';
  }
  function render(){
    var h = '<h4>显示设置</h4>';
    h += '<div class="rs-row"><div class="rs-label">阅读主题</div><div class="rs-swatches">';
    THEMES.filter(function(t){return t.group==='reading';}).forEach(function(t){ h += swatch(t); });
    h += '</div></div>';
    h += '<div class="rs-row"><div class="rs-label">趣味主题</div><div class="rs-swatches">';
    THEMES.filter(function(t){return t.group==='fun';}).forEach(function(t){ h += swatch(t); });
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
    html = html.replace('</style>', THEMES_CSS + '</style>', 1)
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
