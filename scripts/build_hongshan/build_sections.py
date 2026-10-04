#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stream_raw.json -> en_data.json。
按页边界划分章节（新书《Fighting on the Cultural Front》）：
  abbrev(缩写) / intro / ch1..ch8 / epilogue / notes。
类型：章标题='h' 小节标题='subh' 正文='text' 注释条目='note'。
Bibliography 与 Index 不进入（方案B：略去/保留英文）。
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
items = json.load(open(os.path.join(HERE,'stream_raw.json'), encoding='utf-8'))

# 章节边界 (id, 显示标题, start_page, end_page含)
SECTIONS = [
    ('abbrev',   "Abbreviations  缩写表",                                       12, 16),
    ('intro',    "Introduction · Beating Plowshares into Swords  导言：化剑为犁", 18, 29),
    ('ch1',      "Chapter 1 · Drawing the Sword  第一章 · 亮出宝剑",             30, 66),
    ('ch2',      "Chapter 2 · Cutting All Ties  第二章 · 一刀两断",              67, 100),
    ('ch3',      "Chapter 3 · Fighting Over the Stranded  第三章 · 争夺滞留者",   101, 139),
    ('ch4',      "Chapter 4 · Building a Cultural Bastion  第四章 · 构筑文化堡垒", 140, 177),
    ('ch5',      "Chapter 5 · Faking the Exchange  第五章 · 虚构的交流",           178, 217),
    ('ch6',      "Chapter 6 · Setting a New Pattern  第六章 · 开创新格局",         218, 258),
    ('ch7',      "Chapter 7 · Forging the Black Blade  第七章 · 铸就黑色利刃",     259, 296),
    ('ch8',      "Chapter 8 · Lowering the Sword  第八章 · 放下宝剑",              297, 337),
    ('epilogue', "Epilogue · Beyond Rattling  结语：超越空谈",                     338, 355),
    ('notes',    "Notes  注释",                                                    356, 435),
]

NOTES_SUBHEADS = {
    'Introduction: Beating Plowshares into Swords',
    'Epilogue: Beyond Rattling',
    'Notes',
}
for n,c in [('Drawing the Sword','1'),('Cutting All Ties','2'),('Fighting Over the Stranded','3'),
            ('Building a Cultural Bastion','4'),('Faking the Exchange','5'),('Setting a New Pattern','6'),
            ('Forging the Black Blade','7'),('Lowering the Sword','8')]:
    NOTES_SUBHEADS.add(f"{c}. {n}")

def norm(s): return ' '.join(s.split())

def is_noise(t):
    t=t.strip()
    if not t: return True
    if re.fullmatch(r'[\d\s\.\-\[\]ivxlcdmIVXLCDM]+', t): return True
    return False

def main():
    results = []
    for sid, title, a, b in SECTIONS:
        paras = []
        if sid == 'notes':
            # 特判：合并续行
            pending = None   # (text, is_new_entry_head)
            def flush():
                nonlocal pending
                if pending: paras.append({"type":'note',"text":pending})
                pending=None
            for x in items:
                if x['page'] < a or x['page'] > b: continue
                t = norm(x['text']).strip()
                if is_noise(t): continue
                # Notes 主标题
                if t == 'Notes':
                    paras.append({"type":'h',"text":t}); continue
                # 章节注释标题
                if t in NOTES_SUBHEADS:
                    flush(); paras.append({"type":'subh',"text":t}); continue
                # 编号条目开头 -> 新 note；否则续行合并
                if re.match(r'^\d+\.\s', t) or re.match(r'^[a-z]\.\s', t):
                    flush(); pending=t
                else:
                    if pending is None:
                        pending=t
                    else:
                        pending = pending + ' ' + t
            flush()
        else:
            for x in items:
                if x['page'] < a or x['page'] > b: continue
                t = norm(x['text']).strip()
                if is_noise(t): continue
                lvl = x.get('lvl')
                # 章标题 force
                if t in CHAPTER_NAMES:
                    paras.append({"type":'h',"text":t}); continue
                if lvl == 1:
                    paras.append({"type":'h',"text":t}); continue
                if lvl == 2:
                    paras.append({"type":'subh',"text":t}); continue
                paras.append({"type":'text',"text":t})
        # 去重相邻同文同型
        dedup=[]
        for p in paras:
            if dedup and dedup[-1]['text']==p['text'] and dedup[-1]['type']==p['type']:
                continue
            dedup.append(p)
        results.append({"id":sid,"title":title,
            "numText":sum(1 for p in dedup if p['type'] in ('text','note')),
            "numH":sum(1 for p in dedup if p['type']=='h'),
            "numSubh":sum(1 for p in dedup if p['type']=='subh'),
            "chars":sum(len(p['text']) for p in dedup),
            "paras":dedup})
        print(f"{sid:9s} text/note={results[-1]['numText']:4d} h={results[-1]['numH']:3d} subh={results[-1]['numSubh']:3d} chars={results[-1]['chars']}", flush=True)
    with open(os.path.join(HERE,'en_data.json'),'w',encoding='utf-8') as f:
        json.dump([{"id":s["id"],"title":s["title"],"paras":s["paras"]} for s in results], f, ensure_ascii=False)
    tt=sum(s['numText'] for s in results); cc=sum(s['chars'] for s in results)
    print(f"\nTOTAL text/note={tt} subh={sum(s['numSubh'] for s in results)} h={sum(s['numH'] for s in results)} chars={cc}")

CHAPTER_NAMES = {
    'Beating Plowshares into Swords','Drawing the Sword','Cutting All Ties',
    'Fighting Over the Stranded','Building a Cultural Bastion','Faking the Exchange',
    'Setting a New Pattern','Forging the Black Blade','Lowering the Sword','Epilogue',
    'Abbreviations','Introduction', 'Introduction: Beating Plowshares into Swords',
    'Epilogue: Beyond Rattling',
}

if __name__=='__main__':
    main()