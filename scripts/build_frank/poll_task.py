#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""针对指定 batch_id 轮询并下载 zip。用法: python3 poll_task.py <batch_id> <jsonfile>"""
import json, os, sys, time, urllib.request, subprocess
BASE='https://mineru.net/api/v4'
TOK='sk-P5Y5CLmwX7gr6DHxq6hTF65u7GNOWym55EmFY0cfl6STJA9S'
HERE=os.path.dirname(os.path.abspath(__file__))
ZIPDIR=os.path.join(HERE,'zip'); os.makedirs(ZIPDIR,exist_ok=True)
batch, jf = sys.argv[1], sys.argv[2]
print('batch:',batch,flush=True)
start=time.time()
while time.time()-start<7200:
    try:
        req=urllib.request.Request(f"{BASE}/extract-results/batch/{batch}")
        req.add_header('Authorization','Bearer '+TOK); req.add_header('User-Agent','curl/8.0')
        with urllib.request.urlopen(req,timeout=120) as r: j=json.load(r)
    except Exception as e:
        print('err',str(e)[:80],flush=True); time.sleep(15); continue
    if j.get('code')!=0:
        print('code!=0',j.get('msg'),flush=True); time.sleep(15); continue
    results=j['data']['extract_result']; fin=True
    for it in results:
        st=it['state']; fn=it['file_name']
        print(f"  {fn}: {st}"+(f" err={it.get('err_msg','')[:60]}" if st=='failed' else ''),flush=True)
        if st=='done':
            out=os.path.join(ZIPDIR,fn.replace('.pdf','.zip'))
            subprocess.run(['curl','-s','--noproxy','*','-o',out,'-w','   dl HTTP %{http_code} %{size_download}\\n','-L',it['full_zip_url']],check=False)
            print(f"      -> {out}",flush=True)
        elif st!='failed': fin=False
    if fin: print('== 全部结束 ==',flush=True); break
    time.sleep(15)
print('ZIP:',os.listdir(ZIPDIR),flush=True)