import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import concurrent.futures
from trade_model import Trade, TradeCollection, OptimizationResult


class DailyLimitOptimizer:
    """日止盈止损优化器"""

    def __init__(self, trades: TradeCollection):
        self.original_trades = trades
        self.results = []

    def run_optimization(self,
                         profit_limits: List[float],
                         loss_limits: List[float],
                         max_workers: int = 4) -> List[OptimizationResult]:
        """运行优化,测试不同止盈止损组合"""
        self.results = []
        combinations = [(pl, ll) for pl in profit_limits for ll in loss_limits]

        # 使用多线程加速计算
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_params = {
                executor.submit(self._evaluate_parameters, pl, ll): (pl, ll)
                for pl, ll in combinations
            }

            # 收集结果
            for future in concurrent.futures.as_completed(future_to_params):
                pl, ll = future_to_params[future]
                try:
                    result = future.result()
                    self.results.append(result)
                except Exception as e:
                    print(f"Error evaluating parameters pl={pl}, ll={ll}: {e}")

        # 按总盈利降序排序结果
        self.results.sort(key=lambda x: x.total_profit, reverse=True)
        return self.results

    def _evaluate_parameters(self, daily_profit_limit: float, daily_loss_limit: float) -> OptimizationResult:
        """评估特定日止盈/止损参数的效果"""
        # 获取所有交易日期
        unique_dates = self.original_trades.get_unique_dates()

        # 存储优化后的交易
        optimized_trades = []
        daily_metrics = {}
        equity_curve = [0.0]  # 初始权益为0

        # 统计指标
        total_profit = 0.0
        profit_days = 0
        loss_days = 0
        hit_profit_limit_days = 0
        hit_loss_limit_days = 0

        # 按日期处理交易
        for date in unique_dates:
            daily_trades = self.original_trades.get_trades_by_date(date)

            # 初始化当日累计盈亏
            daily_cumulative_profit = 0.0
            daily_included_trades = []
            hit_profit_limit = False
            hit_loss_limit = False

            # 处理当日每笔交易
            for trade in daily_trades:
                # 检查是否已触发日止盈/止损
                if hit_profit_limit or hit_loss_limit:
                    continue

                # 累计当日盈亏
                daily_cumulative_profit += trade.profit_usd

                # 添加到包含的交易中
                daily_included_trades.append(trade)

                # 检查是否触发日止盈
                if daily_profit_limit > 0 and daily_cumulative_profit >= daily_profit_limit:
                    hit_profit_limit = True
                    daily_cumulative_profit = daily_profit_limit  # 限制最大盈利
                    hit_profit_limit_days += 1

                # 检查是否触发日止损
                if daily_loss_limit > 0 and daily_cumulative_profit <= -daily_loss_limit:
                    hit_loss_limit = True
                    daily_cumulative_profit = -daily_loss_limit  # 限制最大亏损
                    hit_loss_limit_days += 1

            # 更新总盈利和权益曲线
            total_profit += daily_cumulative_profit
            equity_curve.append(total_profit)

            # 更新日统计
            if daily_cumulative_profit > 0:
                profit_days += 1
            elif daily_cumulative_profit < 0:
                loss_days += 1

            # 添加到优化后的交易集合
            optimized_trades.extend(daily_included_trades)

            # 记录当日指标
            daily_metrics[date] = {
                'profit': daily_cumulative_profit,
                'trade_count': len(daily_included_trades),
                'hit_profit_limit': hit_profit_limit,
                'hit_loss_limit': hit_loss_limit
            }

        # 计算最大回撤
        max_drawdown = self._calculate_max_drawdown(equity_curve)

        # 创建优化后的交易集合
        optimized_collection = TradeCollection(optimized_trades)

        # 计算盈利因子和胜率
        profit_factor = optimized_collection.get_profit_factor()
        win_rate = optimized_collection.get_win_rate()

        # 创建优化结果对象
        result = OptimizationResult(
            daily_profit_limit=daily_profit_limit,
            daily_loss_limit=daily_loss_limit,
            trades=optimized_collection,
            original_trades=self.original_trades,
            total_profit=total_profit,
            profit_factor=profit_factor,
            win_rate=win_rate,
            total_trade_days=len(unique_dates),
            profit_days=profit_days,
            loss_days=loss_days,
            hit_profit_limit_days=hit_profit_limit_days,
            hit_loss_limit_days=hit_loss_limit_days,
            max_drawdown=max_drawdown,
            trade_count=len(optimized_trades),
            daily_metrics=daily_metrics,
            equity_curve=equity_curve
        )

        return result

    def _calculate_max_drawdown(self, equity_curve: List[float]) -> float:
        """计算最大回撤"""
        max_dd = 0.0
        peak = equity_curve[0]

        for value in equity_curve:
            if value > peak:
                peak = value
            dd = peak - value
            if dd > max_dd:
                max_dd = dd

        return max_dd

    def get_results(self) -> List[OptimizationResult]:
        """获取优化结果"""
        return self.results

    def get_best_result(self) -> Optional[OptimizationResult]:
        """获取最佳优化结果(按总盈利)"""
        if not self.results:
            return None
        return max(self.results, key=lambda x: x.total_profit)

    def get_result_by_id(self, result_id: str) -> Optional[OptimizationResult]:
        """根据ID获取优化结果"""
        for result in self.results:
            if result.id == result_id:
                return result
        return None