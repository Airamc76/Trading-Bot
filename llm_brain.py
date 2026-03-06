"""
llm_brain.py — Motor de Razonamiento con LLM Real

Usa Groq (Llama 3.3 70B - GRATIS) como motor de razonamiento principal.
Fallback: Google Gemini Flash si GEMINI_API_KEY está disponible.

El LLM recibe un snapshot completo del estado del bot y devuelve
decisiones concretas en JSON que modifican el comportamiento real.
"""

import os
import json
import logging
import requests
from datetime import datetime, timezone, timedelta
from database import db, get_bot_config, set_bot_config

logger = logging.getLogger(__name__)

OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")

# Models
OPENAI_MODEL  = "gpt-4o-mini" # Fast, cheap, and very capable
GROQ_MODEL    = "llama-3.3-70b-versatile"
GEMINI_MODEL  = "gemini-2.0-flash"

# Endpoints
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
GROQ_ENDPOINT   = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# No llamar al LLM si ya lo hizo recientemente (ahorra tokens y tiempo)
LLM_COOLDOWN_MINUTES = 14   # <15min para que siempre tenga decisión fresca


def _safe_float(v, d=0.0):
    try:
        return float(v) if v is not None else d
    except (TypeError, ValueError):
        return d


# ── Constructor de contexto ───────────────────────────────────────────────────

def _build_context_snapshot() -> dict:
    """
    Construye un snapshot rico del estado actual del bot para enviar al LLM.
    """
    d = db()

    # Balance y rendimiento general
    bal_rows = d.query("SELECT balance FROM portfolio ORDER BY id DESC LIMIT 1")
    balance  = _safe_float(bal_rows[0]["balance"] if bal_rows else None, 10000.0)

    total_trades = d.query("SELECT COUNT(*) as c FROM paper_trades WHERE status != 'OPEN'")
    wins_row     = d.query("SELECT COUNT(*) as c FROM paper_trades WHERE status = 'WIN'")
    losses_row   = d.query("SELECT COUNT(*) as c FROM paper_trades WHERE status = 'LOSS'")
    open_row     = d.query("SELECT COUNT(*) as c FROM paper_trades WHERE status = 'OPEN'")
    pnl_row      = d.query("SELECT COALESCE(SUM(pnl), 0) as s FROM paper_trades WHERE status != 'OPEN'")

    total  = int(total_trades[0]["c"] or 0)
    wins   = int(wins_row[0]["c"] or 0)
    losses = int(losses_row[0]["c"] or 0)
    open_t = int(open_row[0]["c"] or 0)
    total_pnl = _safe_float(pnl_row[0]["s"])
    win_rate  = wins / total * 100 if total > 0 else 0.0

    # Racha de pérdidas
    recent_statuses = d.query(
        "SELECT status FROM paper_trades WHERE status != 'OPEN' ORDER BY id DESC LIMIT 20"
    )
    loss_streak = 0
    for r in recent_statuses:
        if r["status"] == "LOSS":
            loss_streak += 1
        else:
            break

    # Últimos 10 trades con detalle
    last_trades = d.query("""
        SELECT pair, direction, open_price, close_price, pnl, pnl_pct,
               status, close_reason, open_time, close_time
        FROM paper_trades
        WHERE status != 'OPEN'
        ORDER BY id DESC LIMIT 10
    """)

    # Trades abiertos actuales
    open_trades = d.query(
        "SELECT pair, direction, open_price, stop_loss, take_profit FROM paper_trades WHERE status='OPEN'"
    )

    # Últimas señales
    last_signals = d.query(
        "SELECT pair, direction, score, price FROM signals ORDER BY id DESC LIMIT 10"
    )

    # Macro
    macro = d.query(
        "SELECT dxy_val, nasdaq_val, risk_appetite, dxy_trend, nasdaq_trend "
        "FROM macro_history ORDER BY id DESC LIMIT 1"
    )

    # Config actual del bot
    current_config = {
        "active_strategy":  get_bot_config("ACTIVE_STRATEGY", "ALL"),
        "min_score":        get_bot_config("MIN_SCORE_TO_TRADE", "5.0"),
        "stop_loss_atr":    get_bot_config("STOP_LOSS_ATR", "1.2"),
        "paused_pairs":     get_bot_config("PAUSED_PAIRS", ""),
    }

    # Últimas reflexiones del brain (código)
    code_thoughts = d.query(
        "SELECT category, note, impact FROM bot_memory ORDER BY id DESC LIMIT 5"
    )

    # Balance histórico (últimas 10 snapshots)
    bal_history = d.query(
        "SELECT balance FROM portfolio ORDER BY id DESC LIMIT 10"
    )
    balances = [_safe_float(r["balance"]) for r in bal_history]
    bal_trend = "DECLINING" if len(balances) > 2 and balances[0] < balances[-1] else "STABLE_OR_GROWING"

    return {
        "balance":       round(balance, 2),
        "total_pnl":     round(total_pnl, 2),
        "total_trades":  total,
        "wins":          wins,
        "losses":        losses,
        "open_trades":   open_t,
        "win_rate":      round(win_rate, 1),
        "loss_streak":   loss_streak,
        "balance_trend": bal_trend,
        "last_trades":   last_trades,
        "open_positions": open_trades,
        "last_signals":  last_signals,
        "macro":         macro[0] if macro else {},
        "bot_config":    current_config,
        "code_thoughts": code_thoughts,
        "timestamp_utc": datetime.now(timezone.utc).isoformat()
    }


