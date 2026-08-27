# -*- coding: utf-8 -*-
"""
sync_notes.py — 把 dash_data.json 的实时进度/划线同步回写「我的书架」笔记
- 匹配笔记：优先精确 {title}.md，其次 {short}.md；否则归一化（去括号/冒号后内容）匹配；均无则新建
- 更新内容：front matter status（读完/在读）；替换「## 📝 微信读书划线」区块（导出时间/进度/划线数/按章节分组划线）
- 数据来源：prep_dash.py 输出的 books[].progress / marks / mark_items / chapters
"""
import json, os, re, sys, datetime
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import config

TMP = _HERE
SHELF = config.shelf_dir()
SECTION = "## 📝 微信读书划线"
# 区块结束标记：脚本只维护 SECTION 到该标记之间的内容，标记之后的用户自写内容（读书笔记/读后感）永不删除
END_MARK = "<!-- weread_marks_end -->"

with open(f"{TMP}/dash_data.json", encoding="utf-8") as f:
    D = json.load(f)

books = D.get("books", [])


def norm(s):
    s = re.sub(r"[（(][^（）()]*[）)]", "", s)
    s = re.split(r"[：:]", s)[0]
    s = re.sub(r"[\s:：,，。.!！?？·\-—『』「」]", "", s)
    return s


def find_note(short, title=None):
    # 优先完整书名，再回退短名
    for name in (title, short):
        if not name:
            continue
        exact = os.path.join(SHELF, name + ".md")
        if os.path.exists(exact):
            return exact
    # 书名自身不带括号时视为完整书名，只接受精确匹配（避免与带括号的其它书误合并）
    if "(" not in short and "（" not in short:
        return None
    try:
        names = os.listdir(SHELF)
    except OSError:
        return None
    n_short = norm(title or short)
    hits = []
    for n in names:
        if not n.endswith(".md"):
            continue
        base = n[:-3]
        if norm(base) == n_short:
            hits.append(os.path.join(SHELF, n))
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        print(f"  [跳过] {short} 归一化匹配到多个笔记: {[os.path.basename(h) for h in hits]}")
        return None
    return None


def build_mark_section(book, sync_date):
    items = book.get("mark_items") or []
    n_marks = len(book.get("marks") or [])
    prog = book.get("progress", 0)
    lines = [SECTION, ""]
    lines.append(f"> 导出时间：{sync_date} ｜ 进度：{prog}% ｜ 划线：{n_marks} 条 ｜ 想法：{book.get('ideas', 0)} 条")
    lines.append("")
    read_info = f"> 本月阅读：{book.get('min', 0)} 分钟"
    mark_days = book.get("mark_days") or []
    if mark_days:
        read_info += f" ｜ 阅读日：{'、'.join(mark_days)}"
    profile = book.get("hour_profile") or "—"
    if profile != "—":
        read_info += f" ｜ 时段画像：{profile}"
    lines.append(read_info)
    lines.append("")
    if not items:
        lines.append("> 本期尚未记录划线。")
        lines.append("")
    else:
        groups = []
        seen = set()
        for it in items:
            title = (it.get("chapter") or "").strip() or "未分类章节"
            txt = (it.get("text") or "").strip()
            if not txt:
                continue
            if title not in seen:
                groups.append([title, []])
                seen.add(title)
            groups[-1][1].append(txt)
        for title, quotes in groups:
            lines.append(f"### {title}")
            lines.append("")
            for q in quotes:
                lines.append(f"> {q}")
                lines.append("")
    return "\n".join(lines) + "\n\n" + END_MARK


def new_note_frontmatter(title, author, cover, status, finish_date=""):
    return f"""---
author: "{author}"
publication_year:
publisher: ""
genre: []
douban_id: ""
cover: {cover}
tags:
  - 书籍
status: {status}
created: {datetime.date.today().isoformat()}
source: "[[微信读书]]"
start_date:
finish_date: {finish_date}
rating:
plan: ""
taste_genre: ""
taste_core: []
taste_style: []
taste_pace: ""
taste_region: ""
taste_verified: false
---

# {title}

"""


def set_status(content, status):
    return re.sub(r"(?m)^status:.*$", f"status: {status}", content, count=1)


def set_finish_date(content, date):
    """仅当 finish_date 为空时填充，已有值不覆盖（保留用户手动填写的读完日期）。"""
    if re.search(r"(?m)^finish_date:\s*$", content):
        return re.sub(r"(?m)^finish_date:\s*$", f"finish_date: {date}", content, count=1)
    return content


def main():
    sync_date = datetime.date.today().isoformat()
    report = []
    for b in books:
        short = b["short"]
        title = b.get("title") or short
        status = "读完" if b.get("finished") else "在读"
        n_marks = len(b.get("marks") or [])
        prog = b.get("progress", 0)
        sec = build_mark_section(b, sync_date)
        path = find_note(short, title)
        if path is None:
            path = os.path.join(SHELF, title + ".md")
            finish_date = sync_date if b.get("finished") else ""
            content = new_note_frontmatter(title, b.get("author", ""), b.get("cover", ""), status, finish_date) + sec + "\n"
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            report.append(f"[新建] {title}.md -> {status} {prog}% 划线{n_marks}条")
            continue
        with open(path, encoding="utf-8") as f:
            content = f.read()
        if SECTION in content:
            idx = content.index(SECTION)
            # 找到区块结束标记：标记之后的内容视为用户自写内容，必须保留
            mark_idx = content.find(END_MARK, idx)
            if mark_idx != -1:
                tail = content[mark_idx + len(END_MARK):]
                content = content[:idx].rstrip() + "\n\n" + sec + "\n" + tail
            else:
                # 旧格式文件（无结束标记）：SECTION 之后全为脚本生成的旧区块，整体替换
                content = content[:idx].rstrip() + "\n\n" + sec + "\n"
        else:
            content = content.rstrip() + "\n\n" + sec + "\n"
        content = set_status(content, status)
        if b.get("finished"):
            content = set_finish_date(content, sync_date)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        report.append(f"[更新] {os.path.basename(path)} -> {status} {prog}% 划线{n_marks}条")
    print("\n".join(report))
    print(f"共同步 {len(report)} 本")


if __name__ == "__main__":
    main()
