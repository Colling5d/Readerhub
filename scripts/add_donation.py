#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给首页注入「微信赞赏收款码」紧凑模块（自包含，图片 base64 内嵌，幂等）。

用法:
    python3 scripts/add_donation.py --img path/to/qr.jpg              # 首页底部（默认）
    python3 scripts/add_donation.py --img qr.jpg --pos top            # 放页头下方
    python3 scripts/add_donation.py --img qr.jpg --text $'第一行\\n第二行'
    python3 scripts/add_donation.py --remove books/*/index.html       # 移除旧注入
    python3 scripts/add_donation.py --img qr.jpg <files...>           # 指定文件

设计:
    - 默认只作用于首页 index.html，模块居于页面最下方（页脚上方），紧凑横排：
      左侧小二维码，右侧「投喂」文案；窄屏自动改为竖排。
    - 图片按最长边缩到 <= 480px 并转成优化 PNG，base64 内嵌，保持零外部资源。
    - 重复运行会先移除旧注入再写入，方便换图 / 改文案；--remove 用于清除。
"""
import sys, os, re, base64, io, html as _html, argparse

CSS = '''
  /* ===== 赞赏支持 (DONATION) ===== */
  .donate{max-width:600px;margin:36px auto 22px;padding:14px 16px;display:flex;gap:16px;
    align-items:center;text-align:left;background:var(--panel,#fff);
    border:1px solid var(--line,#e6e1d6);border-radius:14px;
    box-shadow:0 6px 20px rgba(0,0,0,.06);font-family:var(--reader-font,inherit);color:var(--ink,#2b2b2b)}
  .donate .donate-img{flex:0 0 auto;width:auto;height:auto;max-width:118px;max-height:150px;
    border-radius:10px;border:1px solid var(--line,#e6e1d6);background:#fff;
    box-shadow:0 4px 12px rgba(0,0,0,.08)}
  .donate .donate-body{flex:1 1 auto;min-width:0}
  .donate h3{margin:0 0 6px;font-size:14px;letter-spacing:.5px;color:var(--accent,#8a4422)}
  .donate .donate-text{margin:0;font-size:12.5px;line-height:1.75;color:var(--ink-soft,#6f6a60);
    white-space:pre-line}
  @media (max-width:560px){
    .donate{flex-direction:column;text-align:center}
    .donate .donate-img{max-height:168px}
  }
'''

_default_text = (
    '做它其实没费多大劲，就是偷偷啃掉了我不少「偷啃」💰\n'
    '（对，就是 token 那个偷啃）\n'
    '有帮到你就扫码充点偷啃、给我回回血～不充也完全没关系，白嫖也是一种认可 😄'
)


def home_block(datauri, text):
    return ('''
  <section class="donate" id="donate">
    <img class="donate-img" src="%s" alt="微信收款码" loading="lazy">
    <div class="donate-body">
      <h3>❤ 投喂作者</h3>
      <p class="donate-text">%s</p>
    </div>
  </section>
''' % (datauri, _html.escape(text).replace('\n', '<br>')))


def load_qr(path, max_side=480):
    from PIL import Image
    im = Image.open(path).convert('RGBA')
    w, h = im.size
    scale = min(1.0, float(max_side) / max(w, h))
    if scale < 1.0:
        im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format='PNG', optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode('ascii')
    print('  图片 %s: %dx%d -> %dx%d, base64 %d KB' % (path, w, h, im.size[0], im.size[1], len(b64) // 1024))
    return 'data:image/png;base64,' + b64


def strip_old(html):
    # 首页卡片
    html = re.sub(r'\n?\s*<section class="donate[^"]*" id="donate">.*?</section>\n?', '\n', html, flags=re.S)
    # 书页浮层脚本
    html = re.sub(r'\n?<script>\s*/\* ============ 赞赏支持 \(DONATION\).*?</script>\n?', '\n', html, flags=re.S)
    # CSS：从注入标记（或旧版书页注释）一直删到 </style>（可同时清掉重复/残留块）
    html = re.sub(r'\n\s*/\* ===== 赞赏支持 \(DONATION\) ===== \*/.*?(?=</style>)', '\n', html, flags=re.S)
    html = re.sub(r'\n\s*/\* 书页：常驻投喂按钮 \+ 入口浮层 \*/.*?(?=</style>)', '\n', html, flags=re.S)
    return html


def inject_css(html):
    if '</style>' not in html:
        raise RuntimeError('未找到 </style>')
    return html.replace('</style>', CSS + '</style>', 1)


def patch_home(html, datauri, text, pos):
    html = strip_old(html); html = inject_css(html)
    block = home_block(datauri, text)
    if pos == 'top':
        marker = '<div class="wrap">'
        if marker in html:
            html = html.replace(marker, marker + block, 1)
        elif '<div id="grid">' in html:
            html = html.replace('<div id="grid">', block + '<div id="grid">', 1)
        else:
            html = html.replace('</header>', '</header>' + block, 1)
    else:
        if '<footer' in html:
            html = html.replace('<footer', block + '<footer', 1)
        else:
            html = html.replace('</body>', block + '</body>', 1)
    return html


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('--img')
    ap.add_argument('--text', default=_default_text)
    ap.add_argument('--pos', choices=['top', 'bottom'], default='bottom')
    ap.add_argument('--remove', action='store_true')
    ap.add_argument('files', nargs='*')
    a = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if a.files:
        targets = a.files
    else:
        targets = [os.path.join(root, 'index.html')]

    if a.remove:
        for f in targets:
            if not os.path.isfile(f):
                print('!! 找不到', f); continue
            src = open(f, encoding='utf-8').read()
            open(f, 'w', encoding='utf-8').write(strip_old(src))
            print('✓ 已移除注入', os.path.relpath(f, root))
        return

    if not a.img:
        print(__doc__); sys.exit(1)
    datauri = load_qr(a.img)

    for f in targets:
        if not os.path.isfile(f):
            print('!! 找不到', f); continue
        src = open(f, encoding='utf-8').read()
        out = patch_home(src, datauri, a.text, a.pos)
        open(f, 'w', encoding='utf-8').write(out)
        print('✓ 已注入', os.path.relpath(f, root))


if __name__ == '__main__':
    main()
