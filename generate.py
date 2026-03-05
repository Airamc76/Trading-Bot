"""
generate.py — Genera el dashboard HTML estático
GitHub Pages publica este archivo automáticamente.
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

# Sin subcarpetas — todo en la raíz
from database import initialize_database, get_dashboard_data


def generate():
    initialize_database()
    data      = get_dashboard_data()
    data_json = json.dumps(data, default=str, ensure_ascii=False)
    html      = build_html(data_json)

    Path("site").mkdir(exist_ok=True)
    Path("site/index.html").write_text(html, encoding="utf-8")

    print(f"✅ Dashboard generado → site/index.html")
    print(f"   Balance: ${data['balance']:,.2f} | "
          f"Win Rate: {data['win_rate']}% | "
          f"Trades: {data['total_trades']}")


def build_html(data_json: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>Trading Bot — Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{{
  --bg:#04080f;--s1:#080f1a;--s2:#0c1422;--border:#16243a;
  --cyan:#00e5ff;--gold:#ffd000;--green:#00ff88;--red:#ff3b5c;
  --text:#c8d8e8;--muted:#3d5a7a;
  --mono:'IBM Plex Mono',monospace;--sans:'IBM Plex Sans',sans-serif;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:var(--sans);min-height:100vh}}
body::after{{
  content:'';position:fixed;inset:0;pointer-events:none;z-index:999;
  background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,.06) 2px,rgba(0,0,0,.06) 4px);
}}
.page{{max-width:1320px;margin:0 auto;padding:20px 24px}}

/* HEADER */
.header{{
  display:flex;align-items:center;justify-content:space-between;
  padding:18px 24px;margin-bottom:24px;
  background:var(--s1);border:1px solid var(--border);
  border-top:2px solid var(--cyan);border-radius:0 0 12px 12px;
}}
.hlogo{{display:flex;align-items:center;gap:16px}}
.hmark{{
  width:48px;height:48px;font-size:26px;
  background:linear-gradient(135deg,#001a2e,#003a5c);
  border:1px solid var(--cyan);border-radius:10px;
  display:flex;align-items:center;justify-content:center;
}}
.htitle{{font-family:var(--mono);font-size:16px;font-weight:700;color:var(--cyan);letter-spacing:2px}}
.hsub{{font-size:12px;color:var(--muted);margin-top:3px}}
.hright{{text-align:right}}
.hts{{font-family:var(--mono);font-size:11px;color:var(--muted)}}
.hts span{{color:var(--gold)}}
.live{{display:inline-flex;align-items:center;gap:6px;font-family:var(--mono);font-size:11px;color:var(--green);margin-top:4px}}
.live::before{{content:'';width:6px;height:6px;border-radius:50%;background:var(--green);animation:blink 1.4s infinite}}
@keyframes blink{{0%,100%{{opacity:1;box-shadow:0 0 6px var(--green)}}50%{{opacity:.2;box-shadow:none}}}}

/* KPIs */
.kpis{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:20px}}
@media(max-width:900px){{.kpis{{grid-template-columns:repeat(2,1fr)}}}}
.kpi{{background:var(--s2);border:1px solid var(--border);border-radius:10px;padding:20px 22px;position:relative;overflow:hidden;transition:border-color .2s,transform .15s;cursor:default}}
.kpi:hover{{border-color:var(--cyan);transform:translateY(-1px)}}
.ka{{position:absolute;top:0;left:0;width:3px;height:100%;border-radius:10px 0 0 10px}}
.ka.c{{background:var(--cyan)}}.ka.g{{background:var(--green)}}.ka.r{{background:var(--red)}}.ka.y{{background:var(--gold)}}
.klabel{{font-family:var(--mono);font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px}}
.kval{{font-family:var(--mono);font-size:30px;font-weight:700;line-height:1}}
.kval.c{{color:var(--cyan)}}.kval.g{{color:var(--green)}}.kval.r{{color:var(--red)}}.kval.y{{color:var(--gold)}}
.ksub{{font-size:11px;color:var(--muted);margin-top:8px}}

/* GRID */
.g2{{display:grid;grid-template-columns:1fr 340px;gap:16px;margin-bottom:16px}}
.g2b{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
@media(max-width:1100px){{.g2{{grid-template-columns:1fr}}}}
@media(max-width:800px){{.g2b{{grid-template-columns:1fr}}}}

/* PANEL */
.panel{{background:var(--s2);border:1px solid var(--border);border-radius:10px;overflow:hidden}}
.ph{{padding:14px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;background:var(--s1)}}
.phtitle{{font-family:var(--mono);font-size:11px;font-weight:700;color:var(--text);text-transform:uppercase;letter-spacing:1.5px}}
.phsub{{font-size:11px;color:var(--muted);margin-left:auto}}
.pb{{padding:18px 20px}}

/* CHART */
.cbox{{height:200px;position:relative}}

/* SIGNALS */
.slist{{display:flex;flex-direction:column;gap:7px}}
.sitem{{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:var(--s1);border:1px solid var(--border);border-radius:8px;transition:border-color .15s}}
.sitem:hover{{border-color:var(--cyan)}}
.spair{{font-family:var(--mono);font-size:13px;font-weight:700}}
.sts{{font-size:10px;color:var(--muted);margin-top:2px}}
.dbadge{{font-family:var(--mono);font-size:10px;font-weight:700;padding:3px 10px;border-radius:4px;letter-spacing:.5px}}
.dBUY{{background:rgba(0,255,136,.1);color:var(--green);border:1px solid rgba(0,255,136,.2)}}
.dSELL{{background:rgba(255,59,92,.1);color:var(--red);border:1px solid rgba(255,59,92,.2)}}
.dNEUTRAL{{background:rgba(61,90,122,.2);color:var(--muted);border:1px solid var(--border)}}
.sscore{{font-family:var(--mono);font-size:13px;color:var(--gold);font-weight:600}}
.ssent{{font-size:10px;margin-left:8px}}

/* TABLE */
.tw{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{padding:9px 14px;text-align:left;font-family:var(--mono);font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid var(--border);background:var(--s1)}}
td{{padding:11px 14px;border-bottom:1px solid rgba(22,36,58,.6)}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:rgba(0,229,255,.02)}}
.tm{{font-family:var(--mono);font-size:11px}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-family:var(--mono);font-size:10px;font-weight:700}}
.bWIN{{background:rgba(0,255,136,.1);color:var(--green);border:1px solid rgba(0,255,136,.15)}}
.bLOSS{{background:rgba(255,59,92,.1);color:var(--red);border:1px solid rgba(255,59,92,.15)}}
.bOPEN{{background:rgba(0,229,255,.1);color:var(--cyan);border:1px solid rgba(0,229,255,.15)}}

/* DONUT */
.dw{{display:flex;align-items:center;gap:24px}}
.dc{{width:110px;height:110px;flex-shrink:0}}
.ds{{flex:1}}
.drow{{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--border);font-size:12px}}
.drow:last-child{{border-bottom:none}}
.dlabel{{display:flex;align-items:center;gap:8px;color:var(--muted)}}
.ddot{{width:8px;height:8px;border-radius:50%}}

.empty{{text-align:center;padding:40px 20px;color:var(--muted);font-size:12px}}
.empty-icon{{font-size:32px;margin-bottom:10px;opacity:.5}}

footer{{text-align:center;padding:20px;font-size:11px;color:var(--muted);font-family:var(--mono);border-top:1px solid var(--border);margin-top:20px}}
footer span{{color:var(--cyan)}}
/* LESSONS */
.litem{{padding:12px;border-bottom:1px solid var(--border);font-size:11px}}
.litem:last-child{{border-bottom:none}}
.lts{{color:var(--muted);font-size:9px;margin-bottom:4px;display:flex;justify-content:space-between}}
.ltext{{line-height:1.4;color:#eee}}
.lscore{{color:var(--gold);font-weight:700}}

/* MACRO */
.mitem{{display:flex;align-items:center;justify-content:space-between;padding:12px;border-bottom:1px solid var(--border)}}
.mitem:last-child{{border-bottom:none}}
.mval{{font-family:var(--mono);font-size:12px;font-weight:700}}
.mbadge{{font-size:9px;padding:2px 6px;border-radius:4px;margin-left:8px}}
.mUP{{color:var(--green);border:1px solid rgba(0,255,136,.2);background:rgba(0,255,136,.05)}}
.mDOWN{{color:var(--red);border:1px solid rgba(255,59,92,.2);background:rgba(255,59,92,.05)}}
.mNEUTRAL{{color:var(--muted);border:1px solid var(--border);background:rgba(61,90,122,.1)}}
.risk-box{{text-align:center;padding:15px;border-radius:8px;margin-top:10px;font-weight:800;letter-spacing:1px;font-size:14px}}
.rHIGH{{background:rgba(0,255,136,.1);color:var(--green);border:1px solid var(--green)}}
.rLOW{{background:rgba(255,59,92,.1);color:var(--red);border:1px solid var(--red)}}
.rNEUTRAL{{background:var(--s1);color:var(--muted);border:1px solid var(--border)}}

/* BRAIN */
.brain-item{{padding:12px;border-bottom:1px solid var(--border);position:relative}}
.brain-item:last-child{{border-bottom:none}}
.brain-cat{{font-family:var(--mono);font-size:9px;color:var(--gold);text-transform:uppercase;margin-bottom:4px}}
.brain-note{{font-size:11px;line-height:1.4}}
.brain-impact{{position:absolute;right:12px;top:12px;width:6px;height:6px;border-radius:50%}}
.iPOSITIVE{{background:var(--green);box-shadow:0 0 5px var(--green)}}
.iNEGATIVE{{background:var(--red);box-shadow:0 0 5px var(--red)}}
.iNEUTRAL{{background:var(--muted)}}

/* WISHES */
.wish-item{{display:flex;align-items:center;gap:12px;padding:10px;background:rgba(0,229,255,0.03);border:1px solid var(--border);border-radius:6px;margin-bottom:8px}}
.wish-icon{{font-size:16px}}
.wish-text{{font-size:11px;font-weight:500;color:var(--cyan)}}

/* PULSE */
.pulse-item{{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;font-size:10px;border-bottom:1px solid var(--border)}}
.pulse-item:last-child{{border-bottom:none}}
.pdot{{width:6px;height:6px;border-radius:50%;margin-right:8px;display:inline-block}}
.pSUCCESS{{background:var(--green);box-shadow:0 0 5px var(--green)}}
.pRUNNING{{background:var(--gold);box-shadow:0 0 5px var(--gold);animation: blink 1s infinite}}
@keyframes blink {{ 0%{{opacity:1}} 50%{{opacity:0.3}} 100%{{opacity:1}} }}

/* LOGS */
.log-container{{
  font-family:var(--mono);font-size:10px;height:340px;overflow-y:auto;
  background:var(--s1);padding:12px;border:1px solid var(--border);
  scrollbar-width: thin; scrollbar-color: var(--border) transparent;
}}
.log-container::-webkit-scrollbar {{ width: 6px; }}
.log-container::-webkit-scrollbar-track {{ background: transparent; }}
.log-container::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 10px; }}

.log-line{{
  margin-bottom:6px;padding-bottom:6px;border-bottom:1px solid rgba(255,255,255,0.02);
  display:flex;line-height:1.5;
}}
.log-ts{{color:var(--muted);min-width:75px;flex-shrink:0}}
.log-lvl{{width:48px;font-weight:700;margin-right:8px;flex-shrink:0}}
.l-INFO{{color:var(--cyan)}}
.l-WARNING{{color:var(--gold)}}
.l-ERROR{{color:var(--red)}}
.log-msg{{color:rgba(255,255,255,0.9);word-break:break-word}}
</style>
</head>
<body>
<div class="page">

<header class="header">
  <div class="hlogo">
    <div class="hmark">🤖</div>
    <div>
      <div class="htitle">TRADING BOT</div>
      <div class="hsub">Paper Trading · GitHub Actions + Turso</div>
    </div>
  </div>
  <div class="hright">
    <div class="hts">Actualizado: <span id="lastUpdate">...</span></div>
    <div class="live">ACTIVO 24/7</div>
  </div>
</header>

<div class="kpis" id="kpis"></div>

<div class="g2">
  <div class="panel">
    <div class="ph"><span>📈</span><span class="phtitle">Evolución del Balance</span><span class="phsub">demo USD</span></div>
    <div class="pb"><div class="cbox"><canvas id="balChart"></canvas></div></div>
  </div>
  <div class="panel">
    <div class="ph"><span>🔔</span><span class="phtitle">Últimas Señales</span></div>
    <div class="pb"><div class="slist" id="sigList"></div></div>
  </div>
</div>

<div class="g2b">
  <div class="panel">
    <div class="ph"><span>📋</span><span class="phtitle">Trades Recientes</span></div>
    <div class="tw">
      <table>
        <thead><tr><th>Par</th><th>Dir</th><th>Apertura</th><th>P&amp;L</th><th>Estado</th><th>Fecha</th></tr></thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
  </div>
  <div class="panel">
    <div class="ph"><span>🎯</span><span class="phtitle">Win Rate</span></div>
    <div class="pb">
      <div class="dw">
        <div class="dc"><canvas id="wrChart"></canvas></div>
        <div class="ds" id="dstats"></div>
      </div>
    </div>
  </div>
  <div class="panel">
    <div class="ph"><span>🧠</span><span class="phtitle">Diario de Aprendizaje</span><span class="phsub">Feedback Engine</span></div>
    <div class="pb"><div id="lessonFeed"></div></div>
  </div>
  <div class="panel">
    <div class="ph"><span>📠</span><span class="phtitle">Cerebro del Bot</span><span class="phsub">IA Consciousness</span></div>
    <div class="pb"><div id="brainFeed"></div></div>
  </div>
  <div class="panel">
    <div class="ph"><span>💡</span><span class="phtitle">Peticiones de la IA</span><span class="phsub">Autonomous Requests</span></div>
    <div class="pb"><div id="wishFeed"></div></div>
  </div>
  <div class="panel">
    <div class="ph"><span>🌍</span><span class="phtitle">Inteligencia Macro</span><span class="phsub">Global Context</span></div>
    <div class="pb" id="macroBox"></div>
  </div>
  <div class="panel">
    <div class="ph"><span>⚡</span><span class="phtitle">Pulso del Sistema</span><span class="phsub">Activity Heartbeat</span></div>
    <div class="pb" id="pulseBox"></div>
  </div>
  <div class="panel" style="grid-column: 1 / -1">
    <div class="ph"><span>📠</span><span class="phtitle">Registro de Actividad</span><span class="phsub">Live Console Logs</span></div>
    <div class="pb"><div class="log-container" id="logBox"></div></div>
  </div>
</div>

</div>
<footer>🤖 Trading Bot · Paper Trading · <span>Sin dinero real</span> · Próxima actualización ~15 min</footer>

<script>
const D = {data_json};
const f=(n,d=2)=>n==null?'—':Number(n).toLocaleString('es-AR',{{minimumFractionDigits:d,maximumFractionDigits:d}});
const fd=ts=>{{if(!ts)return'—';try{{return new Date(ts).toLocaleString('es-AR',{{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}})}}catch{{return String(ts).slice(0,16)}}}};

// Update header time
document.getElementById('lastUpdate').innerText = fd(D.last_updated);

// KPIs
(()=>{{
  const ret=D.balance?((D.balance-10000)/10000*100):0;
  document.getElementById('kpis').innerHTML=`
    <div class="kpi"><div class="ka c"></div><div class="klabel">💰 Balance Demo</div><div class="kval c">$${{f(D.balance)}}</div><div class="ksub">Inicial: $10,000</div></div>
    <div class="kpi"><div class="ka ${{ret>=0?'g':'r'}}"></div><div class="klabel">📊 Retorno</div><div class="kval ${{ret>=0?'g':'r'}}">${{ret>=0?'+':''}}${{f(ret)}}%</div><div class="ksub">P&L: $${{f(D.total_pnl)}}</div></div>
    <div class="kpi"><div class="ka y"></div><div class="klabel">🎯 Win Rate</div><div class="kval y">${{f(D.win_rate,1)}}%</div><div class="ksub">${{D.wins}}W / ${{D.losses}}L</div></div>
    <div class="kpi"><div class="ka c"></div><div class="klabel">📈 Trades</div><div class="kval c">${{D.total_trades}}</div><div class="ksub">${{D.open_trades}} abiertos</div></div>
    <div class="kpi" id="sentKpi"></div>
  `;
  
  // Calculate average sentiment
  const sigs = D.signals || [];
  const avgSent = sigs.length ? sigs.reduce((a,b)=>a+(Number(b.sentiment)||0), 0) / sigs.length : 0;
  const sentColor = avgSent > 0.1 ? 'g' : avgSent < -0.1 ? 'r' : 'y';
  const sentLabel = avgSent > 0.4 ? 'MUY ALCISTA' : avgSent > 0.1 ? 'ALCISTA' : avgSent < -0.4 ? 'MUY BAJISTA' : avgSent < -0.1 ? 'BAJISTA' : 'NEUTRAL';
  
  document.getElementById('sentKpi').innerHTML = `
    <div class="ka ${{sentColor}}"></div>
    <div class="klabel">🎭 Sentimiento</div>
    <div class="kval ${{sentColor}}">${{sentLabel}}</div>
    <div class="ksub">Score: ${{avgSent.toFixed(2)}} (Promedio)</div>
  `;
}})();

// Balance chart
(()=>{{
  const h=D.balance_history||[];if(!h.length)return;
  new Chart(document.getElementById('balChart'),{{type:'line',data:{{labels:h.map(x=>fd(x.timestamp)),datasets:[{{data:h.map(x=>parseFloat(x.balance)),borderColor:'#00e5ff',backgroundColor:'rgba(0,229,255,0.05)',borderWidth:1.5,pointRadius:0,fill:true,tension:0.4}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{display:false}},y:{{grid:{{color:'rgba(22,36,58,1)'}},ticks:{{color:'#3d5a7a',font:{{family:'IBM Plex Mono',size:10}},callback:v=>'$'+v.toLocaleString()}}}}}}}}}});
}})();

// Señales
(()=>{{
  const el=document.getElementById('sigList'),s=D.signals||[];
  el.innerHTML=!s.length?'<div class="empty"><div class="empty-icon">📡</div><p>Esperando señales...</p></div>':s.slice(0,10).map(x=>{{
    const sentIcon = x.sentiment > 0.1 ? '📈' : x.sentiment < -0.1 ? '📉' : '➖';
    return `<div class="sitem"><div><div class="spair">${{x.pair}} <span class="ssent" title="Sentimiento: ${{Number(x.sentiment).toFixed(2)}}">${{sentIcon}}</span></div><div class="sts">${{fd(x.timestamp)}}</div></div><span class="dbadge d${{x.direction}}">${{x.direction}}</span><div class="sscore">${{f(x.score,1)}}/10</div></div>`;
  }}).join('');
}})();

// Trades
(()=>{{
  const tb=document.getElementById('tbody'),t=D.trades||[];
  if(!t.length){{tb.innerHTML='<tr><td colspan="6"><div class="empty"><div class="empty-icon">📋</div><p>Sin trades aún</p></div></td></tr>';return;}}
  tb.innerHTML=t.slice(0,12).map(x=>{{
    const p=x.pnl!=null?`<span class="tm" style="color:${{Number(x.pnl)>=0?'var(--green)':'var(--red)'}}">${{Number(x.pnl)>=0?'+':''}}$${{f(x.pnl)}}</span>`:'<span style="color:var(--muted)">—</span>';
    return`<tr><td class="tm">${{x.pair}}</td><td><span class="badge b${{x.direction==='BUY'?'WIN':'LOSS'}}">${{x.direction}}</span></td><td class="tm">$${{f(x.open_price,4)}}</td><td>${{p}}</td><td><span class="badge b${{status}}">${{x.status}}</span></td><td style="color:var(--muted);font-size:11px">${{fd(x.open_time)}}</td></tr>`;
  }}).join('');
}})();

// Donut
(()=>{{
  const w=D.wins||0,l=D.losses||0,tot=w+l;
  if(!tot){{document.getElementById('dstats').innerHTML='<div style="color:var(--muted);font-size:12px;padding:8px">Sin trades cerrados aún</div>';return;}}
  new Chart(document.getElementById('wrChart'),{{type:'doughnut',data:{{labels:['Ganados','Perdidos'],datasets:[{{data:[w,l],backgroundColor:['rgba(0,255,136,0.75)','rgba(255,59,92,0.75)'],borderColor:['#00ff88','#ff3b5c'],borderWidth:1}}]}},options:{{cutout:'74%',plugins:{{legend:{{display:false}}}}}}}});
  document.getElementById('dstats').innerHTML=`
    <div class="drow"><div class="dlabel"><div class="ddot" style="background:var(--green)"></div>Ganadores</div><div style="color:var(--green);font-family:var(--mono);font-weight:600">${{w}} (${{f(w/tot*100,1)}}%)</div></div>
    <div class="drow"><div class="dlabel"><div class="ddot" style="background:var(--red)"></div>Perdedores</div><div style="color:var(--red);font-family:var(--mono);font-weight:600">${{l}} (${{f(l/tot*100,1)}}%)</div></div>
    <div class="drow"><div class="dlabel"><div class="ddot" style="background:var(--cyan)"></div>Abiertos</div><div style="font-family:var(--mono);font-weight:600">${{D.open_trades}}</div></div>
  `;
}})();

// Lessons
(()=>{{
  const el=document.getElementById('lessonFeed'),t=D.trades||[];
  const lessons = t.filter(x=>x.lesson);
  if(!lessons.length){{el.innerHTML='<div class="empty"><div class="empty-icon">🧠</div><p>Esperando cierre de trades para generar aprendizaje...</p></div>';return;}}
  el.innerHTML=lessons.slice(0,5).map(x=>`
    <div class="litem">
      <div class="lts"><span>${{fd(x.open_time)}} — ${{x.pair}}</span><span class="lscore">${{f(x.performance_score,1)}}/10</span></div>
      <div class="ltext">${{x.lesson}}</div>
    </div>
  `).join('');
}})();

// Macro
(()=>{{
  const el=document.getElementById('macroBox'), m=D.macro;
  if(!m){{el.innerHTML='<div class="empty"><div class="empty-icon">🌍</div><p>Sincronizando datos macro...</p></div>';return;}}
  
  el.innerHTML=`
    <div class="mitem">
      <div><div style="font-size:12px;font-weight:600">DXY (Dollar Index)</div><div style="font-size:10px;color:var(--muted)">Inversamente correlacionado</div></div>
      <div class="mval">${{f(m.dxy_val)}} <span class="mbadge m${{m.dxy_trend}}">${{m.dxy_trend}}</span></div>
    </div>
    <div class="mitem">
      <div><div style="font-size:12px;font-weight:600">Nasdaq 100</div><div style="font-size:10px;color:var(--muted)">Correlación con riesgo</div></div>
      <div class="mval">${{f(m.nasdaq_val,0)}} <span class="mbadge m${{m.nasdaq_trend}}">${{m.nasdaq_trend}}</span></div>
    </div>
    <div class="risk-box r${{m.risk_appetite}}">
      APETITO POR EL RIESGO: ${{m.risk_appetite}}
    </div>
    <div style="font-size:9px;color:var(--muted);text-align:center;margin-top:10px">
      Sincronizado: ${{fd(m.timestamp)}}
    </div>
  `;
}})();

// Pulse
(()=>{{
  const el=document.getElementById('pulseBox'), hb=D.heartbeats||[];
  if(!hb.length){{el.innerHTML='<div class="empty">Esperando pulso...</div>';return;}}
  
  el.innerHTML = hb.map(h => `
    <div class="pulse-item">
      <div><span class="pdot p${{h.status}}"></span><span style="font-weight:600">${{h.status}}</span></div>
      <div style="color:var(--muted);font-size:9px">${{h.note}}</div>
      <div style="font-family:var(--mono);opacity:0.8">${{fd(h.timestamp).split(',')[1]}}</div>
    </div>
  `).join('');
}})();

// Bot Brain
(()=>{{
  const el=document.getElementById('brainFeed'), m=D.bot_memory||[];
  if(!m.length){{el.innerHTML='<div class="empty">La IA aún no ha generado reflexiones...</div>';return;}}
  el.innerHTML = m.map(x => `
    <div class="brain-item">
      <div class="brain-cat">${{x.category}}</div>
      <div class="brain-impact i${{x.impact}}"></div>
      <div class="brain-note">${{x.note}}</div>
      <div style="font-size:8px;color:var(--muted);margin-top:6px">${{fd(x.timestamp)}}</div>
    </div>
  `).join('');
}})();

// Bot Wishes
(()=>{{
  const el=document.getElementById('wishFeed'), w=D.bot_wishes||[];
  if(!w.length){{el.innerHTML='<div class="empty">No hay peticiones pendientes.</div>';return;}}
  el.innerHTML = w.map(x => `
    <div class="wish-item">
      <div class="wish-icon">${{x.status === 'ACTION' ? '⚡' : '💡'}}</div>
      <div class="wish-text">${{x.wish}}</div>
    </div>
  `).join('');
}})();

// Activity Logs
(()=>{{
  const el=document.getElementById('logBox'), logs=D.system_logs||[];
  if(!logs.length){{el.innerHTML='<div class="empty">Esperando registros...</div>';return;}}
  
  el.innerHTML = logs.map(l => `
    <div class="log-line">
      <div class="log-ts">${{fd(l.timestamp).split(',')[1]}}</div>
      <div class="log-lvl l-${{l.level}}">[${{l.level}}]</div>
      <div class="log-msg">${{l.message}}</div>
    </div>
  `).join('');
}})();
</script>
</body></html>"""


if __name__ == "__main__":
    generate()
