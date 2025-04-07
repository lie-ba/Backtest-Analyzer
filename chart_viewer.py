import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
import tkinter as tk
from datetime import datetime, timedelta
from trade_model import OptimizationResult, TradeCollection


class ChartViewer:
    """图表显示模块"""

    def __init__(self, master):
        self.master = master
        self.figure = None
        self.canvas = None
        self.toolbar = None
        self.selected_results = []

    def setup_figure(self, frame):
        """设置图表框架"""
        self.figure = Figure(figsize=(10, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        self.toolbar = NavigationToolbar2Tk(self.canvas, frame)
        self.toolbar.update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    def plot_equity_curve(self, result: OptimizationResult, clear_first: bool = True):
        """绘制单个优化结果的权益曲线"""
        if clear_first:
            self.selected_results = [result]
        else:
            if result not in self.selected_results:
                self.selected_results.append(result)

        self._update_equity_curve_plot()

    def plot_multiple_equity_curves(self, results: List[OptimizationResult]):
        """绘制多个优化结果的权益曲线比较"""
        self.selected_results = results
        self._update_equity_curve_plot()

    def clear_plots(self):
        """清除所有图表"""
        self.selected_results = []
        self.figure.clear()
        self.canvas.draw()

    def _update_equity_curve_plot(self):
        """更新权益曲线图表"""
        if not self.selected_results:
            return

        self.figure.clear()
        ax = self.figure.add_subplot(111)

        # 绘制每个选中结果的权益曲线
        for result in self.selected_results:
            # 生成日期索引
            dates = result.original_trades.get_unique_dates()
            dates = [dates[0] - timedelta(days=1)] + dates  # 添加起始日期

            # 截断权益曲线，确保长度匹配
            if len(result.equity_curve) > len(dates):
                equity_curve = result.equity_curve[:len(dates)]
            else:
                equity_curve = result.equity_curve

            # 绘制曲线
            label = f"{result.id}: ${result.total_profit:.2f}"
            ax.plot(dates, equity_curve, label=label)

        # 设置图表属性
        ax.set_title("权益曲线比较")
        ax.set_xlabel("日期")
        ax.set_ylabel("盈利 ($)")
        ax.grid(True)
        ax.legend()

        # 格式化x轴日期
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%Y-%m-%d'))

        # 自动调整布局
        self.figure.tight_layout()
        self.canvas.draw()

    def plot_daily_analysis(self, result: OptimizationResult):
        """绘制每日分析图表"""
        self.figure.clear()

        # 创建子图
        ax1 = self.figure.add_subplot(211)  # 每日盈亏
        ax2 = self.figure.add_subplot(212)  # 累计权益

        # 准备数据
        dates = sorted(result.daily_metrics.keys())
        daily_profits = [result.daily_metrics[date]['profit'] for date in dates]
        cumulative_profits = np.cumsum([0] + daily_profits)

        # 绘制每日盈亏柱状图
        positive_profits = [max(0, p) for p in daily_profits]
        negative_profits = [min(0, p) for p in daily_profits]

        ax1.bar(dates, positive_profits, color='green', label='盈利')
        ax1.bar(dates, negative_profits, color='red', label='亏损')

        # 标记止盈止损触发的日期
        for i, date in enumerate(dates):
            metrics = result.daily_metrics[date]
            if metrics['hit_profit_limit']:
                ax1.annotate('PL', (date, positive_profits[i]),
                             textcoords="offset points", xytext=(0, 5), ha='center')
            if metrics['hit_loss_limit']:
                ax1.annotate('LL', (date, negative_profits[i]),
                             textcoords="offset points", xytext=(0, -10), ha='center')

        # 设置每日盈亏图表属性
        ax1.set_title(f"每日盈亏分析 - {result.id}")
        ax1.set_ylabel("盈亏 ($)")
        ax1.grid(True, axis='y')
        ax1.legend()

        # 绘制累计权益曲线
        ax2.plot(dates, cumulative_profits[1:], 'b-', label='累计权益')

        # 设置累计权益图表属性
        ax2.set_title("累计权益曲线")
        ax2.set_xlabel("日期")
        ax2.set_ylabel("累计盈亏 ($)")
        ax2.grid(True)

        # 格式化x轴日期
        for ax in [ax1, ax2]:
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%Y-%m-%d'))

        # 自动调整布局
        self.figure.tight_layout()
        self.canvas.draw()

    def plot_heatmap(self, results: List[OptimizationResult], metric: str = 'total_profit'):
        """绘制热力图"""
        if not results:
            return

        self.figure.clear()
        ax = self.figure.add_subplot(111)

        # 提取所有不同的止盈止损值
        profit_limits = sorted(list(set(r.daily_profit_limit for r in results)))
        loss_limits = sorted(list(set(r.daily_loss_limit for r in results)))

        # 创建网格数据
        data = np.zeros((len(profit_limits), len(loss_limits)))

        # 填充网格数据
        for i, pl in enumerate(profit_limits):
            for j, ll in enumerate(loss_limits):
                for result in results:
                    if result.daily_profit_limit == pl and result.daily_loss_limit == ll:
                        if metric == 'total_profit':
                            data[i, j] = result.total_profit
                        elif metric == 'profit_factor':
                            data[i, j] = result.profit_factor
                        elif metric == 'win_rate':
                            data[i, j] = result.win_rate * 100
                        elif metric == 'max_drawdown':
                            data[i, j] = -result.max_drawdown  # 反转使较小的回撤显示为较好的结果
                        break

        # 创建热力图
        cmap = 'RdYlGn'
        im = ax.imshow(data, cmap=cmap, aspect='auto')

        # 添加坐标轴标签
        ax.set_xticks(np.arange(len(loss_limits)))
        ax.set_yticks(np.arange(len(profit_limits)))
        ax.set_xticklabels([f"${ll}" for ll in loss_limits])
        ax.set_yticklabels([f"${pl}" for pl in profit_limits])

        # 旋转x轴标签
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

        # 添加标题和坐标轴标签
        metric_names = {
            'total_profit': '总盈利 ($)',
            'profit_factor': '盈利因子',
            'win_rate': '胜率 (%)',
            'max_drawdown': '最大回撤 ($)'
        }
        title = f"优化结果热力图 - {metric_names.get(metric, metric)}"
        ax.set_title(title)
        ax.set_xlabel("日止损额 ($)")
        ax.set_ylabel("日止盈额 ($)")

        # 添加色彩条和值标注
        cbar = self.figure.colorbar(im, ax=ax)

        # 在每个格子中显示数值
        for i in range(len(profit_limits)):
            for j in range(len(loss_limits)):
                value = data[i, j]
                if metric == 'profit_factor':
                    text = f"{value:.2f}"
                elif metric == 'win_rate':
                    text = f"{value:.1f}%"
                else:
                    text = f"${value:.0f}"

                ax.text(j, i, text, ha="center", va="center",
                        color="black" if 0.2 < (value - data.min()) / (data.max() - data.min()) < 0.8 else "white")

        # 自动调整布局
        self.figure.tight_layout()
        self.canvas.draw()