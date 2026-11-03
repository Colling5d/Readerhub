#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全文翻译 + 句子对齐（综合 prompt）。
读取 en_data.json → 每个 text/note 段落做 清洁英文+中译+切句+对齐；h 段做纯翻译。
产出 work/translated.json（按 'secid/i' 键，断点续跑）。
"""
import json, os, re, time, threading, urllib.request, math, sys

BASE = os.environ.get('ECNU_API_BASE', 'https://chat.ecnu.edu.cn/open/api/v1/chat/completions')
KEY = os.environ.get('ECNU_API_KEY', 'sk-e1d6953fb6c348d193d8dd4a03c6edc7')
MODEL = os.environ.get('ECNU_API_MODEL', 'ecnu-max')
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, 'work')
os.makedirs(WORK, exist_ok=True)
OUT = os.path.join(WORK, 'translated.json')
EN_DATA = os.path.join(HERE, 'en_data.json')

NWORKERS = int(os.environ.get('ECNU_WORKERS', '2'))
BATCH = int(os.environ.get('ECNU_BATCH', '8'))
MAX_TOK = 22000
CALL_DELAY = float(os.environ.get('ECNU_DELAY', '3.0'))   # 每次调用间的线程内固定间隔，减轻 429

def norm(s):
    return ' '.join(s.split())

def call_api(prompt, max_tokens=MAX_TOK, retries=6):
    payload = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                          "temperature": 0, "max_tokens": max_tokens}).encode()
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(BASE, data=payload, headers={"Content-Type": "application/json",
                                                                      "Authorization": "Bearer " + KEY})
            resp = json.loads(urllib.request.urlopen(req, timeout=360).read())
            content = resp['choices'][0]['message']['content'].strip()
            if content.startswith('```'):
                content = content.split('\n', 1)[1].rsplit('```', 1)[0].strip()
            return content
        except Exception as e:
            last = e
            backoff = 15 + a * 15 if '429' in str(e) else 4 + a * 6
            print(f"    [retry {a+1}] {str(e)[:80]} (backoff {backoff}s)", flush=True)
            time.sleep(backoff)
    raise last

COMBINED = (
    "你是中英对照的图书翻译与句子对齐专家。下面给出若干段英文（来自一本书的OCR，可能存在OCR把单词错误断字/拼字/合并的问题，"
    "如 'signifi cant'→'significant'、'hasbeen'→'has been'、'Eu rope'→'Europe'、'keynot only'→'key not only'、"
    "'re-lations'→'relations'、'par tic u lar'→'particular'；引用的书名/人名/年份务必根据上下文补全拼写）。\n"
    "针对每一段做四件事：\n"
    "1) 复原出**干净、通顺、拼写正确**的英文 en（修正OCR断字/缺字/并字，恢复正确标点，不改变原意、不增删实质内容；"
    "若原文本就是完整正确的，原样保留）；\n"
    "2) 把 en 准确翻译成通顺、符合商务印书馆学术专著风格的中文 zh；人名地名人名（如蒲安臣、詹天佑、徐国琦、杜威）用通行中文译名；\n"
    "3) 把 en 切分为句子列表 en_sents，zh 切分为 zh_sents；\n"
    "4) 给出中英句子对齐 align：[[英句下标,中句下标],...]，允许一对多/多对一。\n"
    "【本书术语表，务必按此译法】taipan→洋行大班；sea power→海权；sea-lanes→海上通道；"
    "chokepoint→咽喉要道；EEZ/exclusive economic zone→专属经济区；A2/AD (anti-access/area denial)→反介入/区域拒止；"
    "carrier strike group→航母打击群；destroyer→驱逐舰；frigate→护卫舰；submarine→潜艇；"
    "TEU (twenty-foot equivalent unit)→标准箱（TEU）；containerization→集装箱化；"
    "Panamax/Post-Panamax→巴拿马型/超巴拿马型；breakbulk→散杂货；bulk carrier→散货船；"
    "flag of convenience→方便旗；lightering→过驳；transshipment→转运；"
    "the Near Seas→近海；the First Island Chain→第一岛链；the nine-dash line→九段线；"
    "the Strait of Malacca→马六甲海峡；the South China Sea→南海；Taiwan Strait→台湾海峡；"
    "Arctic sea ice→北极海冰；thermohaline circulation→温盐环流；El Niño→厄尔尼诺；"
    "IPCC→政府间气候变化专门委员会；Scripps→斯克里普斯（海洋研究所）；Woods Hole→伍兹霍尔；"
    "PLAN (People's Liberation Army Navy)→中国人民解放军海军；US Navy→美国海军；"
    "Central Command→中央司令部；Indo-Pacific→印太；Belt and Road→一带一路；"
    "Maersk→马士基；OOCL→东方海外；COSCO→中远；Evergreen→长荣；Hutchison Whampoa→和记黄埔；"
    "Mahan→马汉；Mackinder→麦金德；Spykman→斯皮克曼；Brookings→布鲁金斯学会；"
    "the Box→集装箱；Lloyd's→劳合社；Suez Canal→苏伊士运河；Panama Canal→巴拿马运河。\n"
    "硬性要求：\n"
    "- 每个对象的 key 必须**原样**保留我给出的标识；\n"
    "- en_sents 顺序首尾拼接必须**逐字符等于 en**；zh_sents 逐字符拼接等于 zh。为满足这点：\n"
    "   * 先完整写下 en，再从 en 里切句，每句必须能从 en 中连续取原词（含标点）；\n"
    "   * 先完整写下 zh，再从 zh 里切句；\n"
    "   * 切勿在 en 与 en_sents 之间、zh 与 zh_sents 之间改动任何词、空格或标点；\n"
    "- 中文句号用“。”，“…”等标点保留；绝不截断；页码/注号（如数字、上标）按原样放进 en 与去对应句。\n"
    "自检：en_sents 用空串 join 后必须与 en 完全相同，否则修正后再输出。\n"
    "只输出一个 JSON 数组（不要 Markdown 代码块、不要任何解释），按给出顺序每段一个对象：\n"
    "{\"key\":\"标识\",\"en\":\"...\",\"zh\":\"...\",\"en_sents\":[...],\"zh_sents\":[...],\"align\":[[0,0],...]}\n\n"
    "段落如下：\n"
)

def build_combined(batch):
    ps = ""
    for key, text in batch:
        ps += f"\n--- {key} ---\n{text}\n"
    return COMBINED + ps

TRANS_ONLY = (
    "你是中英对照图书翻译专家。把下面这段英文标题/小标题/简短文本翻译成通顺的中文（学术专著风格，尽量简洁忠实）。"
    "同时复原出干净正确的英文 en（若原文有OCR断字错误请修正）。\n"
    "只输出一个JSON对象（不要代码块）：{\"key\":\"标识\",\"en\":\"...\",\"zh\":\"...\"}\n"
    "段落标识key原样保留。\n\n"
)

def build_trans_only(key, text):
    return TRANS_ONLY + f"--- {key} ---\n{text}\n"

LOCK = os.path.join(HERE, '.translate.lock')


def acquire_lock():
    """单实例锁：防止多个进程同时写 translated.json 互相覆盖。"""
    if os.path.exists(LOCK):
        try:
            pid = int(open(LOCK).read().strip())
            os.kill(pid, 0)
            print(f'another instance running (pid {pid}); exit', flush=True)
            sys.exit(0)
        except (ValueError, OSError):
            pass
    open(LOCK, 'w').write(str(os.getpid()))
    import atexit
    atexit.register(lambda: os.path.exists(LOCK) and os.remove(LOCK))


def main():
    acquire_lock()
    data = json.load(open(EN_DATA, encoding='utf-8'))
    results = {}
    if os.path.exists(OUT):
        try:
            results = json.load(open(OUT, encoding='utf-8'))
        except Exception:
            results = {}

    # 收集待处理任务： (key, type, text)
    tasks = []
    for sec in data:
        sid = sec['id']
        for i, p in enumerate(sec['paras']):
            key = f"{sid}/{i}"
            if key in results:
                continue
            tasks.append((key, p['type'], p['text']))

    full = len(results)
    print(f"total sections={len(data)} tasks_todo={len(tasks)} already_done={full}", flush=True)

    # 拆成批次；h 用纯翻译 type=T，其余用 combined type=C
    batches = []
    for key, typ, text in tasks:
        batches.append((('T' if typ in ('h', 'subh') else 'C'), key, text))
    # 合并连续同类型，按批打包
    chunked = []
    for kind, key, text in batches:
        if chunked and chunked[-1][0] == kind and len(chunked[-1][1]) < BATCH:
            chunked[-1][1].append((key, text))
        else:
            chunked.append((kind, [(key, text)]))

    lock = threading.Lock()
    done_counter = [0]

    def worker(wid):
        while True:
            try:
                chunk = q.get_nowait()
            except Exception:
                return
            kind, items = chunk
            ok = 0
            time.sleep(CALL_DELAY)
            try:
                if kind == 'C':
                    prompt = build_combined(items)
                    raw = call_api(prompt)
                    arr = parse_json(raw)
                    if not isinstance(arr, list):
                        arr = [arr]
                    # 按 key 匹配
                    for order, it in enumerate(arr):
                        if not isinstance(it, dict):
                            continue
                        key = it.get('key')
                        if not key:
                            cand = [k for k, _ in items if f"{k}" not in results]
                            key = cand[order] if order < len(cand) else None
                            if not key:
                                continue
                        base = f"{key}"
                        if base in results:
                            continue
                        with lock:
                            results[base] = {
                                'type': 'C', 'en': it.get('en', ''), 'zh': it.get('zh', ''),
                                'en_sents': it.get('en_sents', []), 'zh_sents': it.get('zh_sents', []),
                                'align': it.get('align', []),
                            }
                            save(results)
                            ok += 1
                            done_counter[0] += 1
                            if done_counter[0] % 10 == 0:
                                print(f"    >> cumulative done: {done_counter[0]+full}", flush=True)
                else:
                    # 纯翻译 h：逐条（h 通常 1 条/批）
                    for key, text in items:
                        prompt = build_trans_only(key, text)
                        raw = call_api(prompt, max_tokens=2000)
                        it = parse_json(raw)
                        if isinstance(it, list) and it:
                            it = it[0]
                        if not isinstance(it, dict) or not it.get('key'):
                            continue
                        with lock:
                            results[key] = {'type': 'T', 'en': it.get('en', ''), 'zh': it.get('zh', '')}
                            save(results)
                            ok += 1
                            done_counter[0] += 1
            except Exception as e:
                print(f"  [w{wid}] batch failed: {str(e)[:120]}", flush=True)
            finally:
                time.sleep(0.3)

    import queue
    q = queue.Queue()
    for c in chunked:
        q.put(c)
    threads = [threading.Thread(target=worker, args=(k,), daemon=True) for k in range(NWORKERS)]
    for t in threads:
        t.start()
    while True:
        alive = any(t.is_alive() for t in threads)
        if not alive and q.empty():
            break
        time.sleep(8)
    print("ALL DONE total results:", len(results), flush=True)

def save(results):
    tmp = OUT + '.tmp'
    json.dump(results, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False)
    os.replace(tmp, OUT)


def parse_json(content):
    # 容忍外层 ```json 包裹
    if content.startswith('```'):
        content = content.split('\n', 1)[1].rsplit('```', 1)[0].strip()
    try:
        return json.loads(content)
    except Exception:
        # 尝试提取第一个 [ 到最后一个 ]
        try:
            i = content.find('[')
            j = content.rfind(']')
            if i != -1 and j > i:
                return json.loads(content[i:j+1])
        except Exception:
            pass
        try:
            i = content.find('{')
            j = content.rfind('}')
            if i != -1 and j > i:
                return json.loads(content[i:j+1])
        except Exception:
            pass
        raise ValueError("JSON parse failed")

if __name__ == '__main__':
    main()