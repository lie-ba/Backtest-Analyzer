#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
交易数据处理模块
负责将原始交易数据转换为能够应用止盈止损策略的格式
并根据指定的日止盈止损额进行模拟计算
"""

import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from PyQt5.QtCore import QObject, pyqtSignal


class DataProcessor(QObject):
    """交易数据处理类"""

    # 定义信号用于报告进度
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.trades = None
        self.daily_trades = None

    def set_trades(self, trades):
        """
        设置交易数据
        :param trades: 交易数据DataFrame
        """
        self.trades = trades.copy()
        self._prepare_daily_trades()

    def _prepare_daily_trades(self):
        """按交易日期整理交易数据"""
        if self.trades is None or self.trades.empty:
            return

        # 确保交易日期是日期类型
        self.trades['交易日期'] = pd.to_datetime(self.trades['交易日期']).dt.date

        # 按日期分组
        daily_trades = {}
        unique_dates = self.trades['交易日期'].unique()

        total_dates = len(unique_dates)
        processed = 0

        for trade_date in unique_dates:
            # 获取当日的所有交易
            day_trades = self.trades[self.trades['交易日期'] == trade_date].copy()

            # 将当日交易按入场时间排序
            day_trades = day_trades.sort_values('入场时间')

            daily_trades[trade_date] = day_trades

            processed += 1
            progress = int(100 * processed / total_dates)
            self.progress_signal.emit(progress)

        self.daily_trades = daily_trades
        self.status_signal.emit(f"交易数据按日期整理完成，共 {total_dates} 个交易日")

    def apply_daily_limits(self, daily_profit_limit, daily_loss_limit):
        """
        应用日止盈止损限额并计算结果
        :param daily_profit_limit: 日止盈额度 (USD)
        :param daily_loss_limit: 日止损额度 (USD)，应为正数
        :return: 应用止盈止损后的结果
        """
        if self.daily_trades is None:
            self.status_signal.emit("没有可用的交易数据")
            return None

        # 验证参数
        if daily_profit_limit <= 0:
            self.status_signal.emit("日止盈额度必须为正值")
            return None

        if daily_loss_limit <= 0:
            self.status_signal.emit("日止损额度必须为正值")
            return None

        # 计算结果
        result = {
            'daily_profit_limit': daily_profit_limit,
            'daily_loss_limit': daily_loss_limit,
            'trade_details': [],
            'daily_results': [],
            'total_profit': 0,
            'profitable_days': 0,
            'loss_days': 0,
            'profit_limit_triggered_days': 0,
            'loss_limit_triggered_days': 0,
            'total_trades': 0,
            'executed_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'profit_factor': 0,
            'win_rate': 0,
            'max_drawdown': 0,
            'equity_curve': []
        }

        equity = 0
        max_equity = 0
        max_drawdown = 0
        total_profit = 0
        total_loss = 0

        dates = sorted(self.daily_trades.keys())
        total_dates = len(dates)
        processed = 0

        for trade_date in dates:
            day_trades = self.daily_trades[trade_date]

            daily_result = {
                'date': trade_date,
                'trades': [],
                'daily_profit': 0,
                'cumulative_profit': 0,
                'profit_limit_triggered': False,
                'loss_limit_triggered': False
            }

            # 当日累计盈亏
            daily_cumulative_profit = 0

            for _, trade in day_trades.iterrows():
                # 检查当日是否已触发止盈止损
                if daily_result['profit_limit_triggered'] or daily_result['loss_limit_triggered']:
                    # 如果当日已触发止盈止损，此交易不执行
                    trade_result = {
                        '交易#': trade['交易#'],
                        '入场时间': trade['入场时间'],
                        '出场时间': trade['出场时间'],
                        '获利 USD': 0,
                        '原始获利 USD': trade['获利 USD'],
                        '执行': False,
                        '原因': '当日已触发' + ('止盈' if daily_result['profit_limit_triggered'] else '止损')
                    }
                else:
                    # 交易会被执行，检查是否会触发日止盈止损
                    profit_usd = trade['获利 USD']
                    max_trade_profit = trade['最大交易获利 USD']
                    max_trade_loss = abs(trade['最大交易亏损 USD'])

                    # 当前交易执行后的累计盈亏
                    new_daily_profit = daily_cumulative_profit + profit_usd

                    # 检查是否会触发止盈
                    hit_profit_limit = False
                    if profit_usd > 0 and (daily_cumulative_profit + max_trade_profit >= daily_profit_limit):
                        # 触发止盈，获利设为止盈额
                        hit_profit_limit = True
                        adjusted_profit = daily_profit_limit - daily_cumulative_profit
                        trade_result = {
                            '交易#': trade['交易#'],
                            '入场时间': trade['入场时间'],
                            '出场时间': trade['出场时间'],
                            '获利 USD': adjusted_profit,
                            '原始获利 USD': profit_usd,
                            '执行': True,
                            '原因': '触发日止盈'
                        }
                        daily_result['profit_limit_triggered'] = True
                        daily_cumulative_profit = daily_profit_limit
                    # 检查是否会触发止损
                    elif profit_usd < 0 and (daily_cumulative_profit - max_trade_loss <= -daily_loss_limit):
                        # 触发止损，亏损设为止损额
                        adjusted_profit = -daily_loss_limit - daily_cumulative_profit
                        trade_result = {
                            '交易#': trade['交易#'],
                            '入场时间': trade['入场时间'],
                            '出场时间': trade['出场时间'],
                            '获利 USD': adjusted_profit,
                            '原始获利 USD': profit_usd,
                            '执行': True,
                            '原因': '触发日止损'
                        }
                        daily_result['loss_limit_triggered'] = True
                        daily_cumulative_profit = -daily_loss_limit
                    else:
                        # 正常交易，不触发止盈止损
                        trade_result = {
                            '交易#': trade['交易#'],
                            '入场时间': trade['入场时间'],
                            '出场时间': trade['出场时间'],
                            '获利 USD': profit_usd,
                            '原始获利 USD': profit_usd,
                            '执行': True,
                            '原因': '正常交易'
                        }
                        daily_cumulative_profit = new_daily_profit

                daily_result['trades'].append(trade_result)
                result['trade_details'].append(trade_result)

                if trade_result['执行']:
                    result['executed_trades'] += 1
                    if trade_result['获利 USD'] > 0:
                        result['winning_trades'] += 1
                        total_profit += trade_result['获利 USD']
                    elif trade_result['获利 USD'] < 0:
                        result['losing_trades'] += 1
                        total_loss -= trade_result['获利 USD']  # 转为正数

            # 更新当日结果
            daily_result['daily_profit'] = daily_cumulative_profit
            equity += daily_cumulative_profit
            daily_result['cumulative_profit'] = equity

            # 更新最大权益和最大回撤
            max_equity = max(max_equity, equity)
            drawdown = max_equity - equity
            max_drawdown = max(max_drawdown, drawdown)

            result['equity_curve'].append({
                'date': trade_date,
                'equity': equity,
                'drawdown': drawdown
            })

            # 更新每日统计
            if daily_cumulative_profit > 0:
                result['profitable_days'] += 1
            elif daily_cumulative_profit < 0:
                result['loss_days'] += 1

            if daily_result['profit_limit_triggered']:
                result['profit_limit_triggered_days'] += 1

            if daily_result['loss_limit_triggered']:
                result['loss_limit_triggered_days'] += 1

            result['daily_results'].append(daily_result)

            processed += 1
            progress = int(100 * processed / total_dates)
            self.progress_signal.emit(progress)

        # 计算最终统计结果
        result['total_profit'] = equity
        result['total_trades'] = len(self.trades)
        result['max_drawdown'] = max_drawdown

        if total_loss > 0:
            result['profit_factor'] = total_profit / total_loss
        else:
            result['profit_factor'] = float('inf') if total_profit > 0 else 0

        if result['executed_trades'] > 0:
            result['win_rate'] = result['winning_trades'] / result['executed_trades'] * 100

        return result