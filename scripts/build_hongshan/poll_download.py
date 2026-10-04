#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""轮询 MinerU 批量解析结果，全部 done 后下载各 Zip。
需要 NO_PROXY 直连 mineru.net 与 CDN。
"""
import json, os, sys, time, urllib.request, subprocess

BASE = 'https://mineru.net/api/v4'
TOK = 'sk-P5Y5CLmwX7gr6DHxq6hTF65u7GNOWym55EmFY0cfl6STJA9S'
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, 'work')
ZIPDIR = os.path.join(HERE, 'zip')
os.makedirs(ZIPDIR, exist_ok=True)

def get_task(batch_id):
    url = f"{BASE}/extract-results/batch/{batch_id}"
    req = urllib.request.Request(url)
    req.add_header('Authorization','Bearer '+TOK)
    req.add_header('User-Agent','curl/8.0')
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)

def main():
    batch_id = open(os.path.join(WORK,'batch_info.json')).read()
    batch_id = json.loads(batch_id)['batch_id']
    print('batch_id:', batch_id)
    # 记录已下载的
    done = set()
    start = time.time()
    while time.time()-start < 7200:   # 最多等2小时
        try:
            j = get_task(batch_id)
        except Exception as e:
            print('query err:', str(e)[:100], flush=True)
            time.sleep(10); continue
        if j.get('code')!=0:
            print('code!=0:', j.get('msg'), flush=True); time.sleep(10); continue
        results = j['data']['extract_result']
        all_done = True
        for it in results:
            fn = it['file_name']; st = it['state']
            print(f"  {fn}: {st}" + (f" err={it.get('err_msg','')[:80]}" if st=='failed' else ""), flush=True)
            if st == 'done' and fn not in done:
                zu = it['full_zip_url']
                out = os.path.join(ZIPDIR, fn.replace('.pdf','.zip'))
                print(f"    下载: {out}", flush=True)
                subprocess.run(['curl','-s','--noproxy','*','-o',out,'-w','%{http_code}',zu])
                done.add(fn)
            if st != 'done':
                all_done = False
        if all_done and len(results)>0 and set(x['state'] for x in results)&set(['failed']):
            pass
        # 若全部 done/failed
        if results and all(x['state'] in ('done','failed') for x in results):
            print('== 全部结束 ==', flush=True)
            break
        time.sleep(15)
    print('ZIP 文件:', os.listdir(ZIPDIR))

if __name__=='__main__':
    main()