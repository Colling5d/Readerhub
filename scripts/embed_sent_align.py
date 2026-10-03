#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 aligned_sentences.json 生成 SENT_ALIGN JS 块，注入 index.html。
SENT_ALIGN 结构:
{
  "secId/para": {"en":[[s,e],...],"zh":[[s,e],...],"m":[[e_idx,z_idx],...]}
}
切分字符串若能按原文逐句定位则记录 [s,e]；否则该句记 [0,0] 并靠 align 仍能用（尽力而为）。
"""
import json, re, sys, os
BOOK_DIR = "/Users/zhulv/ReaderHub/books/cultures-colliding"
HTML = os.path.join(BOOK_DIR, "index.html")
ALIGN = os.path.join(BOOK_DIR, "aligned_sentences.json")

def extract(marker, s):
    start=s.index(marker)+len(marker); i=start; depth=0
    while i<len(s):
        c=s[i]
        if c=='[': depth+=1
        elif c==']':
            depth-=1
            if depth==0: return s[start:i+1]
        i+=1
    raise ValueError("unterminated: "+marker)

def txt(x): return x['text'] if isinstance(x,dict) else x

def compute_offsets(sents, text):
    # whitespace-tolerant: collapse runs of whitespace to single space for both
    # sentence and source, then map matches back to original text indices.
    offs=[]; pos=0
    flat_src=re.sub(r'\s+',' ',text)
    # build prefix-char mapping from flat index -> original index
    def flat_to_orig(fidx):
        # count original chars consumed up to the point; approximate by scanning
        if fidx<=0: return 0
        seen=0; i=0
        while seen<fidx and i<len(text):
            c=text[i]
            # record start
            if i+1<len(text) and (c.isspace()):
                # a whitespace run in flat->' '
                pass
            seen+=1; i+=1
        return i
    for sn in sents:
        flat_sn=re.sub(r'\s+',' ',sn)
        # locate in flat_src from pos (pos tracks original, convert)
        pos_flat=flat_src.find(flat_sn)
        if pos_flat==-1:
            offs.append(None); continue
        # map pos_flat..pos_flat+len(flat_sn) to original range
        start_orig=map_idx(text, pos_flat)
        end_orig=map_idx(text, pos_flat+len(flat_sn))
        offs.append([start_orig, end_orig])
        pos=end_orig
        # advance flat position by replacing the matched region with spaces to avoid re-match
        flat_src = flat_src[:pos_flat] + ' '*len(flat_sn) + flat_src[pos_flat+len(flat_sn):]
    return offs
def map_idx(text, flat_pos):
    # index into text equivalent to flat_pos (each original ws char collapses)
    cnt=0; i=0
    prev_ws=False
    while i<len(text):
        if text[i].isspace():
            if not prev_ws:
                if cnt>=flat_pos: return i
                cnt+=1; prev_ws=True
            i+=1; continue
        else:
            if cnt>=flat_pos: return i
            cnt+=1; prev_ws=False; i+=1
    return len(text)

def main():
    s=open(HTML,encoding='utf-8').read()
    EN=json.loads(extract('/*__EN__*/', s))
    ZH=json.loads(extract('/*__ZH__*/', s))
    zhmap={z['id']:z for z in ZH}
    def en_text(secid,i):
        sec=next((x for x in EN if x['id']==secid),None)
        if not sec or i>=len(sec['paras']): return None
        p=sec['paras'][i]; return txt(p) if isinstance(p,dict) else p
    def zh_text(secid,i):
        z=zhmap.get(secid)
        if not z or i>=len(z['paras']): return None
        p=z['paras'][i]; return txt(p) if isinstance(p,dict) else p

    data=json.load(open(ALIGN,encoding='utf-8'))
    out={}
    for key,v in data.items():
        eoff=compute_offsets(v['en_sents'], en_text(v['sec'],v['i']) or '')
        zoff=compute_offsets(v['zh_sents'], zh_text(v['sec'],v['i']) or '')
        # drop entries that failed to locate any sentence
        if any(o is None for o in eoff) or any(o is None for o in zoff):
            continue
        # keep only valid align pairs (skip None / bad values)
        m=v.get('align',[])
        pairs=[]
        for a in m:
            if not isinstance(a,(list,tuple)) or len(a)<2: continue
            try:
                ai=int(a[0]); zi=int(a[1])
                if max(ai,zi) < max(len(eoff),len(zoff)):
                    pairs.append([ai,zi])
            except Exception:
                continue
        out[key]={"en":eoff,"zh":zoff,"m":pairs}
    js="var SENT_ALIGN="+json.dumps(out,ensure_ascii=False,separators=(',',':'))+";"
    print(f"entries: {len(out)}")
    # inject before the init IIFE marker (or before TEMP decl). Insert right before '/* 选中句子' block
    marker="// 定位位置 pos 落在哪一句"
    assert marker in s, "inject marker not found"
    s=s.replace(marker, js+"\n"+marker, 1)
    open(HTML,'w',encoding='utf-8').write(s)
    print("injected. new size:", len(s))

if __name__=='__main__':
    main()
