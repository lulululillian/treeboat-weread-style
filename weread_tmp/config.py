# -*- coding: utf-8 -*-
"""
公共配置加载器 — 舟读・微信读书 Obsidian 阅读看板
所有脚本统一从这里读取 config.json，避免硬编码本地绝对路径。
API key 不在此文件出现：沿用环境变量 WEREAD_API_KEY + ~/.bashrc 兜底逻辑。
"""
import json
import os
import re

# 微信读书官方 Skill 网关接口（所有调用接口的脚本统一从这里取）
GATEWAY = "https://i.weread.qq.com/api/agent/gateway"
SKILL_VERSION = "1.0.4"
KEY_FILES = [os.path.expanduser("~/.bashrc"), os.path.expanduser("~/.profile")]


def get_key():
    """读取 WEREAD_API_KEY：环境变量 → ~/.bashrc → ~/.profile 依次兜底。"""
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

_CFG = None


def _here():
    return os.path.dirname(os.path.abspath(__file__))


def load():
    """读取脚本目录下的 config.json；缺失或字段为空时回退默认值。"""
    global _CFG
    if _CFG is not None:
        return _CFG
    defaults = {
        "vault_root": "",
        "stats_rel_dir": "微信读书/阅读统计",
        "shelf_rel_dir": "书影音/我的书架",
        "scripts_dir": "weread_tmp",
        "output_mode": "md",
    }
    cfg = dict(defaults)
    cfg_path = os.path.join(_here(), "config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                user = json.load(f)
            for k in cfg:
                v = user.get(k)
                if v not in (None, ""):
                    cfg[k] = str(v).strip()
        except Exception as e:
            print("[config] config.json 解析失败，使用默认值:", e)
    if not cfg.get("vault_root"):
        raise SystemExit(
            "config.json 缺少 vault_root（Obsidian 库根目录），请先在 weread_tmp/config.json 中填写"
        )
    _CFG = cfg
    return _CFG


def vault_root():
    """Obsidian 库根目录（绝对路径，末尾带 /）。支持相对路径（相对工作区根=脚本目录的父目录）。"""
    cfg = load()
    root = cfg["vault_root"]
    if not os.path.isabs(root):
        base = os.path.dirname(_here())
        root = os.path.normpath(os.path.join(base, root))
    return root.replace("\\", "/").rstrip("/") + "/"


def stats_dir():
    """阅读统计输出目录 = vault 根 + 相对目录"""
    return os.path.join(vault_root(), load()["stats_rel_dir"]).replace("\\", "/")


def data_dir():
    """历史数据目录（dash 归档 + 周快照）
    注意：目录名用 .data（点开头），Obsidian 文件浏览器默认隐藏点开头文件夹，
    避免 data 里的 json/周快照显示在用户库中；dataview/vault 读取不受影响。"""
    return os.path.join(stats_dir(), ".data").replace("\\", "/")


def shelf_dir():
    """书架笔记目录 = vault 根 + 相对目录"""
    return os.path.join(vault_root(), load()["shelf_rel_dir"]).replace("\\", "/")


def vault_name():
    """从 vault_root 推导 Obsidian 库名（用于 obsidian:// URI）"""
    return os.path.basename(vault_root().rstrip("/"))


def output_mode():
    """输出模式：md（默认，Obsidian DataviewJS）/ html（纯网页，无需 Obsidian）/ both（两者都生成）"""
    mode = str(load().get("output_mode", "md") or "md").strip().lower()
    if mode not in ("md", "html", "both"):
        print(f"[config] output_mode 取值 {mode!r} 不合法，回退为 md")
        return "md"
    return mode
