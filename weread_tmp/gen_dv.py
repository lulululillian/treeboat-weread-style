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
import month_report_tpl as _mrp

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
    r"""扫描 .data\YYYY-MM.json（排除当前月），生成历史入口链接"""
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
        note = os.path.join(OUT_DIR, f"{y}年{mo}月阅读统计.md")
        uri = vault_uri(note)
        links.append(f'<a href="{uri}" style="text-decoration:none;background:{V["line"]};color:{V["main"]};'
                     f'padding:3px 12px;border-radius:999px;font-size:11px;white-space:nowrap">{y}年{mo}月</a>')
    if not links:
        return ""
    return ('<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:4px 0 18px;font-size:11px;color:'
            + V["sub"] + '">历史月份 ' + "".join(links) + '</div>')


# ---- 生成月报按钮（点击写入同路径 阅读月报-YYYY-MM.md） ----
def _report_btn(y, mo, cur=False):
    return ('<button data-wr-report="' + str(y) + '-' + str(mo) + '" title="生成本月阅读月报（同目录）" '
            'style="border:1px solid ' + V["line"] + ';background:' + V["white"] + ';color:' + V["main"]
            + ';padding:6px 14px;border-radius:999px;cursor:pointer;font-size:12px;font-family:inherit;'
            'white-space:nowrap;transition:all .15s ease">📊 月报</button>')

def _report_click_js():
    """月报按钮点击逻辑：写入 阅读月报-YYYY-MM.md（模板内嵌，数据由模板运行时读取）
    注意：data_ym 传 '__YM__' 占位符，让模板里 dataPath 保留 __YM__，
    点击按钮时才替换成目标月份——否则会写死为生成页面时的当前月，历史月按钮读错数据。"""
    tpl = _mrp.build_report_js(YEAR, MONTH, THEMES_JS, _CUR_KEY, data_ym="__YM__")
    tpl_json = json.dumps(tpl, ensure_ascii=False)
    return _REPORT_CLICK_JS.replace('__REPORT_TPL_JSON__', tpl_json)

_REPORT_CLICK_JS = (
    "\n"
    "    // 月报生成（绑定页面 root，避免 document 全局监听被旧页面抢占）\n"
    "    root.addEventListener('click', async function(e) {\n"
    "        const btn = e.target.closest('button[data-wr-report]');\n"
    "        if (!btn) return;\n"
    "        const ym = btn.getAttribute('data-wr-report');\n"
    "        const parts = ym.split('-');\n"
    "        const y = parts[0], m = parts[1];\n"
    "        e.preventDefault();\n"
    "        try {\n"
    "          const tpl = __REPORT_TPL_JSON__;\n"
    "          const ym2 = String(y) + '-' + String(m).padStart(2, '0');\n"
    "          const content = tpl.replace(/__YM__/g, ym2)\n"
    "                             .replace(/__YEAR__/g, String(y))\n"
    "                             .replace(/__MONTH__/g, String(m));\n"
    "          const cur = dv.current().file.path || '';\n"
    "          const dir = cur.indexOf('/') >= 0 ? cur.substring(0, cur.lastIndexOf('/')) : '';\n"
    "          const fname = '阅读月报-' + ym2 + '.md';\n"
    "          const outPath = dir ? dir + '/' + fname : fname;\n"
    "          const BT = String.fromCharCode(96);\n"
    "          await app.vault.adapter.write(outPath, BT + BT + BT + 'dataviewjs\\n' + content + '\\n' + BT + BT + BT);\n"
    "          if (typeof app.workspace !== 'undefined') {\n"
    "            app.workspace.openLinkText(fname, '');\n"
    "          }\n"
    "        } catch (err) {\n"
    "          console.error('wr report gen failed', err);\n"
    "        }\n"
    "      });\n"
)

