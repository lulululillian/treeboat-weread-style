# -*- coding: utf-8 -*-
"""月报 dataviewjs 模板 — 舟读・微信读书阅读月报（Obsidian 内渲染）
数据源：同目录 data/YYYY-MM.json（由 refresh.py 自动归档 / archive_month.py 补生成）。
由 gen_dv.py（页面按钮写入）与 gen_monthly_summary.py（命令行）共用，保证两种入口产物一致。
"""
import datetime

# ================= 主题换肤（与阅读统计页一致） =================
THEME_JS = r"""const THEMES = __THEMES__;
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

# ================= 图表 helper（SVG 手绘，全部走 CSS 变量随主题） =================
CHART_HELPERS = r"""
function _e(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function _fmtMin(m){ if(m>=60){ const h=Math.floor(m/60),mm=m%60; return (mm? h+'小时'+String(mm).padStart(2,'0')+'分' : h+'小时'); } return m+'分钟'; }
function _fmtSec(sec){ return _fmtMin(Math.round(sec/60)); }
function _card(title, inner, sub){ return '<div style="background:var(--wr-white);border:0.5px solid var(--wr-line);border-radius:12px;padding:14px 16px;margin-bottom:14px"><div style="font-size:14px;font-weight:500;margin-bottom:10px;color:var(--wr-main)">'+title+'</div>'+inner+(sub?'<div style="font-size:11px;color:var(--wr-faint);margin-top:8px">'+sub+'</div>':'')+'</div>'; }
function _kpi(label, val, sub){ return '<div style="background:var(--wr-white);border:0.5px solid var(--wr-line);border-radius:12px;padding:12px 14px"><div style="font-size:12px;color:var(--wr-sub)">'+label+'</div><div style="font-size:20px;font-weight:500;margin-top:4px;color:var(--wr-main)">'+val+'</div>'+(sub?'<div style="font-size:10px;color:var(--wr-faint);margin-top:2px">'+sub+'</div>':'')+'</div>'; }
function _bar(label, value, pct, right){ return '<div style="margin-bottom:9px"><div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px"><span style="color:var(--wr-main);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding-right:8px">'+label+'</span><span style="color:var(--wr-sub);flex-shrink:0">'+(right||'')+'</span></div><div style="height:7px;background:var(--wr-line);border-radius:4px;overflow:hidden"><div style="height:100%;width:'+pct+'%;background:var(--wr-main);border-radius:4px"></div></div></div>'; }
// 热力色阶（变量）
function _heatCell(m){
  if(m<=0) return 'var(--wr-heat-0)';
  if(m<=15) return 'var(--wr-heat-1)';
  if(m<=45) return 'var(--wr-heat-2)';
  if(m<=90) return 'var(--wr-heat-3)';
  return 'var(--wr-heat-4)';
}
"""

# ================= 主体渲染逻辑 =================
RENDER_JS = r"""
(function(){
  const root = dv.container.createEl('div');
  const cur = dv.current().file.path;
  const dir = cur.indexOf('/') >= 0 ? cur.substring(0, cur.lastIndexOf('/')) : '';
  const dataPath = dir + '/data/__YM__.json';
  async function main(){
    let D = null;
    try {
      const raw = await app.vault.adapter.read(dataPath);
      D = JSON.parse(raw);
    } catch (err) {
      root.innerHTML = '<div style="color:var(--wr-faint);font-size:13px;padding:16px">月报数据未找到（'+_e(dataPath)+'）。<br>请先运行刷新生成该月归档，或确认月报所在目录正确。</div>';
      bindThemeSel(root);
      return;
    }
    const Y = D.year||__YEAR__; const M = D.month||__MONTH__; const ND = D.n_days||31;
    const day_sec = {}; Object.keys(D.day_sec||{}).forEach(function(k){ day_sec[parseInt(k)] = D.day_sec[k]; });
    const total_sec = D.total_sec||0; const read_days = D.read_days||0;
    const books = (D.books||[]).map(function(b){ return {
      short:b.short, title:b.title||b.short, author:b.author||'', sec:Number(b.sec)||0,
      cover:b.cover||'', finished:!!b.finished, progress:Number(b.progress)||0,
      marks:(b.marks||[]).length, month_marks:Number(b.month_marks)||0,
      mark_items:(b.mark_items||[]), hour_profile:b.hour_profile||''
    };}).sort(function(a,b){ return b.sec-a.sec; });
    const finishedN = books.filter(function(b){ return b.finished; }).length;
    const markTotal = books.reduce(function(s,b){ return s+b.month_marks; },0);
    const avgMin = read_days ? Math.round(total_sec/60/read_days) : 0;

    let html = '';
    // ---- 头部 ----
    html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:12px">'
      + '<div style="font-size:16px;font-weight:600;color:var(--wr-main)">📖 阅读月报 · '+Y+' 年 '+M+' 月</div>'
      + '<div style="display:flex;align-items:center;gap:8px">'
      + '<span style="font-size:11px;color:var(--wr-faint)">生成于 '+new Date().toLocaleDateString('zh-CN')+'</span>'
      + '<select id="wr-theme" style="background:var(--wr-white);border:1px solid var(--wr-line);color:var(--wr-main);border-radius:999px;padding:4px 10px;font-size:12px;font-family:inherit;cursor:pointer;outline:none">'
      + Object.keys(THEMES).map(function(k){ return '<option value="'+k+'">'+THEMES[k].name+'</option>'; }).join('') + '</select>'
      + '</div></div>';

    // ---- KPI ----
    html += '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-bottom:14px">'
      + _kpi('本月总时长', _fmtSec(total_sec), '累计阅读')
      + _kpi('阅读天数', read_days + ' 天', '日均 ' + _fmtMin(avgMin))
      + _kpi('阅读书目', books.length + ' 本', '读完 ' + finishedN + ' 本')
      + _kpi('本月划线', markTotal + ' 条', '累计 ' + books.reduce(function(s,b){return s+b.marks;},0) + ' 条')
      + '</div>';

    // ---- 每日时长柱状图 ----
    {
      const days=[]; for(let d=1;d<=ND;d++){ days.push({d:d, m:Math.round((day_sec[d]||0)/60)}); }
      const mx = Math.max.apply(null, days.map(function(x){return x.m;})) || 1;
      const W = 720, H = 120, padB = 18, padT = 8;
      const bw = Math.max(6, Math.floor((W-20)/ND) - 3);
      let s = '<svg width="'+W+'" height="'+(H+padB)+'" style="display:block;max-width:100%;background:transparent">';
      for(let i=0;i<=4;i++){ const gy=padT+(H-padT)*i/4; s+='<line x1="6" y1="'+gy.toFixed(1)+'" x2="'+(W-6)+'" y2="'+gy.toFixed(1)+'" stroke="var(--wr-line)" stroke-opacity="0.5"/>'; }
      days.forEach(function(x,idx){
        const hgt = Math.max(x.m>0? 2:0, (x.m/mx)*(H-padT));
        const xp = 8 + idx*((W-16)/ND);
        const yp = H - hgt;
        s += '<rect x="'+xp.toFixed(1)+'" y="'+yp.toFixed(1)+'" width="'+bw+'" height="'+hgt.toFixed(1)+'" rx="2" fill="'+(x.m>0?'var(--wr-main)':'var(--wr-line)')+'" opacity="'+(x.m>0?0.85:0.4)+'"><title>'+M+'月'+x.d+'日 · '+x.m+' 分钟</title></rect>';
        if(ND<=31 && idx%2===0){ s += '<text x="'+(xp+bw/2).toFixed(1)+'" y="'+(H+12)+'" font-size="8" fill="var(--wr-faint)" text-anchor="middle">'+x.d+'</text>'; }
      });
      s += '</svg>';
      html += _card('每日阅读时长（分钟）', s, '柱子越高＝当天读得越久，悬停查看具体分钟数');
    }

    // ---- 月度热力图 + 每周阅读习惯（左右并排，消除全宽留白） ----
    {
      const w1 = new Date(Y, M-1, 1).getDay(); // 0=周日
      const step=24, cell=21, labelW=20, titleH=26, wdH=16;
      const nRows = Math.ceil((w1 + ND)/7);
      const W2 = labelW + 7*step + 4, H2 = titleH + wdH + nRows*step + 22;
      const wd = ['日','一','二','三','四','五','六'];
      let s = '<svg width="'+W2+'" height="'+H2+'" style="display:block;max-width:100%">';
      for(let c=0;c<7;c++){ s+='<text x="'+(labelW+c*step+cell/2)+'" y="'+(titleH+12)+'" font-size="9" fill="var(--wr-faint)" text-anchor="middle">'+wd[c]+'</text>'; }
      for(let r=0;r<nRows;r++){ s+='<text x="8" y="'+(titleH+wdH+r*step+cell/2+3)+'" font-size="8" fill="var(--wr-faint)" text-anchor="middle">W'+(r+1)+'</text>'; }
      for(let d=1;d<=ND;d++){
        const col = (w1 + d - 1) % 7, row = Math.floor((w1 + d - 1)/7);
        const x = labelW + col*step, y = titleH + wdH + row*step;
        const m = Math.round((day_sec[d]||0)/60);
        s += '<rect x="'+x+'" y="'+y+'" width="'+cell+'" height="'+cell+'" rx="3" fill="'+_heatCell(m)+'" stroke="var(--wr-white)" stroke-width="1"><title>'+M+'月'+d+'日 · '+m+' 分钟</title></rect>';
        s += '<text x="'+(x+4)+'" y="'+(y+cell/2+3)+'" font-size="8" fill="'+(m>0?'var(--wr-white)':'var(--wr-faint)')+'">'+d+'</text>';
      }
      s += '</svg>';
      const heatCard = _card('本月阅读热力图', s, '颜色越深＝当天读得越久');

      const wk = [0,0,0,0,0,0,0];
      for(let d=1;d<=ND;d++){ const wdd = new Date(Y, M-1, d).getDay(); const idx = wdd===0?6:wdd-1; wk[idx] += day_sec[d]||0; }
      const wnames = ['周一','周二','周三','周四','周五','周六','周日'];
      const wmx = Math.max.apply(null, wk) || 1;
      let inner = '';
      wnames.forEach(function(n,i){ inner += _bar(n, _fmtSec(wk[i]), Math.round(wk[i]/wmx*100), _fmtSec(wk[i])); });
      const weekCard = _card('每周阅读习惯（按星期几累计）', inner, '看你更喜欢在工作日还是周末读书');

      html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px;align-items:stretch">' + heatCard + weekCard + '</div>';
    }

    // ---- 24h 时段（环形时钟 + 条形） ----
    {
      const hc = {}; for(let h=0;h<24;h++){ hc[h]=0; }
      books.forEach(function(b){ (b.mark_items||[]).forEach(function(x){ if(x.t){ const dt=new Date(x.t*1000); if(dt.getFullYear()===Y && (dt.getMonth()+1)===M){ const h=dt.getHours(); hc[h]=(hc[h]||0)+1; } } }); });
      const hmax = Math.max.apply(null, Object.keys(hc).map(function(k){return hc[k];})) || 1;
      const cx=85, cy=85, r=62, sw=13, seg=360/24;
      let ring='<svg width="170" height="170" viewBox="0 0 170 170" style="display:block;margin:0 auto">';
      for(let h=0;h<24;h++){
        const c=hc[h]||0; const a0=-90+h*seg, a1=a0+seg;
        const x1=cx+r*Math.cos(a0*Math.PI/180), y1=cy+r*Math.sin(a0*Math.PI/180);
        const x2=cx+r*Math.cos(a1*Math.PI/180), y2=cy+r*Math.sin(a1*Math.PI/180);
        const stroke = c>0 ? 'var(--wr-main)' : 'var(--wr-line)';
        const op = c>0 ? (0.25+0.75*c/hmax) : 0.3;
        ring += '<path d="M'+x1.toFixed(1)+' '+y1.toFixed(1)+' A'+r+' '+r+' 0 0 1 '+x2.toFixed(1)+' '+y2.toFixed(1)+'" fill="none" stroke="'+stroke+'" stroke-width="'+sw+'" stroke-opacity="'+op+'"><title>'+String(h).padStart(2,'0')+':00 · '+c+' 条划线</title></path>';
      }
      ring += '<text x="'+cx+'" y="'+(cy+4)+'" text-anchor="middle" font-size="16" font-weight="600" fill="var(--wr-main)">'+Object.keys(hc).reduce(function(s,k){return s+hc[k];},0)+'</text>';
      ring += '<text x="'+cx+'" y="'+(cy+20)+'" text-anchor="middle" font-size="9" fill="var(--wr-faint)">本月划线</text></svg>';
      // 条形
      const labels = ['0-2','2-4','4-6','6-8','8-10','10-12','12-14','14-16','16-18','18-20','20-22','22-24'];
      const sums = [0,0,0,0,0,0,0,0,0,0,0,0];
      Object.keys(hc).forEach(function(h){ const hh=parseInt(h); sums[Math.min(11,Math.floor(hh/2))] += hc[hh]; });
      const smx = Math.max.apply(null, sums) || 1;
      let bars = '';
      labels.forEach(function(l,i){ bars += _bar(l, sums[i]+' 条', Math.round(sums[i]/smx*100), sums[i]+' 条'); });
      // 本月最佳划线（并入左列环形下方，填补空白）
      const cands = [];
      books.forEach(function(b){ (b.mark_items||[]).forEach(function(x){ if(x.t){ const dt=new Date(x.t*1000); if(dt.getFullYear()===Y && (dt.getMonth()+1)===M && x.text){ cands.push({t:x.t, txt:x.text, bk:b.title, ch:x.chapter||''}); } } }); });
      cands.sort(function(a,b){ return b.t-a.t; });
      let quoteInner = '';
      if(cands.length){
        cands.slice(0,3).forEach(function(c,i){ quoteInner += '<div data-wr-quote style="margin-bottom:10px;padding-left:24px;position:relative"><div style="position:absolute;left:0;top:0;width:18px;height:18px;border-radius:50%;background:var(--wr-main);color:var(--wr-white);font-size:10px;display:flex;align-items:center;justify-content:center;font-weight:600">'+(i+1)+'</div><div style="font-size:12px;color:var(--wr-main);line-height:1.6;background:var(--wr-bg);border-left:2px solid var(--wr-main);border-radius:0 6px 6px 0;padding:6px 10px">“'+_e(c.txt)+'”</div><div style="font-size:10px;color:var(--wr-faint);margin-top:4px">——《'+_e(c.bk)+'》'+(c.ch?' · '+_e(c.ch):'')+'</div></div>'; });
      } else {
        quoteInner = '<div style="font-size:11px;color:var(--wr-faint)">本月暂无划线</div>';
      }
      html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px;align-items:stretch">'
        + '<div data-wr-lcol style="background:var(--wr-white);border:0.5px solid var(--wr-line);border-radius:12px;padding:14px;min-width:0">'+ring+'<div style="font-size:12px;font-weight:500;margin:16px 0 8px;color:var(--wr-sub)">本月最佳划线</div>'+quoteInner+'</div>'
        + '<div data-wr-rcol style="min-width:0">' + _card('24 小时划线时段分布', bars) + '</div>'
        + '</div>';
    }

    // ---- 各书时长占比 donut + 排行 ----
    {
      const top = books.slice(0,8);
      const tot = books.reduce(function(s,b){return s+b.sec;},0) || 1;
      let acc = 0; const cx=85, cy=85, R=58, rw=16;
      let donut = '<svg width="170" height="170" viewBox="0 0 170 170" style="display:block;margin:0 auto">';
      top.forEach(function(b,idx){
        const frac = b.sec/tot;
        const a0 = acc*2*Math.PI - Math.PI/2, a1 = (acc+frac)*2*Math.PI - Math.PI/2;
        acc += frac;
        const x1 = cx + R*Math.cos(a0), y1 = cy + R*Math.sin(a0);
        const x2 = cx + R*Math.cos(a1), y2 = cy + R*Math.sin(a1);
        const large = frac>0.5 ? 1 : 0;
        const hues = ['#414969','#5B6B85','#7E748C','#98A6BC','#B9A5A8','#C9B8B8','#8B9DAF','#A5B4C4'];
        donut += '<path d="M'+x1.toFixed(1)+' '+y1.toFixed(1)+' A'+R+' '+R+' 0 '+large+' 1 '+x2.toFixed(1)+' '+y2.toFixed(1)+'" fill="none" stroke="'+hues[idx%8]+'" stroke-width="'+rw+'" opacity="0.9"><title>'+_e(b.title)+' · '+_fmtSec(b.sec)+'</title></path>';
      });
      donut += '<text x="'+cx+'" y="'+(cy+4)+'" text-anchor="middle" font-size="14" font-weight="600" fill="var(--wr-main)">'+books.length+' 本</text>';
      donut += '<text x="'+cx+'" y="'+(cy+20)+'" text-anchor="middle" font-size="9" fill="var(--wr-faint)">本月书目</text></svg>';
      let legend = '<div style="font-size:11px;line-height:1.9;margin-top:8px">';
      top.forEach(function(b,idx){ const hues = ['#414969','#5B6B85','#7E748C','#98A6BC','#B9A5A8','#C9B8B8','#8B9DAF','#A5B4C4']; legend += '<div style="display:flex;align-items:center;gap:6px"><span style="width:8px;height:8px;border-radius:2px;background:'+hues[idx%8]+';flex-shrink:0"></span><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--wr-main)">'+_e(b.title)+'</span><span style="color:var(--wr-faint);margin-left:auto;flex-shrink:0">'+_fmtSec(b.sec)+'</span></div>'; });
      legend += '</div>';
      // 排行
      const mx = books[0] ? books[0].sec : 1;
      let rank = '';
      books.slice(0,10).forEach(function(b){ rank += _bar(_e(b.title), _fmtSec(b.sec), Math.round(b.sec/mx*100), _fmtSec(b.sec)); });
      html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px">'
        + _card('各书阅读时长占比', donut + legend)
        + _card('阅读时长排行 TOP'+Math.min(10,books.length), rank)
        + '</div>';
    }

    // ---- 各书划线排行 ----
    {
      const withM = books.filter(function(b){ return b.month_marks>0; }).sort(function(a,b){ return b.month_marks-a.month_marks; });
      if(withM.length){
        const mx = withM[0].month_marks || 1;
        let rank = '';
        withM.slice(0,10).forEach(function(b){ rank += _bar(_e(b.title), b.month_marks+' 条', Math.round(b.month_marks/mx*100), b.month_marks+' 条'); });
        html += _card('本月划线最多的书', rank);
      }
    }

    // ---- 读完/在读 ----
    {
      const fin = books.filter(function(b){return b.finished;}).length;
      const ing = books.length - fin;
      const fp = books.length? Math.round(fin/books.length*100):0;
      html += _card('阅读状态分布',
        '<div style="display:flex;gap:10px;margin-bottom:10px">'
        + '<div style="flex:1;background:var(--wr-bg);border-radius:10px;padding:10px;text-align:center"><div style="font-size:11px;color:var(--wr-sub)">读完</div><div style="font-size:22px;font-weight:600;color:var(--wr-main)">'+fin+'</div><div style="font-size:10px;color:var(--wr-faint)">'+fp+'%</div></div>'
        + '<div style="flex:1;background:var(--wr-bg);border-radius:10px;padding:10px;text-align:center"><div style="font-size:11px;color:var(--wr-sub)">在读</div><div style="font-size:22px;font-weight:600;color:var(--wr-main)">'+ing+'</div><div style="font-size:10px;color:var(--wr-faint)">'+(100-fp)+'%</div></div>'
        + '</div>'
        + '<div style="height:8px;background:var(--wr-line);border-radius:4px;overflow:hidden"><div style="height:100%;width:'+fp+'%;background:var(--wr-main);border-radius:4px"></div></div>');
    }

    // ---- 读书卡 ----
    {
      let cards = '';
      books.forEach(function(b){
        const qs = (b.mark_items||[]).filter(function(x){ if(x.t){ const dt=new Date(x.t*1000); return dt.getFullYear()===Y && (dt.getMonth()+1)===M; } return false; }).slice(0,2);
        let qh = '';
        if(qs.length){ qh = qs.map(function(x){ return '<div style="font-size:11px;color:var(--wr-sub);line-height:1.6;padding:5px 9px;border-left:2px solid var(--wr-main);background:var(--wr-bg);margin-bottom:5px;border-radius:0 4px 4px 0">“'+_e(x.text)+'”</div>'; }).join(''); }
        else { qh = '<div style="font-size:11px;color:var(--wr-faint);padding:5px 0">本月尚未记录划线</div>'; }
        const status = b.finished ? '<span style="background:var(--wr-main);color:var(--wr-white);padding:2px 8px;border-radius:10px;font-size:10px">读完</span>' : '<span style="background:var(--wr-line);color:var(--wr-main);padding:2px 8px;border-radius:10px;font-size:10px">在读</span>';
        cards += '<div style="border:0.5px solid var(--wr-line);border-radius:12px;padding:13px 15px;background:var(--wr-white);margin-bottom:10px">'
          + '<div style="display:flex;align-items:center;gap:10px;margin-bottom:9px">'
          + (b.cover ? '<div style="width:42px;height:58px;flex-shrink:0;background-image:url(\''+_e(b.cover)+'\');background-size:cover;background-position:center;background-color:var(--wr-line);border-radius:5px"></div>' : '')
          + '<div style="flex:1;min-width:0"><div style="display:flex;align-items:center;gap:6px"><span style="font-size:14px;font-weight:600;color:var(--wr-main);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+_e(b.title)+'</span>'+status+'</div>'
          + '<div style="display:flex;align-items:center;gap:6px;margin-top:6px"><div style="flex:1;height:5px;background:var(--wr-line);border-radius:3px;overflow:hidden"><div style="height:100%;width:'+b.progress+'%;background:var(--wr-main);border-radius:3px"></div></div><span style="font-size:10px;color:var(--wr-sub);flex-shrink:0">'+b.progress+'%</span></div>'
          + '<div style="font-size:10px;color:var(--wr-faint);margin-top:4px">'+_e(b.author)+' · 本月 '+_fmtSec(b.sec)+' · 划线 '+b.month_marks+' 条'+(b.hour_profile?' · 常读 '+_e(b.hour_profile):'')+'</div></div></div>'
          + qh + '</div>';
      });
      html += _card('本月读书卡', cards, books.length ? '' : '本月没有阅读记录');
    }

    root.innerHTML = html;
    bindThemeSel(root);
    // 左右等高：左列划线实测，超高则从底部移除；多次尝试 + 未布局估算兜底
    try {
      const lc = root.querySelector('[data-wr-lcol]');
      const rc = root.querySelector('[data-wr-rcol]');
      if (lc && rc) {
        const trim = function(){
          let maxH = rc.offsetHeight;
          if (!maxH) { maxH = 12 * 30 + 34 + 28; } // 容器未布局时的保守估算
          if (lc.offsetHeight > maxH) {
            const qs = Array.prototype.slice.call(lc.querySelectorAll('[data-wr-quote]'));
            for (let i = qs.length - 1; i >= 0; i--) {
              if (lc.offsetHeight <= maxH) break;
              if (qs[i] && qs[i].parentNode) qs[i].parentNode.removeChild(qs[i]);
            }
          }
        };
        requestAnimationFrame(trim);
        setTimeout(trim, 150);
        setTimeout(trim, 500);
      }
    } catch (e) {}
  }
  main();
})();
"""


def build_report_js(y, mo, themes_js, cur_key, data_ym=None):
    """返回某月月报的完整 dataviewjs 代码字符串"""
    ym = data_ym or f"{y:04d}-{mo:02d}"
    js = (THEME_JS + "\n" + CHART_HELPERS + "\n" + RENDER_JS)
    js = (js.replace("__THEMES__", themes_js)
            .replace("__CUR__", cur_key)
            .replace("__YM__", ym)
            .replace("__YEAR__", str(y))
            .replace("__MONTH__", str(mo)))
    return js


def build_report_md(y, mo, themes_js, cur_key, data_ym=None):
    """返回某月月报的 md 完整内容（dataviewjs 代码块）"""
    return "```dataviewjs\n" + build_report_js(y, mo, themes_js, cur_key, data_ym) + "\n```\n"
