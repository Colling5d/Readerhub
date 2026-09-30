#!/usr/bin/env python3
"""
add_book.py — 往 ReaderHub 书库新增一本网页阅读器。

用法:
    python3 scripts/add_book.py <book-id> <reading.html> [metadata.json]

参数:
    book-id       唯一标识，例如 cultures-colliding（会作为文件夹名和网址一部分）
    reading.html  刚构建好的自包含阅读器 index.html（1.x MB 那种）
    metadata.json 可选；若提供则用它（须含 id/title），否则进入交互提问

操作:
    1. 校验 reading.html 自包含（不引用外部 http/cdn，单一 <script> 或内联）
    2. 复制到 books/<book-id>/index.html
    3. 生成 metadata.json
    4. 更新总站 index.html 里的 BOOKS 数组
    5. 提示 git 提交

规划提示: 每本书一个独立文件夹，互不影响；站首页 books/*/metadata.json 自动列卡片。
"""
import json, os, re, sys, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOKS_DIR = os.path.join(ROOT, "books")
HUB = os.path.join(ROOT, "index.html")

def err(msg):
    print("!! " + msg); sys.exit(1)

def check_self_contained(path):
    html = open(path, encoding="utf-8").read()
    external = re.findall(r'(?:src|href)\s*=\s*["\'](?:https?:)?//[^"\']+["\']', html)
    external = [x for x in external if "schema" not in x]
    if external:
        err("该 HTML 引用了外部资源，GitHub Pages 会失效:\n  " + "\n  ".join(external[:8]))
    if html.count("<script") > 1 and re.search(r'<script[^>]*\bsrc=', html):
        err("发现外部 <script src=...>，请改为内联。")
    print("  [OK] 自包含校验通过")

def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    book_id = sys.argv[1]
    reader = sys.argv[2]
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", book_id):
        err("book-id 只能含小写字母/数字/连字符: " + book_id)
    if not os.path.isfile(reader):
        err("找不到阅读器文件: " + reader)

    print(f"添加书籍 {book_id}")
    check_self_contained(reader)

    dest = os.path.join(BOOKS_DIR, book_id)
    os.makedirs(dest, exist_ok=True)
    shutil.copy(reader, os.path.join(dest, "index.html"))

    # metadata
    meta_path = os.path.join(dest, "metadata.json")
    if len(sys.argv) >= 4 and os.path.isfile(sys.argv[3]):
        meta = json.load(open(sys.argv[3], encoding="utf-8"))
        meta.setdefault("id", book_id)
        print("  [OK] 使用提供的 metadata.json")
    else:
        print("  -- metadata 交互提问 (留空回车=跳过) --")
        meta = {"id": book_id}
        meta["title"]       = input("  书名 title: ").strip() or book_id
        meta["subtitle"]    = input("  副标题 subtitle: ").strip()
        meta["author"]      = input("  作者 author: ").strip()
        meta["description"] = input("  简介 description: ").strip()
        meta["tags"]        = [t.strip() for t in input("  标签 tags(逗号分隔): ").split(",") if t.strip()]
        meta["lang"]        = input("  语言 lang(如 en-zh): ").strip() or "en-zh"
        meta["featured"]    = bool(input("  是否置顶 featured(y/n): ").strip().lower() in ("y","yes","1"))
        meta["updated"]     = __import__("datetime").date.today().isoformat()
    json.dump(meta, open(meta_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("  [OK] 写入 " + os.path.relpath(meta_path, ROOT))

    # update hub
    hub = open(HUB, encoding="utf-8").read()
    entry = json.dumps(meta, ensure_ascii=False)
    m = re.search(r"(\s*/\* __BOOKS__ \*/)", hub)
    if m:
        marker = m.group(1)
        insert_at = hub.index(marker)
        insertion = ",\n" + entry + "," + marker[0]  # put this book first-ish
        new_hub = hub[:insert_at] + insertion + hub[insert_at + len("/* __BOOKS__ */") + len(marker)-len(marker):]
        open(HUB, "w", encoding="utf-8").write(new_hub)
        print("  [OK] 已更新总站 index.html 的 BOOKS 列表")
    else:
        print("  [WARN] 未在总站 index.html 找到 /* __BOOKS__ */ 标记，跳过自动登记。")

    print(f"\n完成。可访问: books/{book_id}/index.html")
    print("建议提交:")
    print(f"  git add books/{book_id} index.html")
    print(f"  git commit -m 'add book: {book_id}'")
    print(f"  git push")

if __name__ == "__main__":
    main()