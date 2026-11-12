#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为主翻译进程结束后因 JSON parse failed 而缺失的段落补齐翻译。
复用 translate.py 的 API 调用与 prompt 构建；支持断点续跑。
"""
import json, os, sys, time, random, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))

# 复用 translate.py 的常量与函数
spec = importlib.util.spec_from_file_location("tr", os.path.join(HERE, 'translate.py'))
tr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tr)

OUT = tr.OUT
EN_DATA = tr.EN_DATA

def main():
    data = json.load(open(EN_DATA, encoding='utf-8'))
    results = {}
    if os.path.exists(OUT):
        results = json.load(open(OUT, encoding='utf-8'))

    # 找出缺失 key
    missing = []
    for sec in data:
        sid = sec['id']
        for i, p in enumerate(sec['paras']):
            key = f"{sid}/{i}"
            if key not in results:
                missing.append((key, p['type'], p['text']))
    print(f"missing keys: {len(missing)}", flush=True)
    if not missing:
        print("nothing to retry. ALL DONE")
        return

    # 逐段补 (retry robustly, 每段重试多次)
    def call_one(key, typ, text):
        for attempt in range(8):
            try:
                if typ == 'h':
                    prompt = tr.build_trans_only(key, text)
                    out = tr.call_api(prompt, max_tokens=6000)
                    obj = json.loads(out)
                    return obj
                else:
                    prompt = tr.build_combined([(key, text)])
                    out = tr.call_api(prompt, max_tokens=tr.MAX_TOK)
                    arr = json.loads(out)
                    # 找 key 对应的对象
                    for obj in arr:
                        if obj.get('key') == key:
                            return obj
                    # 若只有一个对象但 key 不同，容错
                    if len(arr) == 1:
                        obj = arr[0]
                        obj['key'] = key
                        return obj
                    raise ValueError('key mismatch in returned batch')
            except Exception as e:
                print(f"    [{key}] attempt {attempt+1} failed: {str(e)[:90]}", flush=True)
                time.sleep(3 + attempt * 5)
        return None

    for n, (key, typ, text) in enumerate(missing, 1):
        obj = call_one(key, typ, text)
        if obj is None:
            print(f"GIVE UP {key}", flush=True)
            continue
        # 保存 en/zh（combined 还有 sents/align，trans-only 只有 en/zh）
        # 归一化：确保对象至少有 en 与 zh
        if 'en' not in obj or 'zh' not in obj:
            print(f"WARN {key} no en/zh: {list(obj.keys())}", flush=True)
        results[key] = obj
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False)
        print(f"[{n}/{len(missing)}] done {key} zh={obj.get('zh','')[:40]}", flush=True)
        time.sleep(tr.CALL_DELAY)
        # 每 5 段额外小幅等待，减 429
        if n % 5 == 0:
            time.sleep(3)

    print("done retry. total entries:", len(results))

if __name__ == '__main__':
    main()