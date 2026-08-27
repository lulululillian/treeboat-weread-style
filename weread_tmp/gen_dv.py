# -*- coding: utf-8 -*-
r"""生成 Obsidian DataviewJS 版阅读统计（周/月/天 tab，vault 内渲染）
- 当前月：阅读统计.md，头部含历史月份入口按钮
- 历史月：扫描 data\*.json，逐个生成 阅读统计-YYYY-MM.md（月视图快照）
"""
import runpy, os, sys, datetime, urllib.parse, re, glob, json, subprocess
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import config

VAULT = config.vault_name()
VAULT_ROOT = config.vault_root()
OUT_DIR = config.stats_dir()
DATA_DIR = config.data_dir()

def vault_uri(note_abs):
    """绝对路径 → obsidian://open 的 vault 相对 file 参数"""
    p = os.path.normpath(note_abs).replace("\\", "/")
    root = VAULT_ROOT.replace("\\", "/")
    if p.startswith(root):
        p = p[len(root):]
    return "obsidian://open/?vault=" + urllib.parse.quote(VAULT) + "&file=" + urllib.parse.quote(p, safe="/")


# AIGC 标记特征（外部同步服务 fast-note-sync 注入的溯源 frontmatter）
_AIGC_KEYS = ("AIGC", "ContentProducer", "ProduceID", "ReservedCode")


def strip_aigc_frontmatter(path):
    """删除 md 头部由外部同步服务注入的 AIGC frontmatter 块。

    仅当文件开头是 ``--- ... ---`` frontmatter 且块内包含 AIGC 溯源标记时才删除，
    不触碰正常笔记（如书架笔记的 YAML）。返回是否清理过。
    """
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
    rest = txt[m.end():]
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(rest)
    except OSError:
        return False
    return True

# ---- 复用 gen_html.py 渲染组件（当前月） ----
ns = runpy.run_path(os.path.join(_HERE, "gen_html.py"))
P = ns["PALETTE"]  # 配色卡与 gen_html.py 共用
YEAR = ns.get("YEAR", datetime.datetime.now().year)
MONTH = ns.get("MONTH", datetime.datetime.now().month)

# ---- 全部配色主题（前端换肤数据） ----
with open(ns["_THEMES_PATH"], encoding="utf-8") as f:
    _themes_doc = json.load(f)
_THEMES = _themes_doc["themes"]
_CUR_KEY = _themes_doc.get("current") or list(_THEMES.keys())[0]
_hex2rgb = ns["hex2rgb"]
_lerp = ns["lerp"]
def _heat_for(pal):
    light = _hex2rgb(pal["line"]); dark = _hex2rgb(pal["main"])
    return [pal["bg"]] + [_lerp(light, dark, t) for t in (0.2, 0.45, 0.7, 1.0)]
_themes_js_items = []
for _k, _t in _THEMES.items():
    _p = _t["palette"]
    _themes_js_items.append(
        json.dumps(_k, ensure_ascii=False) + ': {"name": ' + json.dumps(_t.get("name", _k), ensure_ascii=False)
        + ', "palette": ' + json.dumps(_p, ensure_ascii=False)
        + ', "heat": ' + json.dumps(_heat_for(_p)) + '}'
    )
THEMES_JS = "{" + ", ".join(_themes_js_items) + "}"

# CSS 变量引用：md 内联 style 也走变量，换肤时全局跟随
V = {
    "bg": "var(--wr-bg)", "line": "var(--wr-line)", "faint": "var(--wr-faint)",
    "sub": "var(--wr-sub)", "main": "var(--wr-main)", "white": "var(--wr-white)",
}

month = ns["month_view"]
week = ns["week_view_html"]
day = ns["day_view_html"]

# 校验：模板字符串安全（不含反引号 / ${）
for s in (month, week, day):
    assert "`" not in s and "${" not in s, "unsafe char in html"

def btn(v, label, active=False):
    bg = V["white"] if active else "transparent"
    col = V["main"] if active else V["sub"]
    fw = "600" if active else "400"
    sh = "0 1px 4px rgba(0,0,0,.08)" if active else "none"
    return (f'<button data-view="{v}" style="border:none;background:{bg};padding:6px 20px;'
            f'border-radius:999px;cursor:pointer;font-size:13px;color:{col};font-family:inherit;'
            f'white-space:nowrap;font-weight:{fw};box-shadow:{sh};transition:all .15s ease">{label}</button>')

def theme_sel_html():
    opts = "".join(
        f'<option value="{k}">{_t.get("name", k)}</option>' for k, _t in _THEMES.items()
    )
    return ('<select id="wr-theme" style="background:' + V["white"] + ';border:1px solid ' + V["line"]
            + ';color:' + V["main"] + ';border-radius:999px;padding:5px 10px;font-size:12px;'
            'font-family:inherit;cursor:pointer;outline:none" title="切换配色">' + opts + '</select>')

