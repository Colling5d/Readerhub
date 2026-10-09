#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""轮询 MinerU 解析结果并下载 zip；对 failed 的文件自动重传重试。
用法: python3 poll_all.py <batch_id> <batch.json>
batch.json: {"data":{"batch_id":..., "file_urls":[url...]}}
"""
import json, os, sys, time, urllib.request, subprocess, re

BASE = 'https://mineru.net/api/v4'
TOK = 'sk-P5Y5CLmwX7gr6DHxq6hTF65u7GNOWym55EmFY0cfl6STJA9S'
HERE = os.path.dirname(os.path.abspath(__file__))
ZIPDIR = os.path.join(HERE, 'zip'); os.makedirs(ZIPDIR, exist_ok=True)
PDFDIR = os.path.join(HERE, 'pdf')

def poll_batch(batch):
    start = time.time()
    done_names = set()
    for name in os.listdir(ZIPDIR):
        done_names.add(name.replace('.zip', ''))
    while time.time() - start < 7200:
        try:
            req = urllib.request.Request(f"{BASE}/extract-results/batch/{batch}")
            req.add_header('Authorization', 'Bearer ' + TOK); req.add_header('User-Agent', 'curl/8.0')
            with urllib.request.urlopen(req, timeout=120) as r:
                j = json.load(r)
        except Exception as e:
            print('err', str(e)[:80], flush=True); time.sleep(15); continue
        if j.get('code') != 0:
            print('code!=0', j.get('msg'), flush=True); time.sleep(15); continue
        results = j['data']['extract_result']
        for it in results:
            fn = it['file_name']; st = it['state']
            zname = fn.replace('.pdf', '.zip')
            if zname.replace('.zip', '') in done_names:
                continue
            print(f"  {fn}: {st}" + (f" err={it.get('err_msg','')[:60]}" if st == 'failed' else ''), flush=True)
            if st == 'done':
                out = os.path.join(ZIPDIR, zname)
                subprocess.run(['curl', '-s', '--noproxy', '*', '-o', out,
                                '-w', '   dl HTTP %{http_code} %{size_download}\n', '-L',
                                it['full_zip_url']], check=False)
                print(f"      -> {out}", flush=True)
                done_names.add(zname.replace('.zip', ''))
            elif st == 'failed':
                # 重传该文件
                retry_file(fn)
                return
        if all(f.replace('.pdf', '.zip').replace('.zip', '') in done_names for f in os.listdir(PDFDIR)):
            print('== 全部 zip 就绪 ==', flush=True); break
        time.sleep(15)

def retry_file(fn):
    local = os.path.join(PDFDIR, fn)
    if not os.path.isfile(local):
        print('!! 找不到本地文件重传:', local, flush=True); return
    # 换一个 data_id 后缀强制新任务
    data_id = fn.split('.')[0][:110] + '_r2'
    body = {"files": [{"name": fn, "data_id": data_id}], "model_version": "vlm", "enable_table": True}
    resp = urllib.request.urlopen(urllib.request.Request(
        BASE + '/file-urls/batch', data=json.dumps(body).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOK}), timeout=60)
    j = json.load(resp)
    if j.get('code') != 0:
        print('!! 重传申请失败', j.get('msg'), flush=True); return
    url = j['data']['file_urls'][0]; nb = j['data']['batch_id']
    r = subprocess.run(['curl', '-s', '--noproxy', '*', '-o', '/dev/null', '-w', '%{http_code}',
                        '-X', 'PUT', '-T', local, url], capture_output=True, text=True)
    print(f"  retry upload {fn}: HTTP {r.stdout} batch={nb}", flush=True)
    time.sleep(20)
    poll_batch(nb)

def main():
    batch, jf = sys.argv[1], sys.argv[2]
    meta = json.load(open(jf, encoding='utf-8'))
    batch = meta['data'].get('batch_id') or batch
    print('poll batch:', batch, flush=True)
    poll_batch(batch)
    print('ZIP dir:', sorted(os.listdir(ZIPDIR)), flush=True)

if __name__ == '__main__':
    main()