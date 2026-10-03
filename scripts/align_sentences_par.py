#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""并行版句子对齐：多线程调用 API（并发<=3），断点续跑，进度写入 JSON。"""
import json, re, time, os, threading, urllib.request
PROXY="http://127.0.0.1:7890"
BASE="LLM_BASE_URL"
API_KEY="LLM_API_KEY"
MODEL="current-model"
BOOK_DIR="/Users/zhulv/ReaderHub/books/cultures-colliding"
HTML=os.path.join(BOOK_DIR,"index.html")
OUT=os.path.join(BOOK_DIR,"aligned_sentences.json")
NWORKERS=3

def extract(marker,s):
    start=s.index(marker)+len(marker); i=start; depth=0
    while i<len(s):
        c=s[i]
        if c=='[': depth+=1
        elif c==']':
            depth-=1
            if depth==0: return s[start:i+1]
        i+=1
    raise ValueError(marker)

def call_api(prompt, max_tokens=10000, retries=5):
    payload=json.dumps({"model":MODEL,"messages":[{"role":"user","content":prompt}],"temperature":0,"max_tokens":max_tokens}).encode()
    for a in range(retries):
        try:
            req=urllib.request.Request(BASE,data=payload,headers={"Content-Type":"application/json","Authorization":"Bearer "+API_KEY})
            op=urllib.request.build_opener(urllib.request.ProxyHandler({'https':PROXY,'http':PROXY}))
            resp=json.loads(op.open(req,timeout=180).read())
            content=resp['choices'][0]['message']['content'].strip()
            if content.startswith('```'):
                content=content.split('\n',1)[1].rsplit('```',1)[0]
            return json.loads(content)
        except Exception as e:
            print(f"  [retry {a+1}] {str(e)[:80]}",flush=True); time.sleep(2+a*2)
    return None

def build_prompt(batch):
    ps=""
    for b in batch:
        ps+=f"\n---para {b['key']}---\nEN: {b['en']}\nZH: {b['zh']}\n"
    return (f"你是中英对照句子对齐专家。下面有 {len(batch)} 个中英对照段落。对每一段：\n"
     "1) 分别按句号中心切分英文句子（按 . ! ?）和中文句子（按 。！？）；\n"
     "2) 中文里引号内的句号不能导致误切；一句话必须完整包含其结尾引号。\n"
     "3) 每个句子必须原样保留原文（绝不改词/加字/删字/改标点），以便按字符定位。\n"
     "4) 英文句内因分页/换行断裂（如 'Syden-' 和 'Stricker' 实为一句）应合并。\n"
     "5) 中英句子一一对应对齐 align；句数不一致用一对多/多对一，如 [[0,0],[1,1],[1,2]] 表示英句1对中句1和2。\n"
     "关键：每个对象的 key 必须原样照抄我给出的段落标识（如 ch1/79），绝不能改成序号或省略。\n"
    f"只输出一个JSON数组（不要解释或代码块标记），一定要包含全部 {len(batch)} 个段落，按出现顺序，每段为:\n"
     '{"key":"...","en_sents":[],"zh_sents":[],"align":[]}\n段落如下：'+ps)

lock=threading.Lock()
def worker(qidx, q, results):
    while True:
        try: chunk = q.get_nowait()
        except Exception: return
        prompt=build_prompt(chunk)
        data=call_api(prompt)
        if data is None:
            print(f"  [w{qidx}] batch FAILED",flush=True); continue
        if not isinstance(data,list): data=[data]
        with lock:
            chunk_keys=[p['key'] for p in chunk]
            chunk_set=set(chunk_keys)
            for order,item in enumerate(data):
                if not isinstance(item,dict) or ('en_sents' not in item and 'zh_sents' not in item): continue
                key=item.get('key')
                if not key or key not in chunk_set:
                    cand=[c for c in chunk_keys if c not in results]
                    key=cand[order] if order<len(cand) else None
                    if not key: continue
                results[key]={"sec":key.split('/')[0],"i":int(key.split('/')[1]),
                    "en_sents":item.get('en_sents',[]),"zh_sents":item.get('zh_sents',[]),"align":item.get('align',[])}
            json.dump(results,open(OUT,'w',encoding='utf-8'),ensure_ascii=False)
            print(f"  [w{qidx}] batch done -> total {len(results)}",flush=True)
        time.sleep(0.3)

def main():
    s=open(HTML,encoding='utf-8').read()
    EN=json.loads(extract('/*__EN__*/',s)); ZH=json.loads(extract('/*__ZH__*/',s))
    zhmap={z['id']:z for z in ZH}
    def txt(x): return x['text'] if isinstance(x,dict) else x
    pl=[]
    for sec in EN:
        z=zhmap.get(sec['id'])
        if not z: continue
        for i,p in enumerate(sec['paras']):
            if not isinstance(p,dict) or p.get('type','text')!='text' or i>=len(z['paras']): continue
            zt=txt(z['paras'][i])
            if isinstance(p.get('text'),str) and isinstance(zt,str) and len(p['text'].strip())>=3 and len(zt.strip())>=3:
                pl.append({"key":f"{sec['id']}/{i}","en":p['text'],"zh":zt})
    results={}
    if os.path.exists(OUT):
        try: results=json.load(open(OUT,encoding='utf-8'))
        except: results={}
    todo=[p for p in pl if p['key'] not in results]
    BATCH=5
    chunks=[todo[i:i+BATCH] for i in range(0,len(todo),BATCH)]
    print(f"total {len(pl)} done {len(results)} todo {len(todo)} chunks {len(chunks)} workers {NWORKERS}",flush=True)
    q=__import__('queue').Queue()
    for c in chunks: q.put(c)
    threads=[threading.Thread(target=worker,args=(k,q,results),daemon=True) for k in range(NWORKERS)]
    for t in threads: t.start()
    while q.qsize() or any(t.is_alive() for t in threads):
        time.sleep(5)
    print("DONE",len(results),flush=True)

if __name__=='__main__':
    main()
