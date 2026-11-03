# To Rule the Waves — 中英对照阅读本（构建说明）

Bruce D. Jones, *To Rule the Waves: How Control of the World's Oceans Shapes the Fate of the Superpowers*
（New York: Scribner, 2021），408 页 Scribner 版扫描本。

产出：`~/ReaderHub/books/to-rule-the-waves/index.html`（自包含单文件，约 2.1 MB，无任何外部 CSS/JS/字体依赖），
桌面副本：`~/Desktop/ToRuleTheWaves_中英对照/index.html`。

## 规模

| 项 | 数 |
|---|---|
| 节 | 21（扉页、序章、十四章、结论、致谢、注释、参考文献、索引） |
| 段落 | 1279（其中正文/注释/文献 1186 段做逐句对齐） |
| 英文词数 | 143,024 |
| 句级对齐段落 | 1186 |

## 流程

```bash
cd ~/ReaderHub/scripts/build_to-rule-the-waves

# 1) 渲染 200dpi 页面 + macOS Vision OCR（408 页）
python3 extract.py                     # → work/raw/pNNN.png, work/ocr/pNNN.json

# 2) 分节、去页眉页码、合行、抽小标题
python3 build_sections.py              # → en_data.json

# 3) 翻译 + 切句 + 句级对齐（ECNU API，断点续跑、单实例锁）
ECNU_WORKERS=2 ECNU_DELAY=3 ECNU_BATCH=12 python3 translate.py   # → work/translated.json

# 4) 补译超长注释（分块翻译后拼接）
python3 patch_notes.py

# 5) 生成自包含阅读器
python3 build_reader.py                # → ~/ReaderHub/books/to-rule-the-waves/index.html
```

## 关键实现说明

### OCR 列序
macOS Vision OCR 输出列为 `h, x(向下), w, h2`，**不是** `x, y`。`extract.py` 中已按此解析，
并按 y 坐标聚类成行（容差 0.012）后行内按 x 排序；`work/ocr/*.json` 统一为 `{x, y, w, h, text}`（x, y 归一化到 0–1）。

### 分节边界
`SECTIONS` 用 PDF 索引区间（0 基），据 Contents 与实际章首页逐页核对：

| 节 | 区间 | 节 | 区间 |
|---|---|---|---|
| front | 0–11 | ch11 | 227–253 |
| prologue | 12–27 | ch12 | 254–275 |
| ch1 | 28–39 | ch13 | 276–296 |
| ch2 | 40–62 | ch14 | 297–312 |
| ch3 | 63–103 | concl | 314–323 |
| ch4 | 104–120 | ack | 324–328 |
| ch5 | 121–134 | notes | 330–364 |
| ch6 | 135–144 | biblio | 366–381 |
| ch7 | 145–177 | index | 382–400 |
| ch8 | 178–189 | | |
| ch9 | 190–207 | | |
| ch10 | 208–226 | | |

13、99–101、169–171、249–251、313、329、365、401–405 为空页/图片页。
`NO_TEXT_PAGES`（文字层 <12 词的真图片页）为：3, 4, 6, 8, 9, 19, 20, 21, 99, 100, 101, 169, 171, 249, 250, 251, 401, 403, 404, 405。

**注意**：`get_lines()` 以 OCR 为主。曾试过优先用 PDF 文字层，但该扫描本文字层的行序与基线不可靠
（同一页的行会乱序、行距失真），导致段落被打散成 500+ 碎片，故改为 OCR 优先。

### 章首页标题剥离
章首页标题区（部次 / 章号 / 章名 / 副标题）与正文之间有明显疏排空隙。`strip_heads()` 取 y<0.5 范围内
**最后一处** >0.05 的行距空隙之后的行作为正文起点（ch2 的副标题折成两块，取最后一处才正确）。

### 断字修复
`dewraptext()`：合并行内断字（`im-pulse`→`impulse`），保留 `KEEP_HYPHEN` 白名单里的真连字符
（`anti-access`、`sea-lanes`、`1970s-1980s` 等），并用 `MISSING_HEAD` 补回 OCR 丢首字母的残片
（`meri-can`→`American`、`hi-nese`→`Chinese`）。

### 翻译
- 综合 prompt：一段之内同时输出「复原英文 / 中译 / 切句 / 对齐」四个字段，要求 `join(en_sents)==en`。
- 本书术语表写在 prompt 内（洋行大班、海权、咽喉要道、反介入/区域拒止、第一岛链、九段线、马士基、中远、东方海外……）。
- 单实例锁 `.translate.lock`：早期多进程同写 `translated.json` 导致计数回退、结果互相覆盖，加锁后修复。
- 输出原子写入（`save()` 用 tmp + os.replace）。
- 长注释（2–4.7k 字符）整段输出易被截断，用 `patch_notes.py` 按句切成 ~1100 字符块翻译后拼接。

## 已知局限

1. **逐句对齐**：1186 段中有 189 段存在 `en_sents`/`zh_sents` 与整段文本的空格或标点细微不一致，
   阅读器用容错查找兜底，最终仅 3 处英文、13 处中文片段退化为零长度高亮，不影响阅读。
2. **超长注释的对齐**：经 `patch_notes.py` 补译的 9 段退化为整段一对一（无逐句高亮）。
3. **索引（Index）** 为页码串，译文仅便于浏览，不对页码做映射。
4. OCR 仍有零星误识（如人名、罕见专名），未逐条校对；正文以英文原文为准。

## 相关文件

- `slots.py`：21 节的中英目录名、标题、章名（阅读器侧栏与标题栏用）。
- `metadata.json`：书库卡片信息。
- `reader_base.html`：阅读器模板（沿用 ReaderHub 既有模板）。
- `work/translated_old.json`：术语表加入前的一轮译文，保留备查。
