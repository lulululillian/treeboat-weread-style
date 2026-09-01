# -*- coding: utf-8 -*-
"""微信读书阅读统计 — 可交互独立 HTML 生成器（周/月/天三视图 tab 筛选）"""
import json, os, datetime, urllib.parse
import sys
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import config
_CFG = config.load()

TMP = _HERE
DATA_SRC = os.environ.get("WEREAD_DASH_DATA", f"{TMP}/dash_data.json")
with open(DATA_SRC, encoding="utf-8") as f:
    D = json.load(f)

day_sec = {int(k): v for k, v in D["day_sec"].items()}
total_sec = D["total_sec"]
read_days = D["read_days"]
books_raw = D["books"]
prefer = D.get("prefer", "—")

# 进度/读完/划线/封面/作者 全部来自接口实时数据（见 prep_dash.py），不再使用写死字典

VAULT = config.vault_name()
TZ = datetime.timezone(datetime.timedelta(hours=8))

# 动态当前周期（prep_dash.py 已把周期写入 dash_data.json，避免写死月份）
YEAR = int(D.get("year", datetime.datetime.now(TZ).year))
MONTH = int(D.get("month", datetime.datetime.now(TZ).month))
N_DAYS = int(D.get("n_days", 31))
TITLE = f"{YEAR} 年 {MONTH} 月"

# ================= 配色卡（改色只动这里） =================
# bg     页面大底色（也被热力图空格/划线背景复用）
# line   卡片边框 / 进度条底 / 标签底 / 热力图浅格
# faint  弱化文字（无数据、占位）
# sub    次要文字（说明、标签）
# main   主色（标题/链接/进度填充/热力图深格）
# white  卡片底色
# 配色主题从 themes.json 读取：current 指定当前主题，themes 下为已存配色存档
_THEMES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes.json")
_DEFAULT_PALETTE = {
    "bg":    "#EEF2F8",
    "line":  "#D5DEEA",
    "faint": "#98A6BC",
    "sub":   "#5B6B85",
    "main":  "#2F3E5C",
    "white": "#FFFFFF",
}
def _load_palette():
    try:
        with open(_THEMES_PATH, encoding="utf-8") as f:
            td = json.load(f)
        cur = td.get("current") or list(td.get("themes", {}).keys())[0]
        pal = td["themes"][cur]["palette"]
        return {k: pal.get(k, _DEFAULT_PALETTE[k]) for k in _DEFAULT_PALETTE}
    except Exception:
        return dict(_DEFAULT_PALETTE)
PALETTE = _load_palette()
# 模板内出现的固定色值 → CSS 变量（前端换肤：只改 :root 变量即全局变色）
COLOR_MAP = {
    "#FAF6E9": "var(--wr-bg)",
    "#E6D4C0": "var(--wr-line)",
    "#B9A5A8": "var(--wr-faint)",
    "#7E748C": "var(--wr-sub)",
    "#414969": "var(--wr-main)",
    "#FFFFFF": "var(--wr-white)",
}
def remap_colors(s):
    for k, v in COLOR_MAP.items():
        s = s.replace(k, v)
    return s

def hex2rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))

def ob_uri(note):
    p = f"{_CFG['shelf_rel_dir']}/{note}"
    return "obsidian://open/?vault=" + urllib.parse.quote(VAULT) + "&file=" + urllib.parse.quote(p, safe="/")

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def recent_marks(marks, n=2):
    # 划线已由 prep 从 /book/bookmarklist 实时拉取并降序排列
    return (marks or [])[:n]

def month_recent_marks(book, n=2):
    # 只取当前周期的最近划线（mark_items 已按 createTime 降序）
    out = []
    for x in (book.get("mark_items") or []):
        t = x.get("t", 0)
        if not t:
            continue
        dt = datetime.datetime.fromtimestamp(t, TZ)
        if dt.year == YEAR and dt.month == MONTH:
            out.append(x.get("text", ""))
        if len(out) >= n:
            break
    return out

# ---- 每天读的书（基于划线 createTime 实证，由 prep 计算）----
day_book_map = {int(k): v for k, v in D.get("day_book_map", {}).items()}
book_mark_days = {k: v for k, v in D.get("book_mark_days", {}).items()}

books = [{
    "short": b["short"],
    "title": b.get("title") or b["short"],
    "author": b.get("author", ""),
    "min": b["min"],
    "sec": b["sec"],
    "bookId": b.get("bookId", ""),
    "cover": b.get("cover", ""),
    "finished": b.get("finished", False),
    "progress": b.get("progress", 0),
    "marks": b.get("marks", []),
    "mark_items": b.get("mark_items", []),
    "month_marks": b.get("month_marks", 0),
    "ideas": b.get("ideas", 0),
} for b in books_raw]
books.sort(key=lambda x: -x["sec"])

# short（短名）→ title（全名，含冒号后副标题）映射，供周视图等以 short 为 key 的场景统一显示全名
short_to_title = {b["short"]: (b.get("title") or b["short"]) for b in books}

def fmt_min(m):
    if m >= 60:
        h = m // 60; mm = m % 60
        return f"{h}小时{mm:02d}分" if mm else f"{h}小时"
    return f"{m}分钟"

def fmt_sec(sec):
    return fmt_min(round(sec / 60))

# ================= 月视图组件 =================
def lerp(c1, c2, t):
    return "#%02x%02x%02x" % tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
