#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
交易策略优化模块
负责根据给定的参数范围，计算最佳的日止盈止损参数
"""

import pandas as pd
import numpy as np
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal, QThread
from data_processor import DataProcessor


class Optimizer(QObject):
    """交易策略优化器"""

    # 定义信号用于报告进度和结果
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    result_signal = pyqtSignal(list)

    def __init__(self, trades=None):
        super().__init__()
        self.trades = trades
        self.processor = DataProcessor()
        self.processor.progress_signal.connect(self._update_processor_progress)
        self.processor.status_signal.connect(self._update_processor_status)
        self.results = []
        self._current_progress = 0
        self._total_combinations = 0
        self._processed_combinations = 0

    def _update_processor_progress(self, progress):
        """处理数据处理器的进度信号"""
        # 进度计算：每个组合都有一个处理进度，总进度是组合进度 + 处理进度的比例
        combination_progress = progress / 100
        current_progress = (self._processed_combinations + combination_progress) / self._total_combinations * 100
        self.progress_signal.emit(int(current_progress))

    def _update_processor_status(self, status):
        """处理数据处理器的状态信号"""
        self.status_signal.emit(status)

    def set_trades(self, trades):
        """设置交易数据"""
        self.trades = trades
        self.processor.set_trades(trades)

    def run_optimization(self, profit_limits, loss_limits):
        """
        运行优化计算
        :param profit_limits: 日止盈额度范围 (开始, 结束, 步长)
        :param loss_limits: 日止损额度范围 (开始, 结束, 步长)
        """
        if self.trades is None or self.trades.empty:
            self.status_signal.emit("没有交易数据可供优化")
            return

        # 生成所有参数组合
        profit_range = np.arange(profit_limits[0], profit_limits[1] + profit_limits[2], profit_limits[2])
        loss_range = np.arange(loss_limits[0], loss_limits[1] + loss_limits[2], loss_limits[2])

        combinations = [(p, l) for p in profit_range for l in loss_range]
        self._total_combinations = len(combinations)
        self._processed_combinations = 0

        self.status_signal.emit(f"开始优化计算，共 {self._total_combinations} 种参数组合")
        self.results = []

        # 开始计算每种组合的结果
        for profit_limit, loss_limit in combinations:
            self.status_signal.emit(f"计算日止盈 ${profit_limit:.2f} / 日止损 ${loss_limit:.2f}")

            # 应用日止盈止损计算结果
            result = self.processor.apply_daily_limits(profit_limit, loss_limit)

            if result:
                self.results.append(result)

            self._processed_combinations += 1
            progress = self._processed_combinations / self._total_combinations * 100
            self.progress_signal.emit(int(progress))

        # 按总盈利降序排序结果
        self.results.sort(key=lambda x: x['total_profit'], reverse=True)

        self.status_signal.emit(f"优化计算完成，共 {len(self.results)} 个有效结果")
        self.result_signal.emit(self.results)

        return self.results

    def get_results_dataframe(self):
        """
        获取优化结果的DataFrame表示
        :return: 包含所有优化结果的DataFrame
        """
        if not self.results:
            return None

        # 创建结果数据表
        results_data = []
        for result in self.results:
            results_data.append({
                '日止盈 USD': result['daily_profit_limit'],
                '日止损 USD': result['daily_loss_limit'],
                '净盈利 USD': result['total_profit'],
                '盈利因子': round(result['profit_factor'], 2),
                '胜率 %': round(result['win_rate'], 2),
                '交易数': result['total_trades'],
                '执行交易数': result['executed_trades'],
                '盈利交易': result['winning_trades'],
                '亏损交易': result['losing_trades'],
                '盈利日': result['profitable_days'],
                '亏损日': result['loss_days'],
                '触发止盈日': result['profit_limit_triggered_days'],
                '触发止损日': result['loss_limit_triggered_days'],
                '最大回撤 USD': round(result['max_drawdown'], 2),
            })

        return pd.DataFrame(results_data)


class OptimizerThread(QThread):
    """优化器线程类，用于后台运行优化计算"""

    def __init__(self, optimizer, profit_limits, loss_limits):
        super().__init__()
        self.optimizer = optimizer
        self.profit_limits = profit_limits
        self.loss_limits = loss_limits

    def run(self):
        """运行优化计算"""
        self.optimizer.run_optimization(self.profit_limits, self.loss_limits)