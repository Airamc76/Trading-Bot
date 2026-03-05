"""
paper_broker.py — Broker simulado para paper trading
"""
import logging
from datetime import datetime, timezone
import config
from database import (get_portfolio_balance, update_portfolio,
                       get_open_trades, open_paper_trade, close_paper_trade,
                       get_bot_config, get_dashboard_data)

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
        max_open = int(get_bot_config("MAX_OPEN_TRADES", config.MAX_OPEN_TRADES))
        return len(self.open_trades) < max_open

    def _position_size(self, price, stop_loss, atr=None):
        dyn_risk = float(get_bot_config("RISK_PER_TRADE", config.RISK_PER_TRADE))
        dyn_max_pct = float(get_bot_config("MAX_POSITION_SIZE_PCT", config.MAX_POSITION_SIZE_PCT))
        
        # APEX RULE 2: 1-2% risk per trade
        risk_amount = self.balance * dyn_risk
        
        if not stop_loss or price == 0:
            return risk_amount
            
        dist = abs(price - stop_loss)
        dist_pct = dist / price
        
        # Calculate standard size (Size = Risk / Distance to SL)
        # Note: We use distance in percentage to calculate size relative to balance
        size = risk_amount / dist_pct if dist_pct > 0 else risk_amount
        
        # APEX RULE 6: Reduce size by 50% in high volatility (ATR > 2% of price as proxy)
        if atr and (atr / price) > 0.02:
            logger.info("⚠️ High volatility detected (ATR > 2%). Reducing position size by 50% per APEX Rule 6.")
            size *= 0.5
            
        # Hard limit per trade to avoid overexposure
        max_size = self.balance * dyn_max_pct
        return min(size, max_size)

    def open_trade(self, signal_id, pair, direction, price, stop_loss, take_profit, atr=None):
        if not self.can_open_trade():
            return None
        if pair in [t["pair"] for t in self.open_trades]:
            return None
            
        # APEX Rule: R:R must be at least 1:2
        if stop_loss and take_profit:
            risk = abs(price - stop_loss)
            reward = abs(take_profit - price)
            if risk > 0 and (reward / risk) < 1.9: # Allow a bit of margin for 2.0
                logger.warning(f"🚫 Trade rejected for {pair}: R:R too low ({reward/risk:.2f})")
                return None

        size = self._position_size(price, stop_loss, atr)
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
        return get_dashboard_data()
