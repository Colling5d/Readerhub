# ReaderHub · 双语在线阅读馆

一个用 **GitHub Pages** 托管的中英对照网页阅读器合集。每本书是一个自包含的静态 `index.html`，放在独立的 `books/<book-id>/` 文件夹里；站首页会从各书的 `metadata.json` 自动生成入口卡片。

## 结构

```
ReaderHub
├── index.html                      # 总站首页，自动列出所有书
├── books/                          # 每本书一个文件夹
│   └── cultures-colliding/         # 例：中英对照《Cultures Colliding》
│       ├── index.html              # 自包含阅读器（无外部依赖）
│       └── metadata.json           # 书的元信息，供首页渲染
└── scripts/
    └── add_book.py                 # 新增一本书的自动化脚本
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