EMPTY = hex2rgb(PALETTE["bg"]); LIGHT = hex2rgb(PALETTE["line"]); DARK = hex2rgb(PALETTE["main"])
def heat_stops(pal=None):
    """热力色阶 5 档：heat-0=bg（空），heat-1..4 为 line→main 的渐进档"""
    p = pal or PALETTE
    light = hex2rgb(p["line"]); dark = hex2rgb(p["main"])
    return [p["bg"]] + [lerp(light, dark, t) for t in (0.2, 0.45, 0.7, 1.0)]
def cell_color(m):
    # 按分钟分档，输出 CSS 变量，前端换肤时热力图随主题一起变
    if m <= 0:
        return "var(--wr-heat-0)"
    if m <= 15:
        return "var(--wr-heat-1)"
    if m <= 45:
        return "var(--wr-heat-2)"
    if m <= 90:
        return "var(--wr-heat-3)"
    return "var(--wr-heat-4)"

def heatmap_svg():
    yr, mo = YEAR, MONTH
    w1 = datetime.date(yr, mo, 1).weekday()
    sun_idx = (w1 + 1) % 7
    n_days = N_DAYS
    n_rows = (sun_idx + n_days - 1) // 7 + 1
    step, cell, label_w, title_h, wd_h = 29, 26, 24, 28, 18
    top = title_h + wd_h
    legend_h = 24
    width = label_w + 7 * step + 6
    height = top + n_rows * step + legend_h
    wd = ["日", "一", "二", "三", "四", "五", "六"]
    h = [f'<svg width="{width}" height="{height}" style="display:block;max-width:100%">']
    h.append(f'<text x="{label_w}" y="18" font-size="13" font-weight="500" fill="#414969">{TITLE}</text>')
    for c in range(7):
        x = label_w + c * step + cell / 2
        h.append(f'<text x="{x:.0f}" y="{title_h+12}" font-size="10" fill="#7E748C" text-anchor="middle">{wd[c]}</text>')
    for r in range(n_rows):
        y = top + r * step + cell / 2 + 4
        h.append(f'<text x="8" y="{y:.0f}" font-size="10" fill="#7E748C" text-anchor="middle">W{r+1}</text>')
    for d in range(1, n_days + 1):
        col = (sun_idx + d - 1) % 7
        row = (sun_idx + d - 1) // 7
        x = label_w + col * step; y = top + row * step
        mins = round(day_sec.get(d, 0) / 60)
        h.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="4" fill="{cell_color(mins)}" stroke="#FFFFFF" stroke-width="1"><title>{mo}月{d}日 · {mins} 分钟</title></rect>')
        h.append(f'<text x="{x+4}" y="{y+12}" font-size="9" fill="{("#7E748C" if mins>0 else "#B9A5A8")}">{d}</text>')
    lx, ly = label_w, top + n_rows * step + 4
    h.append(f'<text x="{lx}" y="{ly+11}" font-size="10" fill="#7E748C">少</text>')
    for i in range(10):
        t = i / 9
        c = cell_color(t * 86) if t > 0 else "var(--wr-heat-0)"
        h.append(f'<rect x="{lx+18+i*11}" y="{ly}" width="10" height="10" rx="2" fill="{c}"/>')
    h.append(f'<text x="{lx+18+10*11+4}" y="{ly+11}" font-size="10" fill="#7E748C">多</text>')
    h.append('</svg>')
    return "".join(h), n_rows

def top5_html():
    if not books:
        return '<div style="font-size:12px;color:#7E748C;padding:6px 0">暂无阅读记录</div>'
    max_min = max(b["min"] for b in books)
    bars = []
    for b in books[:6]:  # 只取前 6 名，超出不显示（读书卡仍全量展示）
        pct = int(round(b["min"] / max_min * 100)) if max_min else 0
        bars.append(f'<div style="margin-bottom:12px"><div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:5px"><span>{b.get("title") or b["short"]}</span><span style="color:#7E748C">{b["min"]}m</span></div><div style="height:8px;background:#E6D4C0;border-radius:4px;overflow:hidden"><div style="height:100%;width:{pct}%;background:#414969;border-radius:4px"></div></div></div>')
    return "".join(bars)