overview_uri = vault_uri(os.path.join(OUT_DIR, "阅读统计.md"))
header = ('<div style="display:flex;justify-content:space-between;align-items:center;'
          'margin-bottom:12px;flex-wrap:wrap;gap:12px">'
          '<div style="font-size:12px;color:' + V["sub"] + ';letter-spacing:2px">'
          '<b style="font-weight:600;color:' + V["main"] + '">微信读书</b> · ' + str(YEAR) + ' 年 ' + str(MONTH) + ' 月 · 阅读统计</div>'
          '<div style="display:flex;align-items:center;gap:8px">'
          '<a href="' + overview_uri + '" style="text-decoration:none;background:' + V["line"] + ';color:' + V["main"] + ';padding:6px 16px;border-radius:999px;font-size:12px">总览</a>'
          + _report_btn(YEAR, MONTH, True)
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
// 环形时钟波浪动效：注入 keyframes + JS事件绑定，以悬停段为中心向两侧扩散
const _wrRingStyle = document.createElement('style');
_wrRingStyle.textContent = '@keyframes wrRingWave{0%,100%{stroke-width:var(--wr-base-w,12)}50%{stroke-width:calc(var(--wr-base-w,12) + 5)}}.wr-ring-seg:hover{stroke-opacity:1!important;filter:brightness(1.2)!important}';
root.appendChild(_wrRingStyle);
root.querySelectorAll('.wr-ring-svg').forEach(function(svg){
  var segs=svg.querySelectorAll('.wr-ring-seg');
  segs.forEach(function(seg){
    seg.addEventListener('mouseenter',function(){
      var h=parseInt(seg.getAttribute('data-hour'));
      segs.forEach(function(s){
        var i=parseInt(s.getAttribute('data-hour'));
        var dist=Math.min(Math.abs(i-h),24-Math.abs(i-h));
        var delay=dist*0.05+(dist%2)*0.015;
        s.style.strokeDashoffset='0';
        s.style.animation='wrRingWave 1.5s ease-in-out infinite';
        s.style.animationDelay=delay+'s';
      });
    });
    seg.addEventListener('mouseleave',function(){
      segs.forEach(function(s){s.style.animation='';s.style.animationDelay='';s.style.strokeDashoffset='0';});
    });
  });
});
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
    if (on) {
      var ring = sec.querySelector('.wr-ring-svg');
      if (ring) {
        ring.querySelectorAll('.wr-ring-seg').forEach(function(p, i) {
          var da = p.getAttribute('stroke-dasharray');
          p.style.strokeDashoffset = da;
          p.style.animation = 'none';
          void p.offsetWidth;
          p.style.animation = 'wereadRingFill 0.4s ease-out ' + (i * 15) + 'ms forwards';
        });
      }
    }
  });
}
root.querySelectorAll('button[data-view]').forEach(function(btn) {
  btn.addEventListener('click', function() { act(btn.getAttribute('data-view')); });
});
act('month');
_report_click_js()
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
  // 封面点击跳转：事件委托绑定到 document，防止 DataviewJS 重渲染/导航回来后事件丢失
  if (!window.__weread_cover_click_bound) {
    window.__weread_cover_click_bound = true;
    document.addEventListener('click', function(e){
      const a = e.target.closest('#wr-cover-gallery a[data-note]');
      if (!a) return;
      e.preventDefault();
      const note = a.getAttribute('data-note');
      if (note && typeof app !== 'undefined' && app.workspace) {
        app.workspace.openLinkText(note, '', false);
      }
    });
  }
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
        .replace("__W__", V["white"]).replace("__MAIN__", V["main"]).replace("__SUB__", V["sub"])
        .replace("_report_click_js()", _report_click_js()))

now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
md = "```dataviewjs\n" + js + "\n```\n"

OUT_MD = os.path.join(OUT_DIR, f"{YEAR}年{MONTH}月阅读统计.md")
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

