#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_sections.py (custom, for samoylov-russia-china-lecture)
单语俄文文档：按“段落序号”精确切分主题 section（页边界不可靠，因为一页混多主题）。
去重：全文出现完全相同的段落（OCR 重复）只保留首次。
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
items = json.load(open(os.path.join(HERE, 'stream_raw.json'), encoding='utf-8'))
TEXTS = [' '.join(x['text'].split()) for x in items if x['type'] in ('text', 'ref_text')]

# 段落序号区间（含端点）——依据内容自然分节
SECTIONS = [
    ('peter',       'Пётр I и начало изучения Китая в России', (0, 2)),
    ('kyakhta',     'Кяхтинская торговля',                     (3, 11)),
    ('mission',     'Российская Духовная Миссия в Пекине',     (12, 17)),
    ('chinoiserie', 'Русская версия «шинуазри»',               (18, 47)),
    ('tea',         'Чай',                                     (48, 76)),
    ('perlov',      'Перловы — «чайные короли» России',        (77, 85)),
    ('crossyears',  'Перекрестные годы России и Китая',        (86, 112)),
]

# 需丢弃的噪声段（页眉/页码/残缺片段）
DROP = {
    'Самойлов Н.А.', 'ЛЕКЦИЯ 1',
}

def is_noise(t):
    t = t.strip()
    if not t or t in DROP:
        return True
    if re.fullmatch(r'[\d\s\.\-\[\]ivxlcdmIVXLCDM]+', t):
        return True
    return False

def main():
    seen = set()
    results = []
    for sid, title, (a, b) in SECTIONS:
        paras = []
        for i in range(a, min(b + 1, len(TEXTS))):
            t = TEXTS[i]
            if is_noise(t):
                continue
            if t in seen:
                continue
            seen.add(t)
            paras.append({'type': 'text', 'text': t})
        results.append({'id': sid, 'title': title, 'paras': paras})
        print(f"{sid:12s} paras={len(paras):4d} chars={sum(len(p['text']) for p in paras):7d} | {(paras[0]['text'][:45] if paras else '')}", flush=True)

    with open(os.path.join(HERE, 'en_data.json'), 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False)
    print(f"\nTOTAL sections={len(results)} paras={sum(len(s['paras']) for s in results)}", flush=True)

if __name__ == '__main__':
    main()