def cards_html(day_range=None, label="本月"):
    """读书卡列表。
    day_range=None：全量（月视图，显示本月阅读分钟、累计划线等）。
    day_range=(a,b)：仅显示 [a,b] 日内有划线的书，划线/最近阅读均限定在该范围（周/日视图）。
    """
    rng = day_range
    cards = []
    for b in books:
        s = b["short"]; disp = b.get("title") or s; prog = b.get("progress", 0)
        auth = b.get("author", ""); cov = b.get("cover", "")
        if rng:
            a, bday = rng
            # 范围内有划线才展示（book_mark_days 已按日归集）
            if not any(a <= d <= bday for d in book_mark_days.get(s, [])):
                continue
            # 从 mark_items 过滤范围内划线（已按 createTime 降序）
            range_items = []
            for x in (b.get("mark_items") or []):
                t = x.get("t")
                if not t:
                    continue
                dt = datetime.datetime.fromtimestamp(t, TZ)
                if dt.year == YEAR and dt.month == MONTH and a <= dt.day <= bday:
                    range_items.append(x)
            range_count = len(range_items)
            quotes = [x.get("text", "") for x in range_items[:2]]
            last_str = ""
            if range_items:
                ldt = datetime.datetime.fromtimestamp(range_items[0]["t"], TZ)
                last_str = f'<div style="font-size:11px;color:#B9A5A8;white-space:nowrap;flex-shrink:0">最近阅读 {ldt.month}/{ldt.day}</div>'
            min_str = ""  # 范围模式无法按书拆分时长，不显示
            bottom = f"{label}划线 {range_count} 条"
            no_mark = f"{label}尚未记录划线"
        else:
            mk = len(b.get("marks", [])); mkm = b.get("month_marks", 0); ideas = b.get("ideas", 0)
            last_str = ""
            for x in (b.get("mark_items") or []):
                if x.get("t"):
                    ldt = datetime.datetime.fromtimestamp(x["t"], TZ)
                    last_str = f'<div style="font-size:11px;color:#B9A5A8;white-space:nowrap;flex-shrink:0">最近阅读 {ldt.month}/{ldt.day}</div>'
                    break
            quotes = month_recent_marks(b)
            min_str = f'<div style="font-size:11px;color:#7E748C;white-space:nowrap">本月阅读 {b.get("min", 0)} 分钟</div>'
            idea_html = f' · 想法 {ideas} 条' if ideas else ''
            bottom = f"本月划线 {mkm} 条 · 累计 {mk} 条{idea_html}"
            no_mark = "本月尚未记录划线"
        status = ('<span style="background:#414969;color:#FAF6E9;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:500">读完</span>'
                  if b.get("finished")
                  else '<span style="background:#E6D4C0;color:#414969;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:500">在读</span>')
        if quotes:
            q_html = "".join(f'<div style="font-size:12px;color:#7E748C;line-height:1.6;padding:6px 10px;border-left:2px solid #414969;background:#FAF6E9;margin-bottom:6px;border-radius:0 4px 4px 0">“{esc(q)}”</div>' for q in quotes)
        else:
            q_html = f'<div style="font-size:12px;color:#B9A5A8;padding:6px 10px;border-left:2px solid #E6D4C0;background:#FAF6E9;margin-bottom:6px;border-radius:0 4px 4px 0">{no_mark}</div>'
        cards.append(f'''<div style="border:0.5px solid #E6D4C0;border-radius:12px;padding:16px 18px;background:#FFFFFF;margin-bottom:12px">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
<div style="font-size:10px;color:#7E748C;letter-spacing:1.5px">BOOK NOTE · 微信读书</div>
<a href="{ob_uri(disp)}" style="background:#E6D4C0;color:#414969;padding:3px 10px;border-radius:20px;font-size:11px;text-decoration:none">已链 [[{disp}]]</a>
</div>
<div style="display:flex;gap:14px;margin-bottom:10px">
<div style="width:56px;height:78px;flex-shrink:0;background-image:url('{cov}');background-size:cover;background-position:center;background-color:#E6D4C0;border-radius:6px"></div>
<div style="flex:1;min-width:0">
<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px"><div style="flex:1;min-width:0;font-size:18px;font-weight:600;color:#414969;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{disp}</div>{status}{min_str}{last_str}</div>
<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px"><div style="flex:1;height:6px;background:#E6D4C0;border-radius:3px;overflow:hidden"><div style="height:100%;width:{prog}%;background:#414969;border-radius:3px"></div></div><div style="font-size:11px;color:#414969;font-weight:500;min-width:28px;text-align:right">{prog}%</div></div>
<div style="font-size:11px;color:#B9A5A8">{auth}</div>
</div>
</div>
{q_html}
<div style="font-size:11px;color:#7E748C;margin-top:10px">{bottom}</div>
</div>''')
    if not cards:
        label_text = label if rng else "本月"
        return (f'<div style="background:#FFFFFF;border:0.5px solid #E6D4C0;border-radius:12px;'
                f'padding:32px 20px;text-align:center;color:#B9A5A8;font-size:14px;line-height:1.8">'
                f'{label_text}暂无阅读记录<br><span style="font-size:12px;color:#D4C5C8">有阅读记录后将自动展示</span></div>')
    return "".join(cards)

def summary_html():
    total_str = fmt_sec(total_sec); n_books = len(books)
    last_day = max(day_sec.keys()) if day_sec else 28
    ring = ring_clock_svg(_hour_counts_in_range(1, last_day), size=130, label="本月划线")
    ring_html = (f'<div style="background:#FFFFFF;border:0.5px solid #E6D4C0;border-radius:12px;padding:10px 14px;'
                 f'display:flex;align-items:center;justify-content:center;flex:0 0 auto">{ring}</div>') if ring else ''
    return f'''<div style="display:flex;gap:12px;margin-bottom:16px;align-items:stretch;flex-wrap:wrap">
<div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:12px">
<div style="background:#FFFFFF;border:0.5px solid #E6D4C0;border-radius:12px;padding:14px 16px;flex:1;display:flex;flex-direction:column;justify-content:center">
<div style="font-size:12px;color:#7E748C">本月总时长</div><div style="font-size:28px;font-weight:500;margin-top:4px">{total_str}</div></div>
<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px">
<div style="background:#FFFFFF;border:0.5px solid #E6D4C0;border-radius:12px;padding:12px 14px"><div style="font-size:12px;color:#7E748C">阅读天数</div><div style="font-size:20px;font-weight:500;margin-top:4px">{read_days} 天</div></div>
<div style="background:#FFFFFF;border:0.5px solid #E6D4C0;border-radius:12px;padding:12px 14px"><div style="font-size:12px;color:#7E748C">本月书目</div><div style="font-size:20px;font-weight:500;margin-top:4px">{n_books} 本</div></div>
</div></div>
{ring_html}
</div>'''

