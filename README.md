# APEX Trading Bot — Z-Score Mean Reversion

Paper trading bot que opera el **spread BTC/ETH** usando **Z-Score Mean Reversion**, un enfoque estadístico clásico de arbitraje de pares. Ejecuta cada 15 minutos en GitHub Actions y publica el dashboard en GitHub Pages.

---

## Hipótesis del experimento

**BTC y ETH están cointegrados.** Llevan más de 15 años cotizando juntos y su relación log-lineal (`log(ETH) ≈ β × log(BTC)`) tiende a revertir a la media cuando se desvía.

### Tesis central
Cuando el spread `S = log(ETH) - β × log(BTC)` se aleja más de **±2 desviaciones estándar** de su media histórica, la probabilidad de reversión supera el azar. El objetivo es capturar esa reversión de forma sistemática.

### Condiciones para que funcione
1. **Cointegración vigente** (p-value Engle-Granger < 0.05) — se verifica cada 24h
2. **Proceso mean-reverting** (Hurst < 0.5, idealmente < 0.45)
3. **Z-Score extremo** (|Z| > 2.0σ) como señal de entrada
4. **Volumen suficiente** (ETH volume > 70% del promedio)
5. **RSI confirmando** (RSI < 35 para LONG, RSI > 65 para SHORT)

### Resultados esperados
- **Win rate objetivo**: 55-65% (la media revierte, pero hay ruido)
- **R:R esperado**: ~1:1 (simétrico por diseño de la estrategia)
- **Ventaja estadística**: frecuencia de reversión × ratio P&L esperado > 1.0
- **Periodo de prueba**: 2 meses de paper trading antes de evaluar señales manuales

---

## Estrategia

### Spread y Z-Score

```
β = Cov(log_BTC, log_ETH) / Var(log_BTC)   [ventana: 500 velas]
S = log(ETH) - β × log(BTC)
Z = (S - mean(S)) / std(S)                  [ventana: 60 velas]
```

### Señales de entrada

| Z-Score      | Dirección  | Interpretación             |
|-------------|------------|---------------------------|
| Z < -2.0σ   | BUY ETH    | ETH infravalorada vs BTC  |
| Z > +2.0σ   | SELL ETH   | ETH sobrevalorada vs BTC  |
| |Z| < 0.5σ  | NEUTRAL    | Spread en equilibrio       |

### Gestión de posiciones

- **TP**: `|Z| < 0.5σ` (reversión completada)
- **SL**: `|Z| > 3.5σ` (spread sigue ampliándose — la cointegración puede estar fallando)
- **Tamaño**: 1.5% de riesgo por trade, máximo 40% del capital
- **Máximo simultáneo**: 1 posición abierta

### Filtros de calidad (cascade)

1. Cointegración activa (p < 0.05)
2. Hurst < 0.45 (proceso genuinamente mean-reverting)
3. |Z-Score| > ZSCORE_ENTRY (señal estadística real)
4. Volumen y RSI confirman la dirección

---

## Motor de experimentos

Tres variantes corren en paralelo para comparación semanal:

| Slot | Entry | Exit | Stop | Descripción |
|------|-------|------|------|-------------|
| ZSCORE_BASELINE | ±2.0σ | 0.5σ | 3.5σ | Configuración base |
| ZSCORE_AGGRESSIVE | ±1.5σ | 0.3σ | 3.0σ | Entradas más frecuentes |
| ZSCORE_CONSERVATIVE | ±2.5σ | 0.8σ | 4.0σ | Entradas de mayor calidad |

Cada slot tiene su propio balance de $10,000. El **torneo semanal** (lunes) declara el ganador y guarda el veredicto en `bot_memory`.

Para inicializar los slots:
```bash
python reset_experiment.py seed
```

Para ver la comparativa:
```bash
python experiment_engine.py compare
```

---

## Arquitectura

```
run.py              ← Ciclo principal (GitHub Actions cada 15min)
├── fetcher.py      ← Descarga OHLCV de BTC/USDT y ETH/USDT (CCXT)
├── indicators.py   ← OLS beta, Z-Score, Hurst, RSI, cointegración
├── signals.py      ← Filtros cascade → score 0-10 → SL/TP en precio ETH
├── paper_broker.py ← Abre/cierra trades por Z-Score (no por precio crudo)
├── database.py     ← Turso (cloud SQLite) + fallback SQLite local
├── brain.py        ← Reflexión autónoma + torneo semanal (lunes)
├── llm_brain.py    ← LLM (Groq/Gemini/OpenAI) ajusta MIN_SCORE dinámicamente
└── generate.py     ← Dashboard HTML estático → GitHub Pages
```

### Datos almacenados por trade
Cada operación registra en `paper_trades`: strategy_name, z_score_open, hurst_open, coint_pvalue_open, beta_open, macro_regime, eth_rsi_open, experiment_id — para análisis post-hoc completo.

---

## Setup

### Variables de entorno requeridas (GitHub Secrets)

| Variable | Descripción |
|----------|-------------|
| `TURSO_URL` | URL de la base de datos Turso |
| `TURSO_AUTH_TOKEN` | Token de autenticación Turso |
| `GROQ_API_KEY` | API key de Groq (LLM gratuito) |
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram (opcional) |
| `TELEGRAM_CHAT_ID` | Chat ID de Telegram (opcional) |

### Instalación local

```bash
pip install -r requirements.txt
python reset_bot.py          # Reinicio completo a $10,000
python experiment_engine.py seed  # Crear slots de experimento
python run.py                # Ejecutar un ciclo
```

### Reset completo
```bash
FORCE_RESET=true python reset_bot.py
python experiment_engine.py seed
```

---

## Dashboard

Publicado automáticamente en GitHub Pages tras cada ciclo. Incluye:
- Balance y curva de equity
- Win rate y P&L acumulado
- Z-Score actual, Hurst y cointegración
- Historial de trades con contexto completo
- Log del cerebro autónomo (reflexiones del bot)
- Comparativa de experimentos