def hist_links_html():
    r"""扫描 data\YYYY-MM.json（排除当前月），生成历史入口链接"""
    if not os.path.isdir(DATA_DIR):
        return ""
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
    links = []
    for fp in files:
        base = os.path.basename(fp)
        m = re.match(r"^(\d{4})-(\d{2})\.json$", base)
        if not m:
            continue
        y, mo = int(m.group(1)), int(m.group(2))
        if (y, mo) == (YEAR, MONTH):
            continue
        note = os.path.join(OUT_DIR, f"阅读统计-{y:04d}-{mo:02d}.md")
        uri = vault_uri(note)
        links.append(f'<a href="{uri}" style="text-decoration:none;background:{V["line"]};color:{V["main"]};'
                     f'padding:3px 12px;border-radius:999px;font-size:11px;white-space:nowrap">{y}-{mo:02d}</a>')
    if not links:
        return ""
    return ('<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:4px 0 18px;font-size:11px;color:'
            + V["sub"] + '">历史月份 ' + "".join(links) + '</div>')

header = ('<div style="display:flex;justify-content:space-between;align-items:center;'
          'margin-bottom:12px;flex-wrap:wrap;gap:12px">'
          '<div style="font-size:12px;color:' + V["sub"] + ';letter-spacing:2px">'
          '<b style="font-weight:600;color:' + V["main"] + '">微信读书</b> · ' + str(YEAR) + ' 年 ' + str(MONTH) + ' 月</div>'
          '<div style="display:flex;align-items:center;gap:8px">'
          + theme_sel_html() +
          '<div style="display:inline-flex;background:' + V["line"] + ';border-radius:999px;padding:3px">'
          + btn("week", "周") + btn("month", "月", True) + btn("day", "天") +
          '</div></div></div>'
          + hist_links_html())

assert "`" not in header and "${" not in header

SKIN_JS = """const THEMES = __THEMES__;
const DEFAULT_THEME = '__CUR__';
function applyTheme(key) {
  const t = THEMES[key];
  if (!t) return;
  const st = document.documentElement.style;
  const p = t.palette;
  st.setProperty('--wr-bg', p.bg);
  st.setProperty('--wr-line', p.line);
  st.setProperty('--wr-faint', p.faint);
  st.setProperty('--wr-sub', p.sub);
  st.setProperty('--wr-main', p.main);
  st.setProperty('--wr-white', p.white);
  const h = t.heat || [];
  for (let i = 0; i < h.length; i++) st.setProperty('--wr-heat-' + i, h[i]);
  try { localStorage.setItem('weread-wr-theme', key); } catch (e) {}
}
let _wrSaved = null;
try { _wrSaved = localStorage.getItem('weread-wr-theme'); } catch (e) {}
const initTheme = (_wrSaved && THEMES[_wrSaved]) ? _wrSaved : DEFAULT_THEME;
applyTheme(initTheme);
function bindThemeSel(root) {
  const sel = root.querySelector('#wr-theme');
  if (!sel) return;
  sel.value = initTheme;
  sel.addEventListener('change', function() { applyTheme(sel.value); });
}"""

JS = """const H = `%HEADER%`;
const M = `%MONTH%`;
const W = `%WEEK%`;
const D = `%DAY%`;
const root = dv.container.createEl('div');
root.innerHTML = H + M + W + D;
function act(v) {
  ['week','month','day'].forEach(function(x) {
    const sec = root.querySelector('#v-' + x);
    const b = root.querySelector('button[data-view="' + x + '"]');
    const on = (x === v);
    sec.style.display = on ? 'block' : 'none';
    b.style.background = on ? '__W__' : 'transparent';
    b.style.color = on ? '__MAIN__' : '__SUB__';
    b.style.fontWeight = on ? '600' : '400';
    b.style.boxShadow = on ? '0 1px 4px rgba(0,0,0,.08)' : 'none';
  });
}
root.querySelectorAll('button[data-view]').forEach(function(btn) {
  btn.addEventListener('click', function() { act(btn.getAttribute('data-view')); });
});
act('month');
bindThemeSel(root);
(function(){
  const g = root.querySelector('#wr-cover-gallery');
  if (!g) return;
  let paused = false;
  let visible = true;
  g.addEventListener('mouseenter', function(){ paused = true; });
  g.addEventListener('mouseleave', function(){ paused = false; });
  g.addEventListener('wheel', function(e){
    e.preventDefault();
    g.scrollLeft += e.deltaY;
  }, {passive:false});
  try {
    new IntersectionObserver(function(es){
      es.forEach(function(en){ visible = en.isIntersecting; });
    }).observe(g);
  } catch(e) {}
  const maxScroll = function(){ return g.scrollWidth - g.clientWidth; };
  let lastTs = 0;
  function tick(ts){
    if (!g.isConnected) return;
    if (!paused && visible) {
      const mx = maxScroll();
      if (mx > 0) {
        if (g.scrollLeft >= mx - 1) { g.scrollLeft = 0; }
        else { g.scrollLeft += 1; }
      }
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
})();"""