# ================= 周视图（与月视图同构，统计维度＝本周） =================


def cover_gallery_html():
    # 本月在读书籍封面横向画廊（无背景卡样式，带自动滚动动效；按时长降序，缺失封面跳过）
    cards = []
    for b in sorted(books, key=lambda x: x.get("sec", 0), reverse=True):
        disp = b.get("title") or b.get("short") or "未知"
        cov = b.get("cover", "")
        if not cov:
            continue
        tstr = fmt_sec(b.get("sec", 0))
        cards.append(
            f'<div style="flex:0 0 auto;width:96px;text-align:center">'
            f'<a href="{ob_uri(disp)}" data-note="{esc(disp)}" style="text-decoration:none;display:block;cursor:pointer" title="打开笔记：{esc(disp)}">'
            f'<img src="{esc(cov)}" alt="{esc(disp)}" loading="lazy" '
            f'style="width:96px;height:128px;object-fit:cover;border-radius:10px;'
            f'border:0.5px solid #E6D4C0;display:block;box-shadow:0 2px 8px rgba(0,0,0,.08);pointer-events:none"/>'
            f'</a>'
            f'<div style="font-size:11px;color:#414969;margin-top:6px;overflow:hidden;'
            f'text-overflow:ellipsis;white-space:nowrap;max-width:96px">{esc(disp)}</div>'
            f'<div style="font-size:10px;color:#7E748C;margin-top:2px">{tstr}</div>'
            f'</div>')
    if not cards:
        return ""
    return (f'<div style="margin:0 0 16px">'
            f'<div style="font-size:14px;font-weight:500;margin-bottom:10px;color:#414969">本月在读 · 封面</div>'
            f'<div id="wr-cover-gallery" style="display:flex;gap:12px;overflow-x:auto;'
            f'padding:4px 2px 8px;align-items:flex-start;cursor:grab">'
            f'{"".join(cards)}</div></div>')

def week_bounds():
    now = datetime.datetime.now(TZ).date()
    start = now - datetime.timedelta(days=now.weekday())  # 周一起
    a = start.day if start.month == MONTH else 1  # 跨月周从本月 1 日起
    b = min(a + 6, N_DAYS)
    return a, b

WEEK_SNAP_DIR = os.path.join(
    config.data_dir(),
    "week-snapshots")

