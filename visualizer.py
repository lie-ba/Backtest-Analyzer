#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据可视化模块
负责绘制权益曲线、每日盈亏分布等图表
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import seaborn as sns
from datetime import datetime, timedelta
from collections import OrderedDict
import matplotlib.dates as mdates


class Visualizer:
    """交易数据可视化类"""

    def __init__(self):
        # 设置matplotlib样式
        plt.style.use('ggplot')
        sns.set_style("whitegrid")
        # 中文显示问题
        plt.rcParams['font.sans-serif'] = ['SimHei']  # 指定默认字体
        plt.rcParams['axes.unicode_minus'] = False  # 解决保存图像是负号'-'显示为方块的问题

    def create_equity_curve_figure(self, result, title=None):
        """
        创建权益曲线图
        :param result: 优化结果
        :param title: 图表标题
        :return: matplotlib Figure对象
        """
        equity_data = pd.DataFrame(result['equity_curve'])

        fig = Figure(figsize=(10, 6), dpi=100)
        ax = fig.add_subplot(111)

        # 绘制权益曲线
        ax.plot(equity_data['date'], equity_data['equity'], label='权益曲线', linewidth=2)

        # 设置标题和标签
        if title:
            ax.set_title(title)
        else:
            ax.set_title(
                f"日止盈 ${result['daily_profit_limit']:.0f} / 日止损 ${result['daily_loss_limit']:.0f} - 净盈利: ${result['total_profit']:.2f}")
        ax.set_xlabel('日期')
        ax.set_ylabel('权益 (USD)')
        ax.grid(True)

        # 设置x轴日期格式
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        fig.autofmt_xdate()

        # 添加图例
        ax.legend()

        fig.tight_layout()

        return fig

    def create_daily_profit_figure(self, result):
        """
        创建每日盈亏柱状图
        :param result: 优化结果
        :return: matplotlib Figure对象
        """
        daily_results = pd.DataFrame(result['daily_results'])

        fig = Figure(figsize=(10, 6), dpi=100)
        ax = fig.add_subplot(111)

        # 绘制每日盈亏柱状图
        bars = ax.bar(daily_results['date'], daily_results['daily_profit'])

        # 为盈利和亏损设置不同颜色
        for i, bar in enumerate(bars):
            if daily_results['daily_profit'].iloc[i] >= 0:
                bar.set_color('green')
            else:
                bar.set_color('red')

        # 标记触发止盈的日期
        for i, row in daily_results.iterrows():
            if row['profit_limit_triggered']:
                ax.scatter(row['date'], row['daily_profit'], color='blue', marker='^', s=100, zorder=3,
                           label='触发止盈')
            elif row['loss_limit_triggered']:
                ax.scatter(row['date'], row['daily_profit'], color='purple', marker='v', s=100, zorder=3,
                           label='触发止损')

        # 设置标题和标签
        ax.set_title(
            f"每日盈亏 - 日止盈 ${result['daily_profit_limit']:.0f} / 日止损 ${result['daily_loss_limit']:.0f}")
        ax.set_xlabel('日期')
        ax.set_ylabel('每日盈亏 (USD)')
        ax.grid(True)

        # 设置x轴日期格式
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        fig.autofmt_xdate()

        # 添加图例 (用OrderedDict去重)
        handles, labels = ax.get_legend_handles_labels()
        by_label = OrderedDict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys())

        fig.tight_layout()

        return fig

    def create_comparison_figure(self, results, result_indices):
        """
        创建多组结果比较图
        :param results: 所有优化结果列表
        :param result_indices: 要比较的结果索引列表
        :return: matplotlib Figure对象
        """
        if not result_indices:
            return None

        fig = Figure(figsize=(10, 6), dpi=100)
        ax = fig.add_subplot(111)

        # 为每个结果绘制权益曲线
        for idx in result_indices:
            if idx < 0 or idx >= len(results):
                continue

            result = results[idx]
            equity_data = pd.DataFrame(result['equity_curve'])

            label = f"日止盈 ${result['daily_profit_limit']:.0f} / 日止损 ${result['daily_loss_limit']:.0f} - 净盈利: ${result['total_profit']:.2f}"
            ax.plot(equity_data['date'], equity_data['equity'], label=label, linewidth=2)

        # 设置标题和标签
        ax.set_title(f"优化结果比较 - {len(result_indices)} 个结果")
        ax.set_xlabel('日期')
        ax.set_ylabel('权益 (USD)')
        ax.grid(True)

        # 设置x轴日期格式
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        fig.autofmt_xdate()

        # 添加图例
        ax.legend()

        fig.tight_layout()

        return fig