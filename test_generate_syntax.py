import json
from generate import build_html

# Dummy data that mimics what get_dashboard_data returns
dummy_data = {
    "balance": 10000.0,
    "total_pnl": 0.0,
    "total_trades": 0,
    "wins": 0,
    "losses": 0,
    "open_trades": 0,
    "win_rate": 0.0,
    "signals": [],
    "trades": [],
    "balance_history": [],
    "macro": None,
    "heartbeats": [],
    "system_logs": [],
    "bot_memory": [],
    "bot_wishes": [],
    "improvement_requests": [],
    "strategy_performance": [],
    "monthly_metrics": [],
    "signal_only_mode": False,
    "health": {
        "status": "OK",
        "errors_24h": 0,
        "actions_24h": 0,
        "last_heartbeat": None
    },
    "bot_config": {
        "strategy": "ALL",
        "min_score": "5.0",
        "sl_atr": "1.2",
        "paused": False,
        "paused_pairs": "",
        "signal_only": False,
    },
    "last_updated": "2023-01-01T00:00:00Z",
}

try:
    data_json = json.dumps(dummy_data)
    html = build_html(data_json, dummy_data)
    print("✅ build_html formatted successfully!")
except Exception as e:
    print(f"❌ Error formatting build_html: {e}")
    import traceback
    traceback.print_exc()