# ---- 总视图：阅读统计.md（月份筛选 + 各月概览），供书架笔记回链 ----
def _month_overview_data():
    """收集当前月 + 全部历史归档月的概览数据（供总视图渲染）"""
    months = []
    # 当前月（gen_html.py 已加载并计算，命名空间 ns 内可直接取）
    _cur_books = ns.get("books", [])
    _cur_total = ns.get("total_sec", 0)
    _cur_days = ns.get("read_days", 0)
    cur = {
        "y": YEAR, "m": MONTH, "file": f"{YEAR}年{MONTH}月阅读统计.md", "cur": True,
        "total": _cur_total, "days": _cur_days,
        "books": len(_cur_books), "marks": sum(len(b.get("marks") or []) for b in _cur_books),
    }
    months.append(cur)
    # 历史月（data/*.json）
    if os.path.isdir(DATA_DIR):
        for fp in sorted(glob.glob(os.path.join(DATA_DIR, "*.json"))):
            base = os.path.basename(fp)
            mm = re.match(r"^(\d{4})-(\d{2})\.json$", base)
            if not mm:
                continue
            y, mo = int(mm.group(1)), int(mm.group(2))
            if (y, mo) == (YEAR, MONTH):
                continue
            try:
                with open(fp, encoding="utf-8") as _f:
                    dd = json.load(_f)
            except Exception:
                continue
            months.append({
                "y": y, "m": mo, "file": f"{y}年{mo}月阅读统计.md", "cur": False,
                "total": dd.get("total_sec", 0), "days": dd.get("read_days", 0),
                "books": len(dd.get("books", [])), "marks": sum(len(b.get("marks") or []) for b in dd.get("books", [])),
            })
    months.sort(key=lambda x: (-x["y"], -x["m"]))
    return months

def _fmt_overview(sec):
    m = round(sec / 60)
    if m >= 60:
        h, mm = divmod(m, 60)
        return f"{h}小时{mm:02d}分" if mm else f"{h}小时"
    return f"{m}分钟"

_overview_months = _month_overview_data()
_ov_rows = []
for _om in _overview_months:
    _uri = vault_uri(os.path.join(OUT_DIR, _om["file"]))
    _lbl = f'{_om["y"]}年{_om["m"]}月' + (" · 本月" if _om["cur"] else "")
    _ov_rows.append({
        "label": _lbl, "uri": _uri, "file": _om["file"],
        "total": _fmt_overview(_om["total"]), "days": _om["days"],
        "books": _om["books"], "marks": _om["marks"], "cur": _om["cur"],
    })
_OV_JS = json.dumps(_ov_rows, ensure_ascii=False)

_ov_js = (SKIN_JS + "\n"
          "const OV = __OV__;\n"
          "const root = dv.container.createEl('div');\n"
          "root.innerHTML = `<div style='font-size:18px;font-weight:600;color:var(--wr-main);margin:4px 0 2px'>微信读书 · 阅读统计总览</div>`;\n"
          "root.innerHTML += `<div style='font-size:12px;color:var(--wr-sub);margin-bottom:14px'>按月份筛选查看历史阅读数据，点击月份卡片进入对应月统计</div>`;\n"
          "if (!OV.length) {\n"
          "  root.innerHTML += `<div style='color:var(--wr-faint);font-size:13px;padding:12px 0'>暂无数据，先运行刷新生成看板。</div>`;\n"
          "} else {\n"
          "  const sel = document.createElement('select');\n"
          "  sel.style.cssText = 'background:var(--wr-white);border:1px solid var(--wr-line);color:var(--wr-main);border-radius:999px;padding:6px 14px;font-size:13px;font-family:inherit;cursor:pointer;outline:none;margin-bottom:14px';\n"
          "  OV.forEach((o,i)=>{ const op=document.createElement('option'); op.value=String(i); op.textContent=o.label+(o.cur?'(当前)':''); sel.appendChild(op); });\n"
          "  sel.addEventListener('change',()=>{ const o=OV[parseInt(sel.value)]; if(o&&o.file) app.workspace.openLinkText(o.file,'',false); });\n"
          "  root.appendChild(sel);\n"
          "  const grid = document.createElement('div');\n"
          "  grid.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px';\n"
          "  OV.forEach((o)=>{ const c=document.createElement('a'); c.href=o.uri; c.style.cssText='text-decoration:none;background:var(--wr-white);border:0.5px solid var(--wr-line);border-radius:12px;padding:14px 16px;display:block;transition:box-shadow .15s ease;cursor:pointer';\n"
          "    c.onmouseover=()=>{c.style.boxShadow='0 4px 14px rgba(0,0,0,.08)'}; c.onmouseout=()=>{c.style.boxShadow='none'};\n"
          "    c.addEventListener('click',(ev)=>{ ev.preventDefault(); app.workspace.openLinkText(o.file,'',false); });\n"
          "    c.innerHTML = `<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:10px'><span style='font-size:14px;font-weight:600;color:var(--wr-main)'>${o.label}</span>${o.cur?`<span style='background:var(--wr-main);color:var(--wr-white);padding:2px 8px;border-radius:10px;font-size:10px'>本月</span>`:''}</div>`\n"
          "      + `<div style='font-size:22px;font-weight:600;color:var(--wr-main)'>${o.total}</div>`\n"
          "      + `<div style='font-size:11px;color:var(--wr-sub);margin-top:8px'>阅读 ${o.days} 天 · 书目 ${o.books} 本 · 划线 ${o.marks} 条</div>`;\n"
          "    grid.appendChild(c);\n"
          "  });\n"
          "  root.appendChild(grid);\n"
          "}\n"
          "bindThemeSel(root);")
