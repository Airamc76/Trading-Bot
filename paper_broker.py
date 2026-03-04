"""
paper_broker.py — Broker simulado para paper trading
"""
import logging
from datetime import datetime, timezone
import config
from database import (get_portfolio_balance, update_portfolio,
                       get_open_trades, open_paper_trade, close_paper_trade)

logger = logging.getLogger(__name__)


class PaperBroker:
    def __init__(self):
        balance = get_portfolio_balance()
        self.balance = balance if balance is not None else config.PAPER_CAPITAL
        if balance is None:
            update_portfolio(self.balance, self.balance, "🤖 Bot iniciado")
        logger.info(f"💼 Balance: ${self.balance:,.2f}")

    @property
    def open_trades(self):
        return get_open_trades()

    def can_open_trade(self):
        return len(self.open_trades) < config.MAX_OPEN_TRADES

    def _position_size(self, price, stop_loss):
        risk = self.balance * config.RISK_PER_TRADE
        if not stop_loss or price == 0:
            return risk
        dist = abs(price - stop_loss) / price
        max_size = self.balance * config.MAX_POSITION_SIZE_PCT
        size = risk / dist if dist else risk
        return min(size, max_size)

    def open_trade(self, signal_id, pair, direction, price, stop_loss, take_profit):
        if not self.can_open_trade():
            return None
        if pair in [t["pair"] for t in self.open_trades]:
            return None
        size = self._position_size(price, stop_loss)
        tid = open_paper_trade({
            "signal_id": signal_id, "pair": pair, "direction": direction,
            "open_time": datetime.now(timezone.utc).isoformat(), "open_price": price,
            "stop_loss": stop_loss, "take_profit": take_profit,
            "position_size": round(size, 2),
        })
        logger.info(f"📈 #{tid} {pair} {direction} @ {price:.4g} | "
                    f"SL={stop_loss:.4g} TP={take_profit:.4g} | ${size:,.0f}")
        return tid

    def check_and_close_trades(self, prices: dict) -> list:
        closed = []
        for t in self.open_trades:
            price = prices.get(t["pair"])
            if not price:
                continue
            d  = t["direction"]
            sl = float(t["stop_loss"])
            tp = float(t["take_profit"])
            if   (d == "BUY"  and price >= tp) or (d == "SELL" and price <= tp): reason = "TP_HIT"
            elif (d == "BUY"  and price <= sl) or (d == "SELL" and price >= sl): reason = "SL_HIT"
            else: continue
            pnl = close_paper_trade(t["id"], price, reason)
            self.balance += pnl
            update_portfolio(self.balance, self.balance, f"#{t['id']} {reason}")
            emoji = "✅" if pnl > 0 else "❌"
            logger.info(f"{emoji} #{t['id']} {t['pair']} {reason} | P&L ${pnl:+.2f} | Balance ${self.balance:,.2f}")
            closed.append({"id": t["id"], "pair": t["pair"], "reason": reason, "pnl": pnl})
        return closed

    def stats(self):
        from database import get_dashboard_data
        return get_dashboard_data()
