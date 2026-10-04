#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stream_raw.json -> en_data.json (Caroline Frank, Objectifying China, Imagining America)
章节：intro / ch1..ch5 / epilogue / notes。
类型：章标题='h' 正文='text' 注释条目='note'。
前页(1-16) 与 Index(269-276) 不进入（方案B：略去）。
小节标题不单独拆分，并入正文（保持句子对齐的完整性）。
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
items = json.load(open(os.path.join(HERE,'stream_raw.json'), encoding='utf-8'))

# 章节边界 (id, 显示标题, start_page, end_page含; start_page 的第一个 text 为该章标题)
SECTIONS = [
    ('intro',    "Introduction · Beyond the Atlantic in Anglo-America  导言：超越大西洋的英美世界", 17, 42),
    ('ch1',      "Chapter 1 · The First American China Trade  第一章 · 最早的美国对华贸易",       43, 74),
    ('ch2',      "Chapter 2 · Imagining China at Home  第二章 · 在家想象中国",                   75, 112),
    ('ch3',      "Chapter 3 · Islands of Illicit Refinement  第三章 · 不法精致的孤岛",           113, 158),
    ('ch4',      "Chapter 4 · The Oriental Aesthetic in Old Yankee Households  第四章 · 老美国人家中的东方审美", 159, 190),
    ('ch5',      "Chapter 5 · Manly Tea Parties  第五章 · 阳刚的茶会",                         191, 218),
    ('epilogue', "Epilogue · An East Indies Trade for North America  结语：通往北美的东印度贸易", 219, 224),
    ('notes',    "Notes  注释",                                                                 225, 268),
]

NOTES_SUBHEADS = {'Notes','Introduction','Chapter 1','Chapter 2','Chapter 3',
                  'Chapter 4','Chapter 5','Epilogue'}

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
            if not is_noise(t): return t
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
                if is_noise(t): continue
                if t=='Notes':
                    paras.append({"type":'h',"text":t}); continue
                if t in NOTES_SUBHEADS:
                    flush(); paras.append({"type":'subh',"text":t}); continue
                if re.match(r'^\d+\.\s', t) or re.match(r'^[a-z]\.\s', t):
                    flush(); pending=t
                else:
                    pending = t if pending is None else pending + ' ' + t
            flush()
            # h/subh 拆出来合并标题（保留顺序：Notes 大标题 + 各章小标题）
        else:
            # 章标题：该章起始页第一个 text
            ht = first_on_page(a)
            if ht: paras.append({"type":'h',"text":ht})
            for x in items:
                if x['page']<a or x['page']>b: continue
                t=norm(x['text']).strip()
                if is_noise(t): continue
                if t==ht: continue   # 去掉与章标题重复的正文行
                if t in ('Epilogue',): continue
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
        firstline = dedup[0]['text'][:50] if dedup else ''
        print(f"{sid:9s} text/note={numT:4d} h={numH:3d} subh={numS:3d} chars={sum(len(p['text']) for p in dedup):6d} | 首段: {firstline}", flush=True)
    with open(os.path.join(HERE,'en_data.json'),'w',encoding='utf-8') as f:
        json.dump([{"id":s["id"],"title":s["title"],"paras":s["paras"]} for s in results], f, ensure_ascii=False)
    tt=sum(s['numText'] for s in results)
    cc=sum(s['chars'] for s in results)
    print(f"\nTOTAL text/note={tt} subh={sum(s['numSubh'] for s in results)} h={sum(s['numH'] for s in results)} chars={cc}", flush=True)

if __name__=='__main__':
    main()