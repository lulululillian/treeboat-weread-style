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
// 圆环加载填充：只对激活视图圆环触发，延迟错峰，避免多圆环同时动画导致停滞
function runRingFill(ring) {
  setTimeout(function() {
    ring.querySelectorAll('.wr-ring-seg').forEach(function(p, i) {
      var da = p.getAttribute('stroke-dasharray');
      p.style.strokeDashoffset = da;
      p.style.animation = 'none';
      void p.offsetWidth;
      p.style.animation = 'wereadRingFill 0.25s ease-out ' + (i * 10) + 'ms forwards';
    });
  }, 200);
}
requestAnimationFrame(function() {
  requestAnimationFrame(function() {
    root.querySelectorAll('.view.active .wr-ring-svg').forEach(runRingFill);
  });
});
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

# ---- 月视图交互动效（当前月/历史月共用）：环形时钟波浪 + 封面画廊自动滚动 ----
_INTERACT_JS = """// 圆环加载填充：只对激活视图圆环触发，延迟错峰，避免多圆环同时动画导致停滞
function runRingFill(ring) {
  setTimeout(function() {
    ring.querySelectorAll('.wr-ring-seg').forEach(function(p, i) {
      var da = p.getAttribute('stroke-dasharray');
      p.style.strokeDashoffset = da;
      p.style.animation = 'none';
      void p.offsetWidth;
      p.style.animation = 'wereadRingFill 0.25s ease-out ' + (i * 10) + 'ms forwards';
    });
  }, 200);
}
requestAnimationFrame(function() {
  requestAnimationFrame(function() {
    root.querySelectorAll('.view.active .wr-ring-svg').forEach(runRingFill);
  });
});
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

# ---- 月度画廊模式：纯展示弹窗（当前月/历史月共用） ----
# 按钮 #wr-gallery-btn、遮罩 #wr-gallery-mask、模式切换 #wr-gallery-modes 由 gen_html.py 生成
# 数据从隐藏 div #wr-gallery-data 读取（JSON）。三种展示模式：
#   flat  = 平铺封面墙（基础模式）；shelf = 书架立放（封面朝外，站架板上）；
#   spine = 书脊朝外（书侧放，竖排书名写在书脊上，颜色取封面主色，跨域失败回退色板）
_GALLERY_JS = """
// ---- 月度画廊模式（三模式：平铺 / 书架 / 书脊） ----
(function(){
  const btn = root.querySelector('#wr-gallery-btn');
  const mask = root.querySelector('#wr-gallery-mask');
  if (!btn || !mask) return;
  const grid = mask.querySelector('#wr-gallery-grid');
  const dataEl = mask.querySelector('#wr-gallery-data');
  const modeBtns = Array.prototype.slice.call(mask.querySelectorAll('.wr-gmode'));
  let mode = 'flat', items = [], animSeq = 0, spineLayout = 'h', achvStyle = 'classic';
  // 出票机/打印机示意图（AI 生成，公网 URL；离线可替换为本地图）
  const MACHINES = {
    classic: 'https://aka.doubaocdn.com/s/HWLKWsDx2j',
    pink: 'https://aka.doubaocdn.com/s/6seBDrJT1d',
    vintage: 'https://aka.doubaocdn.com/s/pUKrzQO9St',
    stamp: 'https://aka.doubaocdn.com/s/RagG2hqble'
  };
  const nDays = parseInt(dataEl.getAttribute('data-days') || '31', 10);
  const galTitle = dataEl.getAttribute('data-title') || '';
  const galYear = parseInt(dataEl.getAttribute('data-year') || '0', 10);
  const galMonth = parseInt(dataEl.getAttribute('data-month') || '0', 10);
  const dMask = root.querySelector('#wr-book-detail-mask');
  const dPanel = dMask ? dMask.querySelector('#wr-book-detail-panel') : null;

  // 书脊配色：封面取主色，CORS/加载失败回退固定色板
  var PALETTE = ['#5B4A52','#6E5D8C','#8C6D4A','#4A6E68','#7A4E3E','#55637E',
                 '#6E5A4A','#3E5C6E','#8A5A5A','#5A6E4A','#4E4E66','#7C6A3E'];
  function pickColor(it, cb){
    var img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = function(){
      try {
        var cv = document.createElement('canvas'); cv.width = 32; cv.height = 42;
        var cx = cv.getContext('2d'); cx.drawImage(img, 0, 0, 32, 42);
        var d = cx.getImageData(0, 0, 32, 42).data;
        var r=0,g=0,b=0,n=0;
        for (var i=0;i<d.length;i+=4){ if (d[i+3]>120){ r+=d[i]; g+=d[i+1]; b+=d[i+2]; n++; } }
        if (n>0) cb({r:Math.round(r/n),g:Math.round(g/n),b:Math.round(b/n)}); else cb(null);
      } catch(e){ cb(null); }
    };
    img.onerror = function(){ cb(null); };
    img.src = it.c;
  }
  function txtColor(r,g,b){
    var l = (0.299*r + 0.587*g + 0.114*b) / 255;
    return l > 0.62 ? 'rgba(25,30,45,.85)' : 'rgba(255,255,255,.92)';
  }
  function enter(cell){
    var n = animSeq++;
    cell.style.opacity = '0';
    cell.style.transform = 'translateY(14px) scale(.98)';
    cell.style.transition = 'opacity .5s ease,transform .5s ease';
    setTimeout(function(){ cell.style.opacity='1'; cell.style.transform='translateY(0) scale(1)'; }, 40 + n*55);
  }
  function fmtSec(s){
    var m = Math.round((s||0)/60);
    if (m >= 60){ var h = Math.floor(m/60), mm = m%60; return mm ? h+'小时'+String(mm).padStart(2,'0')+'分' : h+'小时'; }
    return m+'分钟';
  }
  function escHtml(s){
    return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
  // 点击书/封面 → 弹出单书详情（右上角"打开笔记"跳书页）
  function showBookDetailByTitle(t){
    if (!dMask || !dPanel) return;
    if (!items.length){ try { items = JSON.parse(dataEl.textContent); } catch(e){} }
    var it = null;
    for (var i=0;i<items.length;i++){ if (items[i].t === t){ it = items[i]; break; } }
    if (!it) return;
    var first = (galYear>0 && galMonth>0) ? new Date(galYear, galMonth-1, 1).getDay() : 0;
    var wd = ['日','一','二','三','四','五','六'];
    var cells = '';
    for (var k=0;k<wd.length;k++){ cells += '<div style="font-size:10px;color:var(--wr-sub);text-align:center;padding:2px 0">'+wd[k]+'</div>'; }
    for (var k2=0;k2<first;k2++){ cells += '<div></div>'; }
    var now = new Date();
    var tIdx = (now.getFullYear()===galYear && now.getMonth()+1===galMonth) ? now.getDate() : 0;
    var readSet = {};
    (it.d||[]).forEach(function(d){ readSet[d]=1; });
    for (var d=1; d<=nDays; d++){
      var on = readSet[d] ? 1 : 0;
      var isT = d===tIdx;
      cells += '<div style="font-size:10px;color:'+(on?'var(--wr-white)':'var(--wr-main)')+';background:'+(on?'var(--wr-main)':'var(--wr-bg)')+';'
        + 'border-radius:5px;text-align:center;padding:3px 0;'+(isT?'box-shadow:inset 0 0 0 1.5px var(--wr-main);':'')+'">'+d+'</div>';
    }
    dPanel.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px">'
      + '<div style="font-size:16px;font-weight:600;color:var(--wr-main);padding-right:8px">'+escHtml(it.t)+'</div>'
      + '<div style="display:flex;align-items:center;gap:8px;flex-shrink:0">'
      + '<a href="'+escHtml(it.l)+'" data-note="'+escHtml(it.t)+'" style="text-decoration:none;background:var(--wr-main);color:var(--wr-white);padding:5px 12px;border-radius:999px;font-size:11px;cursor:pointer" title="打开笔记">打开笔记</a>'
      + '<button id="wr-book-detail-close" style="border:none;background:var(--wr-bg);color:var(--wr-main);width:28px;height:28px;border-radius:50%;font-size:14px;cursor:pointer;line-height:1">×</button></div></div>'
      + '<div style="display:flex;gap:14px;align-items:flex-start">'
      + '<img src="'+escHtml(it.c)+'" alt="'+escHtml(it.t)+'" style="width:104px;height:140px;object-fit:cover;border-radius:10px;box-shadow:0 8px 18px rgba(0,0,0,.18);flex-shrink:0;background:var(--wr-line)"/>'
      + '<div style="flex:1;min-width:0">'
      + '<div style="font-size:12px;color:var(--wr-sub)">'+escHtml(it.a||'')+'</div>'
      + (it.p ? '<div style="font-size:11px;color:var(--wr-sub);margin-top:2px">'+escHtml(it.p)+'</div>' : '')
      + '<div style="margin-top:8px"><span style="font-size:10px;font-weight:600;color:'+(it.f?'var(--wr-main)':'var(--wr-sub)')+';border:1px solid var(--wr-line);padding:2px 8px;border-radius:999px">'+(it.f?'已读完':'在读')+'</span></div>'
      + '<div style="display:flex;gap:14px;margin-top:12px;padding-top:10px;border-top:1px dashed var(--wr-line)">'
      + '<div style="text-align:center"><div style="font-size:13px;font-weight:600;color:var(--wr-main)">'+fmtSec(it.s)+'</div><div style="font-size:10px;color:var(--wr-sub);margin-top:2px">本月时长</div></div>'
      + '<div style="text-align:center"><div style="font-size:13px;font-weight:600;color:var(--wr-main)">'+(it.m||0)+'</div><div style="font-size:10px;color:var(--wr-sub);margin-top:2px">本月划线</div></div>'
      + '<div style="text-align:center"><div style="font-size:13px;font-weight:600;color:var(--wr-main)">'+(it.i||0)+'</div><div style="font-size:10px;color:var(--wr-sub);margin-top:2px">想法</div></div>'
      + '</div></div></div>'
      + '<div style="margin-top:14px"><div style="font-size:11px;color:var(--wr-sub);margin-bottom:6px">'+escHtml(galTitle)+' · 打卡日历（本月读过 '+(it.d||[]).length+' 天）</div>'
      + '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:3px">'+cells+'</div></div>';
    dPanel.querySelector('#wr-book-detail-close').addEventListener('click', closeDetail);
    dMask.style.visibility='visible'; dMask.style.opacity='1';
    dPanel.style.transform='translateY(0) scale(1)';
  }
  function closeDetail(){
    if (!dMask || !dPanel) return;
    dMask.style.opacity='0'; dMask.style.visibility='hidden';
    dPanel.style.transform='translateY(30px) scale(.96)';
  }

  // 1) 平铺封面墙
  function renderFlat(){
    grid.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:24px 20px;margin-top:18px';
    items.forEach(function(it, i){
      const cell = document.createElement('div');
      const img = document.createElement('img');
      img.src = it.c; img.alt = it.t; img.loading = 'lazy';
      img.style.cssText = 'width:100%;aspect-ratio:3/4;object-fit:cover;border-radius:14px;'
        + 'box-shadow:0 8px 20px rgba(0,0,0,.16);background:var(--wr-line);display:block;'
        + 'transition:transform .35s ease,box-shadow .35s ease;cursor:default';
      const t = document.createElement('div');
      t.textContent = it.t;
      t.style.cssText = 'font-size:12px;color:var(--wr-main);margin-top:8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap';
      const a = document.createElement('div');
      a.textContent = it.a;
      a.style.cssText = 'font-size:11px;color:var(--wr-sub);margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap';
      cell.appendChild(img); cell.appendChild(t); cell.appendChild(a);
      cell.addEventListener('mouseenter', function(){
        img.style.transform='translateY(-5px) scale(1.04)'; img.style.boxShadow='0 16px 32px rgba(0,0,0,.26)';
      });
      cell.addEventListener('mouseleave', function(){ img.style.transform=''; img.style.boxShadow=''; });
      cell.addEventListener('click', function(){ showBookDetailByTitle(it.t); });
      grid.appendChild(cell);
      enter(cell);
    });
  }

  // 书架容器（shelf / spine 共用）：分层架子 + 架板
  // per 按面板实际宽度自适应：横排排满，满了自动换下一层
  function panelInnerW(){
    const panel = mask.querySelector('#wr-gallery-panel');
    return (panel.clientWidth || 880) - 36;  // 面板内边距 30×2 折减
  }
  function shelfPer(){ return Math.max(3, Math.floor(panelInnerW() / 70)); }   // 书宽56 + gap12 + 余量
  function spinePer(){ return Math.max(6, Math.floor(panelInnerW() / 24)); }   // 书脊平均宽约21 + gap3
  function shelfLayers(per, rowBuilder, gap, pad){
    grid.style.cssText = 'display:flex;flex-direction:column;gap:16px;margin-top:18px';
    for (var i=0;i<items.length;i+=per){
      const layer = items.slice(i, i+per);
      const shelf = document.createElement('div');
      shelf.style.cssText = 'background:linear-gradient(180deg,rgba(0,0,0,.04),rgba(0,0,0,.16));'
        + 'border-bottom:7px solid var(--wr-line);border-radius:10px;'
        + 'box-shadow:0 6px 14px rgba(0,0,0,.14);padding:' + (pad || '20px 18px 0') + ';position:relative';
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:flex-end;justify-content:center;gap:' + (gap || 12) + 'px';
      layer.forEach(function(it, j){ rowBuilder(it, i+j, row); });
      shelf.appendChild(row);
      grid.appendChild(shelf);
    }
  }

  // 2) 书架模式：封面朝外立放
  function renderShelf(){
    shelfLayers(shelfPer(), function(it, idx, row){
      const cell = document.createElement('div');
      cell.title = it.t;
      const img = document.createElement('img');
      img.src = it.c; img.alt = it.t; img.loading = 'lazy';
      img.style.cssText = 'width:56px;height:84px;object-fit:cover;border-radius:3px 7px 7px 3px;display:block;'
        + 'box-shadow:0 7px 16px rgba(0,0,0,.24), inset 0 0 0 1px rgba(255,255,255,.08);'
        + 'transition:transform .35s ease,box-shadow .35s ease;cursor:default';
      cell.appendChild(img);
      cell.addEventListener('mouseenter', function(){
        img.style.transform='translateY(-7px) scale(1.03)'; img.style.boxShadow='0 14px 26px rgba(0,0,0,.3), inset 0 0 0 1px rgba(255,255,255,.08)';
      });
      cell.addEventListener('mouseleave', function(){ img.style.transform=''; img.style.boxShadow='0 7px 16px rgba(0,0,0,.24), inset 0 0 0 1px rgba(255,255,255,.08)'; });
      cell.addEventListener('click', function(){ showBookDetailByTitle(it.t); });
      row.appendChild(cell); enter(cell);
    });
  }

  // 稳定 hash → 厚度因子（0.35~1.0）：书脊无真实页数数据，用 bookId 模拟厚薄，同一本书每次一致
  function hashF(s){
    s = String(s || '');
    var h = 0;
    for (var i=0;i<s.length;i++){ h = (h*31 + s.charCodeAt(i)) >>> 0; }
    return (h % 1000) / 1000;
  }

  // 书脊排序：读完的书在前，其余按阅读时长降序（月度数据无读完日期，用 finished 代理"已读完"优先）
  function spineItems(){
    var arr = items.slice();
    arr.sort(function(a, b){ return (b.f || 0) - (a.f || 0) || (b.s || 0) - (a.s || 0); });
    return arr;
  }

  // 3) 书脊模式：真实封面书脊——封面窄条 + 顶部书页白边 + 右侧厚度阴影 + 高光渐变 + 竖排书名
  function spineNode(it, h, w){
    const cell = document.createElement('div');
    cell.title = it.t;
    const spine = document.createElement('div');
    spine.style.cssText = 'width:' + w + 'px;height:' + h + 'px;position:relative;cursor:default;'
      + 'border-radius:2px 3px 3px 2px;overflow:hidden;background:var(--wr-line);'
      + 'box-shadow:0 5px 12px rgba(0,0,0,.22);transition:transform .35s ease,box-shadow .35s ease';
    // 真实封面窄条（object-position 取封面中部偏左，模拟书脊视角）
    const img = document.createElement('img');
    img.src = it.c; img.alt = it.t; img.loading = 'lazy';
    img.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;object-fit:cover;'
      + 'object-position:35% 50%;display:block';
    // 顶部书页白边
    const topEdge = document.createElement('div');
    topEdge.style.cssText = 'position:absolute;top:0;left:0;right:0;height:4px;z-index:3;'
      + 'background:linear-gradient(180deg,#F7F2E7,rgba(247,242,231,.5));box-shadow:0 1px 2px rgba(0,0,0,.18)';
    // 右侧厚度阴影
    const sideShade = document.createElement('div');
    sideShade.style.cssText = 'position:absolute;top:0;right:0;bottom:0;width:36%;z-index:2;'
      + 'background:linear-gradient(270deg,rgba(0,0,0,.34),rgba(0,0,0,.04))';
    // 高光（左侧）
    const gloss = document.createElement('div');
    gloss.style.cssText = 'position:absolute;top:0;left:0;bottom:0;width:42%;z-index:2;'
      + 'background:linear-gradient(90deg,rgba(255,255,255,.26),rgba(255,255,255,.02))';
    // 竖排书名（白字 + 阴影保证浅色封面也可读；字号随书高与标题长度自适应，完整容纳）
    const name = document.createElement('div');
    name.textContent = it.t;
    var len = Math.max(1, it.t.length);
    var fs = Math.max(7, Math.min(11, Math.floor((h - 26) / len)));
    name.style.cssText = 'position:absolute;top:4px;left:0;right:0;bottom:6px;z-index:4;'
      + 'display:flex;align-items:center;justify-content:center;'
      + 'writing-mode:vertical-rl;font-size:' + fs + 'px;line-height:' + (fs + 1) + 'px;letter-spacing:0;'
      + 'overflow:hidden;white-space:normal;word-break:break-all;'
      + 'color:rgba(255,255,255,.96);text-shadow:0 1px 2px rgba(0,0,0,.7),0 0 5px rgba(0,0,0,.4)';
    spine.appendChild(img);
    spine.appendChild(sideShade);
    spine.appendChild(gloss);
    spine.appendChild(topEdge);
    spine.appendChild(name);
    cell.appendChild(spine);
    cell.addEventListener('mouseenter', function(){
      spine.style.transform='translateY(-6px) scale(1.05)'; spine.style.boxShadow='0 12px 22px rgba(0,0,0,.3)';
    });
    cell.addEventListener('mouseleave', function(){
      spine.style.transform=''; spine.style.boxShadow='0 5px 12px rgba(0,0,0,.22)';
    });
    cell.addEventListener('click', function(){ showBookDetailByTitle(it.t); });
    return cell;
  }
  function renderSpine(){
    var list = spineItems();
    if (spineLayout === 'v'){ renderSpineV(list); return; }
    shelfLayers(spinePer(), function(it, idx, row){
      const thick = 0.35 + 0.65 * hashF(it.b || (it.t + it.a));   // 0.35~1.0
      const h = 104 + Math.round(thick * 28);   // 104~132px，越厚越高
      const w = 15 + Math.round(thick * 10);    // 18~25px，越厚越宽
      const cell = spineNode(it, h, w);
      row.appendChild(cell); enter(cell);
    }, 3, '26px 24px 0');
  }

  // 3b) 书脊竖排「从下到上」：书横放堆叠——一本本平躺、书脊朝外，由下往上摞成一堆（微微左右交错，随手摞书感）
  function renderSpineV(list){
    grid.style.cssText = 'display:flex;flex-direction:column-reverse;align-items:center;gap:6px;'
      + 'margin-top:16px;padding:4px 30px 24px;overflow-y:auto;max-height:66vh';
    list.forEach(function(it){
      const thick = 0.35 + 0.65 * hashF(it.b || (it.t + it.a));
      const w = 170 + Math.round(thick * 110);   // 170~280px，越长越"高"
      const h = 22 + Math.round(thick * 20);     // 22~42px，越厚越高
      const off = Math.round((Math.random() - 0.5) * 84);   // 随机左右交错 ±42px，每本偏移量不同、位置每次不定
      const cell = document.createElement('div');
      cell.title = it.t;
      cell.style.cssText = 'position:relative;width:' + w + 'px;height:' + h + 'px;margin-left:' + off + 'px;cursor:pointer;'
        + 'border-radius:3px;overflow:hidden;background:var(--wr-line);'
        + 'box-shadow:0 5px 12px rgba(0,0,0,.22);transition:transform .35s ease,box-shadow .35s ease';
      // 封面平铺（横放视角：书脊侧面取封面横向中部）
      const img = document.createElement('img');
      img.src = it.c; img.alt = it.t; img.loading = 'lazy';
      img.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:50% 35%;display:block';
      // 左右封皮压痕
      const leftEdge = document.createElement('div');
      leftEdge.style.cssText = 'position:absolute;top:0;left:0;bottom:0;width:5px;z-index:3;'
        + 'background:linear-gradient(90deg,#F7F2E7,rgba(247,242,231,.5));box-shadow:1px 0 2px rgba(0,0,0,.18)';
      // 底部厚度阴影（书横躺，厚面在上下）
      const thickShade = document.createElement('div');
      thickShade.style.cssText = 'position:absolute;left:0;right:0;bottom:0;height:36%;z-index:2;'
        + 'background:linear-gradient(0deg,rgba(0,0,0,.32),rgba(0,0,0,.03))';
      // 顶部高光
      const gloss = document.createElement('div');
      gloss.style.cssText = 'position:absolute;top:0;left:0;right:0;height:42%;z-index:2;'
        + 'background:linear-gradient(180deg,rgba(255,255,255,.26),rgba(255,255,255,.02))';
      // 书名横排（沿书脊方向：书横躺后书脊文字由竖变横）
      const name = document.createElement('div');
      name.textContent = it.t;
      var fs = Math.max(9, Math.min(15, Math.floor((h - 8) * 1.4)));
      name.style.cssText = 'position:absolute;top:0;left:12px;right:12px;bottom:0;z-index:4;'
        + 'display:flex;align-items:center;justify-content:flex-start;'
        + 'font-size:' + fs + 'px;line-height:' + (fs + 1) + 'px;font-weight:600;'
        + 'overflow:hidden;white-space:nowrap;text-overflow:ellipsis;'
        + 'color:rgba(255,255,255,.96);text-shadow:0 1px 2px rgba(0,0,0,.7),0 0 5px rgba(0,0,0,.4)';
      cell.appendChild(img);
      cell.appendChild(thickShade);
      cell.appendChild(gloss);
      cell.appendChild(leftEdge);
      cell.appendChild(name);
      cell.addEventListener('mouseenter', function(){
        cell.style.transform='translateY(-2px) scale(1.02)'; cell.style.boxShadow='0 10px 20px rgba(0,0,0,.3)';
      });
      cell.addEventListener('mouseleave', function(){
        cell.style.transform=''; cell.style.boxShadow='0 5px 12px rgba(0,0,0,.22)';
      });
      cell.addEventListener('click', function(){ showBookDetailByTitle(it.t); });
      cell.style.opacity = '0';
      cell.style.transform = 'translateY(16px)';
      grid.appendChild(cell);
      setTimeout(function(){
        cell.style.transition = 'opacity .45s ease,transform .45s cubic-bezier(.2,.9,.3,1.1)';
        cell.style.opacity = '1';
        cell.style.transform = 'translateY(0)';
      }, 60 + animSeq * 55);
      animSeq++;
    });
  }

  // 4) 成就模式：小票式图书列表（书名 + 作者/出版社 · 已读完/在读 + 时长），点击行弹详情
  function renderAchv(){
    if (achvStyle === 'pink') renderAchvPink();
    else if (achvStyle === 'vintage') renderAchvVintage();
    else if (achvStyle === 'stamp') renderAchvStamp();
    else renderAchvClassic();
  }

  // 出票机背景：机器与票的衔接（经典/粉彩/印章=机器在上、票从出票口向下吐出；复古=机器在下作背景、纸从纸架向上出）
  function achvMount(grid, ticket, style){
    const up = (style === 'vintage');
    if (up){
      // 复古打字机：机器放大、只露出上半部（纸架+纸头），票底压着纸架，视觉上纸从机器里向上抽出
      const wrap = document.createElement('div');
      wrap.style.cssText = 'position:relative;margin:0 auto;overflow:hidden;';
      const m = document.createElement('img');
      m.src = MACHINES[style] || '';
      m.style.cssText = 'position:absolute;left:50%;bottom:-368px;transform:translateX(-50%);'
        + 'width:158%;max-width:720px;height:auto;object-fit:contain;z-index:1;'
        + 'filter:drop-shadow(0 -12px 18px rgba(0,0,0,.12));';
      m.onerror = function(){ m.style.display = 'none'; };
      wrap.appendChild(m);
      ticket.style.position = 'relative'; ticket.style.zIndex = '2';
      wrap.appendChild(ticket);
      grid.appendChild(wrap);
      return;
    }
    const wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex;flex-direction:column;align-items:center;margin:0 auto';
    const m = document.createElement('img');
    m.src = MACHINES[style] || '';
    m.style.cssText = 'width:100%;max-width:460px;height:auto;object-fit:contain;position:relative;z-index:3;margin-bottom:-16px;filter:drop-shadow(0 8px 14px rgba(0,0,0,.14))';
    m.onerror = function(){ m.style.display = 'none'; };
    wrap.appendChild(m);
    ticket.style.zIndex = '1';
    wrap.appendChild(ticket);
    grid.appendChild(wrap);
  }

  // 小票通用：行交互 + 明细数据
  function achvBase(){
    grid.style.cssText = 'display:flex;justify-content:center;align-items:flex-start;margin-top:18px;padding-bottom:8px';
    const list = spineItems();
    let total = 0;
    list.forEach(function(b){ total += (b.s||0); });
    return { list: list, total: total };
  }
  function achvRows(ticket, list, paper, ink, inkSoft, style){
    list.forEach(function(it){
      const row = document.createElement('div');
      row.style.cssText = 'cursor:pointer;transition:background .2s ease;border-bottom:1px dashed ' + (style === 'stamp' ? 'rgba(17,17,17,.22)' : inkSoft);
      const line = document.createElement('div');
      line.style.cssText = 'display:flex;align-items:baseline;padding:7px 4px 1px';
      const title = document.createElement('span');
      title.textContent = it.t;
      title.style.cssText = 'flex-shrink:0;font-size:12px;font-weight:700;white-space:nowrap';
      const dots = document.createElement('span');
      dots.textContent = '· · · · · · · · · · · · · · · · · · · · · · · · · · · · · ·';
      dots.style.cssText = 'flex:1;min-width:8px;overflow:hidden;white-space:nowrap;font-size:10px;color:' + inkSoft + ';margin:0 4px;text-align:right';
      const dur = document.createElement('span');
      dur.textContent = fmtSec(it.s);
      dur.style.cssText = 'flex-shrink:0;font-size:11px;font-weight:700;white-space:nowrap';
      line.appendChild(title); line.appendChild(dots); line.appendChild(dur);
      const meta = document.createElement('div');
      const metaParts = [(it.f ? '[已读完]' : '[在读]')].concat([it.a, it.p].filter(Boolean));
      meta.textContent = '  ' + metaParts.join(' · ');
      meta.style.cssText = 'font-size:10px;color:' + inkSoft + ';padding:1px 4px 5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap';
      row.appendChild(line); row.appendChild(meta);
      row.addEventListener('click', function(){ showBookDetailByTitle(it.t); });
      row.addEventListener('mouseenter', function(){ row.style.background = style === 'pink' ? 'rgba(196,69,111,.06)' : 'rgba(0,0,0,.045)'; });
      row.addEventListener('mouseleave', function(){ row.style.background = ''; });
      ticket.appendChild(row);
    });
  }

  // 小票①：经典热敏纸（米色 + 噪点 + 等宽点线 + 锯齿）
  function renderAchvClassic(){
    const b = achvBase();
    const list = b.list, total = b.total;
    const paper = '#f6f1e4';
    const ink = '#2d2a24';
    const inkSoft = 'rgba(45,42,36,.68)';
    const mono = "'Courier New', 'Courier', monospace";

    const ticket = document.createElement('div');
    ticket.style.cssText = 'position:relative;width:100%;max-width:460px;background:' + paper + ';color:' + ink + ';'
      + 'font-family:' + mono + ';padding:18px 26px 26px;box-shadow:0 8px 28px rgba(0,0,0,.16);'
      + 'background-image:repeating-linear-gradient(0deg,rgba(0,0,0,.014) 0 1px,transparent 1px 3px),'
      + 'repeating-linear-gradient(90deg,rgba(0,0,0,.008) 0 1px,transparent 1px 5px);';
    const topNotch = document.createElement('div');
    topNotch.style.cssText = 'position:absolute;left:0;right:0;top:0;height:9px;'
      + 'background:linear-gradient(135deg,transparent 7px,' + paper + ' 0),linear-gradient(45deg,transparent 7px,' + paper + ' 0);'
      + 'background-size:14px 14px;background-repeat:repeat-x;background-position:top;';
    const bottomNotch = document.createElement('div');
    bottomNotch.style.cssText = 'position:absolute;left:0;right:0;bottom:0;height:9px;'
      + 'background:linear-gradient(135deg,transparent 7px,' + paper + ' 0),linear-gradient(45deg,transparent 7px,' + paper + ' 0);'
      + 'background-size:14px 14px;background-repeat:repeat-x;background-position:bottom;';
    ticket.appendChild(topNotch);
    ticket.appendChild(bottomNotch);

    const head = document.createElement('div');
    head.style.cssText = 'text-align:center;padding:2px 0 10px';
    head.innerHTML = '<div style="letter-spacing:3px;color:' + inkSoft + ';font-size:10px">* * * * * * * * * *</div>'
      + '<div style="font-size:17px;font-weight:700;letter-spacing:2px;margin-top:5px">舟读 · 阅读小票</div>'
      + '<div style="font-size:12px;margin-top:6px">' + escHtml(galTitle) + ' · 共 ' + list.length + ' 本</div>'
      + '<div style="font-size:10px;color:' + inkSoft + ';margin-top:4px">No.' + (galYear || '----') + '-' + String(galMonth || 0).padStart(2,'0') + '</div>'
      + '<div style="letter-spacing:3px;color:' + inkSoft + ';font-size:10px;margin-top:8px">- - - - - - - - - -</div>';
    ticket.appendChild(head);
    achvRows(ticket, list, paper, ink, inkSoft, 'classic');
    const foot = document.createElement('div');
    foot.style.cssText = 'padding:10px 4px 2px;text-align:center';
    foot.innerHTML = '<div style="display:flex;justify-content:space-between;font-size:11px;font-weight:700;letter-spacing:1px">'
      + '<span>合计 ' + list.length + ' 本</span><span>累计 ' + fmtSec(total) + '</span></div>'
      + '<div style="font-size:10px;color:' + inkSoft + ';margin-top:8px">感谢本月与书为伴，下月再见</div>'
      + '<div style="letter-spacing:3px;color:' + inkSoft + ';font-size:10px;margin-top:8px">* * * * * * * * * *</div>';
    ticket.appendChild(foot);
    achvMount(grid, ticket, 'classic');
  }

  // 小票②：粉彩主题（参考图1：品牌 + emoji 图标行 + ITEM/PRICE 两列 + 标语 + 条形码）
  function renderAchvPink(){
    const b = achvBase();
    const list = b.list, total = b.total;
    const paper = '#FFF6F9';
    const ink = '#C4456F';
    const inkSoft = 'rgba(196,69,111,.6)';
    const mono = "'Courier New', 'Courier', monospace";

    const ticket = document.createElement('div');
    ticket.style.cssText = 'position:relative;width:100%;max-width:460px;background:' + paper + ';color:' + ink + ';'
      + 'font-family:' + mono + ';padding:18px 26px 26px;box-shadow:0 8px 28px rgba(0,0,0,.14);'
      + 'background-image:repeating-linear-gradient(0deg,rgba(196,69,111,.018) 0 1px,transparent 1px 3px);';
    const topNotch = document.createElement('div');
    topNotch.style.cssText = 'position:absolute;left:0;right:0;top:0;height:9px;'
      + 'background:linear-gradient(135deg,transparent 7px,' + paper + ' 0),linear-gradient(45deg,transparent 7px,' + paper + ' 0);'
      + 'background-size:14px 14px;background-repeat:repeat-x;background-position:top;';
    const bottomNotch = document.createElement('div');
    bottomNotch.style.cssText = 'position:absolute;left:0;right:0;bottom:0;height:9px;'
      + 'background:linear-gradient(135deg,transparent 7px,' + paper + ' 0),linear-gradient(45deg,transparent 7px,' + paper + ' 0);'
      + 'background-size:14px 14px;background-repeat:repeat-x;background-position:bottom;';
    ticket.appendChild(topNotch);
    ticket.appendChild(bottomNotch);

    const head = document.createElement('div');
    head.style.cssText = 'text-align:center;padding:2px 0 8px';
    head.innerHTML = '<div style="font-size:15px;letter-spacing:1px">舟读 · READ</div>'
      + '<div style="font-size:16px;margin-top:4px;letter-spacing:4px">📖 ✏️ ☕ 📚 🌙</div>'
      + '<div style="font-size:11px;margin-top:6px;letter-spacing:2px">' + escHtml(galTitle) + ' · 共 ' + list.length + ' 本</div>'
      + '<div style="display:flex;justify-content:space-between;font-size:10px;color:' + inkSoft + ';margin-top:8px;border-bottom:1px dashed ' + inkSoft + ';padding-bottom:5px">'
      + '<span>ITEM</span><span>PRICE</span></div>';
    ticket.appendChild(head);
    achvRows(ticket, list, paper, ink, inkSoft, 'pink');
    const foot = document.createElement('div');
    foot.style.cssText = 'padding:9px 4px 2px;text-align:center';
    foot.innerHTML = '<div style="display:flex;justify-content:space-between;font-size:11px;font-weight:700;letter-spacing:2px;border-top:1px dashed ' + inkSoft + ';padding-top:7px">'
      + '<span>TOTAL</span><span>累计 ' + fmtSec(total) + '</span></div>'
      + '<div style="font-size:10px;color:' + inkSoft + ';margin-top:9px;letter-spacing:1px">今天也要读点好的 ✨</div>'
      + '<div style="width:170px;height:24px;margin:12px auto 0;opacity:.85;'
      + 'background:repeating-linear-gradient(90deg,' + ink + ' 0 2px,transparent 2px 5px),'
      + 'repeating-linear-gradient(90deg,' + ink + ' 0 1px,transparent 1px 3px,' + ink + ' 3px 5px,transparent 5px 8px);"></div>'
      + '<div style="font-size:10px;letter-spacing:3px;margin-top:6px;color:' + inkSoft + '">舟读 · READ</div>';
    ticket.appendChild(foot);
    achvMount(grid, ticket, 'pink');
  }

  // 小票③：复古打字机信纸（参考图2：顶部两侧小字 + 留白 + 底部品牌标语）
  function renderAchvVintage(){
    const b = achvBase();
    const list = b.list, total = b.total;
    const paper = '#FBF7EE';
    const ink = '#3E3A33';
    const inkSoft = 'rgba(62,58,51,.62)';
    const mono = "'Courier New', 'Courier', monospace";

    const ticket = document.createElement('div');
    ticket.style.cssText = 'position:relative;width:100%;max-width:480px;background:' + paper + ';color:' + ink + ';'
      + 'font-family:' + mono + ';padding:26px 34px 30px;box-shadow:0 8px 28px rgba(0,0,0,.12);'
      + 'background-image:repeating-linear-gradient(0deg,rgba(0,0,0,.012) 0 1px,transparent 1px 5px);';

    const topRow = document.createElement('div');
    topRow.style.cssText = 'display:flex;justify-content:space-between;font-size:10px;color:' + inkSoft + ';letter-spacing:1px;padding-bottom:18px;border-bottom:1px solid rgba(62,58,51,.25)';
    topRow.innerHTML = '<span>舟读 · ' + (galYear || '----') + '.' + String(galMonth || 0).padStart(2,'0') + '</span><span>reading note</span>';
    ticket.appendChild(topRow);

    const head = document.createElement('div');
    head.style.cssText = 'text-align:center;padding:34px 0 26px';
    head.innerHTML = '<div style="font-size:22px;font-weight:700;letter-spacing:8px">本月书单</div>'
      + '<div style="font-size:10px;color:' + inkSoft + ';margin-top:10px;font-style:italic">the books of this month · ' + list.length + ' 本</div>';
    ticket.appendChild(head);

    achvRows(ticket, list, paper, ink, inkSoft, 'vintage');

    const foot = document.createElement('div');
    foot.style.cssText = 'text-align:center;padding:26px 0 4px;border-top:1px solid rgba(62,58,51,.25)';
    foot.innerHTML = '<div style="font-size:12px;letter-spacing:4px">舟读书房</div>'
      + '<div style="font-size:10px;color:' + inkSoft + ';margin-top:8px;font-style:italic">old memory of new time ....</div>'
      + '<div style="font-size:10px;color:' + inkSoft + ';margin-top:14px;letter-spacing:2px">合计 ' + list.length + ' 本 · 累计 ' + fmtSec(total) + '</div>';
    ticket.appendChild(foot);
    achvMount(grid, ticket, 'vintage');
  }

  // 小票④：白纸黑字印章版（参考图3：黑字曲目式 + 编号日期 + 红印章 + 版权小字）
  function renderAchvStamp(){
    const b = achvBase();
    const list = b.list, total = b.total;
    const paper = '#FFFFFF';
    const ink = '#111111';
    const inkSoft = 'rgba(17,17,17,.5)';
    const mono = "'Courier New', 'Courier', monospace";
    const red = 'rgba(224,51,51,.6)';

    const ticket = document.createElement('div');
    ticket.style.cssText = 'position:relative;width:100%;max-width:460px;background:' + paper + ';color:' + ink + ';'
      + 'font-family:' + mono + ';padding:16px 26px 22px;box-shadow:0 8px 28px rgba(0,0,0,.16);';
    const topNotch = document.createElement('div');
    topNotch.style.cssText = 'position:absolute;left:0;right:0;top:0;height:12px;'
      + 'background:linear-gradient(135deg,transparent 9px,' + paper + ' 0),linear-gradient(45deg,transparent 9px,' + paper + ' 0);'
      + 'background-size:18px 18px;background-repeat:repeat-x;background-position:top;';
    const bottomNotch = document.createElement('div');
    bottomNotch.style.cssText = 'position:absolute;left:0;right:0;bottom:0;height:12px;'
      + 'background:linear-gradient(135deg,transparent 9px,' + paper + ' 0),linear-gradient(45deg,transparent 9px,' + paper + ' 0);'
      + 'background-size:18px 18px;background-repeat:repeat-x;background-position:bottom;';
    ticket.appendChild(topNotch);
    ticket.appendChild(bottomNotch);

    // 红印章（右上角）
    const stampOuter = document.createElement('div');
    stampOuter.style.cssText = 'position:absolute;top:20px;right:26px;width:60px;height:60px;border-radius:50%;'
      + 'border:2px solid ' + red + ';display:flex;align-items:center;justify-content:center;transform:rotate(-10deg);opacity:.9';
    const stampInner = document.createElement('div');
    stampInner.style.cssText = 'width:42px;height:42px;border-radius:50%;border:1px dashed ' + red + ';'
      + 'display:flex;align-items:center;justify-content:center;color:' + red + ';font-size:9px;font-weight:700;letter-spacing:1px;text-align:center;line-height:1.5';
    stampInner.innerHTML = '舟读<br>已阅';
    stampOuter.appendChild(stampInner);
    ticket.appendChild(stampOuter);

    const head = document.createElement('div');
    head.style.cssText = 'text-align:center;padding:4px 0 6px';
    head.innerHTML = '<div style="font-size:18px;font-weight:700;letter-spacing:3px">舟读 · 月度书单</div>'
      + '<div style="font-size:8px;color:' + inkSoft + ';margin-top:3px;letter-spacing:3px">MONTHLY READING RECEIPT</div>'
      + '<div style="display:flex;justify-content:space-between;font-size:9px;color:' + inkSoft + ';margin-top:10px;border-bottom:1px solid rgba(17,17,17,.25);padding-bottom:5px">'
      + '<span>' + escHtml(galTitle) + '</span><span>No.' + (galYear || '----') + '-' + String(galMonth || 0).padStart(2,'0') + '</span></div>';
    ticket.appendChild(head);
    achvRows(ticket, list, paper, ink, inkSoft, 'stamp');
    const foot = document.createElement('div');
    foot.style.cssText = 'padding:8px 4px 2px;text-align:center';
    foot.innerHTML = '<div style="display:flex;justify-content:space-between;font-size:11px;font-weight:700;letter-spacing:2px;border-top:1px solid rgba(17,17,17,.25);padding-top:7px">'
      + '<span>TOTAL [ MIN ]</span><span>' + fmtSec(total) + '</span></div>'
      + '<div style="font-size:7px;color:' + inkSoft + ';margin-top:10px;letter-spacing:1px;line-height:1.6">'
      + 'COPYRIGHT 2026 舟读 · 阅读看板 · POWERED BY WEREAD &amp; OBSIDIAN</div>';
    ticket.appendChild(foot);
    achvMount(grid, ticket, 'stamp');
  }

  function setMode(m){
    mode = m; animSeq = 0;
    grid.innerHTML = '';
    modeBtns.forEach(function(b){
      const on = b.getAttribute('data-mode') === m;
      b.style.background = on ? 'var(--wr-main)' : 'transparent';
      b.style.color = on ? 'var(--wr-white)' : 'var(--wr-sub)';
      b.style.border = on ? '1px solid var(--wr-main)' : '1px solid var(--wr-line)';
    });
    const layoutBox = mask.querySelector('#wr-spine-layout');
    if (layoutBox){
      if (m === 'spine'){ layoutBox.style.display = 'flex'; }
      else { layoutBox.style.display = 'none'; }
      layoutBox.querySelectorAll('.wr-slayout').forEach(function(b){
        const on = b.getAttribute('data-layout') === spineLayout;
        b.style.background = on ? 'var(--wr-main)' : 'transparent';
        b.style.color = on ? 'var(--wr-white)' : 'var(--wr-sub)';
      });
    }
    const aStyleBox = mask.querySelector('#wr-achv-style');
    if (aStyleBox){
      if (m === 'achv'){ aStyleBox.style.display = 'flex'; }
      else { aStyleBox.style.display = 'none'; }
      aStyleBox.querySelectorAll('.wr-astyle').forEach(function(b){
        const on = b.getAttribute('data-style') === achvStyle;
        b.style.background = on ? 'var(--wr-main)' : 'transparent';
        b.style.color = on ? 'var(--wr-white)' : 'var(--wr-sub)';
      });
    }
    if (m === 'shelf') renderShelf();
    else if (m === 'spine') renderSpine();
    else if (m === 'achv') renderAchv();
    else renderFlat();
  }

  function build(){
    try { items = JSON.parse(dataEl.textContent); } catch(e) {}
    renderFlat();
  }
  function open(){
    if (!grid.innerHTML) build();
    mask.style.visibility = 'visible';
    mask.style.opacity = '1';
    const panel = mask.querySelector('#wr-gallery-panel');
    panel.style.transform = 'translateY(0) scale(1)';
  }
  function close(){
    mask.style.opacity = '0';
    mask.style.visibility = 'hidden';
    const panel = mask.querySelector('#wr-gallery-panel');
    panel.style.transform = 'translateY(30px) scale(.96)';
  }
  btn.addEventListener('click', open);
  modeBtns.forEach(function(b){
    b.addEventListener('click', function(){ setMode(b.getAttribute('data-mode')); });
  });
  const layoutBox = mask.querySelector('#wr-spine-layout');
  if (layoutBox){
    layoutBox.querySelectorAll('.wr-slayout').forEach(function(b){
      b.addEventListener('click', function(){
        spineLayout = b.getAttribute('data-layout');
        if (mode === 'spine'){ setMode('spine'); }
      });
    });
  }
  const aStyleBox = mask.querySelector('#wr-achv-style');
  if (aStyleBox){
    aStyleBox.querySelectorAll('.wr-astyle').forEach(function(b){
      b.addEventListener('click', function(){
        achvStyle = b.getAttribute('data-style');
        if (mode === 'achv'){ setMode('achv'); }
      });
    });
  }
  // 主页面封面滚动条：点击封面 → 弹该书详情（右上角"打开笔记"跳书页，覆盖旧的直接跳转逻辑）
  const coverStrip = root.querySelector('#wr-cover-gallery');
  if (coverStrip && !coverStrip.dataset.wrBound){
    coverStrip.dataset.wrBound = '1';
    coverStrip.addEventListener('click', function(e){
      const a = e.target && e.target.closest ? e.target.closest('a[data-t]') : null;
      if (!a) return;
      e.preventDefault();
      e.stopPropagation();  // 阻止主 JS 的 document 级直接打开书页逻辑
      showBookDetailByTitle(a.getAttribute('data-t'));
    });
  }
  mask.querySelector('#wr-gallery-close').addEventListener('click', close);
  mask.addEventListener('click', function(e){ if (e.target === mask) close(); });
  if (dMask) dMask.addEventListener('click', function(e){ if (e.target === dMask) closeDetail(); });
  document.addEventListener('keydown', function(e){
    if (e.key !== 'Escape') return;
    if (dMask && dMask.style.visibility === 'visible') closeDetail();
    else close();
  });
})();
"""

JS = SKIN_JS + "\n" + JS + "\n" + _GALLERY_JS
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
               + _INTERACT_JS + "\n"
               + _report_click_js() + "\n"
               + _GALLERY_JS + "\n"
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
