#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仅重新申请文件上传URL并用 curl PUT -T 上传（去掉 Content-Type, 使 OSS 签名匹配）。"""
import json, os, sys, subprocess, urllib.request

BASE = 'https://mineru.net/api/v4'
TOK = 'sk-P5Y5CLmwX7gr6DHxq6hTF65u7GNOWym55EmFY0cfl6STJA9S'
HERE = os.path.dirname(os.path.abspath(__file__))
PDFDIR = os.path.join(HERE, 'pdf')

def main():
    pdfs = sorted(f for f in os.listdir(PDFDIR) if f.endswith('.pdf'))
    files_list = [{"name": f, "data_id": os.path.splitext(f)[0][:128]} for f in pdfs]
    payload = {"files": files_list, "model_version": 'vlm',
               "enable_formula": False, "enable_table": True}
    req = urllib.request.Request(BASE+'/file-urls/batch',
                                 data=json.dumps(payload).encode(), method='POST')
    req.add_header('Authorization','Bearer '+TOK)
    req.add_header('User-Agent','curl/8.0')
    with urllib.request.urlopen(req, timeout=180) as r:
        j = json.load(r)
    if j.get('code')!=0:
        print('申请失败', j); return
    batch_id = j['data']['batch_id']
    urls = j['data']['file_urls']
    with open(os.path.join(HERE,'work','batch_id.txt'),'w') as f: f.write(batch_id)
    print('batch_id:', batch_id)
    for name, u in zip([f['name'] for f in files_list], urls):
        path = os.path.join(PDFDIR, name)
        print(f"curl PUT -T {name} ...", flush=True)
        r = subprocess.run(['curl','-s','-o','/dev/null','-w','%{http_code}','-X','PUT','-T',path,u],
                           capture_output=True, text=True)
        print(f"  {name} -> HTTP {r.stdout}", flush=True)
    print('DONE')

if __name__=='__main__':
    main()