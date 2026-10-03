#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中英句子切分 + 一一对应对齐（调用大模型 API）
读取 e-book HTML 里的 EN/ZH JSON 数据 → 分批调用 API → 生成 {sec_id,para} -> 句子对齐
结果保存到 ../books/<book>/aligned_sentences.json（可断点续跑）
密钥从环境变量读取，勿硬编码。
"""
import json, re, sys, time, os, urllib.request

PROXY = os.environ.get("API_PROXY", "http://127.0.0.1:7890")
BASE = os.environ.get("LLM_BASE_URL")
API_KEY = os.environ.get("LLM_API_KEY")
MODEL = os.environ.get("LLM_MODEL", "current-model")
if not API_KEY or not BASE:
    raise SystemExit("请设置环境变量 LLM_API_KEY 与 LLM_BASE_URL")

BOOK_DIR = "/Users/zhulv/ReaderHub/books/cultures-colliding"
HTML = os.path.join(BOOK_DIR, "index.html")
OUT = os.path.join(BOOK_DIR, "aligned_sentences.json")

def extract(marker, s):
    start = s.index(marker) + len(marker); i = start; depth = 0
    while i < len(s):
        c = s[i]
        if c == '[': depth += 1
        elif c == ']':
            depth -= 1
            if depth == 0: return s[start:i+1]
        i += 1
    raise ValueError("unterminated array: " + marker)

def load_data():
    s = open(HTML, encoding='utf-8').read()
    EN = json.loads(extract('/*__EN__*/', s))
    ZH = json.loads(extract('/*__ZH__*/', s))
    return EN, ZH

def call_api(prompt, max_tokens=10000, retries=4):
    payload = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                          "temperature": 0, "max_tokens": max_tokens}).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(BASE, data=payload,
                headers={"Content-Type": "application/json", "Authorization": "Bearer " + API_KEY})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({'https': PROXY, 'http': PROXY}))
            resp = json.loads(opener.open(req, timeout=180).read())
            content = resp['choices'][0]['message']['content']
            # strip code fences if present
            content = content.strip()
            if content.startswith("```"):
                content = content.split('\n', 1)[1]
                content = content.rsplit('```', 1)[0]
            return json.loads(content)
        except Exception as e:
            print(f"  [attempt {attempt+1} failed: {e}]", flush=True)
            if attempt < retries-1:
                time.sleep(3 + attempt*3)
    return None

def build_prompt(batch):
    # batch: list of dicts {key, en, zh}
    ps = ""
    for b in batch:
        ps += f"\n---para {b['key']}---\nEN: {b['en']}\nZH: {b['zh']}\n"
    return (f"你是中英对照句子对齐专家。下面有 {len(batch)} 个中英对照段落。对每一段：\n"
            "1) 分别按句号中心切分英文句子（按 . ! ?）和中文句子（按 。！？）；\n"
            "2) 中文里引号内的句号不能导致误切（引号内标点不作为句界）；一句话必须完整包含其结尾引号。\n"
            "3) 每个句子必须原样保留原文（用于计算字符位置，绝不能改词、加字、删字、改标点），英文句首后的空格保留。\n"
            "4) 英文句子之间和中文句子之间做一一对应对齐 align；句数不一致时用一对多/多对一（如 [[0,0],[1,1],[1,2]] 表示英文句1对应中文句1和2）。\n"
            "5) 若英文某句因分页/换行而断裂（如 'Syden-' 和 'Stricker' 其实是同一句），要合并成一句。\n"
            "关键：每个对象的 key 必须原样照抄我给出的段落标识（如 ch1/79），绝不能改成序号或省略。\n只输出一个JSON数组（不要任何解释或代码块标记），一定要包含全部段落，按段落出现顺序，每段为:\n"
            "{\"key\":段落标识,\"en_sents\":[\"...\"],\"zh_sents\":[\"...\"],\"align\":[[e,z],...]}\n"
            "段落如下：" + ps)

BATCH = 6

def main():
    EN, ZH = load_data()
    zhmap = {z['id']: z for z in ZH}
    # collect text paragraphs
    para_list = []
    for sec in EN:
        z = zhmap.get(sec['id'])
        if not z: continue
        for i, p in enumerate(sec['paras']):
            if not isinstance(p, dict) or p.get('type', 'text') != 'text': continue
            if i >= len(z['paras']): continue
            zt = z['paras'][i].get('text') if isinstance(z['paras'][i], dict) else z['paras'][i]
            if not isinstance(p.get('text'), str) or not isinstance(zt, str): continue
            if len(p['text'].strip()) < 3 or len(zt.strip()) < 3: continue
            para_list.append({"key": f"{sec['id']}/{i}", "sec": sec['id'], "i": i,
                              "en": p['text'], "zh": zt})

    # load existing results
    results = {}
    if os.path.exists(OUT):
        try: results = json.load(open(OUT, encoding='utf-8'))
        except: results = {}

    todo = [p for p in para_list if p['key'] not in results]
    print(f"total text paras: {len(para_list)} | already done: {len(para_list)-len(todo)} | todo: {len(todo)}", flush=True)

    # chunk into batches
    chunks = [todo[i:i+BATCH] for i in range(0, len(todo), BATCH)]
    for ci, chunk in enumerate(chunks):
        prompt = build_prompt(chunk)
        data = call_api(prompt)
        if data is None:
            print(f"  batch {ci} FAILED (will retry later)", flush=True)
            continue
        if not isinstance(data, list):
            data = [data]
        n_ok = 0
        chunk_keys = [p['key'] for p in chunk]
        chunk_set = set(chunk_keys)
        # try items in returned order, matching by key first, then positionally
        for order, item in enumerate(data):
            if not isinstance(item, dict) or ('en_sents' not in item and 'zh_sents' not in item): continue
            key = item.get('key')
            if not key or key not in chunk_set:
                # positional fallback to the spot in this chunk (order-based from keys if dedup'd)
                # map by finding a chunk slot whose key not yet filled
                cand = [c for c in chunk_keys if c not in results]
                key = cand[order] if order < len(cand) else None
                if not key: continue
            results[key] = {"sec": key.split('/')[0], "i": int(key.split('/')[1]),
                            "en_sents": item.get('en_sents', []), "zh_sents": item.get('zh_sents', []),
                            "align": item.get('align', [])}
            json.dump(results, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
            n_ok += 1
        # if model returned fewer items than the chunk, log the shortfall
        if n_ok < len(chunk):
            print(f"    (chunk shortfall: got {n_ok}/{len(chunk)} items)", flush=True)
        print(f"  batch {ci+1}/{len(chunks)} done: {n_ok} paras (cumulative {len(results)})", flush=True)
        time.sleep(0.4)  # slight delay; concurrency already serial here

    print("DONE. results:", len(results), "->", OUT, flush=True)

if __name__ == '__main__':
    main()
