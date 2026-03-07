from database import db, get_bot_config
d = db()
# Ver configuración de trading pausado
print(f"TRADING_PAUSED: {get_bot_config('TRADING_PAUSED')}")
# Ver balance actual
bal = d.query("SELECT balance FROM portfolio ORDER BY id DESC LIMIT 1")
if bal: print(f"Balance en DB: {bal[0]['balance']}")
else: print("No hay datos en portfolio")
# Ver cantidad de trades
trades = d.query("SELECT COUNT(*) as c FROM paper_trades")
print(f"Total trades en DB: {trades[0]['c']}")
