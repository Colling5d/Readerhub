#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""To Rule the Waves (Bruce D. Jones, Scribner 2021) —— 抽页、OCR、分节。

输出：
  work/raw/pNNN.png     每页图片
  work/ocr/pNNN.json    Vision OCR 行（含坐标）
  en_data.json          [{id,title,paras:[{type,text}]}]
  work/pages.json       页面元数据（页码、章属）
"""
import json, os, re, subprocess, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
PDF = os.path.join(HERE, 'book.pdf')
WORK = os.path.join(HERE, 'work')
RAW = os.path.join(WORK, 'raw')
OCR = os.path.join(WORK, 'ocr')
os.makedirs(RAW, exist_ok=True)
os.makedirs(OCR, exist_ok=True)
OCR_BIN = '/Users/zhulv/pdfproof/scripts/vision_ocr'
DPI = 200

# pdf 索引 → 节  (起, 止, 含止)
SECTIONS = [
    ('front',  'Front Matter',        (0, 11)),
    ('prologue', 'Prologue — A Box in the Jungle', (12, 28)),
    ('ch1',   'Chapter 1 · Secrets of the High North',            (29, 45)),
    ('ch2',   'Chapter 2 · The Outer Perimeter',                  (46, 64)),
    ('ch3',   'Chapter 3 · Charting Today’s World',               (65, 88)),
    ('ch4',   'Chapter 4 · Western Tide Rising',                  (89, 115)),
    ('ch5',   'Chapter 5 · Taipans of Globalization',             (116, 134)),
    ('ch6',   'Chapter 6 · The Great Closing',                    (135, 150)),
    ('ch7',   'Chapter 7 · Global Supply Ships',                  (151, 178)),
    ('ch8',   'Chapter 8 · Pirates of the Twenty-First Century',  (179, 194)),
    ('ch9',   'Chapter 9 · The Near Seas',                        (195, 226)),
    ('ch10',  'Chapter 10 · America’s Lake',                      (227, 247)),
    ('ch11',  'Chapter 11 · To Conquer the Seas',                 (248, 271)),
    ('ch12',  'Chapter 12 · The Salt of the Oceans',              (272, 300)),
    ('ch13',  'Chapter 13 · Oceanography and Power',              (301, 322)),
    ('ch14',  'Chapter 14 · Hot Waters Rising',                   (323, 352)),
    ('concl', 'Conclusion · Come Hell and High Water',            (353, 378)),
    ('ack',   'Acknowledgments',                                  (379, 383)),
    ('notes', 'Notes',                                            (384, 400)),
    ('index', 'Index',                                            (401, 407)),
]

NO_TEXT_PAGES = {3, 4, 6, 8, 9, 19, 20, 21, 99, 100, 101, 169, 171,
                 249, 250, 251, 401, 403, 404, 405}  # 实测：正文文字层<12词的真图片页


def group_rows(lines):
    """按 y 坐标聚类成行（容差 ~0.012），行内按 x 排序。"""
    if not lines:
        return lines
    rows = []
    for l in sorted(lines, key=lambda z: (z['y'], z['x'])):
        if rows and abs(l['y'] - rows[-1][0]['y']) <= 0.012:
            rows[-1].append(l)
        else:
            rows.append([l])
    out = []
    for r in rows:
        out.extend(sorted(r, key=lambda z: z['x']))
    return out


def need_ocr_text(pdf, i):
    """图片页（正文空白页）需要 OCR；正文有大段乱码的页也 OCR。"""
    t = pdf[i].get_text()
    letters = len(re.findall(r'[A-Za-z]', t))
    if letters < 40:
        return True
    words = re.findall(r'[A-Za-z]{2,}', t)
    if words and sum(len(w) for w in words) / len(words) < 2.2:
        return True
    return False


def run():
    import fitz
    pdf = fitz.open(PDF)
    n = pdf.page_count
    for i in range(n):
        png = os.path.join(RAW, f'p{i:03d}.png')
        if not os.path.exists(png):
            pdf[i].get_pixmap(dpi=DPI).save(png)
    print('rendered', n, flush=True)
    todo = [i for i in range(n) if not os.path.exists(os.path.join(OCR, f'p{i:03d}.json'))]
    print('need ocr', len(todo), flush=True)
    for i in todo:
        out = subprocess.run([OCR_BIN, os.path.join(RAW, f'p{i:03d}.png'), 'en-US'],
                             capture_output=True, text=True)
        lines = []
        for ln in out.stdout.splitlines():
            parts = ln.split('\t')
            if len(parts) != 5:
                continue
            # vision_ocr 输出列顺序：y  x  w  h
            y, x, w, h = (float(v) for v in parts[:4])
            lines.append({'x': x, 'y': y, 'w': w, 'h': h, 'text': parts[4]})
        lines = group_rows(lines)
        json.dump(lines, open(os.path.join(OCR, f'p{i:03d}.json'), 'w'), ensure_ascii=False)
    print('ocr done', flush=True)


if __name__ == '__main__':
    run()
