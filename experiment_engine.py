"""
experiment_engine.py — Motor de experimentos de estrategia

Gestiona slots independientes de paper trading, cada uno con su propio
balance de $10,000 y configuración de parámetros. Permite comparar
variantes de la estrategia Z-Score semana a semana.

Uso desde CLI:
    python experiment_engine.py list
    python experiment_engine.py create "ZSCORE_AGGRESSIVE" "Entry 1.5σ, Exit 0.3σ"
    python experiment_engine.py compare
"""
import sys
import json
import logging
from datetime import datetime, timezone
from database import (
    initialize_database,
    create_experiment, get_active_experiment, list_experiments,
    compare_experiments, get_experiment_stats, get_bot_config, set_bot_config,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ExperimentEngine")


# ── Experimentos predefinidos ─────────────────────────────────────────────────

PREDEFINED_EXPERIMENTS = {
    "ZSCORE_BASELINE": {
        "description": "Configuración base: Entry ±2.0σ, Exit 0.5σ, Stop 3.5σ, H<0.45",
        "config": {
            "ZSCORE_ENTRY":       2.0,
            "ZSCORE_EXIT":        0.5,
            "ZSCORE_STOP":        3.5,
            "HURST_THRESHOLD":    0.45,
            "MIN_SCORE_TO_TRADE": 5.0,
        },
    },
    "ZSCORE_AGGRESSIVE": {
        "description": "Entrada más temprana: Entry ±1.5σ, Exit 0.3σ, Stop 3.0σ",
        "config": {
            "ZSCORE_ENTRY":       1.5,
            "ZSCORE_EXIT":        0.3,
            "ZSCORE_STOP":        3.0,
            "HURST_THRESHOLD":    0.45,
            "MIN_SCORE_TO_TRADE": 4.5,
        },
    },
    "ZSCORE_CONSERVATIVE": {
        "description": "Entrada más selectiva: Entry ±2.5σ, Exit 0.8σ, Stop 4.0σ",
        "config": {
            "ZSCORE_ENTRY":       2.5,
            "ZSCORE_EXIT":        0.8,
            "ZSCORE_STOP":        4.0,
            "HURST_THRESHOLD":    0.40,
            "MIN_SCORE_TO_TRADE": 6.0,
        },
    },
}


def ensure_default_experiment():
    """
    Garantiza que siempre haya al menos un experimento activo.
    Si no existe ninguno, crea el BASELINE.
    Devuelve el ID del experimento activo.
    """
    active = get_active_experiment()
    if active:
        return int(active["id"])

    logger.info("⚗️ No hay experimento activo — creando ZSCORE_BASELINE...")
    spec = PREDEFINED_EXPERIMENTS["ZSCORE_BASELINE"]
    exp_id = create_experiment(
        name        = "ZSCORE_BASELINE",
        description = spec["description"],
        config      = spec["config"],
    )
    set_bot_config("ACTIVE_EXPERIMENT_ID", str(exp_id))
    logger.info(f"⚗️ Experimento #{exp_id} ZSCORE_BASELINE iniciado con $10,000")
    return exp_id


def get_current_experiment_id() -> int | None:
    """Devuelve el ID del experimento activo actual."""
    cached = get_bot_config("ACTIVE_EXPERIMENT_ID")
    if cached:
        try:
            return int(cached)
        except (ValueError, TypeError):
            pass
    active = get_active_experiment()
    return int(active["id"]) if active else None


def print_comparison():
    """Imprime tabla comparativa de todos los experimentos."""
    stats = compare_experiments()
    if not stats:
        print("No hay experimentos registrados.")
        return

    print(f"\n{'─'*80}")
    print(f"  {'EXPERIMENTO':<25} {'ESTADO':<10} {'TRADES':<8} {'WR%':<8} {'P&L':<12} {'RET%':<8} {'BAL':<12}")
    print(f"{'─'*80}")
    for s in stats:
        if not s:
            continue
        print(f"  {s['name']:<25} {s['status']:<10} {s['total_trades']:<8} "
              f"{s['win_rate']:<8.1f} ${s['total_pnl']:<11.2f} "
              f"{s['return_pct']:<8.2f} ${s['current_balance']:<11,.2f}")
    print(f"{'─'*80}\n")


def create_predefined(name: str):
    """Crea un experimento predefinido por nombre."""
    if name not in PREDEFINED_EXPERIMENTS:
        print(f"Experimento '{name}' no encontrado. Disponibles: {list(PREDEFINED_EXPERIMENTS.keys())}")
        return None
    spec = PREDEFINED_EXPERIMENTS[name]
    exp_id = create_experiment(name, spec["description"], spec["config"])
    print(f"✅ Experimento #{exp_id} '{name}' creado.")
    return exp_id


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    initialize_database()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"

    if cmd == "list":
        exps = list_experiments()
        if not exps:
            print("No hay experimentos registrados.")
        else:
            for e in exps:
                cfg = json.loads(e.get("config_json") or "{}")
                print(f"\n#{e['id']} [{e['status']}] {e['name']}")
                print(f"   {e.get('description', '')}")
                print(f"   Balance: ${float(e.get('current_balance') or 10000):.2f} "
                      f"(inicial: ${float(e.get('initial_balance') or 10000):.2f})")
                print(f"   Config: {json.dumps(cfg)}")
                s = get_experiment_stats(int(e["id"]))
                print(f"   Trades: {s['total_trades']} | WR: {s['win_rate']:.1f}% | "
                      f"P&L: ${s['total_pnl']:+.2f} | Return: {s['return_pct']:+.2f}%")

    elif cmd == "compare":
        print_comparison()

    elif cmd == "create":
        name = sys.argv[2] if len(sys.argv) > 2 else None
        desc = sys.argv[3] if len(sys.argv) > 3 else ""
        if not name:
            print("Uso: experiment_engine.py create <nombre> [descripcion]")
            sys.exit(1)
        if name in PREDEFINED_EXPERIMENTS:
            create_predefined(name)
        else:
            exp_id = create_experiment(name, desc)
            print(f"✅ Experimento #{exp_id} '{name}' creado.")

    elif cmd == "activate":
        name = sys.argv[2] if len(sys.argv) > 2 else None
        if not name:
            print("Uso: experiment_engine.py activate <nombre>")
            sys.exit(1)
        exps = list_experiments()
        match = next((e for e in exps if e["name"] == name), None)
        if not match:
            print(f"Experimento '{name}' no encontrado.")
            sys.exit(1)
        set_bot_config("ACTIVE_EXPERIMENT_ID", str(match["id"]))
        print(f"✅ Experimento activo cambiado a #{match['id']} '{name}'")

    elif cmd == "seed":
        print("Creando experimentos predefinidos...")
        for name in PREDEFINED_EXPERIMENTS:
            create_predefined(name)
        print("\nPara activar uno: python experiment_engine.py activate ZSCORE_BASELINE")

    else:
        print(f"Comando desconocido: {cmd}")
        print("Comandos: list | compare | create <name> [desc] | activate <name> | seed")
