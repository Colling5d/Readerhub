#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全文翻译 + 句子对齐（综合 prompt）。
读取 en_data.json → 每个 text/note 段落做 清洁英文+中译+切句+对齐；h 段做纯翻译。
产出 work/translated.json（按 'secid/i' 键，断点续跑）。
"""
import json, os, re, time, threading, urllib.request, math, sys

BASE = 'https://chat.ecnu.edu.cn/open/api/v1/chat/completions'
KEY = 'sk-e1d6953fb6c348d193d8dd4a03c6edc7'
MODEL = 'ecnu-max'
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, 'work')
os.makedirs(WORK, exist_ok=True)
OUT = os.path.join(WORK, 'translated.json')
EN_DATA = os.path.join(HERE, 'en_data.json')

NWORKERS = 3
BATCH = 3
MAX_TOK = 16000
CALL_DELAY = 2.0   # 每次调用间的线程内固定间隔，减轻 429

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
            backoff = 4 + a * 8 if '429' in str(e) else 3 + a * 4
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

def main():
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
                            json.dump(results, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
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
                            json.dump(results, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
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