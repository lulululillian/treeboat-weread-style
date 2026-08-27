# -*- coding: utf-8 -*-
"""
舟读・微信读书 Obsidian 阅读看板 · 一键自动更新脚本
从 GitHub 拉取最新版本的脚本文件，自动保留用户的 config.json 和 themes.json。

使用方式：
    python weread_tmp/update.py

更新完成后运行：
    python weread_tmp/refresh.py
"""
import os, sys, urllib.request, shutil, datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# GitHub 仓库信息（模板仓库地址，修改此处可指向自己的 fork）
REPO_OWNER = "lulululillian"
REPO_NAME = "treeboat-weread-style"
BRANCH = "master"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/weread_tmp"

# 需要从 GitHub 拉取覆盖的脚本文件
UPDATE_FILES = [
    "config.py",
    "refresh.py",
    "prep_dash.py",
    "gen_html.py",
    "gen_dv.py",
    "sync_notes.py",
    "archive_month.py",
    "gen_monthly_summary.py",
    "update.py",
]

# 用户专属文件，绝不覆盖（更新时跳过）
KEEP_FILES = ["config.json", "themes.json"]

TIMEOUT = 30  # 单个文件下载超时（秒）


def download_file(filename):
    """从 GitHub raw 下载单个文件，返回 bytes 或 None"""
    url = f"{RAW_BASE}/{filename}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "weread-readstats-updater/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            if resp.status != 200:
                return None
            return resp.read()
    except Exception as e:
        return None


def main():
    print("=" * 56)
    print("  微信读书阅读统计 · 一键自动更新")
    print("=" * 56)
    print(f"  仓库: {REPO_OWNER}/{REPO_NAME} ({BRANCH})")
    print(f"  本地: {_HERE}")
    print()

    # 检查是否已完成初始配置
    config_path = os.path.join(_HERE, "config.json")
    if not os.path.exists(config_path):
        print("⚠ 未找到 config.json，你可能还没完成初始配置。")
        print("  请先按 README.md 的「配置步骤」填写 config.json，")
        print("  配置完成后再运行本脚本更新。")
        return

    # 备份当前版本（更新失败可回滚）
    print("正在备份当前版本...")
    backup_dir = os.path.join(_HERE, f"_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(backup_dir, exist_ok=True)
    backed = 0
    for f in UPDATE_FILES:
        src = os.path.join(_HERE, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(backup_dir, f))
            backed += 1
    print(f"  已备份 {backed} 个文件到: {backup_dir}")
    print()

    # 下载并更新
    print("正在从 GitHub 拉取最新版本...")
    print()
    success, failed = [], []

    for filename in UPDATE_FILES:
        print(f"  更新 {filename:<24}", end=" ")
        content = download_file(filename)
        if content is None:
            print("✗ 下载失败")
            failed.append(filename)
            continue
        try:
            with open(os.path.join(_HERE, filename), "wb") as f:
                f.write(content)
            success.append(filename)
            print("✓ 已更新")
        except Exception as e:
            print(f"✗ 写入失败 ({e})")
            failed.append(filename)

    print()
    print("=" * 56)
    print(f"  更新完成: 成功 {len(success)} 个  失败 {len(failed)} 个")
    print("=" * 56)

    if failed:
        print()
        print("以下文件更新失败（可能是网络连接 GitHub 不稳定）：")
        for f in failed:
            print(f"  ✗ {f}")
        print()
        print("解决方式（任选其一）：")
        print("  1. 重新运行: python weread_tmp/update.py")
        print(f"  2. 手动下载: https://github.com/{REPO_OWNER}/{REPO_NAME}/tree/{BRANCH}/weread_tmp")
        print("     把失败的文件下载后覆盖到 weread_tmp/ 目录即可")
        print()
        print("已成功更新的文件不受影响，可以正常使用。")

    print()
    print("✓ 你的配置文件 config.json 和主题文件 themes.json 已自动保留，不会被覆盖。")
    print()
    print("下一步：运行以下命令刷新数据，应用新版本功能：")
    print("  python weread_tmp/refresh.py")
    print()


if __name__ == "__main__":
    main()
