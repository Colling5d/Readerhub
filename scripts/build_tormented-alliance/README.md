# The Tormented Alliance — 中英对照阅读本（构建说明）

Zach Fredman, *The Tormented Alliance: American Servicemen and the Occupation of China, 1941–1949*
（Chapel Hill: University of North Carolina Press, 2022），448 页原生数字版 PDF（有完整文字层，**无需 OCR**）。

产出：`~/ReaderHub/books/tormented-alliance/index.html`（自包含单文件，约 2.1 MB，无外部 CSS/JS/字体依赖）。

## 规模

| 项 | 数 |
|---|---|
| 节 | 15（卷首、目录与图表、致谢、大事年表、导言、六章、尾声、注释、参考文献、索引） |
| 段落 | 2894（正文/注释/文献/索引） |
| 句级对齐段落 | 1830（正文 + 注释；参考文献与索引为整段对照，不做句级） |
| 脚注标记 | 4171 处可悬浮 |

## 流程

```bash
cd ~/ReaderHub/scripts/build_tormented-alliance

# 1) 文字层抽取 + 分节（PDF 文字层，不走 MinerU/OCR）
python3 extract.py                 # → en_data.json, work/pages.json

# 2) 翻译 + 切句 + 句级对齐（ECNU API，断点续跑）
ECNU_WORKERS=5 ECNU_BATCH=3 ECNU_CHARS=2600 ECNU_DELAY=1.0 \
  ECNU_RAPID_SECS=biblio,index python3 -u translate.py    # → work/translated.json

# 3) 生成自包含阅读器
python3 build_reader.py            # → ~/ReaderHub/books/tormented-alliance/index.html

# 4) 注入交互（幂等）
cd ~/ReaderHub/scripts
python3 add_theme_and_hud.py      ../books/tormented-alliance/index.html
python3 add_footnote_tooltips.py  ../books/tormented-alliance/index.html
python3 add_lang_toggle.py        ../books/tormented-alliance/index.html
python3 add_notes_export.py       ../books/tormented-alliance/index.html
```

## 关键实现说明

### 富文本 PDF 的段落切分
本书每行是独立的 PDF block，y 坐标等距（17.1pt），**没有首行缩进**。判断段界只能靠**行间空隙**：
正文 17.1pt、段间 31.9pt，故 `gap_thr=24`。跨页时若上一行不以句末标点结束，则视为同段续接
（`paragraphs_from_stream(crosspage=True)`）；`biblio/index/chrono` 关闭跨页续接，避免把两条文献粘连。

### 章首页与节标题
章首页标题为 Bold 21pt、副题为 Bold 16.7pt，正文 14.8pt。`marks[].bold` 记录段首行是否为 Bold，
配合"短于 80 字符且不以句号结尾"判定为 `subh`（节标题）。章标题本身由 `SECTIONS` 的 `title` 提供，
故生成后**删去与章标题重复的首段**（7 节），并把 notes 里附着在注末的 `Chapter N` 拆为独立小标题
（此步在各节下标上做了重编号，`work/translated.json` 同步 reindex）。

### 备注「两栏年表」
年表页（17–20）为两栏排版：左栏日期右对齐（x≈86–122），右栏事件（x≈195）。
`chrono_entries()` 按 y 聚行、按 x 分栏配对；原文多数条目本就没有事件说明，保留原样。

### 上标脚注
PDF 文字层的脚注号是 Unicode 上标（¹²³…），阅读器的脚注系统不识别。
`sup_to_tag()` 统一转为 `<sup>N</sup>`，再由 `add_footnote_tooltips.py` 渲染为可悬停的
`<sup class="fnmark" data-fn="N">`。转换同时作用于 `en`、`zh`、`en_sents`、`zh_sents`，保证对齐区间不偏。

### 修复：中文脚注正则误伤标签属性
`add_footnote_tooltips.py` 的中文纯文本规则 `([。，、；：）】」』”’"])(\s*)(\d{1,3})` 会把
`data-fn="1"` 里的 `"1` 当成脚注号再包一层，产生
`data-fn="&lt;sup class=" fnmark"="">1</sup>"&gt;1` 的坏标记。
已在脚本中加入 `insideTag(whole, off)` 判断（中英两侧纯文本规则都加），避免在标签内部匹配。
该修复对今后所有书通用。

### 翻译
- 综合 prompt 一次产出「复原英文 / 中译 / 切句 / 对齐」，术语表内置（黄仁霖、战地服务团、
  翻译官、飞虎队、豫湘桂战役、驼峰航线、吉普女郎、治外法权、驻军地位协定等）。
- `ECNU_RAPID_SECS=biblio,index`：参考文献与索引改用**批量纯翻译**（每批 12 条、无句级对齐），
  这两节约 1000 段，可省去大量 token 与时间。
- 并发与限流：6 并发会稳定触发 429；实测 **5 worker × 3 段/批（≤2600 字符）** 可稳定在 ~40 段/分钟。
- 批失败自动二分重试，单条再失败则退回纯翻译，保证不留空洞。

## 已知局限

1. 原文行内断字（`inter- preters`）由翻译模型在 `en` 中复原，个别专名可能仍有误。
2. 少数段首被分页切断（如 `[GMD])`、`sic ]` 等插入语），已尽量并回相邻段，仍有零星残片。
3. 参考文献与索引为整段对照，无句子级高亮（与 `to-rule-the-waves` 的处理一致）。
4. 年表中原文缺失的事件说明无法补出（源 PDF 即如此）。

## 相关文件

- `slots.py`：15 节的目录名、标题、章名。
- `metadata.json`：书库卡片信息。
- `reader_base.html`：阅读器模板（取自 `books/winning-third-world`，功能最全）。
- `work/translated.json`：翻译与对齐数据（2894 条）。
- `work/en_data.bak.json`、`work/translated.bak.json`：上标转换前的备份。
