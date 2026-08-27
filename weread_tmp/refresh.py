# -*- coding: utf-8 -*-
"""
微信读书阅读统计 · 一键刷新
流程：拉最新数据 → 存 monthly.json → prep_dash → gen_dv → 更新 阅读统计.md
说明：
  - 优先读环境变量 WEREAD_API_KEY；非交互 shell 可能没 source ~/.bashrc，
    因此这里会自动从 ~/.bashrc 解析兜底，确保定时任务也能拿到 key。
  - 由 automation 或手动运行均可，cwd 需为工作区根目录。
  - 失败兜底：接口拉取或任一步骤失败时，保留/回滚旧数据，看板不被清空。
"""
import os, json, re, shutil, subprocess, sys, urllib.request, datetime
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import config

KEY_FILES = [os.path.expanduser("~/.bashrc"), os.path.expanduser("~/.profile")]
GATEWAY = "https://i.weread.qq.com/api/agent/gateway"
SKILL_VERSION = "1.0.4"
KEEP = ["readTimes", "readDays", "readLongest", "preferCategory", "preferCategoryWord",
        "readStat", "registTime", "dayAverageReadTime", "baseTime", "totalReadTime",
        "readDistributionWord", "preferBooks", "readRecordsWord",
        "preferTime", "preferTimeWord", "compare", "preferAuthor", "preferPublisher", "preferCp"]


