# -*- coding: utf-8 -*-
"""
gen_monthly_summary.py — 生成微信读书阅读月报（Obsidian dataviewjs 版，数据图丰富）
用法: python gen_monthly_summary.py [YYYY-MM]
  - 不带参数：默认上月（供每月 1 号定时任务使用）
  - 数据源：vault 阅读统计/data/YYYY-MM.json（refresh 自动归档 / archive_month.py 补生成）
  - 与 Obsidian 内「生成月报」按钮共用同一模板 month_report_tpl.py
"""
import os, sys, json, datetime
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import config
import month_report_tpl as _mrp
from datetime import timezone, timedelta

TZ = timezone(timedelta(hours=8))
OUT_DIR = config.stats_dir()
DATA_DIR = config.data_dir()


def fmt_min(m):
    if m >= 60:
        h, mm = divmod(m, 60)
        return f"{h}小时{mm:02d}分" if mm else f"{h}小时"
    return f"{m}分钟"


def load(y, mo):
    fp = os.path.join(DATA_DIR, f"{y:04d}-{mo:02d}.json")
    if not os.path.exists(fp):
        sys.exit(f"未找到归档数据 {fp}，请先运行 archive_month.py {y:04d}-{mo:02d} 补生成")
    with open(fp, encoding="utf-8") as f:
        return json.load(f)



def ensure_data(y, mo):
    """确保该月归档数据存在（模板运行时也需要它）"""
    fp = os.path.join(DATA_DIR, f"{y:04d}-{mo:02d}.json")
    if not os.path.exists(fp):
        sys.exit(f"未找到归档数据 {fp}，请先运行 archive_month.py {y:04d}-{mo:02d} 补生成")
    return fp

def build(y, mo):
    D = load(y, mo)
    n_days = D.get("n_days", 31)
    day_sec = {int(k): v for k, v in D.get("day_sec", {}).items()}
    total_sec = D.get("total_sec", 0)
    read_days = D.get("read_days", 0)
    books = D.get("books", [])
    finished = [b for b in books if b.get("finished")]
    prefer = D.get("prefer", "—")
    pt_word = D.get("prefer_time_word") or ""
    pa = D.get("prefer_author") or ""
    pp = D.get("prefer_publisher") or ""
    pc = D.get("prefer_cp") or ""

    lines = []
    lines.append("---")
    lines.append(f"title: 阅读月报 {y:04d}-{mo:02d}")
    lines.append("source: 微信读书")
    lines.append(f"month: {y:04d}-{mo:02d}")
    lines.append("---")
    lines.append("")
    lines.append(f"# 📖 阅读月报 · {y} 年 {mo} 月")
    lines.append("")

    # 总览
    n_books = len(books)
    lines.append("## 总览")
    lines.append("")
    lines.append("| 本月总时长 | 阅读天数 | 阅读书目 | 读完 |")
    lines.append("|---|---|---|---|")
    lines.append(f"| {fmt_min(round(total_sec / 60))} | {read_days} 天 | {n_books} 本 | {len(finished)} 本 |")
    lines.append("")

    # 每日时长（文本条形）
    lines.append("## 每日时长")
    lines.append("")
    mx = max((day_sec.get(d, 0) for d in range(1, n_days + 1)), default=0) or 1
    bar_lines = []
    for d in range(1, n_days + 1):
        sec = day_sec.get(d, 0)
        if sec <= 0:
            continue
        pct = sec / mx
        filled = int(round(pct * 16))
        bar = "█" * filled + "░" * (16 - filled)
        bar_lines.append(f"{mo:02d}/{d:02d} {bar} {fmt_min(round(sec / 60))}")
    if bar_lines:
        lines.append("```text")
        lines.extend(bar_lines)
        lines.append("```")
    else:
        lines.append("本月无阅读记录。")
    lines.append("")

    # 读完书目
    lines.append("## 读完书目")
    lines.append("")
    if finished:
        for b in sorted(finished, key=lambda x: -x.get("sec", 0)):
            lines.append(f"- **{b.get('short', '')}**（{b.get('author', '')}）")
    else:
        lines.append("本月没有读完的书。")
    lines.append("")

    # 最佳划线 TOP5（按本月划线数）
    lines.append("## 最佳划线")
    lines.append("")
    with_marks = [b for b in books if b.get("month_marks", 0) > 0]
    if with_marks:
        top = sorted(with_marks, key=lambda x: -x.get("month_marks", 0))[:5]
        idx = 1
        for b in top:
            # 取本月最近一条划线
            recent = ""
            for x in (b.get("mark_items") or []):
                t = x.get("t", 0)
                if not t:
                    continue
                dt = datetime.datetime.fromtimestamp(t, TZ)
                if dt.year == y and dt.month == mo:
                    recent = x.get("text", "")
                    break
            if recent:
                lines.append(f"{idx}. “{recent}” ——《{b.get('short', '')}》")
            else:
                lines.append(f"{idx}. 《{b.get('short', '')}》（本月 {b.get('month_marks', 0)} 条划线）")
            idx += 1
    else:
        lines.append("本月暂无划线记录。")
    lines.append("")

    # 偏好
    lines.append("## 偏好")
    lines.append("")
    lines.append(f"- 分类：{prefer}")
    if pt_word:
        lines.append(f"- 时段：{pt_word}")
    if pa:
        lines.append(f"- 作者：{pa}")
    if pp:
        lines.append(f"- 出版社：{pp}")
    if pc:
        lines.append(f"- 版权方：{pc}")
    lines.append("")
    return "\n".join(lines)


def _hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lerp(a, b, t):
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _heat_for(pal):
    """热力色阶 5 档（与 gen_dv.py 一致）：heat-0=bg，heat-1..4 为 line→main 渐进"""
    light = _hex2rgb(pal["line"])
    dark = _hex2rgb(pal["main"])
    return [pal["bg"]] + [_lerp(light, dark, t) for t in (0.2, 0.45, 0.7, 1.0)]


def _themes_js():
    """从 themes.json 构造前端换肤数据（与 gen_dv.py 一致）"""
    tp = os.path.join(_HERE, "themes.json")
    with open(tp, encoding="utf-8") as f:
        td = json.load(f)
    items = []
    for k, t in td["themes"].items():
        items.append(json.dumps(k, ensure_ascii=False) + ': {"name": ' + json.dumps(t.get("name", k), ensure_ascii=False)
                     + ', "palette": ' + json.dumps(t["palette"], ensure_ascii=False)
                     + ', "heat": ' + json.dumps(_heat_for(t["palette"]), ensure_ascii=False) + '}')
    return "{" + ", ".join(items) + "}", (td.get("current") or list(td["themes"].keys())[0])


def main():
    if len(sys.argv) >= 2:
        y, mo = map(int, sys.argv[1].split("-"))
    else:
        now = datetime.datetime.now(TZ)
        prev = now.replace(day=1) - timedelta(days=1)
        y, mo = prev.year, prev.month
    ensure_data(y, mo)
    themes_js, cur = _themes_js()
    md = _mrp.build_report_md(y, mo, themes_js, cur)
    out = os.path.join(OUT_DIR, f"阅读月报-{y:04d}-{mo:02d}.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    print("written:", out, f"({len(md)} chars)")


if __name__ == "__main__":
    main()
