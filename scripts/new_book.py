#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""new_book.py — 一键建书向导：给 PDF + 章节配置，自动完成建书全部阶段。

用法:
    python3 scripts/new_book.py --config book.json --all
    python3 scripts/new_book.py --config book.json --steps mineru,extract,sections
    python3 scripts/new_book.py --config book.json --steps translate,build,register,deploy

阶段(steps, 按顺序):
    split_pdf   拆 PDF（>200 页自动多份）
    mineru      申请 URL + 上传 + 轮询 + 下载 zip（失败自动重传）
    unzip       解压
    extract     unzip -> stream_raw.json
    sections    生成 build_sections.py 并产出 en_data.json
    translate   ECNU 翻译（后台断点续跑，翻译量大请耐心）
    retry       补齐缺失段
    build       生成 books/<id>/index.html
    register    metadata.json + 登记首页 BOOKS
    deploy      git commit + push（自动探测代理，见 scripts/gitpush.sh）

book.json 字段:
    id         必填 唯一标识（小写字母数字连字符）
    pdf        必填 源 PDF 路径
    title      书名(EN)
    author_en  作者英文
    author_cn  作者中文
    subtitle   登记副标题
    description 登记简介（含引号需转义）
    tags       [] 登记标签
    base_book  阅读器模板书 id，默认 chinese-americans-shared-history
    sections   [] 章节表: {"id","title","start","end","type","labels"(可选)}
               labels: {"id":[en短标签,中文短标签]} 用于 TOC；也可在 sections 里给
               type 取值 ""(正文) / "notes"(注释合并)
    notes_subheads [] notes 区的分区标题（如 "Chapter 1" ...）
    meta       {} 额外登记字段（featured/lang/chapterCount 等）
