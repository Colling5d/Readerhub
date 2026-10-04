#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""申请 upload URL + curl PUT 上传两张 PDF，存 batch + url。"""
import json, os, subprocess, urllib.request, re

BASE='https://mineru.net/api/v4'
TOK='sk-P5Y5CLmwX7gr6DHxq6hTF65u7GNOWym55EmFY0cfl6STJA9S'
HERE=os.path.dirname(os.path.abspath(__file__))
PDFDIR=os.path.join(HERE,'pdf'); WORK=os.path.join(HERE,'work')
os.makedirs(WORK,exist_ok=True)

def main():
    pdfs=sorted(f for f in os.listdir(PDFDIR) if f.endswith('.pdf'))
    files_list=[{"name":f,"data_id":f.split('.')[0][:120]} for f in pdfs]
    payload={"files":files_list,"model_version":"vlm","enable_formula":False,"enable_table":True}
    req=urllib.request.Request(BASE+'/file-urls/batch',data=json.dumps(payload).encode(),method='POST')
    req.add_header('Authorization','Bearer '+TOK); req.add_header('User-Agent','curl/8.0')
    with urllib.request.urlopen(req,timeout=180) as r: j=json.load(r)
    if j.get('code')!=0:
        print('申请失败:',j); return
    batch=j['data']['batch_id']; urls=j['data']['file_urls']
    with open(os.path.join(WORK,'batch.json'),'w') as f:
        json.dump({"batch_id":batch,"urls":urls,"names":[f['name'] for f in files_list]},f,indent=2)
    print('batch_id:',batch)
    for name,u in zip([f['name'] for f in files_list],urls):
        path=os.path.join(PDFDIR,name)
        r=subprocess.run(['curl','-s','-o','/dev/null','-w','%{http_code}','-X','PUT','-T',path,u],capture_output=True,text=True)
        print(f"  upload {name}: HTTP {r.stdout}")
    print("DONE")

if __name__=='__main__':
    main()