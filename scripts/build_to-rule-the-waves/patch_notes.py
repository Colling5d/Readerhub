#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补译失败的超长注释：按句边界切成 ~1200 字符块分别翻译，再拼接。
对齐退化为整段一对一（注释段不需要逐句高亮）。"""
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import translate as T  # 复用 call_api

HERE = os.path.dirname(os.path.abspath(__file__))
EN = json.load(open(os.path.join(HERE, 'en_data.json'), encoding='utf-8'))
OUT = os.path.join(HERE, 'work', 'translated.json')
res = json.load(open(OUT, encoding='utf-8'))

SYS = ('你是学术著作翻译。把下面这段英文（图书注释/参考文献条目，可能含网址）译成规范中文，'
       '保留全部网址、数字、期刊卷期页码与人名原样不译；书名首次出现给中文并括注原文。'
       '只输出译文本身，不要任何解释或代码块。\n\n')


def chunks(text, limit=1100):
    parts = re.split(r'(?<=[.;:])\s+', text)
    out, cur = [], ''
    for p in parts:
        if cur and len(cur) + len(p) > limit:
            out.append(cur); cur = p
        else:
            cur = (cur + ' ' + p).strip()
    if cur:
        out.append(cur)
    return out


def main():
    todo = []
    for sec in EN:
        for i, p in enumerate(sec['paras']):
            k = f"{sec['id']}/{i}"
            if k in res:
                continue
            todo.append((k, p['text']))
    print('todo', len(todo), flush=True)
    for k, text in todo:
        zh = []
        ok = True
        for c in chunks(text):
            try:
                zh.append(T.call_api(SYS + c, max_tokens=3000, retries=4).strip())
            except Exception as e:
                print('  fail chunk', str(e)[:60], flush=True); ok = False; break
            time.sleep(2)
        if not ok:
            continue
        zh_text = ''.join(zh)
        res[k] = {'type': 'C', 'en': text, 'zh': zh_text,
                  'en_sents': [text], 'zh_sents': [zh_text], 'align': [[0, 0]]}
        T.save(res)
        print('  done', k, len(zh_text), flush=True)
    print('final', len(res), flush=True)


if __name__ == '__main__':
    main()