def get_key():
    k = os.environ.get("WEREAD_API_KEY")
    if k:
        return k
    for f in KEY_FILES:
        if os.path.exists(f):
            try:
                txt = open(f, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            m = re.search(r'WEREAD_API_KEY\s*=\s*["\']([^"\']+)["\']', txt)
            if m:
                return m.group(1)
    return None


def fetch_monthly():
    key = get_key()
    if not key:
        sys.exit("WEREAD_API_KEY 缺失：请在 ~/.bashrc 配置，或 export 后再运行")
    body = json.dumps({"api_name": "/readdata/detail", "mode": "monthly",
                       "skill_version": SKILL_VERSION}).encode()
    req = urllib.request.Request(GATEWAY, data=body, method="POST")
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Content-Type", "application/json")
    data = json.loads(urllib.request.urlopen(req, timeout=30).read())
    if data.get("errcode"):
        sys.exit(f"接口报错 errcode={data.get('errcode')} {data.get('errmsg')}")
    return {k: data.get(k) for k in KEEP}


def save_week_snapshot(here):
    r"""归档本周快照到 vault data\week-snapshots\week-YYYY-MM-DD.json（周一起始日）
    供周视图计算「较上周日均」环比；每次刷新都更新本周快照。"""
    try:
        with open(os.path.join(here, "dash_data.json"), encoding="utf-8") as f:
            dash = json.load(f)
        day_sec = dash.get("day_sec") or {}
        today = datetime.date.today()
        start = today - datetime.timedelta(days=today.weekday())  # 本周一
        secs = {}
        for i in range(7):
            dd = start + datetime.timedelta(days=i)
            v = day_sec.get(str(dd.day), 0)
            if (dd.year, dd.month) != (dash.get("year"), dash.get("month")):
                v = 0  # 跨月部分 dash 无数据，按 0 处理（与 gen_html week_bounds 一致）
            secs[dd.strftime("%Y-%m-%d")] = int(v)
        total = sum(secs.values())
        snap = {
            "week_start": start.strftime("%Y-%m-%d"),
            "week_end": (start + datetime.timedelta(days=6)).strftime("%Y-%m-%d"),
            "day_sec": secs,
            "total_sec": total,
            "avg_sec": round(total / 7),
        }
        snap_dir = os.path.join(
            config.data_dir(),
            "week-snapshots")
        os.makedirs(snap_dir, exist_ok=True)
        target = os.path.join(snap_dir, "week-" + start.strftime("%Y-%m-%d") + ".json")
        with open(target, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=2)
        print("周快照:", target, "本周日均", snap["avg_sec"], "秒")
    except Exception as e:
        print("周快照归档失败(不影响主流程):", e)


# AIGC 标记特征（外部同步服务 fast-note-sync 注入的溯源 frontmatter）
_AIGC_KEYS = ("AIGC", "ContentProducer", "ProduceID", "ReservedCode")


def strip_aigc_frontmatter(path):
    """删除 md 头部由外部同步服务注入的 AIGC frontmatter 块，返回是否清理过。"""
    try:
        with open(path, encoding="utf-8") as f:
            txt = f.read()
    except OSError:
        return False
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?", txt, re.S)
    if not m:
        return False
    block = m.group(1)
    if not any(k.lower() in block.lower() for k in _AIGC_KEYS):
        return False
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(txt[m.end():])
    except OSError:
        return False
    return True


def clean_aigc_in_stats():
    """扫描 stats 目录下所有 .md（当前月 + 历史月快照），清除 AIGC frontmatter。

    这是「生成之后检查，有就删除」的兜底：即使外部同步服务在生成后
    重新注入了 AIGC 标记，下次刷新也会被自动清掉。
    """
    stats = config.stats_dir()
    if not os.path.isdir(stats):
        return 0
    n = 0
    for name in sorted(os.listdir(stats)):
        if not name.endswith(".md"):
            continue
        p = os.path.join(stats, name)
        if strip_aigc_frontmatter(p):
            print("aigc cleaned:", p)
            n += 1
    return n


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    # ---- 刷新失败兜底：先备份旧数据，任一步失败回滚，看板不被清空 ----
    backup = {}
    for name in ("monthly.json", "dash_data.json"):
        p = os.path.join(here, name)
        if os.path.exists(p):
            bak = p + ".bak"
            try:
                shutil.copyfile(p, bak)
                backup[name] = bak
            except OSError:
                pass
    try:
        data = fetch_monthly()
    except BaseException as e:
        print("拉取接口失败，保留旧数据不动:", e)
        return
    try:
        with open(os.path.join(here, "monthly.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("monthly.json 已更新:", len(data.get("readTimes", {})), "个阅读日")
        subprocess.run([sys.executable, os.path.join(here, "prep_dash.py")], cwd=root, check=True)
        # 归档当月 dash 到 vault data\YYYY-MM.json（历史月份查看 + 月度总结数据源）
        try:
            with open(os.path.join(here, "dash_data.json"), encoding="utf-8") as f:
                dash = json.load(f)
            y, mo = dash.get("year"), dash.get("month")
            if y and mo:
                data_dir = config.data_dir()
                os.makedirs(data_dir, exist_ok=True)
                target = os.path.join(data_dir, f"{y:04d}-{mo:02d}.json")
                shutil.copyfile(os.path.join(here, "dash_data.json"), target)
                print("归档:", target)
        except Exception as e:
            print("归档失败(不影响主流程):", e)
        save_week_snapshot(here)
        subprocess.run([sys.executable, os.path.join(here, "sync_notes.py")], cwd=root, check=True)
        mode = config.output_mode()
        if mode in ("md", "both"):
            subprocess.run([sys.executable, os.path.join(here, "gen_dv.py")], cwd=root, check=True)
        if mode in ("html", "both"):
            subprocess.run([sys.executable, os.path.join(here, "gen_html.py")], cwd=root, check=True)
        # 生成后兜底：清除外部同步服务注入的 AIGC frontmatter（当前月 + 历史月）
        n_cleaned = clean_aigc_in_stats()
        print("阅读统计已刷新，书架笔记已同步"
              + (f"，已清理 {n_cleaned} 个 AIGC 标记" if n_cleaned else ""))
    except BaseException as e:
        # 任一步失败：回滚旧数据，保留看板
        for name, bak in backup.items():
            if os.path.exists(bak):
                try:
                    shutil.copyfile(bak, os.path.join(here, name))
                except OSError:
                    pass
        print("刷新失败，已回滚旧数据，看板保持原样:", e)
        raise


if __name__ == "__main__":
    main()