def week_compare_html():
    """本周 vs 上周：按日均比较。渲染为左列内嵌对比条（嵌入周热力图卡片下方）。"""
    try:
        now = datetime.datetime.now(TZ).date()
        this_start = (now - datetime.timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        import glob
        files = sorted(glob.glob(os.path.join(WEEK_SNAP_DIR, "week-*.json")))
        prev_fp = None
        for fp in files:
            base = os.path.basename(fp)[5:-5]  # week-YYYY-MM-DD.json → YYYY-MM-DD
            if base < this_start:
                prev_fp = fp
        if not prev_fp:
            return ('<div style="flex:1;margin-top:12px">'
                    '<div style="font-size:12px;font-weight:500;margin-bottom:8px">较上周日均</div>'
                    '<div style="font-size:11px;color:#B9A5A8">上周数据不足，暂无法计算周环比</div></div>')
        with open(prev_fp, encoding="utf-8") as f:
            snap = json.load(f)
        prev_avg = int(snap.get("avg_sec") or 0)
        a, b = week_bounds()
        this_avg = sum(day_sec.get(d, 0) for d in range(a, b + 1)) / 7
        if prev_avg <= 0:
            return ('<div style="flex:1;margin-top:12px">'
                    '<div style="font-size:12px;font-weight:500;margin-bottom:8px">较上周日均</div>'
                    '<div style="font-size:11px;color:#B9A5A8">上周无阅读数据，暂无法计算周环比</div></div>')
        pct = (this_avg - prev_avg) / prev_avg
        txt = f"{'+' if pct >= 0 else ''}{pct * 100:.0f}%"
        mx = max(prev_avg, this_avg) or 1
        pw = max(int(prev_avg / mx * 100), 2)
        tw = max(int(this_avg / mx * 100), 2)
        return (f'<div style="flex:1;margin-top:12px">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">'
                f'<div style="font-size:12px;font-weight:500">较上周日均</div>'
                f'<span style="font-size:14px;font-weight:600;color:#414969">{txt}</span></div>'
                f'<div style="display:flex;flex-direction:column;gap:8px">'
                f'<div><div style="display:flex;justify-content:space-between;font-size:11px;color:#7E748C;margin-bottom:4px">'
                f'<span>上周日均</span><span>{fmt_sec(prev_avg)}</span></div>'
                f'<div style="height:8px;background:#E6D4C0;border-radius:4px;overflow:hidden">'
                f'<div style="height:100%;width:{pw}%;background:#B9A5A8;border-radius:4px"></div></div></div>'
                f'<div><div style="display:flex;justify-content:space-between;font-size:11px;color:#7E748C;margin-bottom:4px">'
                f'<span>本周日均</span><span>{fmt_sec(this_avg)}</span></div>'
                f'<div style="height:8px;background:#E6D4C0;border-radius:4px;overflow:hidden">'
                f'<div style="height:100%;width:{tw}%;background:#414969;border-radius:4px"></div></div></div>'
                f'</div></div>')
    except Exception:
        return ('<div style="flex:1;margin-top:12px">'
                '<div style="font-size:12px;font-weight:500;margin-bottom:8px">较上周日均</div>'
                '<div style="font-size:11px;color:#B9A5A8">上周数据不足，暂无法计算周环比</div></div>')

def week_stats_html(a, b):
    wsec = sum(v for d, v in day_sec.items() if a <= d <= b)
    wdays = sum(1 for d, v in day_sec.items() if a <= d <= b and v > 0)
    wbks = set()
    for d in range(a, b + 1):
        wbks.update(day_book_map.get(d, []))
    ring = ring_clock_svg(_hour_counts_in_range(a, b), size=130, label="本周划线")
    ring_html = (f'<div style="background:#FFFFFF;border:0.5px solid #E6D4C0;border-radius:12px;padding:10px 14px;'
                 f'display:flex;align-items:center;justify-content:center;flex:0 0 auto">{ring}</div>') if ring else ''
    return f'''<div style="display:flex;gap:12px;margin-bottom:16px;align-items:stretch;flex-wrap:wrap">
<div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:12px">
<div style="background:#FFFFFF;border:0.5px solid #E6D4C0;border-radius:12px;padding:14px 16px;flex:1;display:flex;flex-direction:column;justify-content:center">
<div style="font-size:12px;color:#7E748C">本周总时长</div><div style="font-size:28px;font-weight:500;margin-top:4px">{fmt_sec(wsec)}</div></div>
<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px">
<div style="background:#FFFFFF;border:0.5px solid #E6D4C0;border-radius:12px;padding:12px 14px"><div style="font-size:12px;color:#7E748C">本周阅读天数</div><div style="font-size:20px;font-weight:500;margin-top:4px">{wdays} 天</div></div>
<div style="background:#FFFFFF;border:0.5px solid #E6D4C0;border-radius:12px;padding:12px 14px"><div style="font-size:12px;color:#7E748C">本周书目</div><div style="font-size:20px;font-weight:500;margin-top:4px">{len(wbks)} 本</div></div>
</div></div>
{ring_html}
</div>'''

def week_heat_svg(a, b):
    days = list(range(a, b + 1))  # 周一→周日
    step, cell, label_w, title_h, wd_h = 29, 26, 24, 28, 18
    top = title_h + wd_h
    legend_h = 24
    width = label_w + 7 * step + 6
    height = top + step + legend_h
    wd = ["一", "二", "三", "四", "五", "六", "日"]
    h = [f'<svg width="{width}" height="{height}" style="display:block;max-width:100%">']
    h.append(f'<text x="{label_w}" y="18" font-size="13" font-weight="500" fill="#414969">{MONTH}/{a} – {MONTH}/{b}</text>')
    for i, d in enumerate(days):
        h.append(f'<text x="{label_w + i * step + cell / 2:.0f}" y="{title_h+12}" font-size="10" fill="#7E748C" text-anchor="middle">{wd[i]}</text>')
        x, y = label_w + i * step, top
        mins = round(day_sec.get(d, 0) / 60)
        h.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="4" fill="{cell_color(mins)}" stroke="#FFFFFF" stroke-width="1"><title>{MONTH}/{d} · {mins} 分钟</title></rect>')
        h.append(f'<text x="{x+4}" y="{y+12}" font-size="9" fill="{("#7E748C" if mins>0 else "#B9A5A8")}">{d}</text>')
    lx, ly = label_w, top + step + 4
    h.append(f'<text x="{lx}" y="{ly+11}" font-size="10" fill="#7E748C">少</text>')
    for i in range(10):
        t = i / 9
        c = cell_color(t * 86) if t > 0 else "var(--wr-heat-0)"
        h.append(f'<rect x="{lx+18+i*11}" y="{ly}" width="10" height="10" rx="2" fill="{c}"/>')
    h.append(f'<text x="{lx+18+10*11+4}" y="{ly+11}" font-size="10" fill="#7E748C">多</text>')
    h.append('</svg>')
    return "".join(h)

def week_book_counts(a, b):
    # 统计 [a, b] 日内每本书的划线条数（book_mark_days 由 prep 实时归集）
    counts = {}
    for title, days in book_mark_days.items():
        c = sum(1 for d in days if a <= d <= b)
        if c:
            counts[title] = c
    return sorted(counts.items(), key=lambda x: -x[1])

def week_books_html(pairs):
    if not pairs:
        return '<div style="font-size:12px;color:#B9A5A8;padding:6px 0">本周暂无划线记录</div>'
    mx = pairs[0][1]
    bars = []
    for t, c in pairs[:6]:  # 同月视图：最多 6 本
        disp = short_to_title.get(t, t)  # 统一显示全名（含冒号后副标题）
        pct = int(round(c / mx * 100)) if mx else 0
        bars.append(f'<div style="margin-bottom:12px"><div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:5px"><span>{disp}</span><span style="color:#7E748C">{c} 条</span></div><div style="height:8px;background:#E6D4C0;border-radius:4px;overflow:hidden"><div style="height:100%;width:{pct}%;background:#414969;border-radius:4px"></div></div></div>')
    return "".join(bars)

def week_daily_list_html(a, b):
    wd = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    mins_list = [round(day_sec.get(d, 0) / 60) for d in range(a, b + 1)]
    mx = max(mins_list) or 1
    rows = []
    for i, m in enumerate(mins_list):
        pct = int(m / mx * 100)
        rows.append(
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">'
            f'<div style="width:30px;font-size:11px;color:#7E748C;flex-shrink:0">{wd[i]}</div>'
            f'<div style="flex:1;height:8px;background:#E6D4C0;border-radius:4px;overflow:hidden">'
            f'<div style="height:100%;width:{pct}%;background:#414969;border-radius:4px"></div></div>'
            f'<div style="width:46px;font-size:11px;color:#414969;text-align:right;flex-shrink:0">{m} 分</div></div>')
    return "".join(rows)

# ================= 通用：24小时环形时钟图（顺时针渐入动效） =================
def ring_clock_svg(hour_counts, size=140, label="划线"):
    """hour_counts: {hour: count}; 生成带顺时针渐入+JS悬停波浪动效的24小时环形时钟 SVG（无数据时显示空状态）"""
    import math
    total = sum(hour_counts.values())
    if not hour_counts:
        hour_counts = {}
    max_count = max(hour_counts.values()) if hour_counts else 1
    cx = cy = size / 2
    r = size * 0.36
    stroke_w = size * 0.085
    seg_angle = 360 / 24
    arc_len = 2 * math.pi * r * seg_angle / 360
    segments = []
    for h in range(24):
        count = hour_counts.get(h, 0)
        start_a = -90 + h * seg_angle
        end_a = start_a + seg_angle
        x1 = cx + r * math.cos(math.radians(start_a))
        y1 = cy + r * math.sin(math.radians(start_a))
        x2 = cx + r * math.cos(math.radians(end_a))
        y2 = cy + r * math.sin(math.radians(end_a))
        if count == 0:
            stroke, opacity = "#E6D4C0", "0.35"
        else:
            stroke, opacity = "#414969", f"{0.3 + 0.7 * (count / max_count):.2f}"
        segments.append(
            f'<path class="wr-ring-seg" data-hour="{h}" d="M {x1:.1f} {y1:.1f} A {r} {r} 0 0 1 {x2:.1f} {y2:.1f}" '
            f'fill="none" stroke="{stroke}" stroke-width="{stroke_w}" stroke-opacity="{opacity}" '
            f'stroke-dasharray="{arc_len:.1f}" stroke-dashoffset="{arc_len:.1f}" '
            f'style="animation:wereadRingFill 0.4s ease-out {h * 15}ms forwards;cursor:pointer;'
            f'transition:stroke-width .15s ease,stroke-opacity .15s ease;'
            f'--wr-base:{opacity};--wr-base-w:{stroke_w}">'
            f'<title>{h:02d}:00 · {count} 条划线</title></path>')
    fs = int(size * 0.17)
    ss = int(size * 0.075)
    hover_w = stroke_w + 7
    return (f'<svg class="wr-ring-svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}" style="flex-shrink:0;display:block">'
            f'<style>'
            f'@keyframes wrRingWave {{'
            f'  0%,100% {{ stroke-width:var(--wr-base-w,12); }}'
            f'  50% {{ stroke-width:calc(var(--wr-base-w,12) + 5); }}'
            f'}}'
            f'.wr-ring-seg:hover {{'
            f'  stroke-width:{hover_w}!important;'
            f'  stroke-opacity:1!important;'
            f'  filter:brightness(1.2)!important;'
            f'}}'
            f'</style>'
            f'{"".join(segments)}'
            f'<text x="{cx}" y="{cy - 1}" text-anchor="middle" font-size="{fs}" font-weight="600" fill="#414969">{total}</text>'
            f'<text x="{cx}" y="{cy + ss + 3}" text-anchor="middle" font-size="{ss}" fill="#B9A5A8">{label}</text>'
            f'</svg>')


def _hour_counts_in_range(day_start, day_end):
    """统计 [day_start, day_end] 日期范围内各小时的划线条数"""
    from collections import Counter
    counts = Counter()
    for bk in books:
        for x in (bk.get("mark_items") or []):
            t = x.get("t", 0)
            if not t:
                continue
            dt = datetime.datetime.fromtimestamp(t, TZ)
            if dt.year == YEAR and dt.month == MONTH and day_start <= dt.day <= day_end:
                counts[dt.hour] += 1
    return counts


# ================= 天视图（今日时长 + 读书卡） =================
def day_view():
    now = datetime.datetime.now(TZ).date()
    d = now.day if (now.year, now.month) == (YEAR, MONTH) else max(day_sec)
    mins = round(day_sec.get(d, 0) / 60)
    wdn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][datetime.date(YEAR, MONTH, d).weekday()]
    ring = ring_clock_svg(_hour_counts_in_range(d, d), size=120, label="今日划线")
    ring_html = f'<div style="flex:0 0 auto;display:flex;align-items:center">{ring}</div>'
    cards_area = cards_html(day_range=(d, d), label="今日")
    return f'''
<section id="v-day" class="view">
<div style="background:#FFFFFF;border:0.5px solid #E6D4C0;border-radius:12px;padding:14px 18px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
<div><div style="font-size:12px;color:#7E748C">今日读书时长 · {MONTH} 月 {d} 日 {wdn}</div><div style="font-size:24px;font-weight:500;margin-top:6px">{mins} 分钟</div></div>
{ring_html}
</div>
<div style="margin-bottom:14px">
<div style="font-size:14px;font-weight:500;margin-bottom:12px">读书卡</div>
{cards_area}</div>
</section>'''

