#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把合并后的有序流切分成章节，产出 sections_meta.json 与 en_data.json。

en_data.json: [{id, title, paras:[{type, text}]}]  (英文正文结构)
type: 'text' 普通段落 / 'h' 小节标题 / 'note' 注释条目 / 'subh' 注释内子标题
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
stream = json.load(open(os.path.join(HERE, "stream_raw.json"), encoding='utf-8'))

def norm(s):
    return ' '.join(s.split())

# 章节边界: (开始idx, 结束idx(不含), id, 显示标题)
# 顺序严格参照索引 43..1953+, 覆盖全部。
SECTIONS = [
    (43,  57,  "fwd",   "Foreword  前言"),
    (57,  60,  "spell", "A Note on the Spelling of Chinese Names  中文姓名拼写说明"),
    (60,  121, "intro", "Introduction  导言"),
    (121, 246, "ch1",   "Chapter 1 · Anson Burlingame  安森·蒲安臣"),
    (246, 358, "ch2",   "Chapter 2 · The Chinese Education Mission  幼童留美教育"),
    (358, 460, "ch3",   "Chapter 3 · Ge Kunhua  戈鲲化"),
    (460, 638, "ch4",   "Chapter 4 · Frank Goodnow  古德诺"),
    (638, 709, "ch5",   "Chapter 5 · John Dewey  约翰·杜威"),
    (709, 772, "ch6",   "Chapter 6 · Shared Diplomatic Journey through Sports  体育外交的共同旅程"),
    (772, 788, "concl", "Conclusion  结语"),
    (788, 1624,"notes", "Notes  注释"),
    (1624,1679,"glossary","Selected Glossary  术语表"),
    (1679,1946,"biblio","Selected Bibliography  参考书目"),
    (1946,1953,"ack",  "Acknowledgments  致谢"),
    (1953,None,"index","Index  索引"),
]

def clean_text(t):
    # 归一化空白；去除孤立的纯页/行号块（纯数字行）—— 由上层判断
    return norm(t)

def is_folio(t):
    # 纯数字 / 罗马数字 页脚
    if not t: return True
    t = t.strip()
    if re.fullmatch(r'[ivxlcdmIVXLCDM\.\- ]+', t or ''): return True
    if re.fullmatch(r'\d+', t): return True
    return False

def is_body_junk(t, typ):
    # 卷首/封面/目录相关噪音（保留，但译为内容时可能跳）；先保留原样
    return False

def build():
    result = []  # sections
    for s_idx, e_idx, sid, title in SECTIONS:
        paras = []
        for i in range(s_idx, e_idx if e_idx is not None else len(stream)):
            b = stream[i]
            t = norm(b['text'])
            if not t or is_folio(t):
                continue
            typ = b['type']
            if typ == 'title':
                para_type = 'h'
            elif typ == 'ref_text':
                para_type = 'note'
            else:
                para_type = 'text'
            paras.append({"type": para_type, "text": t})
        result.append({"id": sid, "title": title,
                       "numText": sum(1 for p in paras if p["type"] == "text"),
                       "numH": sum(1 for p in paras if p["type"] == "h"),
                       "numNote": sum(1 for p in paras if p["type"] == "note"),
                       "chars": sum(len(p["text"]) for p in paras),
                       "paras": paras})
    with open(os.path.join(HERE, "sections_meta.json"), 'w', encoding='utf-8') as f:
        json.dump([{k: s[k] for k in ("id","title","numText","numH","numNote","chars")} for s in result],
                  f, ensure_ascii=False, indent=2)
    with open(os.path.join(HERE, "en_data.json"), 'w', encoding='utf-8') as f:
        json.dump([{"id": s["id"], "title": s["title"], "paras": s["paras"]} for s in result],
                  f, ensure_ascii=False)
    tot = sum(s["numText"] for s in result)
    totn = sum(s["numNote"] for s in result)
    totc = sum(s["chars"] for s in result)
    for s in result:
        print(f"{s['id']:8s} text={s['numText']:4d} h={s['numH']:3d} note={s['numNote']:4d} chars={s['chars']}")
    print(f"TOTAL text={tot} note={totn} chars={totc}")

if __name__ == '__main__':
    build()