import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_parser import TradingViewDataParser
from optimizer import DailyLimitOptimizer
from trade_model import OptimizationResult, TradeCollection
from chart_viewer import ChartViewer
from utils import format_currency, format_percentage, generate_range
from gui.optimization_panel import OptimizationPanel
from gui.results_panel import ResultsPanel
from gui.detail_panel import DetailPanel


class MainWindow:
    """主窗口"""

    def __init__(self, root):
        self.root = root
        self.root.title("TradingView日内止盈止损优化器")
        self.root.geometry("1280x800")
        self.root.minsize(1024, 768)

        # 设置应用图标
        try:
            self.root.iconbitmap('icon.ico')
        except:
            pass  # 如果图标文件不存在，忽略错误

        # 数据和优化器
        self.data_parser = TradingViewDataParser()
        self.optimizer = None
        self.optimization_results = []
        self.selected_results = []

        # 创建菜单
        self._create_menu()

        # 创建主框架
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 创建顶部控制区域
        self.control_frame = ttk.LabelFrame(self.main_frame, text="控制面板")
        self.control_frame.pack(fill=tk.X, pady=(0, 10))

        # 文件加载区域
        self.file_frame = ttk.Frame(self.control_frame)
        self.file_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(self.file_frame, text="数据文件:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.file_path_var = tk.StringVar()
        ttk.Entry(self.file_frame, textvariable=self.file_path_var, width=60).grid(row=0, column=1, padx=5, pady=5,
                                                                                   sticky=tk.W + tk.E)
        ttk.Button(self.file_frame, text="浏览...", command=self._browse_file).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(self.file_frame, text="加载数据", command=self._load_data).grid(row=0, column=3, padx=5, pady=5)

        # 数据信息显示
        self.info_frame = ttk.Frame(self.control_frame)
        self.info_frame.pack(fill=tk.X, padx=10, pady=5)

        self.info_label = ttk.Label(self.info_frame, text="未加载数据")
        self.info_label.pack(anchor=tk.W)

        # 创建Notebook (选项卡控件)
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # 创建优化面板
        self.optimization_panel = OptimizationPanel(self.notebook, self)
        self.notebook.add(self.optimization_panel.frame, text="优化")

        # 创建结果面板
        self.results_panel = ResultsPanel(self.notebook, self)
        self.notebook.add(self.results_panel.frame, text="优化结果")

        # 创建详细信息面板
        self.detail_panel = DetailPanel(self.notebook, self)
        self.notebook.add(self.detail_panel.frame, text="详细交易")

        # 设置状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # 绑定选项卡切换事件
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _create_menu(self):
        """创建菜单栏"""
        menubar = tk.Menu(self.root)

        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="打开数据文件...", command=self._browse_file)
        file_menu.add_command(label="保存优化结果...", command=self._save_results)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        menubar.add_cascade(label="文件", menu=file_menu)

        # 视图菜单
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="优化", command=lambda: self.notebook.select(0))
        view_menu.add_command(label="优化结果", command=lambda: self.notebook.select(1))
        view_menu.add_command(label="详细交易", command=lambda: self.notebook.select(2))
        menubar.add_cascade(label="视图", menu=view_menu)

        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="关于", command=self._show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)

        self.root.config(menu=menubar)

    def _browse_file(self):
        """浏览并选择文件"""
        file_path = filedialog.askopenfilename(
            title="选择TradingView导出数据文件",
            filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")]
        )
        if file_path:
            self.file_path_var.set(file_path)

    def _load_data(self):
        """加载数据文件"""
        file_path = self.file_path_var.get()
        if not file_path:
            messagebox.showerror("错误", "请先选择数据文件")
            return

        self.status_var.set("正在加载数据...")
        self.root.update()

        try:
            success = self.data_parser.load_excel(file_path)
            if success:
                # 获取解析后的交易记录
                trades = self.data_parser.get_trades()

                # 检查是否有有效的交易记录
                if not trades or len(trades.trades) == 0:
                    messagebox.showerror("错误",
                                         "未能从文件中提取任何有效的交易记录。请检查文件是否包含交易数据，并且格式正确。")
                    self.status_var.set("数据加载失败 - 无有效交易记录")
                    return

                # 获取交易摘要信息
                summary = self.data_parser.get_trade_summary()

                # 更新UI显示
                info_text = (
                    f"已加载数据: {os.path.basename(file_path)}\n"
                    f"工作表: {self.data_parser.sheet_name}\n"
                    f"交易笔数: {summary['total_trades']}, "
                    f"交易日数: {summary['unique_dates']}, "
                    f"胜率: {format_percentage(summary['win_rate'])}, "
                    f"总盈利: {format_currency(summary['total_profit'])}"
                )
                self.info_label.config(text=info_text)

                # 创建优化器
                self.optimizer = DailyLimitOptimizer(trades)

                # 更新优化面板
                self.optimization_panel.update_for_data(trades)

                # 切换到优化选项卡
                self.notebook.select(0)

                self.status_var.set(f"已加载 {summary['total_trades']} 笔交易数据")
            else:
                messagebox.showerror("错误",
                                     "无法加载数据文件。\n\n可能的原因:\n1. 文件格式不正确\n2. 文件不包含TradingView交易数据\n3. 数据格式与预期不符\n\n请确保您导出的是完整的TradingView交易历史记录。")
                self.status_var.set("加载数据失败")
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            messagebox.showerror("错误", f"加载数据时出错:\n{str(e)}\n\n详细错误信息已记录到控制台")
            print("详细错误信息:")
            print(error_details)
            self.status_var.set("加载数据出错")

    def run_optimization(self, profit_limits, loss_limits):
        """运行优化"""
        if not self.optimizer:
            messagebox.showerror("错误", "请先加载数据")
            return

        self.status_var.set("正在运行优化...")
        self.root.update()

        try:
            # 运行优化
            self.optimization_results = self.optimizer.run_optimization(profit_limits, loss_limits)

            # 更新结果面板
            self.results_panel.update_results(self.optimization_results)

            # 切换到结果选项卡
            self.notebook.select(1)

            self.status_var.set(f"优化完成，共 {len(self.optimization_results)} 个结果")
        except Exception as e:
            messagebox.showerror("错误", f"优化过程出错: {str(e)}")
            self.status_var.set("优化失败")

    def show_result_details(self, result: OptimizationResult):
        """显示优化结果详情"""
        if not result:
            return

        # 更新详细信息面板
        self.detail_panel.update_for_result(result)

        # 切换到详细信息选项卡
        self.notebook.select(2)

        self.status_var.set(f"显示结果详情: {result.id}")

    def _save_results(self):
        """保存优化结果到Excel文件"""
        if not self.optimization_results:
            messagebox.showinfo("提示", "没有可保存的优化结果")
            return

        file_path = filedialog.asksaveasfilename(
            title="保存优化结果",
            defaultextension=".xlsx",
            filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")]
        )

        if not file_path:
            return

        try:
            # 创建一个包含优化结果的DataFrame
            data = []
            for result in self.optimization_results:
                data.append({
                    "ID": result.id,
                    "日止盈额": result.daily_profit_limit,
                    "日止损额": result.daily_loss_limit,
                    "总盈利": result.total_profit,
                    "盈利因子": result.profit_factor,
                    "胜率": result.win_rate,
                    "交易数": result.trade_count,
                    "总交易日": result.total_trade_days,
                    "盈利日数": result.profit_days,
                    "亏损日数": result.loss_days,
                    "触发止盈日数": result.hit_profit_limit_days,
                    "触发止损日数": result.hit_loss_limit_days,
                    "最大回撤": result.max_drawdown
                })

            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False)

            messagebox.showinfo("成功", f"优化结果已保存到: {file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"保存结果时出错: {str(e)}")

    def _show_about(self):
        """显示关于对话框"""
        about_text = "TradingView日内止盈止损优化器\n\n" \
                     "功能：分析TradingView回测数据，找出最佳的日止盈与止损额\n\n" \
                     "作者：Python Trading Tools Team\n" \
                     "版本：1.0.0"

        messagebox.showinfo("关于", about_text)

    def _on_tab_changed(self, event):
        """处理选项卡切换事件"""
        tab_id = self.notebook.index("current")

        # 根据当前选项卡更新UI状态
        if tab_id == 0:  # 优化选项卡
            pass
        elif tab_id == 1:  # 结果选项卡
            self.results_panel.on_show()
        elif tab_id == 2:  # 详细信息选项卡
            self.detail_panel.on_show()