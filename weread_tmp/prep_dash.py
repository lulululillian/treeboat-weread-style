# -*- coding: utf-8 -*-
"""
prep_dash.py — 从微信读书接口实时计算阅读统计
依赖 refresh.py 已拉取的 monthly.json（/readdata/detail monthly），
并额外调用 /user/notebooks（读完状态/进度/划线数）与 /book/bookmarklist（划线内容）。
输出 dash_data.json 供 gen_html.py 渲染。

关键口径（依据 weread skill readdata.md / notes.md + 实测）：
- 总时长用接口 totalReadTime（秒），readTimes 仅作热力图明细
- 读完判定：markedStatus == 4（实测 readStat「读完N本」与 markedStatus=4 的书精确吻合）
- 划线内容来自 /book/bookmarklist 的 updated[].markText，按 createTime 降序
"""
import os, json, re, calendar, datetime, urllib.request, sys
from datetime import timezone, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import config

TMP = _HERE
TZ = timezone(timedelta(hours=8))
GATEWAY = config.GATEWAY
SKILL_VERSION = config.SKILL_VERSION


def call(body):
    body = dict(body)
    body["skill_version"] = SKILL_VERSION
    req = urllib.request.Request(GATEWAY, data=json.dumps(body).encode(), method="POST")
    req.add_header("Authorization", "Bearer " + config.get_key())
    req.add_header("Content-Type", "application/json")
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


# ---- 1. 阅读统计详情（refresh.py 已拉好存 monthly.json）----
# 支持 WEREAD_MONTHLY_SRC 指定输入（历史月份归档用），默认 monthly.json
MONTHLY_SRC = os.environ.get("WEREAD_MONTHLY_SRC", f"{TMP}/monthly.json")
with open(MONTHLY_SRC, encoding="utf-8") as f:
    m = json.load(f)

# 动态当前周期（baseTime=0 表示当前周期；若传历史 baseTime 则按它归集，避免写死月份）
bt = m.get("baseTime")
cur_dt = datetime.datetime.fromtimestamp(int(bt), TZ) if bt else datetime.datetime.now(TZ)
CUR_YEAR, CUR_MONTH = cur_dt.year, cur_dt.month

rt = m.get("readTimes", {})
daily = {}
for k, v in rt.items():
    ts = int(k)
    bj = datetime.datetime.fromtimestamp(ts, tz=timezone.utc) + timedelta(hours=8)
    daily[bj.day] = v  # 秒
day_sec = daily
total_sec = m.get("totalReadTime") or sum(daily.values())
read_days = m.get("readDays") or len(daily)
prefer = m.get("preferCategoryWord") or m.get("preferCategory") or "—"

# ---- 2. 笔记本概览（读完状态/进度/划线数），游标分页拉全 ----
nb_map = {}
last = 0
while True:
    nb = call({"api_name": "/user/notebooks", "count": 20, "lastSort": last})
    for b in nb.get("books", []):
        nb_map[b.get("bookId")] = {
            "markedStatus": b.get("markedStatus", 0),
            "readingProgress": b.get("readingProgress", 0),
            "noteCount": b.get("noteCount", 0),
        }
    if nb.get("hasMore") == 1 and nb.get("books"):
        last = nb["books"][-1].get("sort", last)
    else:
        break

