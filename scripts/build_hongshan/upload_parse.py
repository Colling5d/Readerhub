#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把拆分的本地 PDF 用 MinerU 精准 API 批量上传并自动提交解析任务。
流程: POST /api/v4/file-urls/batch 申请签名上传URL -> PUT 上传本地文件 -> 自动解析。
保存 batch_id 到 work/batch_id.txt。
注意 mineru.net 需 NO_PROXY 直连。
"""
import json, os, sys, time, urllib.request

BASE = 'https://mineru.net/api/v4'
TOK = 'sk-P5Y5CLmwX7gr6DHxq6hTF65u7GNOWym55EmFY0cfl6STJA9S'
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, 'work')
os.makedirs(WORK, exist_ok=True)
PDFDIR = os.path.join(HERE, 'pdf')
MODEL = 'vlm'

def api(res):
    """urllib 发起请求, 设置 UA, 返回 json."""
    req = urllib.request.Request(res['url'], data=res.get('data'), method=res.get('method','GET'))
    req.add_header('Content-Type', res.get('ctype','application/json'))
    req.add_header('Authorization', 'Bearer ' + TOK)
    req.add_header('User-Agent', 'curl/8.0')
    with urllib.request.urlopen(req, timeout=180) as r:
        body = r.read()
        try:
            return json.loads(body)
        except Exception:
            return {'code': -1, 'raw': body[:500].decode()}

def main():
    files_list = []
    pdfs = sorted(f for f in os.listdir(PDFDIR) if f.endswith('.pdf'))
    if not pdfs:
        print('no pdf'); return
    for f in pdfs:
        files_list.append({"name": f, "data_id": os.path.splitext(f)[0][:128]})
    print("上传文件:", [f['name'] for f in files_list], flush=True)
    # 1) 申请上传URL
    payload = {"files": files_list, "model_version": MODEL,
               "enable_formula": False, "enable_table": True}
    r = api({'url': BASE+'/file-urls/batch', 'data': json.dumps(payload).encode(), 'method':'POST'})
    print("申请结果:", json.dumps(r, ensure_ascii=False)[:400], flush=True)
    if r.get('code') != 0:
        print('申请失败:', r.get('msg')); return
    batch_id = r['data']['batch_id']
    urls = r['data']['file_urls']
    with open(os.path.join(WORK,'batch_id.txt'),'w') as f:
        f.write(batch_id)
    print('batch_id:', batch_id, flush=True)
    # 2) PUT 上传每个文件
    for name, u in zip([f['name'] for f in files_list], urls):
        path = os.path.join(PDFDIR, name)
        print(f"上传 {name} ...", flush=True)
        with open(path,'rb') as fbody:
            data = fbody.read()
        req = urllib.request.Request(u, data=data, method='PUT')
        req.add_header('Content-Type','application/octet-stream')
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                print('  PUT', resp.status, flush=True)
        except urllib.error.HTTPError as e:
            print('  PUT HTTPError', e.code, e.read()[:200], flush=True)
    print('上传完成, 等待自动解析. batch_id=', batch_id, flush=True)

if __name__ == '__main__':
    main()