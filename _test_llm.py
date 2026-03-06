import sys
import json
sys.path.insert(0, '.')

from llm_brain import _build_context_snapshot, _should_run_llm
from database import initialize_database

print("=== TEST: LLM Context Snapshot ===")
try:
    initialize_database()
    snapshot = _build_context_snapshot()
    
    # Print a summary of the context
    print(f"Balance: {snapshot['balance']}")
    print(f"Total Trades: {snapshot['total_trades']}")
    print(f"Win Rate: {snapshot['win_rate']}%")
    print(f"Loss Streak: {snapshot['loss_streak']}")
    print(f"Snapshot Keys: {list(snapshot.keys())}")
    
    print("\nPASS: Context snapshot built successfully.")
except Exception as e:
    print(f"FAIL: Context snapshot building failed: {e}")
    import traceback; traceback.print_exc()

print("\n=== TEST: LLM Run Decision ===")
print(f"Should run LLM? {'Yes' if _should_run_llm() else 'No (Cooldown or missing API keys)'}")