# ---- 3. 书本列表（readLongest）→ 关联状态 → 实时划线 ----
books = []
day_book_map = {}
book_mark_days = {}  # short -> [本月划线所在日...]（含重复，用于周维度按条统计）
for b in (m.get("readLongest") or []):
    bk = b.get("book", {})
    title_full = bk.get("title", "")
    short = title_full.split("：")[0].split("(")[0].strip()
    # 显示用完整书名：去掉半角括号内冗余文案（如营销语），超长截断
    title_disp = re.sub(r"\([^)]*\)", "", title_full).strip()
    if len(title_disp) > 40:
        title_disp = title_disp[:40] + "…"
    bookId = bk.get("bookId", "")
    nb = nb_map.get(bookId, {})
    finished = (nb.get("markedStatus", 0) == 4)  # 实测：4=读完
    progress = nb.get("readingProgress", 0)
    note_count = nb.get("noteCount", 0)

    marks = []  # [text]，createTime 降序
    mark_items = []  # [{t, text, chapter}]，createTime 降序（供 sync_notes 按章节写回笔记）
    chapters = {}  # chapterUid(str) -> 章节标题
    ideas = 0  # 想法数（bookmarklist 中 type==2 的条目）
    if note_count > 0 and bookId:
        try:
            bl = call({"api_name": "/book/bookmarklist", "bookId": bookId})
            chapters = {str(c.get("chapterUid")): (c.get("title") or "").strip()
                        for c in bl.get("chapters", [])}
            for it in bl.get("updated", []):
                if it.get("type") == 2:
                    ideas += 1
                    continue
                t = (it.get("markText") or "").strip()
                if t:
                    marks.append(t)
                    mark_items.append({
                        "t": it.get("createTime", 0),
                        "text": t,
                        "chapter": chapters.get(str(it.get("chapterUid")), ""),
                    })
        except Exception as e:
            print("  bookmarklist 失败:", bookId, e)
    mark_items.sort(key=lambda x: -x["t"])
    # 本月划线数（按 createTime 归入当前周期）
    month_marks = sum(1 for x in mark_items
                      if datetime.datetime.fromtimestamp(x["t"], TZ).year == CUR_YEAR
                      and datetime.datetime.fromtimestamp(x["t"], TZ).month == CUR_MONTH)
    # 阅读日（划线实证日）与时段画像（按划线时刻小时分布估算）
    _mdays = sorted({datetime.datetime.fromtimestamp(x["t"], TZ).day for x in mark_items
                     if x.get("t")
                     and datetime.datetime.fromtimestamp(x["t"], TZ).year == CUR_YEAR
                     and datetime.datetime.fromtimestamp(x["t"], TZ).month == CUR_MONTH})
    mark_days = [f"{CUR_MONTH}/{d}" for d in _mdays]
    from collections import Counter
    _hc = Counter()
    for x in mark_items:
        t = x.get("t", 0)
        if t:
            _hc[datetime.datetime.fromtimestamp(t, TZ).hour] += 1
    hour_profile = "—"
    if _hc:
        top = max(_hc.values())
        hours = sorted(h for h, c in _hc.items() if c >= top * 0.4)
        segs = []
        start = prev = hours[0]
        for h in hours[1:]:
            if h - prev <= 2:
                prev = h
            else:
                segs.append((start, prev))
                start = prev = h
        segs.append((start, prev))
        best = max(segs, key=lambda s: sum(_hc.get(h, 0) for h in range(s[0], s[1] + 1)))
        hour_profile = f"{best[0]:02d}-{best[1] + 1:02d}点"

    # 按划线 createTime 归集到本月各天（周/天视图用）
    for x in mark_items:
        dt = datetime.datetime.fromtimestamp(x["t"], TZ)
        if dt.year == CUR_YEAR and dt.month == CUR_MONTH:
            day_book_map.setdefault(dt.day, []).append(short)
            book_mark_days.setdefault(short, []).append(dt.day)

    books.append({
        "short": short,
        "title": title_disp,
        "author": bk.get("author", ""),
        "sec": b.get("readTime", 0),
        "min": round(b.get("readTime", 0) / 60),
        "bookId": bookId,
        "cover": bk.get("cover", ""),
        "finished": finished,
        "progress": progress,
        "marks": marks,
        "mark_items": mark_items,
        "chapters": chapters,
        "month_marks": month_marks,
        "ideas": ideas,
        "mark_days": mark_days,
        "hour_profile": hour_profile,
    })

# 同一作品的不同版本（如"卡拉马佐夫兄弟" vs"卡拉马佐夫兄弟（套装上下册）"），
# 按归一化书名（去全角/半角括号内容、去冒号后文）分组，
# 只保留阅读时间最长的一本，隐藏被弃读的版本，避免页面重复
def _norm_title(t):
    t = re.sub(r"[（(][^（）()]*[）)]", "", t)
    t = re.sub(r"[：:].*$", "", t)
    return t.strip()

_best_map = {}  # norm -> 保留的 book 字典
for bk in books:
    n = _norm_title(bk["title"])
    if n not in _best_map or bk["sec"] > _best_map[n]["sec"]:
        _best_map[n] = bk