_ov_js = (_ov_js.replace("__OV__", _OV_JS)
                .replace("__THEMES__", THEMES_JS).replace("__CUR__", _CUR_KEY))
assert "`" not in _ov_js.split("const OV =")[0]  # SKIN_JS 与模板部分不含反引号
_ov_md = "```dataviewjs\n" + _ov_js + "\n```\n"
_ov_out = os.path.join(OUT_DIR, "阅读统计.md")
with open(_ov_out, "w", encoding="utf-8") as f:
    f.write(_ov_md)
if strip_aigc_frontmatter(_ov_out):
    print("aigc cleaned:", _ov_out)
print("overview:", _ov_out, f"({len(_ov_md)} chars)")


# ---- 历史月份快照：逐个 .data\YYYY-MM.json 生成 阅读统计-YYYY-MM.md ----
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
        back_uri = vault_uri(os.path.join(OUT_DIR, "阅读统计.md"))  # 总览入口
        hheader = ('<div style="display:flex;justify-content:space-between;align-items:center;'
                   'margin-bottom:12px;flex-wrap:wrap;gap:12px">'
                   '<div style="font-size:12px;color:' + V["sub"] + ';letter-spacing:2px">'
                   '<b style="font-weight:600;color:' + V["main"] + '">微信读书</b> · '
                   + str(hy) + ' 年 ' + str(hmo) + ' 月 · 阅读统计</div>'
                   '<div style="display:flex;align-items:center;gap:8px">'
                   + _report_btn(hy, hmo, False)
                   + theme_sel_html() +
                   '<a href="' + back_uri + '" style="text-decoration:none;background:' + V["line"] + ';color:'
                   + V["main"] + ';padding:6px 16px;border-radius:999px;font-size:12px">返回总览</a>'
                   '</div></div>')
        assert "`" not in hheader and "${" not in hheader
        hjs = (SKIN_JS + "\n"
               "const H = `%HEADER%`;\nconst M = `%MONTH%`;\n"
               "const root = dv.container.createEl('div');\n"
               "root.innerHTML = H + M;\n"
               + _report_click_js() + "\n"
               "bindThemeSel(root);")
        hjs = (hjs.replace("%HEADER%", hheader).replace("%MONTH%", hmonth)
                   .replace("__THEMES__", THEMES_JS).replace("__CUR__", _CUR_KEY))
        hmd = "```dataviewjs\n" + hjs + "\n```\n"
        hout = os.path.join(OUT_DIR, f"{y}年{mo}月阅读统计.md")
        with open(hout, "w", encoding="utf-8") as f:
            f.write(hmd)
        if strip_aigc_frontmatter(hout):
            print("aigc cleaned:", hout)
        print("hist:", hout, f"({len(hmd)} chars)")
else:
    print("hist: data dir not found:", DATA_DIR)
