import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
import threading

from trade_model import OptimizationResult
from chart_viewer import ChartViewer
from utils import format_currency, format_percentage


class ResultsPanel:
    """优化结果展示面板"""

    def __init__(self, parent, main_window):
        self.parent = parent
        self.main_window = main_window
        self.frame = ttk.Frame(parent)

        # 结果数据
        self.results = []
        self.selected_results = []

        # 控件变量
        self.metric_var = tk.StringVar(value="total_profit")

        # 创建界面
        self._create_widgets()

    def _create_widgets(self):
        """创建界面控件"""
        # 分割界面为左右两部分
        panel = ttk.PanedWindow(self.frame, orient=tk.HORIZONTAL)
        panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧是结果表格
        left_frame = ttk.Frame(panel)
        panel.add(left_frame, weight=1)

        # 结果表格控制区域
        control_frame = ttk.Frame(left_frame)
        control_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(control_frame, text="排序方式:").pack(side=tk.LEFT, padx=5)
        sort_combobox = ttk.Combobox(control_frame, values=[
            "总盈利", "盈利因子", "胜率", "交易数", "最大回撤", "日止盈额", "日止损额"
        ], state="readonly", width=15)
        sort_combobox.current(0)
        sort_combobox.pack(side=tk.LEFT, padx=5)

        sort_button = ttk.Button(control_frame, text="排序",
                                 command=lambda: self._sort_results(sort_combobox.get()))
        sort_button.pack(side=tk.LEFT, padx=5)

        # 比较所选项
        compare_button = ttk.Button(control_frame, text="比较所选", command=self._compare_selected)
        compare_button.pack(side=tk.RIGHT, padx=5)

        # 清除选择
        clear_button = ttk.Button(control_frame, text="清除选择", command=self._clear_selection)
        clear_button.pack(side=tk.RIGHT, padx=5)

        # 结果表格
        table_frame = ttk.Frame(left_frame)
        table_frame.pack(fill=tk.BOTH, expand=True)

        # 创建表格的滚动条
        table_scroll_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
        table_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        table_scroll_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
        table_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        # 创建表格
        self.results_table = ttk.Treeview(
            table_frame,
            columns=("id", "profit_limit", "loss_limit", "total_profit", "profit_factor",
                     "win_rate", "trade_count", "max_drawdown", "profit_days", "loss_days",
                     "hit_profit_days", "hit_loss_days"),
            show="headings",
            yscrollcommand=table_scroll_y.set,
            xscrollcommand=table_scroll_x.set
        )

        # 配置滚动条
        table_scroll_y.config(command=self.results_table.yview)
        table_scroll_x.config(command=self.results_table.xview)

        # 配置表格列
        self.results_table.heading("id", text="ID")
        self.results_table.heading("profit_limit", text="日止盈额")
        self.results_table.heading("loss_limit", text="日止损额")
        self.results_table.heading("total_profit", text="总盈利")
        self.results_table.heading("profit_factor", text="盈利因子")
        self.results_table.heading("win_rate", text="胜率")
        self.results_table.heading("trade_count", text="交易数")
        self.results_table.heading("max_drawdown", text="最大回撤")
        self.results_table.heading("profit_days", text="盈利日数")
        self.results_table.heading("loss_days", text="亏损日数")
        self.results_table.heading("hit_profit_days", text="止盈触发日")
        self.results_table.heading("hit_loss_days", text="止损触发日")

        # 设置列宽
        self.results_table.column("id", width=80, anchor=tk.CENTER)
        self.results_table.column("profit_limit", width=80, anchor=tk.CENTER)
        self.results_table.column("loss_limit", width=80, anchor=tk.CENTER)
        self.results_table.column("total_profit", width=100, anchor=tk.E)
        self.results_table.column("profit_factor", width=80, anchor=tk.CENTER)
        self.results_table.column("win_rate", width=80, anchor=tk.CENTER)
        self.results_table.column("trade_count", width=80, anchor=tk.CENTER)
        self.results_table.column("max_drawdown", width=100, anchor=tk.E)
        self.results_table.column("profit_days", width=80, anchor=tk.CENTER)
        self.results_table.column("loss_days", width=80, anchor=tk.CENTER)
        self.results_table.column("hit_profit_days", width=80, anchor=tk.CENTER)
        self.results_table.column("hit_loss_days", width=80, anchor=tk.CENTER)

        self.results_table.pack(fill=tk.BOTH, expand=True)

        # 绑定表格事件
        self.results_table.bind("<Double-1>", self._on_result_double_click)
        self.results_table.bind("<<TreeviewSelect>>", self._on_result_select)

        # 右侧是图表和热力图
        right_frame = ttk.Frame(panel)
        panel.add(right_frame, weight=2)

        # 图表选择控制区域
        chart_control_frame = ttk.Frame(right_frame)
        chart_control_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(chart_control_frame, text="图表类型:").pack(side=tk.LEFT, padx=5)

        # 指标选择
        ttk.Label(chart_control_frame, text="指标:").pack(side=tk.LEFT, padx=(15, 5))
        metric_combobox = ttk.Combobox(chart_control_frame, textvariable=self.metric_var, values=[
            "总盈利", "盈利因子", "胜率", "最大回撤"
        ], state="readonly", width=12)
        metric_combobox.current(0)
        metric_combobox.pack(side=tk.LEFT, padx=5)

        # 热力图按钮
        heatmap_button = ttk.Button(chart_control_frame, text="生成热力图",
                                    command=lambda: self._show_heatmap(self.metric_var.get()))
        heatmap_button.pack(side=tk.LEFT, padx=5)

        # 图表区域
        chart_frame = ttk.Frame(right_frame)
        chart_frame.pack(fill=tk.BOTH, expand=True)

        # 创建图表查看器
        self.chart_viewer = ChartViewer(self.frame)
        self.chart_viewer.setup_figure(chart_frame)

    def update_results(self, results: List[OptimizationResult]):
        """更新优化结果"""
        self.results = results
        self._update_results_table()

        # 如果有结果，显示热力图
        if results:
            self._show_heatmap("总盈利")

    def _update_results_table(self):
        """更新结果表格"""
        # 清空表格
        for item in self.results_table.get_children():
            self.results_table.delete(item)

        # 插入新数据
        for result in self.results:
            self.results_table.insert("", tk.END, values=(
                result.id,
                f"${result.daily_profit_limit:.0f}",
                f"${result.daily_loss_limit:.0f}",
                f"${result.total_profit:.2f}",
                f"{result.profit_factor:.2f}",
                f"{result.win_rate * 100:.1f}%",
                result.trade_count,
                f"${result.max_drawdown:.2f}",
                result.profit_days,
                result.loss_days,
                result.hit_profit_limit_days,
                result.hit_loss_limit_days
            ))

    def _sort_results(self, sort_by: str):
        """根据选定的列排序结果"""
        if not self.results:
            return

        # 映射列名到结果属性
        sort_map = {
            "总盈利": ("total_profit", True),
            "盈利因子": ("profit_factor", True),
            "胜率": ("win_rate", True),
            "交易数": ("trade_count", True),
            "最大回撤": ("max_drawdown", False),  # 最大回撤越小越好
            "日止盈额": ("daily_profit_limit", True),
            "日止损额": ("daily_loss_limit", True)
        }

        if sort_by in sort_map:
            attr, reverse = sort_map[sort_by]
            self.results.sort(key=lambda x: getattr(x, attr), reverse=reverse)
            self._update_results_table()

    def _on_result_double_click(self, event):
        """处理结果表格的双击事件"""
        selection = self.results_table.selection()
        if not selection:
            return

        # 获取选中项的索引
        item = selection[0]
        index = self.results_table.index(item)

        if 0 <= index < len(self.results):
            # 显示选中结果的详情
            self.main_window.show_result_details(self.results[index])

    def _on_result_select(self, event):
        """处理结果表格的选择事件"""
        selection = self.results_table.selection()

        # 清空已选择的结果
        self.selected_results = []

        # 更新选中的结果
        for item in selection:
            index = self.results_table.index(item)
            if 0 <= index < len(self.results):
                self.selected_results.append(self.results[index])

        # 如果只选中了一个结果，显示其权益曲线
        if len(self.selected_results) == 1:
            self.chart_viewer.plot_equity_curve(self.selected_results[0])

    def _compare_selected(self):
        """比较选中的多个结果"""
        if len(self.selected_results) < 2:
            messagebox.showinfo("提示", "请至少选择两个结果进行比较")
            return

        # 显示多个结果的权益曲线
        self.chart_viewer.plot_multiple_equity_curves(self.selected_results)

    def _clear_selection(self):
        """清除表格选择"""
        self.results_table.selection_remove(self.results_table.selection())
        self.selected_results = []

    def _show_heatmap(self, metric_name: str):
        """显示指定指标的热力图"""
        if not self.results:
            messagebox.showinfo("提示", "没有可用的优化结果")
            return

        # 映射指标名称到属性
        metric_map = {
            "总盈利": "total_profit",
            "盈利因子": "profit_factor",
            "胜率": "win_rate",
            "最大回撤": "max_drawdown"
        }

        metric = metric_map.get(metric_name, "total_profit")
        self.chart_viewer.plot_heatmap(self.results, metric)

    def on_show(self):
        """选项卡显示时的处理"""
        # 刷新图表
        if hasattr(self, 'selected_results') and self.selected_results:
            if len(self.selected_results) == 1:
                self.chart_viewer.plot_equity_curve(self.selected_results[0])
            else:
                self.chart_viewer.plot_multiple_equity_curves(self.selected_results)
        elif hasattr(self, 'results') and self.results:
            metric_name = self.metric_var.get()
            metric_map = {
                "总盈利": "total_profit",
                "盈利因子": "profit_factor",
                "胜率": "win_rate",
                "最大回撤": "max_drawdown"
            }
            metric = metric_map.get(metric_name, "total_profit")
            self.chart_viewer.plot_heatmap(self.results, metric)