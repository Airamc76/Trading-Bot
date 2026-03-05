import sqlite3
import os
from database import TursoClient, USE_TURSO, TURSO_URL, TURSO_AUTH_TOKEN

def sync():
    if not USE_TURSO:
        print("Error: No Turso config found for target.")
        return
    
    # 1. Read from Local
    local_conn = sqlite3.connect("db/local.db")
    local_conn.row_factory = sqlite3.Row
    local_trades = local_conn.execute("SELECT * FROM paper_trades").fetchall()
    
    # 2. Setup Turso
    turso = TursoClient(TURSO_URL, TURSO_AUTH_TOKEN)
    
    print(f"Syncing {len(local_trades)} trades to Turso...")
    for t in local_trades:
        # Check if exists in Turso
        remote = turso.query("SELECT * FROM paper_trades WHERE id = ?", [t["id"]])
        if not remote:
            print(f"Pushing missing ID {t['id']} ({t['pair']}) to Turso...")
            sql = "INSERT OR REPLACE INTO paper_trades (id, signal_id, pair, direction, open_time, close_time, open_price, close_price, stop_loss, take_profit, position_size, pnl, pnl_pct, status, close_reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            params = [t["id"], t["signal_id"], t["pair"], t["direction"], t["open_time"], t["close_time"], t["open_price"], t["close_price"], t["stop_loss"], t["take_profit"], t["position_size"], t["pnl"], t["pnl_pct"], t["status"], t["close_reason"]]
            turso.execute(sql, params)
        elif remote[0]["status"] != t["status"]:
            print(f"Updating ID {t['id']} status to {t['status']} on Turso...")
            turso.execute("UPDATE paper_trades SET status=?, pnl=?, pnl_pct=?, close_time=?, close_price=?, close_reason=? WHERE id=?", [t["status"], t["pnl"], t["pnl_pct"], t["close_time"], t["close_price"], t["close_reason"], t["id"]])
    
    turso.commit()
    print("✅ Sync complete!")

if __name__ == '__main__':
    sync()
