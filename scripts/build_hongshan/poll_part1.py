#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只轮询 part1 的重传 batch1 并下载 zip。"""
import json, os, time, urllib.request, subprocess
BASE='https://mineru.net/api/v4'
TOK='sk-P5Y5CLmwX7gr6DHxq6hTF65u7GNOWym55EmFY0cfl6STJA9S'
HERE=os.path.dirname(os.path.abspath(__file__))
WORK=os.path.join(HERE,'work')
ZIPDIR=os.path.join(HERE,'zip')
os.makedirs(ZIPDIR,exist_ok=True)
batch=open(os.path.join(WORK,'batch1_id.txt')).read().strip()
print('batch1:',batch)
start=time.time()
while time.time()-start<3600:
    try:
        req=urllib.request.Request(f"{BASE}/extract-results/batch/{batch}")
        req.add_header('Authorization','Bearer '+TOK)
        req.add_header('User-Agent','curl/8.0')
        with urllib.request.urlopen(req,timeout=120) as r:
            j=json.load(r)
    except Exception as e:
        print('err',str(e)[:80],flush=True); time.sleep(12); continue
    res=j.get('data',{}).get('extract_result',[])
    if not res:
        time.sleep(10); continue
    it=res[0]; st=it['state']
    print(f"part1: {st}"+(f" err={it.get('err_msg','')[:100]}" if st=='failed' else ''),flush=True)
    if st=='done' and it.get('full_zip_url'):
        out=os.path.join(ZIPDIR,'part1_p1-200.zip')
        subprocess.run(['curl','-s','--noproxy','*','-o',out,'-w','HTTP %{http_code}','',it['full_zip_url']])
        print(f"\ndownloaded {out}",flush=True)
        print('DONE',flush=True); break
    if st=='failed':
        print('FAILED permanently',flush=True); break
    time.sleep(15)
print('exit')