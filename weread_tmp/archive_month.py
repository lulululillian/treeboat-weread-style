# -*- coding: utf-8 -*-
"""
archive_month.py — 归档指定月份的微信读书阅读统计
用法: python archive_month.py YYYY-MM   (如 python archive_month.py 2026-07)
流程: 按目标月 15 日 baseTime 调 /readdata/detail monthly → prep_dash
      → 输出 dash 到 vault 内 data\YYYY-MM.json（供历史月份查看与月度总结复用）
说明: prep_dash.py 会额外请求 /user/notebooks 与 /book/bookmarklist（实时状态/划线），
      归档内容与每月刷新生成的口径一致。
"""
import os, sys, json, shutil, datetime, urllib.request
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import config
from datetime import timezone, timedelta

TMP = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TMP)
GATEWAY = "https://i.weread.qq.com/api/agent/gateway"
SKILL_VERSION = "1.0.4"
TZ = timezone(timedelta(hours=8))
VAULT_DATA = config.data_dir()
KEY_FILES = [os.path.expanduser("~/.bashrc"), os.path.expanduser("~/.profile")]
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
            m = __import__("re").search(r'WEREAD_API_KEY\s*=\s*["\']([^"\']+)["\']', txt)
            if m:
                return m.group(1)
    return None


def fetch_monthly_hist(y, m):
    key = get_key()
    if not key:
        sys.exit("WEREAD_API_KEY 缺失：请在 ~/.bashrc 配置，或 export 后再运行")
    ts = int(datetime.datetime(y, m, 15, tzinfo=TZ).timestamp())
    body = json.dumps({"api_name": "/readdata/detail", "mode": "monthly",
                       "baseTime": ts, "skill_version": SKILL_VERSION}).encode()
    req = urllib.request.Request(GATEWAY, data=body, method="POST")
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Content-Type", "application/json")
    data = json.loads(urllib.request.urlopen(req, timeout=30).read())
    if data.get("errcode"):
        sys.exit(f"接口报错 errcode={data.get('errcode')} {data.get('errmsg')}")
    return {k: data.get(k) for k in KEEP}


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python archive_month.py YYYY-MM")
    y, m = map(int, sys.argv[1].split("-"))
    data = fetch_monthly_hist(y, m)
    bt = data.get("baseTime")
    if bt:
        d = datetime.datetime.fromtimestamp(int(bt), TZ)
        if (d.year, d.month) != (y, m):
            sys.exit(f"接口返回月份 {d.year}-{d.month:02d}，与目标 {y:04d}-{m:02d} 不符")
    mfile = os.path.join(TMP, f"monthly_{y}{m:02d}.json")
    with open(mfile, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    dfile = os.path.join(TMP, f"dash_{y}{m:02d}.json")
    env = dict(os.environ)
    env["WEREAD_MONTHLY_SRC"] = mfile
    env["WEREAD_DASH_OUT"] = dfile
    import subprocess
    subprocess.run([sys.executable, os.path.join(TMP, "prep_dash.py")],
                   cwd=ROOT, env=env, check=True)
    os.makedirs(VAULT_DATA, exist_ok=True)
    target = os.path.join(VAULT_DATA, f"{y:04d}-{m:02d}.json")
    shutil.copyfile(dfile, target)
    print("archived:", target, f"| 阅读日 {data.get('readDays')} | 总时长 {data.get('totalReadTime')}s")


if __name__ == "__main__":
    main()
