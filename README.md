# ReaderHub · 双语在线阅读馆

一个用 **GitHub Pages** 托管的中英对照网页阅读器合集。每本书是一个自包含的静态 `index.html`，放在独立的 `books/<book-id>/` 文件夹里；站首页会从各书的 `metadata.json` 自动生成入口卡片。

阅读器支持**连续滚动跨章节阅读**：整本书一次渲染为连续长文，可从第一章一直滑到最后一章，滚动时自动跟随当前章节（目录高亮 + 顶部章节提示）。句子级中英对照：选中任一栏的句子，另一栏对应的句子（AI 生成的 1:1/1:n 对齐）自动高亮并滚动到可见处；另提供选中高亮 / 划线笔记、全文检索、阅读位置记忆、章节目录与整句复制等功能。

**阅读主题与字体**：左下角「⚙ 主题」可切换亮色 / 护眼米黄 / 深色 / 夜间黑四套配色，并可选择字体（宋体 / 楷体 / 黑体 / 系统）与字号（小 / 中 / 大 / 特大），设置在所有书之间共享并记忆。

**当前章节提示**：目录中的当前章节以强调色高亮；折叠隐藏目录后，滚动时阅读区右上角会短暂浮现一个轻量章节药丸，显示当前所在章节，随后自动隐去，点击可重新展开目录。

**脚注悬浮提示**：正文中的上标脚注编号（如 `⁶`）保持不变，鼠标悬停其上会浮出对应的注释内容（中文优先中文、英文优先英文，缺失则回退到另一语言），移动端可点击切换；原有的注释章节与正文标记均完整保留。

**赞赏支持**：首页最下方有一个紧凑的「❤ 投喂作者」小模块（左侧小二维码，右侧文案），收款码以 base64 内嵌，仍是零外部资源。

## 结构

```
ReaderHub
├── index.html                      # 总站首页，自动列出所有书
├── books/                          # 每本书一个文件夹
│   └── cultures-colliding/         # 例：中英对照《Cultures Colliding》
│       ├── index.html              # 自包含阅读器（无外部依赖）
│       └── metadata.json           # 书的元信息，供首页渲染
└── scripts/
    ├── add_book.py                # 新增一本书的自动化脚本
    ├── add_sidebar_toggle.py      # 注入目录折叠交互
    ├── add_theme_and_hud.py       # 注入阅读主题 / 字体 / 章节 HUD
    ├── add_continuous_scroll.py   # 注入连续滚动（跨章节阅读）
    ├── add_footnote_tooltips.py  # 注入脚注悬浮提示（悬停上标编号显示注释）
    └── add_donation.py          # 注入微信赞赏收款码（base64 内嵌）
├── assets/
│   └── donation-qr.jpg         # 赞赏收款码源图（供新增书复用）
```

## 在线地址约定

仓库名假设为 `<repo>`，你的用户名为 `<user>`，GitHub Pages 启用后：

```
https://<user>.github.io/<repo>/                     # 总站
https://<user>.github.io/<repo>/books/<book-id>/     # 某本书阅读器
```

## 如何新增一本书（今后会经常用）

```bash
# 1) 先把构建好的自包含阅读器放到某个临时位置，例如 ~/reader.html
# 2) 运行脚本（会校验自包含、复制、生成元信息、登记到总站）
python3 scripts/add_book.py my-book ~/reader.html
# 3) 提交并推送
git add -A
git commit -m "add book: my-book"
git push
# 4) 访问 https://<user>.github.io/<repo>/books/my-book/
```

脚本若有外部资源（`http`/`cdn` 引用、外部 `<script src>`）会**拒绝**——因为 GitHub Pages 无法正确加载外部相对路径资源，且跨域受限。构建阅读器时请保持全内联。

## 一次性部署步骤（首次）

1. 在 GitHub 新建仓库（如 `ReaderHub`，Public）。
2. 本地关联并推送：
   ```bash
   git remote add origin git@github.com:<user>/<repo>.git
   git branch -M main
   git push -u origin main
   ```
3. 仓库 Settings → Pages → Source: `main` 分支 / `/(root)` → Save。
4. 等 1 分钟，访问在线地址。

## 约定

- 每本书一个文件夹，互不影响，方便单独更新。
- `metadata.json` 字段：`id,title,subtitle,author,description,tags,lang,featured,updated`；`featured` 置顶展示。
- 阅读器必须全自包含（内联 CSS/JS、无外部图片字体），才能被 Pages 稳定托管。

## 许可证 / License

本项目以 **CC BY-NC 4.0（署名 — 非商业性使用 4.0 国际）** 授权，详见 [LICENSE](LICENSE)。

- ✅ 允许：复制、分发、修改、基于本项目二次创作（非商业用途），但需**署名**并注明许可条款。
- ❌ 禁止：任何**商业性使用**（包括但不限于售卖、付费墙、广告变现、商业产品集成等）。

> 注意：`books/` 下各书收录的**英文原著正文**版权归其各自作者与出版方所有，仅作学习、研究与对照阅读之用，不在此授权范围内。详见 [NOTICE](NOTICE)。