"""
reset_experiment.py — Reinicia los slots de experimento

Limpia los trades y balances de los experimentos sin tocar el historial
principal de trading. Útil para empezar una nueva ronda de comparación
semanal sin borrar el balance del bot.

Uso:
    python reset_experiment.py               # muestra estado actual
    python reset_experiment.py reset <name>  # reinicia un experimento
    python reset_experiment.py reset all     # reinicia todos
    python reset_experiment.py seed          # crea los 3 experimentos predefinidos
"""
import sys
import os
import logging
from database import db, initialize_database, create_experiment, list_experiments, set_bot_config
from experiment_engine import PREDEFINED_EXPERIMENTS, create_predefined, print_comparison

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ResetExperiment")


def reset_experiment(name: str):
    """Reinicia el balance y trades de un experimento a $10,000."""
    initialize_database()
    d = db()

    exps = list_experiments()
    match = next((e for e in exps if e["name"] == name), None)

    if not match:
        print(f"⚠️  Experimento '{name}' no encontrado.")
        return False

    exp_id = int(match["id"])

    # Limpiar trades del experimento (solo los de este slot)
    d.execute("DELETE FROM paper_trades WHERE experiment_id = ?", [exp_id])
    d.execute(
        "UPDATE experiments SET current_balance = initial_balance, "
        "status = 'ACTIVE', ended_at = NULL WHERE id = ?",
        [exp_id]
    )
    d.commit()
    logger.info(f"✅ Experimento #{exp_id} '{name}' reiniciado a $10,000")
    return True


def reset_all():
    """Reinicia todos los experimentos."""
    initialize_database()
    exps = list_experiments()
    if not exps:
        print("No hay experimentos registrados.")
        return
    for e in exps:
        reset_experiment(e["name"])


def show_status():
    initialize_database()
    print_comparison()
    exps = list_experiments()
    active = next((e for e in exps if e["status"] == "ACTIVE"), None)
    if active:
        print(f"Experimento activo: #{active['id']} {active['name']}")
        active_id_cfg = "ACTIVE_EXPERIMENT_ID"
        from database import get_bot_config
        cfg_id = get_bot_config(active_id_cfg)
        print(f"bot_config[{active_id_cfg}] = {cfg_id}")


if __name__ == "__main__":
    cmd  = sys.argv[1] if len(sys.argv) > 1 else "status"
    arg2 = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "status":
        show_status()

    elif cmd == "reset":
        if not arg2:
            print("Uso: reset_experiment.py reset <nombre|all>")
            sys.exit(1)
        if arg2 == "all":
            confirm = input("⚠️  ¿Reiniciar TODOS los experimentos? (s/n): ")
            if confirm.lower() == "s":
                reset_all()
        else:
            reset_experiment(arg2)

    elif cmd == "seed":
        initialize_database()
        print("Creando los 3 experimentos predefinidos...")
        for name in PREDEFINED_EXPERIMENTS:
            create_predefined(name)
        print("\nActiva uno con: python experiment_engine.py activate ZSCORE_BASELINE")
        show_status()

    else:
        print(f"Comando desconocido: {cmd}")
        print("Comandos: status | reset <nombre|all> | seed")
