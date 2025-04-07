import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime

from trade_model import OptimizationResult, Trade
from chart_viewer import ChartViewer
from utils import format_currency, format_percentage, export_to_excel


class DetailPanel:
    """优化结果详细信息面板"""

    def __init__(self, parent, main_window):
        self.parent = parent
        self.main_window = main_window
        self.frame = ttk.Frame(parent)

        # 当前查看的结果
        self.current_result = None

        # 创建界面
        self._create_widgets()

    def _create_widgets(self):
        """创建界面控件"""
        # 分割界面为上下两部分
        panel = ttk.PanedWindow(self.frame, orient=tk.VERTICAL)
        panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 上部是结果概览和图表
        top_frame = ttk.Frame(panel)
        panel.add(top_frame, weight=1)

        # 上部分为左右两个区域
        top_panel = ttk.PanedWindow(top_frame, orient=tk.HORIZONTAL)
        top_panel.pack(fill=tk.BOTH, expand=True)

        # 左侧是结果概览
        overview_frame = ttk.LabelFrame(top_panel, text="结果概览")
        top_panel.add(overview_frame, weight=1)

        # 概览内容
        self.overview_text = tk.Text(overview_frame, wrap=tk.WORD, width=40, height=20)
        overview_scroll = ttk.Scrollbar(overview_frame, orient=tk.VERTICAL, command=self.overview_text.yview)
        self.overview_text.config(yscrollcommand=overview_scroll.set)

        overview_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.overview_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 右侧是图表
        chart_frame = ttk.LabelFrame(top_panel, text="权益曲线")
        top_panel.add(chart_frame, weight=2)

        # 创建图表查看器
        self.chart_viewer = ChartViewer(self.frame)
        self.chart_viewer.setup_figure(chart_frame)

        # 下部是交易明细
        bottom_frame = ttk.LabelFrame(panel, text="交易明细")
        panel.add(bottom_frame, weight=2)

        # 添加操作按钮
        button_frame = ttk.Frame(bottom_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(button_frame, text="导出交易明细...", command=self._export_trades).pack(side=tk.LEFT, padx=5)

        # 交易筛选
        ttk.Label(button_frame, text="筛选:").pack(side=tk.LEFT, padx=(15, 5))

        self.filter_var = tk.StringVar(value="所有交易")
        filter_combobox = ttk.Combobox(button_frame, textvariable=self.filter_var, values=[
            "所有交易", "盈利交易", "亏损交易", "触发止盈日交易", "触发止损日交易"
        ], state="readonly", width=15)
        filter_combobox.pack(side=tk.LEFT, padx=5)

        ttk.Button(button_frame, text="应用筛选", command=self._apply_filter).pack(side=tk.LEFT, padx=5)

        # 交易明细表格
        table_frame = ttk.Frame(bottom_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 创建表格的滚动条
        table_scroll_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
        table_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        table_scroll_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
        table_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        # 创建交易明细表格
        self.trades_table = ttk.Treeview(
            table_frame,
            columns=("id", "date", "entry_time", "exit_time", "direction",
                     "entry_price", "exit_price", "quantity", "profit", "max_profit", "max_loss"),
            show="headings",
            yscrollcommand=table_scroll_y.set,
            xscrollcommand=table_scroll_x.set
        )

        # 配置滚动条
        table_scroll_y.config(command=self.trades_table.yview)
        table_scroll_x.config(command=self.trades_table.xview)

        # 配置表格列
        self.trades_table.heading("id", text="交易#")
        self.trades_table.heading("date", text="日期")
        self.trades_table.heading("entry_time", text="入场时间")
        self.trades_table.heading("exit_time", text="出场时间")
        self.trades_table.heading("direction", text="方向")
        self.trades_table.heading("entry_price", text="入场价格")
        self.trades_table.heading("exit_price", text="出场价格")
        self.trades_table.heading("quantity", text="数量")
        self.trades_table.heading("profit", text="盈亏")
        self.trades_table.heading("max_profit", text="最大获利")
        self.trades_table.heading("max_loss", text="最大亏损")

        # 设置列宽
        self.trades_table.column("id", width=60, anchor=tk.CENTER)
        self.trades_table.column("date", width=100, anchor=tk.CENTER)
        self.trades_table.column("entry_time", width=150, anchor=tk.CENTER)
        self.trades_table.column("exit_time", width=150, anchor=tk.CENTER)
        self.trades_table.column("direction", width=60, anchor=tk.CENTER)
        self.trades_table.column("entry_price", width=100, anchor=tk.E)
        self.trades_table.column("exit_price", width=100, anchor=tk.E)
        self.trades_table.column("quantity", width=80, anchor=tk.CENTER)
        self.trades_table.column("profit", width=100, anchor=tk.E)
        self.trades_table.column("max_profit", width=100, anchor=tk.E)
        self.trades_table.column("max_loss", width=100, anchor=tk.E)

        self.trades_table.pack(fill=tk.BOTH, expand=True)

    def update_for_result(self, result: OptimizationResult):
        """根据优化结果更新界面"""
        self.current_result = result

        # 更新概览信息
        self._update_overview()

        # 更新图表
        self.chart_viewer.plot_daily_analysis(result)

        # 更新交易明细
        self._update_trades_table()

    def _update_overview(self):
        """更新概览信息"""
        if not self.current_result:
            return

        # 清空概览文本
        self.overview_text.delete(1.0, tk.END)

        # 添加概览信息
        result = self.current_result
        overview_text = f"优化参数 ID: {result.id}\n\n"
        overview_text += f"日止盈额: ${result.daily_profit_limit:.2f}\n"
        overview_text += f"日止损额: ${result.daily_loss_limit:.2f}\n\n"

        overview_text += f"整体表现:\n"
        overview_text += f"总盈利: ${result.total_profit:.2f}\n"
        overview_text += f"盈利因子: {result.profit_factor:.2f}\n"
        overview_text += f"胜率: {result.win_rate * 100:.1f}%\n"
        overview_text += f"最大回撤: ${result.max_drawdown:.2f}\n\n"

        overview_text += f"交易统计:\n"
        overview_text += f"交易总数: {result.trade_count}\n"
        overview_text += f"交易日数: {result.total_trade_days}\n"
        overview_text += f"盈利日数: {result.profit_days}\n"
        overview_text += f"亏损日数: {result.loss_days}\n"
        overview_text += f"触发日止盈的天数: {result.hit_profit_limit_days}\n"
        overview_text += f"触发日止损的天数: {result.hit_loss_limit_days}\n\n"

        # 添加更详细的每日统计
        if result.daily_metrics:
            # 计算平均日盈亏
            daily_profits = [metrics["profit"] for metrics in result.daily_metrics.values()]
            avg_daily_profit = sum(daily_profits) / len(daily_profits) if daily_profits else 0

            overview_text += f"每日统计:\n"
            overview_text += f"平均日盈亏: ${avg_daily_profit:.2f}\n"
            overview_text += f"日盈亏标准差: ${np.std(daily_profits):.2f}\n"
            overview_text += f"最佳交易日: ${max(daily_profits):.2f}\n"
            overview_text += f"最差交易日: ${min(daily_profits):.2f}\n"

        # 与原始交易集合比较
        if result.original_trades:
            original_total_profit = result.original_trades.get_total_profit()
            original_trade_count = len(result.original_trades)
            original_win_rate = result.original_trades.get_win_rate()

            overview_text += f"\n与原始交易比较:\n"
            profit_change = result.total_profit - original_total_profit
            profit_pct_change = (profit_change / abs(original_total_profit)) * 100 if original_total_profit else 0

            overview_text += f"原始总盈利: ${original_total_profit:.2f}\n"
            overview_text += f"盈利变化: ${profit_change:.2f} ({profit_pct_change:+.1f}%)\n"
            overview_text += f"原始交易数: {original_trade_count}\n"
            overview_text += f"交易数变化: {result.trade_count - original_trade_count}\n"
            overview_text += f"原始胜率: {original_win_rate * 100:.1f}%\n"
            overview_text += f"胜率变化: {(result.win_rate - original_win_rate) * 100:+.1f}%\n"

        # 插入到概览文本框
        self.overview_text.insert(tk.END, overview_text)
        self.overview_text.config(state=tk.DISABLED)  # 设为只读

    def _update_trades_table(self):
        """更新交易明细表格"""
        if not self.current_result:
            return

        # 清空表格
        for item in self.trades_table.get_children():
            self.trades_table.delete(item)

        # 获取交易记录
        trades = self.current_result.trades.trades

        # 应用筛选
        filter_type = self.filter_var.get()
        if filter_type == "盈利交易":
            trades = [t for t in trades if t.profit_usd > 0]
        elif filter_type == "亏损交易":
            trades = [t for t in trades if t.profit_usd < 0]
        elif filter_type == "触发止盈日交易":
            hit_profit_dates = [date for date, metrics in self.current_result.daily_metrics.items()
                                if metrics["hit_profit_limit"]]
            trades = [t for t in trades if t.trade_date in hit_profit_dates]
        elif filter_type == "触发止损日交易":
            hit_loss_dates = [date for date, metrics in self.current_result.daily_metrics.items()
                              if metrics["hit_loss_limit"]]
            trades = [t for t in trades if t.trade_date in hit_loss_dates]

        # 插入交易记录
        for trade in trades:
            # 格式化日期和时间
            date_str = trade.trade_date.strftime("%Y-%m-%d")
            entry_time_str = trade.entry_time.strftime("%Y-%m-%d %H:%M:%S")
            exit_time_str = trade.exit_time.strftime("%Y-%m-%d %H:%M:%S")

            # 格式化方向
            direction_str = "多" if trade.direction == "long" else "空"

            # 插入到表格
            self.trades_table.insert("", tk.END, values=(
                trade.trade_id,
                date_str,
                entry_time_str,
                exit_time_str,
                direction_str,
                f"{trade.entry_price:.2f}",
                f"{trade.exit_price:.2f}",
                trade.quantity,
                f"${trade.profit_usd:.2f}",
                f"${trade.max_profit_usd:.2f}",
                f"${trade.max_loss_usd:.2f}"
            ))

    def _apply_filter(self):
        """应用交易筛选"""
        self._update_trades_table()

    def _export_trades(self):
        """导出交易明细到Excel"""
        if not self.current_result or not self.current_result.trades:
            messagebox.showinfo("提示", "没有可导出的交易记录")
            return

        # 获取保存文件路径
        file_path = tk.filedialog.asksaveasfilename(
            title="导出交易明细",
            defaultextension=".xlsx",
            filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")]
        )

        if not file_path:
            return

        try:
            # 创建DataFrame
            trades = self.current_result.trades.trades

            # 应用筛选
            filter_type = self.filter_var.get()
            if filter_type == "盈利交易":
                trades = [t for t in trades if t.profit_usd > 0]
            elif filter_type == "亏损交易":
                trades = [t for t in trades if t.profit_usd < 0]
            elif filter_type == "触发止盈日交易":
                hit_profit_dates = [date for date, metrics in self.current_result.daily_metrics.items()
                                    if metrics["hit_profit_limit"]]
                trades = [t for t in trades if t.trade_date in hit_profit_dates]
            elif filter_type == "触发止损日交易":
                hit_loss_dates = [date for date, metrics in self.current_result.daily_metrics.items()
                                  if metrics["hit_loss_limit"]]
                trades = [t for t in trades if t.trade_date in hit_loss_dates]

            # 准备数据
            data = []
            for trade in trades:
                data.append({
                    "交易#": trade.trade_id,
                    "日期": trade.trade_date.strftime("%Y-%m-%d"),
                    "入场时间": trade.entry_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "出场时间": trade.exit_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "方向": "多" if trade.direction == "long" else "空",
                    "入场价格": trade.entry_price,
                    "出场价格": trade.exit_price,
                    "数量": trade.quantity,
                    "盈亏": trade.profit_usd,
                    "最大获利": trade.max_profit_usd,
                    "最大亏损": trade.max_loss_usd
                })

            df = pd.DataFrame(data)

            # 添加结果信息
            info_df = pd.DataFrame([{
                "参数ID": self.current_result.id,
                "日止盈额": self.current_result.daily_profit_limit,
                "日止损额": self.current_result.daily_loss_limit,
                "总盈利": self.current_result.total_profit,
                "盈利因子": self.current_result.profit_factor,
                "胜率": self.current_result.win_rate,
                "最大回撤": self.current_result.max_drawdown,
                "交易数": self.current_result.trade_count,
                "触发止盈日数": self.current_result.hit_profit_limit_days,
                "触发止损日数": self.current_result.hit_loss_limit_days,
                "筛选类型": filter_type
            }])

            # 创建Excel写入器
            with pd.ExcelWriter(file_path) as writer:
                info_df.to_excel(writer, sheet_name="优化结果信息", index=False)
                df.to_excel(writer, sheet_name="交易明细", index=False)

            messagebox.showinfo("成功", f"交易明细已导出到: {file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"导出交易明细时出错: {str(e)}")

    def on_show(self):
        """选项卡显示时的处理"""
        # 启用编辑概览文本
        self.overview_text.config(state=tk.NORMAL)

        # 刷新界面
        if self.current_result:
            self._update_overview()
            self.chart_viewer.plot_daily_analysis(self.current_result)