# ================= 组装 =================
hm, n_rows = heatmap_svg()

# ================= 扩展预留渲染（数据达阈值才有值，缺失时优雅降级） =================
def tag_html(label, value):
    if not value:
        return ""
    return (f'<div style="font-size:12px;color:#7E748C;margin-top:10px"><span style="color:#B9A5A8">{label}</span> '
            f'<span style="background:#E6D4C0;color:#414969;padding:3px 10px;border-radius:12px;font-size:12px">{value}</span></div>')

def prefer_time_html(pt):
    if not pt:
        return '<div style="font-size:12px;color:#B9A5A8;padding:6px 0">暂无固定阅读时段</div>'
    items = []
    for ts, sec in pt.items():
        try:
            hh = datetime.datetime.fromtimestamp(int(ts), TZ).hour
        except Exception:
            continue
        items.append((hh, int(sec)))
    items.sort()
    if not items:
        return '<div style="font-size:12px;color:#B9A5A8;padding:6px 0">暂无固定阅读时段</div>'
    mx = max(s for _, s in items) or 1
    bars = []
    for hh, sec in items:
        pct = int(round(sec / mx * 100))
        bars.append(
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
            f'<div style="width:34px;font-size:10px;color:#7E748C;text-align:right;flex-shrink:0">{hh}:00</div>'
            f'<div style="flex:1;height:10px;background:#E6D4C0;border-radius:4px;overflow:hidden">'
            f'<div style="height:100%;width:{pct}%;background:#414969;border-radius:4px"></div></div>'
            f'<div style="width:52px;font-size:10px;color:#7E748C;flex-shrink:0">{fmt_sec(sec)}</div></div>')
    return "".join(bars)

