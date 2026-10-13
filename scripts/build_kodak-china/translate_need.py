import json, os, time, threading
import translate as T
NEED=json.load(open('work/need_translate.json'))
OUT='work/need_done.json'
done=json.load(open(OUT)) if os.path.exists(OUT) else {}
lock=threading.Lock()
todo=[x for x in NEED if x[0] not in done]
print('待译',len(todo),'/',len(NEED))
idx=[0]
def work():
    while True:
        with lock:
            if idx[0]>=len(todo): return
            k,typ,txt=todo[idx[0]]; idx[0]+=1
        try:
            raw=T.call_api(T.build_combined([(k,txt)]), max_tokens=6000)
            arr=T.parse_json(raw)
            it=arr[0] if isinstance(arr,list) else arr
            with lock:
                done[k]={'type':'C','en':it.get('en',txt),'zh':it.get('zh',''),
                         'en_sents':it.get('en_sents',[]),'zh_sents':it.get('zh_sents',[]),
                         'align':it.get('align',[])}
                json.dump(done,open(OUT,'w'),ensure_ascii=False)
                print('OK',k,'|',it.get('zh','')[:40],flush=True)
        except Exception as e:
            print('ERR',k,str(e)[:70],flush=True)
ths=[threading.Thread(target=work) for _ in range(int(os.environ.get('ECNU_WORKERS','4')))]
[t.start() for t in ths]; [t.join() for t in ths]
print('done', len([x for x in NEED if x[0] in done]),'/',len(NEED))