"""
import json, os, re, sys, glob, shutil, subprocess, argparse, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
TEMPLATES = os.path.join(SCRIPTS, "templates")
BOOKS = os.path.join(ROOT, "books")
HUB = os.path.join(ROOT, "index.html")

MINERU_BASE = 'https://mineru.net/api/v4'
MINERU_TOK = 'sk-P5Y5CLmwX7gr6DHxq6hTF65u7GNOWym55EmFY0cfl6STJA9S'

def read(p):
    return open(p, encoding='utf-8').read()

def tmpl(name):
    return read(os.path.join(TEMPLATES, name))

def sh(cmd, cwd=None, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, **kw)

def log(msg, tag=''):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}]{'['+tag+']' if tag else ''} {msg}", flush=True)

def inject(text, mapping):
    for k, v in mapping.items():
        text = text.replace(k, str(v))
    return text

# ============ 生成书特定脚本 ============
def build_sections_src(cfg):
    secs = cfg['sections']
    lit = "[\n"
    for s in secs:
        is_notes = "True" if s.get('type') == 'notes' else "False"
        lit += f"    ({s['id']!r}, {s['title']!r}, ({s['start']}, {s['end']}), {is_notes}),\n"
    lit += "]"
    sub = repr(set(cfg.get('notes_subheads', [])))
    return inject(tmpl('build_sections.py'), {"__SECTIONS__": lit, "__NOTES_SUBHEADS__": sub})

def slot_dicts(cfg):
    """返回 (TOC_ORDER_lit, toc_label_body, title_map_body, sectitle_body)
    labels 从每个 section 元素取 (s.get('labels', [EN,ZH]))；缺失时回退 title。
    也接受顶层 cfg['labels']={sid:[EN,ZH]}。"""
    order = [s['id'] for s in cfg['sections']]
    toplabels = cfg.get('labels', {}) or {}
    tocl = {}; titm = {}; sect = {}
    for s in cfg['sections']:
        sid = s['id']
        pair = s.get('labels') or toplabels.get(sid)
        if not pair or len(pair) < 2:
            pair = [s['title'], s['title']]
        en_l, zh_l = pair[0], pair[1]
        tocl[sid] = [en_l, zh_l]
        titm[sid] = f"{zh_l} · {en_l}"
        sect[sid] = zh_l
    toc_order_lit = "[" + ", ".join(repr(x) for x in order) + "]"
    import json as J
    return (toc_order_lit,
            J.dumps(tocl, ensure_ascii=False, indent=4),
            J.dumps(titm, ensure_ascii=False, indent=4),
            J.dumps(sect, ensure_ascii=False, indent=4))

def slots_src(cfg):
    o, tl, tm, st = slot_dicts(cfg)
    return inject(tmpl('slots.py'), {"__TOC_ORDER__": o, "__TOC_LABEL__": tl,
                                     "__TITLE_MAP__": tm, "__SECTITLE__": st})

BASE_INFO = {
    'chinese-americans-shared-history': ('Chinese and Americans: A Shared History', 'Xu Guoqi · 徐国琦'),
    'cultures-colliding': ('Cultures Colliding', 'John R. Haddad'),
    'fighting-cultural-front': ('Fighting on the Cultural Front', 'Hongshan Li · 李洪山'),
    'objectifying-china': ('Objectifying China, Imagining America', 'Caroline Frank · 卡罗琳·弗兰克'),
    'winning-third-world': ('Winning the Third World', 'Gregg A. Brazinsky · 格雷格·A·布拉金斯基'),
}

def build_reader_src(cfg):
    base = cfg.get('base_book') or 'chinese-americans-shared-history'
    bt, ba = BASE_INFO.get(base, BASE_INFO['chinese-americans-shared-history'])
    author_attr = f"{cfg.get('author_en','')} · {cfg.get('author_cn','')}".strip(' ·')
    book_dir = os.path.join(BOOKS, cfg['id'])
    return inject(tmpl('build_reader.py'), {
        "__BOOK_DIR__": repr(book_dir),
        "__TITLE__": cfg['title'],
        "__BASE_TITLE__": bt,
        "__AUTHOR_ATTR__": author_attr,
        "__BASE_AUTHOR__": re.escape(ba),
        "__POSKEY__": f"readerhub_pos_{cfg['id']}",
        "__BOOKKEY__": f"readerhub_notes_{cfg['id']}",
    })

# ============ 阶段实现 ============
def prep_build_dir(cfg):
    bid = cfg['id']
    d = os.path.join(SCRIPTS, 'build_' + bid)
    os.makedirs(os.path.join(d, 'work'), exist_ok=True)
    # 通用脚本复制（translate/retry 完全通用）
    for f in ('translate.py', 'retry_missing.py'):
        if not os.path.isfile(os.path.join(d, f)):
            shutil.copy(os.path.join(TEMPLATES, f), os.path.join(d, f))
    return d

def step_split_pdf(cfg, bd, force):
    pdf = cfg['pdf']
    od = os.path.join(bd, 'pdf')
    os.makedirs(od, exist_ok=True)
    if glob.glob(os.path.join(od, '*.pdf')) and not force:
        log('pdf/ 已有，跳过', 'split'); return
    for old in glob.glob(os.path.join(od, '*.pdf')):
        os.remove(old)
    r = sh(f'''python3 - '{pdf}' '{od}' <<'PY'
import sys, fitz, os
src,out=sys.argv[1],sys.argv[2]
d=fitz.open(src); n=d.page_count; s=1; k=1
while s<=n:
    e=min(s+199,n); doc=fitz.open(src); new=fitz.open()
    new.insert_pdf(doc,from_page=s-1,to_page=e-1)
    fp=f"{out}/part{k}_p{s}-{e}.pdf"; new.save(fp); new.close(); doc.close()
    print(fp, round(os.path.getsize(fp)/1e6,2), "MB"); s=e+1; k+=1
print("TOTAL", n)
PY''')
    print(r.stdout + r.stderr)

def step_mineru(cfg, bd, force):
    import urllib.request
    pdf = os.path.join(bd, 'pdf')
    files = sorted(glob.glob(os.path.join(pdf, '*.pdf')))
    if not files:
        log('无 pdf，先跑 split_pdf', 'mineru'); return
    zipdone = glob.glob(os.path.join(bd, 'zip', '*.zip'))
    if len(zipdone) == len(files) and not force:
        log('zip 已就绪，跳过', 'mineru'); return
    os.makedirs(os.path.join(bd, 'zip'), exist_ok=True)
    req = {"files": [{"name": os.path.basename(f), "data_id": os.path.basename(f).split('.')[0][:120]} for f in files],
           "model_version": "vlm", "enable_table": True}
    reqj = json.dumps(req).encode()
    try:
        resp = json.loads(urllib.request.urlopen(urllib.request.Request(
            MINERU_BASE + '/file-urls/batch', data=reqj,
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + MINERU_TOK}), timeout=60).read())
        if resp.get('code') != 0:
            raise RuntimeError(resp.get('msg'))
    except Exception as e:
        log(f'urllib 申请失败 {str(e)[:50]}，退回 curl', 'mineru')
        open(os.path.join(bd, 'work', '_mineru_req.json'), 'w').write(json.dumps(req))
        r = sh(f"curl -s --noproxy '*' --max-time 60 -X POST {MINERU_BASE}/file-urls/batch "
               f"-H 'Content-Type: application/json' -H 'Authorization: Bearer {MINERU_TOK}' "
               f"-d @{os.path.join(bd, 'work', '_mineru_req.json')}")
        resp = json.loads(r.stdout)
    batch = resp['data']['batch_id']
    urls = resp['data']['file_urls']
    open(os.path.join(bd, 'work', 'batch.json'), 'w').write(json.dumps(resp, ensure_ascii=False))
    log(f'batch={batch} {len(files)} 份', 'mineru')
    for name, u in zip([os.path.basename(f) for f in files], urls):
        r = sh(f"curl -s --noproxy '*' -o /dev/null -w '%{{http_code}}' -X PUT -T {os.path.join(pdf, name)} {u}")
        log(f'上传 {name}: HTTP {r.stdout}', 'mineru')
    # 轮询（同步跑完）
    open(os.path.join(bd, 'poll_all.py'), 'w').write(tmpl('poll_all.py'))
    r = sh(f"python3 -u poll_all.py '{batch}' '{os.path.join(bd,'work','batch.json')}'", cwd=bd)
    print(r.stdout + r.stderr)

def step_unzip(bd):
    for z in sorted(glob.glob(os.path.join(bd, 'zip', '*.zip'))):
        name = os.path.basename(z).replace('.zip', '')
        td = os.path.join(bd, 'unzip', name)
        os.makedirs(td, exist_ok=True)
        r = sh(f"unzip -o -q '{z}' -d '{td}'")
    log('unzip 完成', 'unzip')

def step_extract(bd):
    if not glob.glob(os.path.join(bd, 'unzip', '*')):
        log('无 unzip，先跑 mineru/unzip', 'extract'); return
    open(os.path.join(bd, 'extract.py'), 'w').write(tmpl('extract.py'))
    r = sh("python3 extract.py", cwd=bd)
    print(r.stdout + r.stderr)
    log('stream_raw.json 已生成', 'extract')

def step_sections(cfg, bd):
    if not cfg.get('sections'):
        log('配置缺 sections，请填 book.json', 'sections'); return
    with open(os.path.join(bd, 'build_sections.py'), 'w', encoding='utf-8') as f:
        f.write(build_sections_src(cfg))
    with open(os.path.join(bd, 'slots.py'), 'w', encoding='utf-8') as f:
        f.write(slots_src(cfg))
    r = sh("python3 build_sections.py", cwd=bd)
    print(r.stdout + r.stderr)
    log('en_data.json 已生成', 'sections')

def step_translate(cfg, bd):
    en = os.path.join(bd, 'en_data.json')
    if not os.path.isfile(en):
        log('无 en_data.json，先跑 sections', 'translate'); return
    shutil.copy(os.path.join(TEMPLATES, 'translate.py'), os.path.join(bd, 'translate.py'))
    p = subprocess.Popen(['python3', '-u', 'translate.py'], cwd=bd,
                         stdout=open(os.path.join(bd, 'work', 'translate.log'), 'a'),
                         stderr=subprocess.STDOUT)
    log(f'translate PID {p.pid}（logs: work/translate.log）', 'translate')

def step_retry(cfg, bd):
    r = sh("python3 retry_missing.py", cwd=bd)
    print(r.stdout + r.stderr)

def step_build(cfg, bd):
    if not os.path.isfile(os.path.join(bd, 'work', 'translated.json')):
        log('无 translated.json，先跑 translate/retry', 'build'); return
    with open(os.path.join(bd, 'build_reader.py'), 'w', encoding='utf-8') as f:
        f.write(build_reader_src(cfg))
    base = cfg.get('base_book') or 'chinese-americans-shared-history'
    shutil.copy(os.path.join(BOOKS, base, 'index.html'), os.path.join(bd, 'reader_base.html'))
    r = sh("python3 build_reader.py", cwd=bd)
    print(r.stdout + r.stderr)
    log('阅读器已生成', 'build')
    # 注入「目录折叠」「主题/字体/章节 HUD」「连续滚动」「脚注悬浮提示」（幂等；若 base 已带则跳过）
    idx = os.path.join(BOOKS, cfg['id'], 'index.html')
    for tool in ('add_sidebar_toggle.py', 'add_theme_and_hud.py', 'add_continuous_scroll.py', 'add_footnote_tooltips.py'):
        tp = os.path.join(SCRIPTS, tool)
        if os.path.isfile(idx) and os.path.isfile(tp):
            sh(f'python3 {tool} "{idx}"', cwd=SCRIPTS)
            log(f'{tool} 已注入', 'build')
    # 注：赞赏模块只放在首页底部（scripts/add_donation.py），不在单本书内注入。

def step_register(cfg, bd):
    idx = os.path.join(BOOKS, cfg['id'], 'index.html')
    if not os.path.isfile(idx):
        log('先跑 build', 'register'); return
    meta = dict(cfg.get('meta', {}))
    meta.setdefault('id', cfg['id'])
    meta.setdefault('title', cfg['title'])
    meta.setdefault('author', f"{cfg.get('author_cn','')} {cfg.get('author_en','')}".strip())
    if cfg.get('subtitle'):
        meta.setdefault('subtitle', cfg['subtitle'])
    if cfg.get('description'):
        meta.setdefault('description', cfg['description'])
    if not meta.get('updated'):
        meta['updated'] = datetime.date.today().isoformat()
    meta_path = os.path.join(BOOKS, cfg['id'], 'metadata.json')
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    log(f'metadata.json 已写 {len(json.dumps(meta, ensure_ascii=False))} bytes', 'register')
    # 首页登记
    hub = open(HUB, encoding='utf-8').read()
    m = re.search(r"(\s*/\* __BOOKS__ \*/)", hub)
    if m and cfg['id'] not in hub:
        marker = m.group(1)
        insert_at = hub.index(marker)
        entry = ",\n" + json.dumps(meta, ensure_ascii=False) + "\n  "
        hub = hub[:insert_at] + entry + hub[insert_at:]
        open(HUB, 'w', encoding='utf-8').write(hub)
        log('已登记首页 BOOKS', 'register')
    else:
        log('已登记过或未找到标记', 'register')

def step_deploy(cfg, bd):
    bid = cfg['id']
    r = sh(f"cd {ROOT} && git add books/{bid} scripts/build_{bid} index.html assets "
           f"scripts/templates scripts/new_book.py scripts/*.py scripts/gitpush.sh && "
           f"git commit -m 'add book: {bid}'")
    print(r.stdout + r.stderr)
    # 推送：交给 gitpush.sh 自动探测代理（本地代理可用则走代理，否则直连）。
    # 旧写法把 127.0.0.1:7890 写死，代理未开时会导致 push 失败。
    push_sh = os.path.join(SCRIPTS, 'gitpush.sh')
    if os.path.isfile(push_sh):
        r = sh(f"bash '{push_sh}' origin main", cwd=ROOT)
    else:
        r = sh("git push origin main", cwd=ROOT)
    print(r.stdout + r.stderr)

ORDER = ['split_pdf', 'mineru', 'unzip', 'extract', 'sections', 'translate', 'retry', 'build', 'register', 'deploy']

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--steps', default=None)
    ap.add_argument('--force', action='store_true')
    na = ap.parse_args()
    cfg = json.load(open(na.config, encoding='utf-8'))
    bd = prep_build_dir(cfg)
    if na.all and not na.steps:
        steps = ORDER
    elif na.steps:
        steps = [s.strip() for s in na.steps.split(',')]
    else:
        steps = []
        for s in ['sections', 'build', 'register', 'deploy']:
            print(f"{s}: 未勾选，用 --all 或 --steps 运行")
        ap.print_help(); return
    for s in ORDER:
        if s not in steps:
            continue
        log(f"===== {s} =====")
        if s == 'split_pdf': step_split_pdf(cfg, bd, na.force)
        elif s == 'mineru': step_mineru(cfg, bd, na.force)
        elif s == 'unzip': step_unzip(bd)
        elif s == 'extract': step_extract(bd)
        elif s == 'sections': step_sections(cfg, bd)
        elif s == 'translate': step_translate(cfg, bd)
        elif s == 'retry': step_retry(cfg, bd)
        elif s == 'build': step_build(cfg, bd)
        elif s == 'register': step_register(cfg, bd)
        elif s == 'deploy': step_deploy(cfg, bd)
    log('完成')

if __name__ == '__main__':
    main()