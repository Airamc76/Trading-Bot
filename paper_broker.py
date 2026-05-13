"""
paper_broker.py — Broker simulado para Z-Score Mean Reversion (BTC/ETH Spread)

Gestiona trades de spread: LONG (BUY ETH + SHORT BTC) y SHORT (SELL ETH + LONG BTC).
El cierre de posiciones de spread se hace por Z-score, no por precio crudo.
"""
import logging
from datetime import datetime, timezone
import config
from database import (get_portfolio_balance, update_portfolio,
                       get_open_trades, open_paper_trade, close_paper_trade,
                       get_bot_config, get_dashboard_data)

logger = logging.getLogger(__name__)

SPREAD_PAIR = "BTC_ETH_SPREAD"


class PaperBroker:
    def __init__(self):
        balance = get_portfolio_balance()
        self.balance = balance if balance is not None else config.PAPER_CAPITAL
        if balance is None:
            update_portfolio(self.balance, self.balance, "🤖 Bot iniciado — Z-Score Strategy")
        logger.info(f"💼 Balance: ${self.balance:,.2f}")

    @property
    def open_trades(self):
        return get_open_trades()

    def can_open_trade(self):
        max_open = int(get_bot_config("MAX_OPEN_TRADES", config.MAX_OPEN_TRADES))
        return len(self.open_trades) < max_open

    def _position_size(self, eth_price: float, stop_loss: float) -> float:
        dyn_risk    = float(get_bot_config("RISK_PER_TRADE",        config.RISK_PER_TRADE))
        dyn_max_pct = float(get_bot_config("MAX_POSITION_SIZE_PCT", config.MAX_POSITION_SIZE_PCT))

        risk_amount = self.balance * dyn_risk

        if not stop_loss or eth_price == 0:
            return risk_amount

        dist_pct = abs(eth_price - stop_loss) / eth_price
        if dist_pct <= 0:
            return risk_amount

        size = risk_amount / dist_pct
        max_size = self.balance * dyn_max_pct
        return min(size, max_size)

    def open_trade(self, signal_id: int, pair: str, direction: str,
                   price: float, stop_loss: float, take_profit: float,
                   atr=None, context: dict = None) -> int | None:
        """
        Abre un trade de spread.
        direction = 'BUY'  → Long ETH, Short BTC
        direction = 'SELL' → Short ETH, Long BTC
        El par siempre es BTC_ETH_SPREAD.
        context   = dict con z_score_open, hurst_open, coint_pvalue_open, beta_open,
                    macro_regime, eth_rsi_open para observabilidad del experimento.
        """
        if not self.can_open_trade():
            logger.info("🚫 Max open trades alcanzado — no se abre nuevo spread")
            return None

        if any(t["pair"] == SPREAD_PAIR for t in self.open_trades):
            logger.info("🚫 Ya hay un spread trade abierto — esperando cierre")
            return None

        ctx  = context or {}
        size = self._position_size(price, stop_loss)
        tid  = open_paper_trade({
            "signal_id":          signal_id,
            "pair":               SPREAD_PAIR,
            "direction":          direction,
            "open_time":          datetime.now(timezone.utc).isoformat(),
            "open_price":         price,
            "stop_loss":          stop_loss,
            "take_profit":        take_profit,
            "position_size":      round(size, 2),
            "strategy_name":      ctx.get("strategy_name", "ZSCORE_MEAN_REVERSION"),
            "z_score_open":       ctx.get("z_score_open"),
            "hurst_open":         ctx.get("hurst_open"),
            "coint_pvalue_open":  ctx.get("coint_pvalue_open"),
            "beta_open":          ctx.get("beta_open"),
            "macro_regime":       ctx.get("macro_regime"),
            "eth_rsi_open":       ctx.get("eth_rsi_open"),
        })
        dir_label = "LONG SPREAD (BUY ETH)" if direction == "BUY" else "SHORT SPREAD (SELL ETH)"
        logger.info(f"📈 #{tid} {dir_label} | ETH @ ${price:,.2f} | "
                    f"SL=${stop_loss:,.2f} TP=${take_profit:,.2f} | ${size:,.0f}")
        return tid

    def close_spread_trade_by_zscore(self, z_score: float,
                                     eth_price: float) -> list:
        """
        Cierra trades de spread cuando el Z-score alcanza los umbrales.

        - TP: |z_score| < ZSCORE_EXIT  (reversión completada)
        - SL: z_score < -ZSCORE_STOP (para LONG) o > +ZSCORE_STOP (para SHORT)
        """
        exit_z = float(get_bot_config("ZSCORE_EXIT", config.ZSCORE_EXIT))
        stop_z = float(get_bot_config("ZSCORE_STOP", config.ZSCORE_STOP))
        closed = []

        for t in self.open_trades:
            if t["pair"] != SPREAD_PAIR:
                continue

            direction = t["direction"]
            reason    = None

            if abs(z_score) <= exit_z:
                reason = "TP_HIT"   # Spread revirtió a la media
            elif direction == "BUY"  and z_score <= -stop_z:
                reason = "SL_HIT"   # Spread empeoró más (ETH sigue cayendo)
            elif direction == "SELL" and z_score >= stop_z:
                reason = "SL_HIT"   # Spread empeoró más (ETH sigue subiendo)

            if not reason:
                continue

            pnl = close_paper_trade(t["id"], eth_price, reason)
            self.balance += pnl
            update_portfolio(
                self.balance, self.balance,
                f"#{t['id']} {reason} Z={z_score:.2f}"
            )
            emoji = "✅" if pnl > 0 else "❌"
            logger.info(
                f"{emoji} #{t['id']} {SPREAD_PAIR} {reason} | "
                f"Z={z_score:.2f} | P&L ${pnl:+.2f} | Balance ${self.balance:,.2f}"
            )
            closed.append({
                "id": t["id"], "pair": SPREAD_PAIR,
                "reason": reason, "pnl": pnl
            })

        return closed

    def stats(self):
        return get_dashboard_data()