JS = SKIN_JS + "\n" + JS
js = (JS.replace("%HEADER%", header).replace("%MONTH%", month)
        .replace("%WEEK%", week).replace("%DAY%", day)
        .replace("__THEMES__", THEMES_JS).replace("__CUR__", _CUR_KEY)
        .replace("__W__", V["white"]).replace("__MAIN__", V["main"]).replace("__SUB__", V["sub"]))

now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
md = "```dataviewjs\n" + js + "\n```\n"

OUT_MD = os.path.join(OUT_DIR, "阅读统计.md")
OUT_HTML = os.path.join(OUT_DIR, "阅读统计.html")
MODE = config.output_mode()

with open(OUT_MD, "w", encoding="utf-8") as f:
    f.write(md)

# 生成后兜底检查：若外部同步服务在写入瞬间注入了 AIGC frontmatter，立即清除
if strip_aigc_frontmatter(OUT_MD):
    print("aigc cleaned:", OUT_MD)

# 网页模式（无需 Obsidian）：生成独立 HTML；仅 md 模式时删除残留
if MODE in ("html", "both"):
    os.environ.pop("WEREAD_DASH_DATA", None)  # 清除历史月循环残留，确保生成当前月
    subprocess.run([sys.executable, os.path.join(_HERE, "gen_html.py")],
                   cwd=os.path.dirname(_HERE), check=True)
elif os.path.exists(OUT_HTML):
    try:
        os.remove(OUT_HTML)
    except OSError:
        pass

print("written:", OUT_MD, f"({len(md)} chars)")
print("removed:", OUT_HTML, "exists:", os.path.exists(OUT_HTML))

# ---- 历史月份快照：逐个 data\YYYY-MM.json 生成 阅读统计-YYYY-MM.md ----
if os.path.isdir(DATA_DIR):
    hist_files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
    for fp in hist_files:
        base = os.path.basename(fp)
        m = re.match(r"^(\d{4})-(\d{2})\.json$", base)
        if not m:
            continue
        y, mo = int(m.group(1)), int(m.group(2))
        if (y, mo) == (YEAR, MONTH):
            continue
        os.environ["WEREAD_DASH_DATA"] = fp
        import runpy as _rp
        hns = _rp.run_path(os.path.join(_HERE, "gen_html.py"), run_name="gen_html_hist")
        P2 = hns["PALETTE"]
        hmonth = hns["month_view"]
        hy = hns.get("YEAR", y)
        hmo = hns.get("MONTH", mo)
        assert "`" not in hmonth and "${" not in hmonth
        back_uri = vault_uri(os.path.join(OUT_DIR, "阅读统计.md"))
        hheader = ('<div style="display:flex;justify-content:space-between;align-items:center;'
                   'margin-bottom:12px;flex-wrap:wrap;gap:12px">'
                   '<div style="font-size:12px;color:' + V["sub"] + ';letter-spacing:2px">'
                   '<b style="font-weight:600;color:' + V["main"] + '">微信读书</b> · '
                   + str(hy) + ' 年 ' + str(hmo) + ' 月 · 历史快照</div>'
                   '<div style="display:flex;align-items:center;gap:8px">'
                   + theme_sel_html() +
                   '<a href="' + back_uri + '" style="text-decoration:none;background:' + V["line"] + ';color:'
                   + V["main"] + ';padding:6px 16px;border-radius:999px;font-size:12px">返回当前月</a>'
                   '</div></div>')
        assert "`" not in hheader and "${" not in hheader
        hjs = (SKIN_JS + "\n"
               "const H = `%HEADER%`;\nconst M = `%MONTH%`;\n"
               "const root = dv.container.createEl('div');\n"
               "root.innerHTML = H + M;\n"
               "bindThemeSel(root);")
        hjs = (hjs.replace("%HEADER%", hheader).replace("%MONTH%", hmonth)
                   .replace("__THEMES__", THEMES_JS).replace("__CUR__", _CUR_KEY))
        hmd = "```dataviewjs\n" + hjs + "\n```\n"
        hout = os.path.join(OUT_DIR, f"阅读统计-{y:04d}-{mo:02d}.md")
        with open(hout, "w", encoding="utf-8") as f:
            f.write(hmd)
        if strip_aigc_frontmatter(hout):
            print("aigc cleaned:", hout)
        print("hist:", hout, f"({len(hmd)} chars)")
else:
    print("hist: data dir not found:", DATA_DIR)
