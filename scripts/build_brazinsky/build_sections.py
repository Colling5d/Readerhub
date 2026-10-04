#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stream_raw.json -> en_data.json (Gregg Brazinsky, Winning the Third World)
章节：intro / ch1..ch10 / conclusion / notes。
类型：章标题='h' 小节并入正文='text' 注释条目='note' 注释分区标题='subh'。
Bibliography(420-437) 与 Index(438-441) 不进入（方案B：略去）。
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
items = json.load(open(os.path.join(HERE,'stream_raw.json'), encoding='utf-8'))

SECTIONS = [
    ('intro',      "Introduction  导言",                                16, 30),
    ('ch1',        "Chapter 1 · The Emergence of a Rivalry  第一章 · 竞争关系的产生", 31, 63),
    ('ch2',        "Chapter 2 · The Burdens of Status  第二章 · 地位的负担",      64, 91),
    ('ch3',        "Chapter 3 · From Geneva to Bandung  第三章 · 从日内瓦到万隆", 92, 122),
    ('ch4',        "Chapter 4 · Advancing the Peace Offensive  第四章 · 推进和平攻势", 123, 148),
    ('ch5',        "Chapter 5 · The Cultural Competition  第五章 · 文化竞争",     149, 182),
    ('ch6',        "Chapter 6 · China's Radicalization and the American Response  第六章 · 中国的激进与美国的回应", 183, 211),
    ('ch7',        "Chapter 7 · The Diplomatic Campaign  第七章 · 外交运动",       212, 247),
    ('ch8',        "Chapter 8 · Insurgency and Counterinsurgency  第八章 · 叛乱与反叛乱", 248, 286),
    ('ch9',        "Chapter 9 · The Economic Competition  第九章 · 经济竞争",       287, 320),
    ('ch10',       "Chapter 10 · Competition and Cooperation  第十章 · 竞争与合作", 321, 363),
    ('conclusion', "Conclusion  结语",                                      364, 373),
    ('notes',      "Notes  注释",                                         374, 419),
]

NOTES_SUBHEADS = {'Notes','Abbreviations','Introduction','Conclusion',
                  'Chapter 1','Chapter 2','Chapter 3','Chapter 4','Chapter 5',
                  'Chapter 6','Chapter 7','Chapter 8','Chapter 9','Chapter 10'}

def norm(s): return ' '.join(s.split())

def is_noise(t):
    t=t.strip()
    if not t: return True
    if re.fullmatch(r'[\d\s\.\-\[\]ivxlcdmIVXLCDM]+', t): return True
    return False

def first_on_page(pg):
    for x in items:
        if x['page']==pg and x['type'] in ('text','ref_text'):
            t=norm(x['text']).strip()
            if not is_noise(t) and t!='This page intentionally left blank': return t
    return None

def main():
    results=[]
    for sid, title, a, b in SECTIONS:
        paras=[]
        if sid=='notes':
            pending=None
            def flush():
                nonlocal pending
                if pending: paras.append({"type":'note',"text":pending})
                pending=None
            for x in items:
                if x['page']<a or x['page']>b: continue
                t=norm(x['text']).strip()
                if is_noise(t) or t=='This page intentionally left blank': continue
                if t in NOTES_SUBHEADS:
                    flush(); paras.append({"type":'subh',"text":t}); continue
                if t.startswith('Notes:') and sid=='notes':
                    flush(); paras.append({"type":'subh',"text":t}); continue
                if re.match(r'^\d+\.\s', t) or re.match(r'^[a-z]\.\s', t):
                    flush(); pending=t
                else:
                    pending = t if pending is None else pending + ' ' + t
            flush()
        else:
            # 章标题 = 起始页第一个有效 text（Chapter N 后接章名，可能两行合并，取合并结果）
            ht = first_on_page(a)
            if ht:
                paras.append({"type":'h',"text":ht})
            for x in items:
                if x['page']<a or x['page']>b: continue
                t=norm(x['text']).strip()
                if is_noise(t) or t=='This page intentionally left blank': continue
                if t==ht: continue
                if t in ('Conclusion','Epilogue'): continue
                paras.append({"type":'text',"text":t})
        # 去重相邻
        dedup=[]
        for p in paras:
            if dedup and dedup[-1]['text']==p['text'] and dedup[-1]['type']==p['type']:
                continue
            dedup.append(p)
        numT=sum(1 for p in dedup if p['type'] in ('text','note'))
        numH=sum(1 for p in dedup if p['type']=='h'); numS=sum(1 for p in dedup if p['type']=='subh')
        results.append({"id":sid,"title":title,"numText":numT,"numH":numH,"numSubh":numS,
                        "chars":sum(len(p['text']) for p in dedup),"paras":dedup})
        firstline=dedup[0]['text'][:45] if dedup else ''
        print(f"{sid:10s} text/note={numT:4d} h={numH:3d} subh={numS:3d} chars={sum(len(p['text']) for p in dedup):6d} | {firstline}", flush=True)
    with open(os.path.join(HERE,'en_data.json'),'w',encoding='utf-8') as f:
        json.dump([{"id":s["id"],"title":s["title"],"paras":s["paras"]} for s in results], f, ensure_ascii=False)
    print(f"\nTOTAL text/note={sum(s['numText'] for s in results)} subh={sum(s['numSubh'] for s in results)} h={sum(s['numH'] for s in results)} chars={sum(s['chars'] for s in results)}", flush=True)

if __name__=='__main__':
    main()