# ── Sistema de prompts ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Eres el Managing Director (MD) de APEX Trading Bot, un motor de razonamiento 100% autónomo. 
Tu misión es tomar decisiones ejecutivas sobre la estrategia, el riesgo y la operativa del bot basándote en datos reales y los principios de John J. Murphy (Análisis Técnico de los Mercados Financieros).

Tu palabra es ley. Si decides pausar, el bot se pausa. Si decides cambiar de estrategia, el bot cambia.

MANDATOS CRÍTICOS (Murphy's Laws):
1. La tendencia es tu amiga: Opera a favor de la tendencia primaria. No intentes adivinar techos/suelos sin confirmación clara.
2. El volumen confirma el precio: Si el precio sube pero el volumen/momentum cae, la tendencia es sospechosa.
3. El mercado lo descuenta todo: Todo factor externo ya está en el precio. Confía en lo que ves en los datos.
4. Gestiona el riesgo primero: Tu prioridad #1 es la supervivencia del capital. Si el win_rate < 30% o hay una racha de >5 pérdidas, entra en modo ultra-defensivo.
5. Análisis Multitemporal: Considera que las señales de 1H/4H mandan sobre las de 15min.

REGLAS DE RESPUESTA:
- Responde ÚNICAMENTE con un objeto JSON válido. Sin markdown, sin texto adicional.
- Los campos "thought" y "action_taken" deben estar SIEMPRE en Español.
- Tu razonamiento debe ser FACTUAL: cita porcentajes de win rate, rachas de pérdidas, P&L exacto y regímenes macro.

JSON SCHEMA:
{
  "thought": "<Reasoning in Spanish citing specific data and Murphy's principles>",
  "strategy_mode": "ALL | B_EMA_PULLBACK | R_RSI_EXTREME | M_MACD_MOMENTUM | PAUSE_ALL",
  "min_score": <float 4.5 - 9.5>,
  "stop_loss_atr": <float 0.8 - 3.0>,
  "pairs_to_pause": ["PAIR1", "PAIR2"],
  "pairs_to_resume": ["PAIR3"],
  "action_taken": "<Summary in Spanish of the executive decision>",
  "confidence": <int 1-10>,
  "market_regime": "TRENDING_UP | TRENDING_DOWN | CHOPPY | RISK_OFF | RISK_ON"
}"""


def _call_openai(context: dict) -> dict | None:
    """Llama a OpenAI ChatGPT (GPT-4o-mini)."""
    if not OPENAI_API_KEY:
        return None

    user_message = f"""Current bot state (analyze and decide):

{json.dumps(context, indent=2, default=str)}

Respond only with the JSON decision object."""

    try:
        resp = requests.post(
            OPENAI_ENDPOINT,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_message}
                ],
                "temperature": 0.3,
                "max_tokens": 800,
                "response_format": {"type": "json_object"}
            },
            timeout=25
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        logger.warning(f"⚠️ LLM (OpenAI) error: {e}")
        return None


def _call_groq(context: dict) -> dict | None:
    """Llama a Groq Llama 3.3 70B."""
    if not GROQ_API_KEY:
        return None

    user_message = f"""Current bot state (analyze and decide):

{json.dumps(context, indent=2, default=str)}

Respond only with the JSON decision object."""

    try:
        resp = requests.post(
            GROQ_ENDPOINT,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_message}
                ],
                "temperature": 0.3,
                "max_tokens": 800,
                "response_format": {"type": "json_object"}
            },
            timeout=20
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        logger.warning(f"⚠️ LLM (Groq) error: {e}")
        return None


def _call_gemini(context: dict) -> dict | None:
    """Fallback a Gemini Flash."""
    if not GEMINI_API_KEY:
        return None

    prompt = f"""{SYSTEM_PROMPT}

Current bot state:
{json.dumps(context, indent=2, default=str)}

Respond only with the JSON decision object."""

    try:
        resp = requests.post(
            f"{GEMINI_ENDPOINT}?key={GEMINI_API_KEY}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 800,
                    "responseMimeType": "application/json"
                }
            },
            timeout=20
        )
        resp.raise_for_status()
        content = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(content)
    except Exception as e:
        logger.warning(f"⚠️ LLM (Gemini) error: {e}")
        return None


# ── Aplicador de decisiones ───────────────────────────────────────────────────

def _validate_decision(decision: dict) -> dict:
    """Valida y limita las decisiones del LLM dentro de rangos seguros."""
    # Strategy mode
    valid_strategies = {"ALL", "B_EMA_PULLBACK", "R_RSI_EXTREME", "M_MACD_MOMENTUM", "PAUSE_ALL"}
    if decision.get("strategy_mode") not in valid_strategies:
        decision["strategy_mode"] = "ALL"

    # Min score — entre 4.5 y 9.5
    decision["min_score"] = max(4.5, min(9.5, _safe_float(decision.get("min_score"), 5.0)))

    # Stop loss ATR — entre 0.8 y 3.0 (límite duro)
    decision["stop_loss_atr"] = max(0.8, min(3.0, _safe_float(decision.get("stop_loss_atr"), 1.2)))

    # Listas
    if not isinstance(decision.get("pairs_to_pause"), list):
        decision["pairs_to_pause"] = []
    if not isinstance(decision.get("pairs_to_resume"), list):
        decision["pairs_to_resume"] = []

    # Thought y action
    if not decision.get("thought"):
        decision["thought"] = "No specific reasoning provided."
    if not decision.get("action_taken"):
        decision["action_taken"] = "Parameters reviewed."

    # Confidence
    decision["confidence"] = max(1, min(10, int(decision.get("confidence", 5))))

    return decision


def _apply_decision(decision: dict):
    """Aplica las decisiones del LLM a la configuración real del bot."""
    d = db()
    changes = []
    used_model = "ChatGPT" if OPENAI_API_KEY else ("Groq" if GROQ_API_KEY else "Gemini")

    # Estrategia activa
    old_strategy = get_bot_config("ACTIVE_STRATEGY", "ALL")
    new_strategy  = decision["strategy_mode"]

    if new_strategy == "PAUSE_ALL":
        set_bot_config("TRADING_PAUSED", "true")
        changes.append(f"Trading PAUSADO por LLM (confianza: {decision['confidence']}/10)")
    else:
        set_bot_config("TRADING_PAUSED", "false")
        if old_strategy != new_strategy:
            set_bot_config("ACTIVE_STRATEGY", new_strategy)
            changes.append(f"Estrategia: {old_strategy} → {new_strategy}")

    # Score mínimo
    old_score = _safe_float(get_bot_config("MIN_SCORE_TO_TRADE", "5.0"))
    new_score  = decision["min_score"]
    if abs(old_score - new_score) >= 0.4:  # Solo cambiar si diferencia significativa
        set_bot_config("MIN_SCORE_TO_TRADE", str(round(new_score, 1)))
        changes.append(f"Min score: {old_score:.1f} → {new_score:.1f}")

    # ATR de Stop Loss
    old_atr = _safe_float(get_bot_config("STOP_LOSS_ATR", "1.2"))
    new_atr  = decision["stop_loss_atr"]
    if abs(old_atr - new_atr) >= 0.1:
        set_bot_config("STOP_LOSS_ATR", str(round(new_atr, 2)))
        changes.append(f"SL ATR: {old_atr:.2f} → {new_atr:.2f}")

    # Pares a pausar
    paused_str = get_bot_config("PAUSED_PAIRS", "")
    paused = [p for p in paused_str.split(",") if p] if paused_str else []

    for pair in decision.get("pairs_to_pause", []):
        if pair and pair not in paused:
            paused.append(pair)
            changes.append(f"Par pausado: {pair}")

    for pair in decision.get("pairs_to_resume", []):
        if pair in paused:
            paused.remove(pair)
            changes.append(f"Par reanudado: {pair}")

    set_bot_config("PAUSED_PAIRS", ",".join(paused))

    # Guardar el pensamiento del LLM en bot_memory
    thought_text = decision.get("thought", "")
    full_thought = f"[{used_model}] {thought_text}"

    # Verificar que no sea duplicado
    existing = d.query(
        "SELECT id FROM bot_memory WHERE note = ? LIMIT 1",
        [full_thought]
    )
    if not existing:
        d.execute(
            "INSERT INTO bot_memory (category, note, impact) VALUES (?, ?, ?)",
            [
                "LLM_REASONING",
                full_thought,
                "POSITIVE" if decision["confidence"] >= 7 else "NEUTRAL"
            ]
        )
        d.commit()

    # Guardar acción en bot_wishes
    action_summary = decision.get("action_taken", "")
    if changes:
        action_summary += f" | Cambios: {', '.join(changes)}"
    
    if action_summary:
        d.execute(
            "INSERT INTO bot_wishes (wish, status) VALUES (?, 'ACTION')",
            [action_summary]
        )
        d.commit()

    logger.info(f"🤖 LLM Decision aplicada (confianza {decision['confidence']}/10):")
    for c in changes:
        logger.info(f"   → {c}")


def _should_run_llm() -> bool:
    """Verifica si debemos llamar al LLM ahora."""
    if not any([OPENAI_API_KEY, GROQ_API_KEY, GEMINI_API_KEY]):
        return False

    last_run = get_bot_config("LLM_LAST_RUN", None)
    if not last_run:
        return True

    try:
        last_dt = datetime.fromisoformat(last_run)
        elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds() / 60
        return elapsed >= LLM_COOLDOWN_MINUTES
    except Exception:
        return True


# ── Punto de entrada ──────────────────────────────────────────────────────────

def run_llm_brain_cycle():
    """Ejecuta el ciclo de razonamiento LLM priorizando OpenAI -> Groq -> Gemini."""
    if not _should_run_llm():
        return

    context = _build_context_snapshot()
    decision = None

    if OPENAI_API_KEY:
        logger.info(f"🤖 LLM Brain: solicitando razonamiento a {OPENAI_MODEL}...")
        decision = _call_openai(context)
    
    if decision is None and GROQ_API_KEY:
        logger.info(f"🤖 LLM Brain: solicitando razonamiento a {GROQ_MODEL}...")
        decision = _call_groq(context)

    if decision is None and GEMINI_API_KEY:
        logger.info("🤖 LLM Brain: solicitando razonamiento a Gemini Flash...")
        decision = _call_gemini(context)

    if decision:
        try:
            decision = _validate_decision(decision)
            _apply_decision(decision)
            set_bot_config("LLM_LAST_RUN", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            logger.error(f"🤖 LLM Brain: error aplicando decisión: {e}")