prefer_extra = ""
if D.get("prefer_author"):
    prefer_extra += tag_html("偏好作者", D["prefer_author"])
if D.get("prefer_publisher"):
    prefer_extra += tag_html("偏好出版社", D["prefer_publisher"])
if D.get("prefer_cp"):
    prefer_extra += tag_html("偏好版权方", D["prefer_cp"])

pt_word = D.get("prefer_time_word") or ""
prefer_time_block = ''
if D.get("prefer_time"):
    prefer_time_block = (f'<div style="background:#FFFFFF;border:0.5px solid #E6D4C0;border-radius:12px;'
                         f'padding:16px;margin-bottom:14px">'
                         f'<div style="font-size:14px;font-weight:500;margin-bottom:12px">'
                         f'24 小时时段分布{" · " + pt_word if pt_word else ""}</div>'
                         f'{prefer_time_html(D.get("prefer_time"))}</div>')
else:
    prefer_time_block = (f'<div style="background:#FFFFFF;border:0.5px solid #E6D4C0;border-radius:12px;'
                         f'padding:14px 16px;margin-bottom:14px">'
                         f'<span style="font-size:12px;color:#B9A5A8">本月阅读时长不足，暂不分析偏好时段</span></div>')

# 分类
prefer_block = f'''<div style="background:#FFFFFF;border:0.5px solid #E6D4C0;border-radius:12px;padding:16px;margin-bottom:14px">
<div style="font-size:14px;font-weight:500;margin-bottom:10px">本月分类偏好</div><span style="background:#E6D4C0;color:#414969;padding:6px 14px;border-radius:20px;font-size:13px">{prefer}</span>{prefer_extra}</div>'''

month_view = f'''
<style>@keyframes wereadRingFill {{ to {{ stroke-dashoffset: 0; }} }}</style>
<section id="v-month" class="view active">
{summary_html()}
{cover_gallery_html()}
<div style="display:flex;gap:14px;flex-wrap:wrap;align-items:stretch;margin-bottom:14px">
<div style="background:#FFFFFF;border:0.5px solid #E6D4C0;border-radius:12px;padding:16px;flex:0 0 auto">
<div style="font-size:14px;font-weight:500;margin-bottom:12px">读书热力图</div>
{hm}
<div style="font-size:11px;color:#7E748C;margin-top:8px">格内数字为日期，颜色越深＝当天读得越久。</div></div>
<div style="background:#FFFFFF;border:0.5px solid #E6D4C0;border-radius:12px;padding:16px 20px;flex:1;min-width:280px;display:flex;flex-direction:column">
<div style="font-size:14px;font-weight:500;margin-bottom:12px">本月阅读时长排行</div>
<div style="flex:1">{top5_html()}</div></div>
</div>
<div style="margin-bottom:14px">
<div style="font-size:14px;font-weight:500;margin-bottom:12px">读书卡</div>
{cards_html()}</div>
{prefer_block}
{prefer_time_block}
</section>'''