_keep = set(id(b) for b in _best_map.values())
_dropped = [bk for bk in books if id(bk) not in _keep]
books = [bk for bk in books if id(bk) in _keep]

# 被丢弃译本在 day_book_map / book_mark_days 中的引用，合并到保留译本名下
if _dropped:
    _short_map = {bk["short"]: bk for bk in books}
    for dk, shorts in list(day_book_map.items()):
        new_shorts = []
        for s in shorts:
            src = next((b for b in _dropped if b["short"] == s), None)
            if src is not None:
                n = _norm_title(src["title"])
                keep_bk = _best_map[n]
                new_shorts.append(keep_bk["short"])
            else:
                new_shorts.append(s)
        day_book_map[dk] = list(dict.fromkeys(new_shorts))
    for s in list(book_mark_days.keys()):
        src = next((b for b in _dropped if b["short"] == s), None)
        if src is not None:
            keep_short = _best_map[_norm_title(src["title"])]["short"]
            book_mark_days.setdefault(keep_short, []).extend(book_mark_days.pop(s))

books.sort(key=lambda x: -x["sec"])
for k in day_book_map:
    day_book_map[k] = list(dict.fromkeys(day_book_map[k]))

# ---- 输出 ----
def _compute_fallback_prefer(hc):
    """微信读书未返回偏好时段时，按划线时间统计整月活跃时段，返回 (prefer_time, prefer_time_word)"""
    if not hc:
        return {}, ""
    top = max(hc.values())
    hours = sorted(h for h, c in hc.items() if c >= top * 0.4)
    segs = []
    if hours:
        start = prev = hours[0]
        for h in hours[1:]:
            if h - prev <= 2:
                prev = h
            else:
                segs.append((start, prev))
                start = prev = h
        segs.append((start, prev))
    if not segs:
        return {}, ""
    best = max(segs, key=lambda s: sum(hc.get(h, 0) for h in range(s[0], s[1] + 1)))
    word = f"{best[0]:02d}-{best[1] + 1:02d}点"
    base = datetime.datetime.now(TZ).replace(minute=0, second=0, microsecond=0)
    pt = {}
    for h in range(best[0], best[1] + 1):
        ts = base.replace(hour=h).timestamp()
        pt[str(int(ts))] = hc.get(h, 0)
    return pt, word


# 兜底：微信读书未返回偏好时段时（时段较分散，接口判定不足），按划线时间自行统计整月活跃时段
_pt_api = m.get("preferTime") or {}
_pw_api = m.get("preferTimeWord") or ""
if not _pt_api:
    from collections import Counter as _Ctr
    _hc = _Ctr()
    for _bk in books:
        for _x in (_bk.get("mark_items") or []):
            _t = _x.get("t", 0)
            if _t:
                _hc[datetime.datetime.fromtimestamp(_t, TZ).hour] += 1
    _pt_api, _pw_api = _compute_fallback_prefer(_hc)


out = {
    "year": CUR_YEAR,
    "month": CUR_MONTH,
    "n_days": calendar.monthrange(CUR_YEAR, CUR_MONTH)[1],
    "day_sec": day_sec,
    "total_sec": total_sec,
    "read_days": read_days,
    "books": books,
    "prefer": prefer,
    "day_book_map": day_book_map,
    "book_mark_days": book_mark_days,
    "prefer_time": _pt_api or {},
    "prefer_time_word": _pw_api or "",
    "compare": m.get("compare"),
    "prefer_author": m.get("preferAuthor") or "",
    "prefer_publisher": m.get("preferPublisher") or "",
    "prefer_cp": m.get("preferCp") or "",
}
DASH_OUT = os.environ.get("WEREAD_DASH_OUT", f"{TMP}/dash_data.json")
with open(DASH_OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print("total_sec:", total_sec, "| read_days:", read_days, "| books:", len(books))
print("prefer:", prefer)
for bk in books:
    print(f"  {bk['short']} | 读完={bk['finished']} | {bk['progress']}% | 划线{len(bk['marks'])}条")
print("day_book_map:", day_book_map)
print("saved dash_data.json")
