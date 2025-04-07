import pandas as pd
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional


@dataclass
class Trade:
    """单笔交易记录"""
    trade_id: int
    entry_time: datetime
    exit_time: datetime
    direction: str  # 'long' or 'short'
    entry_price: float
    exit_price: float
    quantity: float
    profit_usd: float
    max_profit_usd: float
    max_loss_usd: float

    @property
    def trade_date(self) -> datetime:
        """获取交易日期（以入场时间为准）"""
        return self.entry_time.replace(hour=0, minute=0, second=0, microsecond=0)

    @property
    def is_profitable(self) -> bool:
        """判断交易是否盈利"""
        return self.profit_usd > 0

    def __str__(self) -> str:
        return f"Trade #{self.trade_id}: {self.direction} {self.quantity} @ {self.entry_price} -> {self.exit_price}, Profit: ${self.profit_usd:.2f}"


class TradeCollection:
    """交易记录集合"""

    def __init__(self, trades: List[Trade] = None):
        self.trades = trades or []
        self._sort_trades()

    def _sort_trades(self):
        """按入场时间排序交易记录"""
        self.trades.sort(key=lambda x: x.entry_time, reverse=False)

    def add_trade(self, trade: Trade):
        """添加交易记录"""
        self.trades.append(trade)
        self._sort_trades()

    def get_trades_by_date(self, date: datetime) -> List[Trade]:
        """获取特定日期的交易记录"""
        target_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        return [t for t in self.trades if t.trade_date == target_date]

    def get_date_range(self) -> Tuple[datetime, datetime]:
        """获取交易记录的日期范围"""
        if not self.trades:
            return None, None

        dates = [t.trade_date for t in self.trades]
        return min(dates), max(dates)

    def get_unique_dates(self) -> List[datetime]:
        """获取所有不重复的交易日期"""
        if not self.trades:
            return []

        dates = set(t.trade_date for t in self.trades)
        return sorted(list(dates))

    def get_total_profit(self) -> float:
        """获取总盈利"""
        return sum(t.profit_usd for t in self.trades)

    def get_win_rate(self) -> float:
        """获取胜率"""
        if not self.trades:
            return 0.0

        win_trades = sum(1 for t in self.trades if t.is_profitable)
        return win_trades / len(self.trades)

    def get_profit_factor(self) -> float:
        """获取盈利因子 (总盈利/总亏损的绝对值)"""
        total_profit = sum(t.profit_usd for t in self.trades if t.is_profitable)
        total_loss = abs(sum(t.profit_usd for t in self.trades if not t.is_profitable))

        if total_loss == 0:
            return float('inf') if total_profit > 0 else 0.0

        return total_profit / total_loss if total_loss != 0 else float('inf')

    def __len__(self) -> int:
        return len(self.trades)

    def to_dataframe(self) -> pd.DataFrame:
        """转换为DataFrame格式"""
        if not self.trades:
            return pd.DataFrame()

        data = []
        for trade in self.trades:
            data.append({
                'trade_id': trade.trade_id,
                'entry_time': trade.entry_time,
                'exit_time': trade.exit_time,
                'direction': trade.direction,
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'quantity': trade.quantity,
                'profit_usd': trade.profit_usd,
                'max_profit_usd': trade.max_profit_usd,
                'max_loss_usd': trade.max_loss_usd,
                'trade_date': trade.trade_date
            })

        return pd.DataFrame(data)


@dataclass
class OptimizationResult:
    """优化结果"""
    daily_profit_limit: float  # 日止盈额
    daily_loss_limit: float  # 日止损额
    trades: TradeCollection  # 实际执行的交易
    original_trades: TradeCollection  # 原始交易集合
    total_profit: float  # 总盈利
    profit_factor: float  # 盈利因子
    win_rate: float  # 胜率
    total_trade_days: int  # 总交易日数
    profit_days: int  # 盈利日数
    loss_days: int  # 亏损日数
    hit_profit_limit_days: int  # 触发日止盈的天数
    hit_loss_limit_days: int  # 触发日止损的天数
    max_drawdown: float  # 最大回撤
    trade_count: int  # 交易数量
    daily_metrics: Dict  # 每日指标
    equity_curve: List[float]  # 权益曲线

    @property
    def id(self) -> str:
        """生成唯一标识符"""
        return f"PL{self.daily_profit_limit:.0f}_LL{self.daily_loss_limit:.0f}"

    def __str__(self) -> str:
        return (f"结果 {self.id}: 盈利=${self.total_profit:.2f}, 盈利因子={self.profit_factor:.2f}, "
                f"胜率={self.win_rate * 100:.1f}%, 交易数={self.trade_count}, "
                f"最大回撤=${self.max_drawdown:.2f}")