week_view_html = f'''
<section id="v-week" class="view">
{week_stats_html(*week_bounds())}
<div style="display:flex;gap:14px;flex-wrap:wrap;align-items:stretch;margin-bottom:14px">
<div style="background:#FFFFFF;border:0.5px solid #E6D4C0;border-radius:12px;padding:16px;flex:0 0 auto;display:flex;flex-direction:column">
<div style="font-size:14px;font-weight:500;margin-bottom:12px">本周热力图</div>
{week_heat_svg(*week_bounds())}
<div style="font-size:11px;color:#7E748C;margin-top:8px">周一至周日，格内数字为日期，颜色越深＝当天读得越久。</div>
{week_compare_html()}</div>
<div style="background:#FFFFFF;border:0.5px solid #E6D4C0;border-radius:12px;padding:16px 20px;flex:1;min-width:280px;display:flex;flex-direction:column">
<div style="font-size:14px;font-weight:500;margin-bottom:12px">本周划线最多的书</div>
<div style="flex:1">{week_books_html(week_book_counts(*week_bounds()))}</div></div>
</div>
<div style="margin-bottom:14px">
<div style="font-size:14px;font-weight:500;margin-bottom:12px">读书卡</div>
{cards_html(day_range=week_bounds(), label="本周")}</div>
{prefer_block}
</section>'''

day_view_html = day_view()

# 统一走配色卡
month_view = remap_colors(month_view)
week_view_html = remap_colors(week_view_html)
day_view_html = remap_colors(day_view_html)

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>微信读书 · 阅读统计</title>
<style>
:root {{
  --wr-bg: {PALETTE["bg"]};
  --wr-line: {PALETTE["line"]};
  --wr-faint: {PALETTE["faint"]};
  --wr-sub: {PALETTE["sub"]};
  --wr-main: {PALETTE["main"]};
  --wr-white: {PALETTE["white"]};
  --wr-heat-0: {heat_stops()[0]};
  --wr-heat-1: {heat_stops()[1]};
  --wr-heat-2: {heat_stops()[2]};
  --wr-heat-3: {heat_stops()[3]};
  --wr-heat-4: {heat_stops()[4]};
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 0;
  background: var(--wr-bg);
  font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: var(--wr-main);
  -webkit-font-smoothing: antialiased;
}}
.container {{ max-width: 720px; margin: 0 auto; padding: 14px 20px 32px; }}
.header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 12px; }}
.brand {{ font-size: 12px; color: var(--wr-sub); letter-spacing: 2px; }}
.brand b {{ font-weight: 600; color: var(--wr-main); }}
.seg {{ display: inline-flex; background: var(--wr-line); border-radius: 999px; padding: 3px; }}
.seg button {{
  border: none; background: transparent; padding: 6px 20px; border-radius: 999px;
  cursor: pointer; font-size: 13px; color: var(--wr-sub); font-family: inherit;
  transition: all .15s ease; white-space: nowrap;
}}
.seg button.active {{ background: var(--wr-white); color: var(--wr-main); font-weight: 600; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
.view {{ display: none; }}
.view.active {{ display: block; animation: fade .2s ease; }}
@keyframes fade {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes wereadRingFill {{ to {{ stroke-dashoffset: 0; }} }}
</style>
</head>
<body>
<div class="container">
<style>@keyframes wereadRingFill {{ to {{ stroke-dashoffset: 0; }} }}</style>
  <div class="header">
    <div class="brand"><b>微信读书</b> · {YEAR} 年 {MONTH} 月</div>
    <div class="seg">
      <button data-view="week">周</button>
      <button data-view="month" class="active">月</button>
      <button data-view="day">天</button>
    </div>
  </div>

{month_view}

{week_view_html}

{day_view_html}

</div>
<script>
const segs = document.querySelectorAll('.seg button');
const views = document.querySelectorAll('.view');
segs.forEach(btn => {{
  btn.addEventListener('click', () => {{
    segs.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    views.forEach(v => v.classList.remove('active'));
    var target = document.getElementById('v-' + btn.dataset.view);
    target.classList.add('active');
    var ring = target.querySelector('.wr-ring-svg');
    if (ring) {{
      ring.querySelectorAll('.wr-ring-seg').forEach(function(p, i) {{
        var da = p.getAttribute('stroke-dasharray');
        p.style.strokeDashoffset = da;
        p.style.animation = 'none';
        void p.offsetWidth;
        p.style.animation = 'wereadRingFill 0.4s ease-out ' + (i * 15) + 'ms forwards';
      }});
    }}
  }});
}});
// 环形时钟波浪动效：鼠标悬停某段时，以该段为中心向两侧扩散波浪
function initRingClockWave() {{
  document.querySelectorAll('.wr-ring-svg').forEach(function(svg) {{
    var segs = svg.querySelectorAll('.wr-ring-seg');
    segs.forEach(function(seg) {{
      seg.addEventListener('mouseenter', function() {{
        var h = parseInt(seg.getAttribute('data-hour'));
        segs.forEach(function(s) {{
          var i = parseInt(s.getAttribute('data-hour'));
          var dist = Math.min(Math.abs(i - h), 24 - Math.abs(i - h));
          var delay = dist * 0.05 + (dist % 2) * 0.015;
          s.style.strokeDashoffset = '0';
          s.style.animation = 'wrRingWave 1.5s ease-in-out infinite';
          s.style.animationDelay = delay + 's';
        }});
      }});
      seg.addEventListener('mouseleave', function() {{
        segs.forEach(function(s) {{
          s.style.animation = '';
          s.style.animationDelay = '';
          s.style.strokeDashoffset = '0';
        }});
      }});
    }});
  }});
}}
initRingClockWave();
</script>
</body>
</html>'''

html = remap_colors(html)

if __name__ == "__main__":  # 直接运行才写独立 HTML；被 gen_dv 复用时只提供组件
    OUT = os.path.join(config.stats_dir(), "阅读统计.html")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("written:", OUT)
print("day_book_map:", day_book_map)
print("views: month / week / day")
