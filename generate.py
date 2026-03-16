"""
generate.py — Genera el dashboard HTML estático
GitHub Pages publica este archivo automáticamente.
"""
import sys
import json
import re
from pathlib import Path
from datetime import datetime, timezone

from database import initialize_database, get_dashboard_data


def generate():
    initialize_database()
    from database import USE_TURSO
    print(f"DEBUG: USE_TURSO={USE_TURSO}")
    data      = get_dashboard_data()
    print(f"DEBUG: Trade count in data={len(data.get('trades', []))}")
    data_json = json.dumps(data, default=str, ensure_ascii=False)
    html      = build_html(data_json, data)

    Path("site").mkdir(exist_ok=True)
    Path("site/index.html").write_text(html, encoding="utf-8")

    print(f"✅ Dashboard generado → site/index.html ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC)")
    print(f"   Balance: ${data['balance']:,.2f} | "
          f"Win Rate: {data['win_rate']}% | "
          f"Trades: {data['total_trades']}")


def build_html(data_json: str, data: dict) -> str:
    health = data.get("health", {})
    status = health.get("status", "OK")
    h_class = status
    h_text = "SISTEMA SALUDABLE" if status == "OK" else ("AVISO DE RED" if status == "WARNING" else "BOT DESCONECTADO")
    
    last_hb = health.get("last_heartbeat", "---")
    if last_hb and "T" in last_hb:
        last_hb = last_hb.split("T")[1][:5]

    err_24h = health.get("errors_24h", 0)
    act_24h = health.get("actions_24h", 0)

    memory = data.get("bot_memory", [])
    last_llm = next((x for x in memory if x.get("category") == "LLM_REASONING"), None)
    
    md_thought = "El Managing Director está analizando los datos actuales del mercado..."
    md_model = "MD"
    md_time = ""

    if last_llm:
        note = last_llm.get("note", "")
        import re
        md_thought = re.sub(r'^\[.*?\]\s*', '', note)
        m = re.match(r'^\[(.*?)\]', note)
        md_model = m.group(1) if m else "IA"
        
        ts = last_llm.get("timestamp")
        if ts and "T" in ts:
            md_time = ts.split("T")[1][:5]

    config = data.get("bot_config", {})
    is_paused       = config.get("paused", False)
    is_signal_only  = config.get("signal_only", False)
    paused_pairs_count = len(config.get("paused_pairs", "").split(",")) if config.get("paused_pairs") else 0

    return f"""<!DOCTYPE html>
<html lang="es" class="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>Apex Trading — AI Director</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script src="https://cdn.tailwindcss.com"></script>
<script>
  tailwind.config = {{
    darkMode: 'class',
    theme: {{
      extend: {{
        fontFamily: {{ sans: ['Inter', 'sans-serif'], mono: ['JetBrains Mono', 'monospace'] }},
        colors: {{
          dark: '#050b14', panel: 'rgba(13, 22, 38, 0.65)', border_light: 'rgba(255,255,255,0.08)',
          accent: '#00e5ff', pos: '#00ff88', neg: '#ff3b5c', warn: '#ffd000'
        }}
      }}
    }}
  }}
</script>
<style>
  body {{ background: #050b14; color: #cbd5e1; min-height: 100vh; position: relative; }}
  body::before {{ content: ''; position: fixed; inset: 0; pointer-events: none; z-index: -1;
    background: radial-gradient(circle at 50% 0%, rgba(0, 229, 255, 0.08) 0vw, transparent 50vw),
                radial-gradient(circle at 100% 100%, rgba(0, 255, 136, 0.05) 0vw, transparent 40vw); }}
  .glass-panel {{ background: var(--panel); backdrop-filter: blur(16px); border: 1px solid var(--border_light); border-radius: 16px; box-shadow: 0 8px 32px rgba(0,0,0,0.3); overflow: hidden; transition: transform 0.2s, box-shadow 0.2s; }}
  .glass-panel:hover {{ box-shadow: 0 12px 40px rgba(0,229,255,0.08); border-color: rgba(0,229,255,0.2); }}
  .panel-header {{ padding: 14px 20px; border-bottom: 1px solid var(--border_light); background: rgba(0,0,0,0.2); display: flex; align-items: center; gap: 10px; }}
  .panel-title {{ font-family: 'JetBrains Mono'; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: #f8fafc; }}
  .panel-body {{ padding: 20px; }}
  
  .badge {{ padding: 3px 8px; border-radius: 6px; font-family: 'JetBrains Mono'; font-size: 10px; font-weight: 700; border: 1px solid transparent; }}
  .bWIN, .bBUY, .mUP {{ background: rgba(0,255,136,0.1); color: var(--pos); border-color: rgba(0,255,136,0.2); }}
  .bLOSS, .bSELL, .mDOWN {{ background: rgba(255,59,92,0.1); color: var(--neg); border-color: rgba(255,59,92,0.2); }}
  .bOPEN {{ background: rgba(0,229,255,0.1); color: var(--accent); border-color: rgba(0,229,255,0.2); }}
  
  .custom-scroll::-webkit-scrollbar {{ width: 6px; }}
  .custom-scroll::-webkit-scrollbar-track {{ background: transparent; }}
  .custom-scroll::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.1); border-radius: 10px; }}
  .custom-scroll::-webkit-scrollbar-thumb:hover {{ background: rgba(0,229,255,0.5); }}

  table th {{ font-family: 'JetBrains Mono'; font-size: 10px; text-transform: uppercase; color: #64748b; font-weight: 600; padding-bottom: 10px; text-align: left; }}
  table td {{ padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.04); font-size: 13px; }}
  tr:last-child td {{ border-bottom: none; }}
  
  .pulse-dot {{ width: 8px; height: 8px; border-radius: 50%; background: var(--pos); box-shadow: 0 0 10px var(--pos); animation: pulse 2s infinite; }}
  @keyframes pulse {{ 0% {{ opacity: 1; transform: scale(1); }} 50% {{ opacity: 0.4; transform: scale(1.2); }} 100% {{ opacity: 1; transform: scale(1); }} }}
  
  .md-box {{ background: linear-gradient(135deg, rgba(8,15,26,0.8), rgba(12,26,45,0.9)); border: 1px solid rgba(0,229,255,0.3); box-shadow: inset 0 0 20px rgba(0,229,255,0.05); }}
  .glow-text {{ text-shadow: 0 0 10px currentColor; }}
</style>
</head>
<body class="antialiased selection:bg-accent selection:text-black">

<div class="max-w-[1400px] mx-auto p-4 md:p-6 lg:p-8 space-y-6">

  <!-- HEADER -->
  <header class="glass-panel animate__animated animate__fadeInDown">
    <div class="flex flex-col md:flex-row items-center justify-between p-5 md:p-6 bg-gradient-to-r from-transparent via-[rgba(0,229,255,0.03)] to-transparent border-t-2 border-t-accent">
      <div class="flex items-center gap-5">
        <div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-[#0c1a30] to-[#040810] border border-accent flex items-center justify-center text-3xl shadow-[0_0_20px_rgba(0,229,255,0.2)]">🤖</div>
        <div>
          <h1 class="font-mono text-xl font-extrabold tracking-widest text-accent glow-text">APEX AI DIRECTOR</h1>
          <p class="text-xs text-slate-400 mt-1 font-medium">Turso DB · GitHub Actions · Llama 3.3 70B</p>
        </div>
      </div>
      <div class="text-right mt-4 md:mt-0">
        <div class="font-mono text-xs tracking-wider text-slate-400">SYNC: <span id="lastUpdate" class="text-warn font-bold">...</span></div>
        <div class="flex items-center justify-end gap-2 mt-2">
          <div class="pulse-dot"></div>
          <span class="font-mono text-xs font-bold text-pos tracking-wide">SYSTEM ONLINE</span>
        </div>
      </div>
    </div>
  </header>

  <!-- SIGNAL BANNERS -->
  {'''<div class="glass-panel animate__animated animate__fadeIn relative overflow-hidden bg-warn/5 border-warn/30">
        <div class="absolute left-0 top-0 bottom-0 w-1 bg-warn"></div>
        <div class="p-4 flex items-center gap-4">
            <div class="text-2xl">📊</div>
            <div>
                <h3 class="font-mono text-warn font-bold text-sm tracking-wide">MODO SEÑAL ACTIVO</h3>
                <p class="text-xs text-slate-400 mt-1">El bot NO ejecuta trades automáticamente. Envia señales por Telegram.</p>
            </div>
        </div>
    </div>''' if is_signal_only else ''}

  <!-- KPIs -->
  <div class="grid grid-cols-2 lg:grid-cols-4 gap-4" id="kpis"></div>

  <!-- MAIN GRID -->
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
    
    <!-- BALANCE CHART -->
    <div class="glass-panel lg:col-span-2 animate__animated animate__fadeInUp" style="animation-delay: 0.1s;">
      <div class="panel-header">
        <span class="text-lg">📈</span><h2 class="panel-title">Evolución del Balance</h2>
        <span class="text-xs text-slate-500 ml-auto font-mono">USD DEMO</span>
      </div>
      <div class="panel-body h-[280px]">
        <canvas id="balChart"></canvas>
      </div>
    </div>

    <!-- AI DIRECTOR PANEL -->
    <div class="glass-panel md-box flex flex-col animate__animated animate__fadeInUp" style="animation-delay: 0.2s;">
      <div class="p-5 flex-1 flex flex-col">
        <div class="font-mono text-xs text-warn font-bold tracking-widest mb-4 flex items-center gap-2">
          <span class="text-base">🧠</span> MANAGING DIRECTOR
        </div>
        
        <div class="flex items-center gap-3 mb-4">
          <span class="badge { 'bLOSS' if is_paused else 'bWIN' } px-3 py-1 text-xs">{ 'PAUSADO' if is_paused else 'OPERATIVO' }</span>
          <span class="badge border-warn/30 text-warn bg-warn/10">{ md_model }</span>
          <span class="font-mono text-xs text-slate-400 ml-auto">{ md_time }</span>
        </div>
        
        <div class="flex-1 bg-black/30 border border-white/5 rounded-xl p-4 mb-5 relative">
          <div class="absolute -left-1 top-4 bottom-4 w-1 bg-accent/50 rounded-r"></div>
          <p class="text-sm leading-relaxed text-slate-200 italic font-medium">"{ md_thought }"</p>
        </div>
        
        <div class="grid grid-cols-2 gap-3 mt-auto">
          <div class="bg-white/5 rounded-lg p-3 border border-white/5 hover:bg-white/10 transition-colors">
            <div class="text-[9px] font-mono text-slate-500 mb-1 tracking-wider uppercase">Estrategia</div>
            <div class="font-mono text-xs font-bold text-accent truncate">{ config.get('strategy', '---') }</div>
          </div>
          <div class="bg-white/5 rounded-lg p-3 border border-white/5 hover:bg-white/10 transition-colors">
            <div class="text-[9px] font-mono text-slate-500 mb-1 tracking-wider uppercase">Score Mínimo</div>
            <div class="font-mono text-xs font-bold text-white"><span class="text-accent">{ config.get('min_score', '5.0') }</span> / 10</div>
          </div>
          <div class="bg-white/5 rounded-lg p-3 border border-white/5 hover:bg-white/10 transition-colors">
            <div class="text-[9px] font-mono text-slate-500 mb-1 tracking-wider uppercase">Riesgo / ATR</div>
            <div class="font-mono text-xs font-bold text-warn">{ config.get('sl_atr', '1.2') }x</div>
          </div>
          <div class="bg-white/5 rounded-lg p-3 border border-white/5 hover:bg-white/10 transition-colors">
            <div class="text-[9px] font-mono text-slate-500 mb-1 tracking-wider uppercase">Pares Pausados</div>
            <div class="font-mono text-xs font-bold text-neg">{ paused_pairs_count }</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
    <!-- TRADES TABLE -->
    <div class="glass-panel lg:col-span-2 animate__animated animate__fadeInUp" style="animation-delay: 0.3s;">
      <div class="panel-header justify-between">
        <div class="flex items-center gap-2"><span class="text-lg">📋</span><h2 class="panel-title">Trades Recientes</h2></div>
      </div>
      <div class="panel-body overflow-x-auto">
        <table class="w-full text-left">
          <thead><tr><th>Par</th><th>Dir</th><th>Entrada</th><th>P&L</th><th>Estado</th><th>Cierre/Apertura</th></tr></thead>
          <tbody id="tbody"></tbody>
        </table>
      </div>
    </div>

    <!-- WIN RATE DONUT -->
    <div class="glass-panel flex flex-col animate__animated animate__fadeInUp" style="animation-delay: 0.4s;">
      <div class="panel-header"><span class="text-lg">🎯</span><h2 class="panel-title">Precisión</h2></div>
      <div class="panel-body flex-1 flex flex-col justify-center">
        <div class="flex items-center gap-6">
          <div class="w-28 h-28 shrink-0 relative">
            <canvas id="wrChart"></canvas>
            <div class="absolute inset-0 flex items-center justify-center font-mono font-bold text-xl text-white" id="wrCenter"></div>
          </div>
          <div class="flex-1 space-y-3" id="dstats"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- SECONDARY ROW -->
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
    <!-- MARKET MONITOR -->
    <div class="glass-panel flex flex-col animate__animated animate__fadeInUp" style="animation-delay: 0.5s;">
      <div class="panel-header"><span class="text-base">🔎</span><h2 class="panel-title">Radar Mercado</h2></div>
      <div class="panel-body p-3 flex-1 custom-scroll overflow-y-auto max-h-[300px] space-y-2" id="marketMonitor"></div>
    </div>
    
    <!-- MACRO -->
    <div class="glass-panel flex flex-col animate__animated animate__fadeInUp" style="animation-delay: 0.6s;">
      <div class="panel-header"><span class="text-base">🌍</span><h2 class="panel-title">Macro Contexto</h2></div>
      <div class="panel-body flex-1 flex flex-col justify-around" id="macroBox"></div>
    </div>

    <!-- STRATEGY PERF -->
    <div class="glass-panel lg:col-span-2 flex flex-col animate__animated animate__fadeInUp" style="animation-delay: 0.8s;">
      <div class="panel-header"><span class="text-base">🔬</span><h2 class="panel-title">Rendimiento por Estrategia</h2></div>
      <div class="panel-body p-0 custom-scroll overflow-y-auto max-h-[300px]" id="stratBox"></div>
    </div>
  </div>

</div>

<footer class="text-center py-8 font-mono text-[10px] text-slate-500 border-t border-border_light mt-8">
  <p>🚀 APEX AI DIRECTOR v2.0 <span class="mx-2">|</span> PAPER TRADING <span class="mx-2">|</span> <span class="text-accent glow-text">NO HAY DINERO REAL INVOLUCRADO</span></p>
</footer>

<script>
const D = {data_json};
const f=(n,d=2)=>n==null?'—':Number(n).toLocaleString('en-US',{{minimumFractionDigits:d,maximumFractionDigits:d}});
const fd=ts=>{{if(!ts)return'—';try{{return new Date(ts).toLocaleString('es-ES',{{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}})}}catch{{return String(ts).slice(0,16)}}}};

document.getElementById('lastUpdate').innerText = fd(D.last_updated);

// KPIs
(()=>{{
  const ret = D.balance ? ((D.balance-10000)/10000*100) : 0;
  const kpis = document.getElementById('kpis');
  
  const makeKpi = (icon, label, value, sub, colorClass, highlight=false) => `
    <div class="glass-panel relative ${{highlight?'bg-accent/5 border-accent/30':''}} group">
        ${{highlight ? '<div class="absolute inset-x-0 top-0 h-0.5 bg-accent shadow-[0_0_10px_#00e5ff]"></div>' : ''}}
        <div class="p-4 md:p-5">
            <div class="flex items-center gap-2 mb-2 text-slate-400">
                <span class="text-sm">${{icon}}</span>
                <span class="font-mono text-[10px] uppercase tracking-widest font-bold">${{label}}</span>
            </div>
            <div class="font-mono text-2xl md:text-3xl font-extrabold ${{colorClass}} tracking-tight transition-transform group-hover:scale-[1.02]">${{value}}</div>
            <div class="text-[10px] text-slate-500 mt-2 font-medium">${{sub}}</div>
        </div>
    </div>
  `;

  const retColor = ret >= 0 ? 'text-pos' : 'text-neg';
  
  kpis.innerHTML = `
    ${{makeKpi('💰', 'Balance Demo', '$'+f(D.balance), 'Inicial: $10,000', 'text-white', true)}}
    ${{makeKpi('📈', 'Retorno (P&L)', (ret>=0?'+':'')+f(ret)+'%', '$'+f(D.total_pnl), retColor)}}
    ${{makeKpi('🎯', 'Win Rate', f(D.win_rate, 1)+'%', D.wins+'W / '+D.losses+'L', 'text-warn')}}
    ${{makeKpi('📊', 'Total Trades', D.total_trades, D.open_trades+' Activos', 'text-accent')}}
  `;
}})();

// Chart Theme setup
Chart.defaults.color = '#64748b';
Chart.defaults.font.family = "'JetBrains Mono', monospace";

// Balance Chart
(()=>{{
  const h=D.balance_history||[]; 
  if(!h.length) return;
  const ctx = document.getElementById('balChart').getContext('2d');
  const gradient = ctx.createLinearGradient(0, 0, 0, 250);
  gradient.addColorStop(0, 'rgba(0, 229, 255, 0.4)');
  gradient.addColorStop(1, 'rgba(0, 229, 255, 0.0)');

  new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: h.map(x=>fd(x.timestamp)),
      datasets: [{{
        data: h.map(x=>parseFloat(x.balance)),
        borderColor: '#00e5ff', borderWidth: 2, pointRadius: 0, hoverPointRadius: 6,
        fill: true, backgroundColor: gradient, tension: 0.4
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }}, tooltip: {{ mode: 'index', intersect: false, backgroundColor: 'rgba(15,23,42,0.9)', titleColor: '#fff', bodyColor: '#00e5ff', padding: 10, borderColor: 'rgba(0,229,255,0.3)', borderWidth: 1 }} }},
      scales: {{
        x: {{ display: false }},
        y: {{ grid: {{ color: 'rgba(255,255,255,0.05)', drawBorder: false }}, ticks: {{ callback: v => '$'+v.toLocaleString() }} }}
      }},
      interaction: {{ mode: 'nearest', axis: 'x', intersect: false }}
    }}
  }});
}})();

// Trades Table
(()=>{{
  const tb = document.getElementById('tbody'), t = D.trades||[];
  if(!t.length) {{ tb.innerHTML = `<tr><td colspan="6" class="text-center py-8 text-slate-500"><div class="text-3xl mb-2 opacity-50">📋</div>Sin trades históricos</td></tr>`; return; }}
  
  tb.innerHTML = t.slice(0,8).map(x => {{
    const pnlFloat = Number(x.pnl);
    const pnlStr = x.pnl != null ? `<span class="font-mono font-bold ${{pnlFloat>=0?'text-pos':'text-neg'}}">${{pnlFloat>=0?'+':''}}$${{f(pnlFloat)}}</span>` : '<span class="text-slate-600">—</span>';
    return `<tr class="hover:bg-white/5 transition-colors group">
      <td class="font-mono font-bold text-accent group-hover:pl-2 transition-all">${{x.pair}}</td>
      <td><span class="badge b${{x.direction}}">${{x.direction}}</span></td>
      <td class="font-mono">$${{f(x.open_price, 4)}}</td>
      <td>${{pnlStr}}</td>
      <td><span class="badge b${{x.status}} shadow-sm">${{x.status}}</span></td>
      <td class="text-[10px] text-slate-400 font-mono">${{fd(x.close_time || x.open_time)}}</td>
    </tr>`;
  }}).join('');
}})();

// Win Rate Donut
(()=>{{
  const w = D.wins||0, l = D.losses||0, tot = w+l;
  if(tot) {{
      document.getElementById('wrCenter').innerText = f(w/tot*100,0)+'%';
      new Chart(document.getElementById('wrChart'), {{
        type: 'doughnut',
        data: {{ labels: ['Ganados','Perdidos'], datasets: [{{ data: [w,l], backgroundColor: ['#00ff88','#ff3b5c'], borderColor: 'transparent', borderWidth: 0 }}] }},
        options: {{ cutout: '80%', plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ label: (c)=> ` ${{c.formattedValue}} Trades` }} }} }} }}
      }});
      
      document.getElementById('dstats').innerHTML = `
        <div class="flex justify-between items-center text-sm border-b border-white/5 pb-2">
            <span class="flex items-center gap-2 text-slate-400"><span class="w-2 h-2 rounded-full bg-pos"></span>Ganadores</span>
            <span class="font-mono font-bold text-pos">${{w}} <span class="text-xs opacity-70">(${{f(w/tot*100,0)}}%)</span></span>
        </div>
        <div class="flex justify-between items-center text-sm border-b border-white/5 pb-2">
            <span class="flex items-center gap-2 text-slate-400"><span class="w-2 h-2 rounded-full bg-neg"></span>Perdedores</span>
            <span class="font-mono font-bold text-neg">${{l}} <span class="text-xs opacity-70">(${{f(l/tot*100,0)}}%)</span></span>
        </div>
        <div class="flex justify-between items-center text-sm">
            <span class="flex items-center gap-2 text-slate-400"><span class="w-2 h-2 rounded-full bg-accent animate-pulse"></span>Activos</span>
            <span class="font-mono font-bold text-white">${{D.open_trades}}</span>
        </div>
      `;
  }} else {{
      document.getElementById('dstats').innerHTML = '<div class="text-center text-slate-500 w-full mt-10">Esperando Cierres</div>';
  }}
}})();

// Market Monitor
(()=>{{
  const el = document.getElementById('marketMonitor'), m = D.market_monitor||[];
  if(!m.length) {{ el.innerHTML = '<div class="text-center p-4 text-slate-500">Sincronizando feed...</div>'; return; }}
  
  el.innerHTML = m.map(x => {{
    const sColor = x.score >= 5 ? 'text-pos' : x.score >= 3 ? 'text-warn' : 'text-slate-500';
    const bgHov = x.score >= 5 ? 'hover:bg-pos/10 hover:border-pos/30' : 'hover:bg-white/5';
    const icon = x.sentiment > 0.1 ? '<span class="text-pos">▲</span>' : x.sentiment < -0.1 ? '<span class="text-neg">▼</span>' : '<span class="text-slate-600">➖</span>';
    
    return `<div class="flex items-center justify-between p-3 rounded-xl border border-white/5 bg-black/20 transition-all ${{bgHov}} cursor-default">
        <div>
            <div class="font-mono font-bold text-sm text-accent flex items-center gap-2">${{x.pair}} ${{icon}}</div>
            <div class="font-mono text-xs text-slate-300">$${{f(x.price, x.pair.includes('=X')?4:2)}}</div>
        </div>
        <div class="font-mono text-sm font-bold ${{sColor}} bg-black/40 px-2 py-1 rounded">${{f(x.score,1)}}/10</div>
    </div>`;
  }}).join('');
}})();

// Macro Context
(()=>{{
  const el = document.getElementById('macroBox'), m = D.macro;
  if(!m) {{ el.innerHTML = '<div class="text-center p-4 text-slate-500">Recabando inteligencia global...</div>'; return; }}
  
  el.innerHTML = `
    <div class="flex justify-between items-center p-3 border-b border-white/5">
        <div><h4 class="font-bold text-sm text-slate-200">DXY (Dollar)</h4><span class="text-[10px] text-slate-500">Inverso a Cripto</span></div>
        <div class="text-right">
            <div class="font-mono font-bold text-sm">${{f(m.dxy_val)}}</div>
            <span class="badge m${{m.dxy_trend}}">${{m.dxy_trend}}</span>
        </div>
    </div>
    <div class="flex justify-between items-center p-3 border-b border-white/5">
        <div><h4 class="font-bold text-sm text-slate-200">Nasdaq 100</h4><span class="text-[10px] text-slate-500">Apetito tecnológico</span></div>
        <div class="text-right">
            <div class="font-mono font-bold text-sm">${{f(m.nasdaq_val, 0)}}</div>
            <span class="badge m${{m.nasdaq_trend}}">${{m.nasdaq_trend}}</span>
        </div>
    </div>
    <div class="mt-4 p-3 rounded-xl border ${{m.risk_appetite=='RISK_ON'?'bg-pos/10 border-pos/30 text-pos': m.risk_appetite=='RISK_OFF'?'bg-neg/10 border-neg/30 text-neg':'bg-white/5 border-white/10 text-slate-400'}} text-center">
        <div class="text-[10px] font-mono tracking-widest uppercase mb-1">Entorno de Riesgo</div>
        <div class="font-bold tracking-wider">${{m.risk_appetite}}</div>
    </div>
  `;
}})();

// Strategy Perf
(()=>{{
  const el = document.getElementById('stratBox'), s = D.strategy_performance||[];
  if(!s.length) {{ el.innerHTML = '<div class="p-6 text-center text-slate-500">Insuficientes datos para reportar estrategias.</div>'; return; }}
  
  el.innerHTML = s.map(x=>{{
    const total=parseInt(x.total)||0, wins=parseInt(x.wins)||0;
    const wr = total>0? (wins/total*100).toFixed(0) : 0;
    const pnl = parseFloat(x.total_pnl)||0;
    const wrColor = wr>=50?'text-pos':wr>=35?'text-warn':'text-neg';
    const map = {{'B_EMA_PULLBACK':'EMA Pullback','R_RSI_EXTREME':'RSI Extremo','M_MACD_MOMENTUM':'MACD Momentum','ALL':'Híbrida'}};
    const name = map[x.strategy] || x.strategy;
    
    return `<div class="flex justify-between items-center p-4 border-b border-white/5 hover:bg-white/5 transition-colors">
        <div>
            <div class="font-mono font-bold text-xs text-slate-200">${{name}}</div>
            <div class="text-[10px] text-slate-500 font-mono mt-1">${{total}} trades | µ $${{f(x.avg_pnl)}}</div>
        </div>
        <div class="text-right">
            <div class="font-mono font-bold text-sm ${{pnl>=0?'text-pos':'text-neg'}}">${{pnl>=0?'+':''}}$${{f(pnl)}}</div>
            <div class="font-mono text-[10px] font-bold ${{wrColor}}">${{wr}}% WR</div>
        </div>
    </div>`;
  }}).join('');
}})();
</script>
</body></html>"""


if __name__ == "__main__":
    try:
        generate()
    except Exception as e:
        import traceback
        print("\n❌ CRITICAL: Dashboard generation failed!")
        traceback.print_exc()
        sys.exit(1)
