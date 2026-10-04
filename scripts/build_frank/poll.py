#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""轮询 batch 结果，全部 done 后下载各 Zip 到 zip/。"""
import json, os, time, urllib.request, subprocess
BASE='https://mineru.net/api/v4'
TOK='sk-P5Y5CLmwX7gr6DHxq6hTF65u7GNOWym55EmFY0cfl6STJA9S'
HERE=os.path.dirname(os.path.abspath(__file__))
WORK=os.path.join(HERE,'work'); ZIPDIR=os.path.join(HERE,'zip')
os.makedirs(ZIPDIR,exist_ok=True)
batch=json.load(open(os.path.join(WORK,'batch.json')))['data']['batch_id']
print('batch:',batch)
start=time.time()
done=set()
while time.time()-start<7200:
    try:
        req=urllib.request.Request(f"{BASE}/extract-results/batch/{batch}")
        req.add_header('Authorization','Bearer '+TOK); req.add_header('User-Agent','curl/8.0')
        with urllib.request.urlopen(req,timeout=120) as r: j=json.load(r)
    except Exception as e:
        print('err',str(e)[:80],flush=True); time.sleep(15); continue
    if j.get('code')!=0:
        print('code!=0',j.get('msg'),flush=True); time.sleep(15); continue
    results=j['data']['extract_result']
    allfin=True
    for it in results:
        st=it['state']; fn=it['file_name']
        print(f"  {fn}: {st}"+(f" err={it.get('err_msg','')[:60]}" if st=='failed' else ''),flush=True)
        if st=='done' and fn not in done:
            out=os.path.join(ZIPDIR,fn.replace('.pdf','.zip'))
            subprocess.run(['curl','-s','--noproxy','*','-o',out,'-w','HTTP %{http_code}','',it['full_zip_url']])
            print(f"    下载 {out}",flush=True); done.add(fn)
        if st not in ('done','failed'): allfin=False
    if allfin and len(results)>0:
        print('== 全部结束 ==',flush=True); break
    time.sleep(15)
print('ZIP:',os.listdir(ZIPDIR))