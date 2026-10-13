#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mono_css.py — 单语布局 + 中文专著排版 CSS（幂等）。必须在所有注入工具之后运行。"""
import sys
CSS = """
/* ==== MONOLINGUAL (zh-only) ==== */
.main{display:flex !important;flex-direction:column !important;overflow:hidden}
.col.zh{display:none !important}
.col.en{flex:1 1 auto;min-height:0;height:100%;overflow-y:auto;border-right:none !important;max-width:840px;width:100%;margin:0 auto;box-sizing:border-box;padding:0 56px 140px}
.col.en .col-head{display:none !important}
.p.table{margin:1.6em 0;text-align:center}
.p.table img{max-width:100%;height:auto;border:1px solid var(--line);border-radius:6px}

/* ==== 排版层级（中文专著）==== */
.col.en{font-size:17px;line-height:1.95;color:#1f1f1f;text-align:justify}
.col.en .p.p{margin:0 0 1.1em;text-indent:2em}
.col.en .p.p.h1,.col.en .p.p.h1sub,.col.en .p.p.h2,.col.en .p.p.cap{text-indent:0}

/* 章标题（第X章 / 緒章 / 結論 …）*/
.p.h1{
  font-size:27px;font-weight:800;letter-spacing:.06em;text-align:center;
  margin:2.6em 0 1.4em;color:var(--accent);text-indent:0;
  line-height:1.5;
}
.p.h1::after{
  content:"";display:block;width:56px;height:3px;border-radius:2px;
  background:linear-gradient(90deg,var(--accent),transparent);margin:.7em auto 0;
}
/* 章副题 */
.p.h1sub{
  font-size:19px;font-weight:600;letter-spacing:.08em;text-align:center;
  margin:-1em 0 1.8em;color:#5a5a5a;text-indent:0;line-height:1.6;
}
/* 节标题（一、 / （一） / 前言 …）*/
.p.h2{
  font-size:20px;font-weight:700;margin:2.2em 0 .9em;color:#2a2a2a;
  text-align:left;text-indent:0;line-height:1.6;letter-spacing:.02em;
  padding-left:14px;border-left:4px solid var(--accent);
}
/* 表格题注 */
.p.cap{
  font-size:15px;font-weight:600;color:var(--ink-soft,#8a8a8a);
  text-align:center;text-indent:0;margin:2em 0 .6em;letter-spacing:.02em;
}
/* 脚注 */
.note{font-size:13.5px;line-height:1.75;margin:0 0 .5em;color:#5a5a5a;text-indent:0}

/* 首字下沉（每章正文第一段）*/
.p.body-lead{text-indent:0}
.p.body-lead::first-letter{
  float:left;font-size:3.1em;line-height:.86;font-weight:800;
  margin:.06em .12em 0 0;color:var(--accent);
}

@media (max-width:760px){
  .col.en{padding:0 18px 120px;font-size:16px}
  .p.h1{font-size:22px;margin:2em 0 1em}
  .p.h2{font-size:18px}
}
"""
def main():
    p = sys.argv[1]
    h = open(p, encoding='utf-8').read()
    if 'MONOLINGUAL (zh-only)' in h:
        # 移除旧块再重贴，保证内容最新
        h = re.sub(r'\n?/\* ==== MONOLINGUAL \(zh-only\) ==== \*/.*?(?=\n\*/|\n[a-zA-Z#\.\[@])', '', h, count=1, flags=re.S)
    h = h.replace('</style>', CSS + '</style>', 1)
    open(p, 'w', encoding='utf-8').write(h)
    print('mono CSS applied')
import re
if __name__ == '__main__':
    main()
