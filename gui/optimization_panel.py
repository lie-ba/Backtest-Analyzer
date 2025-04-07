import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
from typing import List, Dict, Optional
import threading

from trade_model import TradeCollection
from utils import generate_range


class OptimizationPanel:
    """优化参数设置界面"""

    def __init__(self, parent, main_window):
        self.parent = parent
        self.main_window = main_window
        self.frame = ttk.Frame(parent)

        # 状态变量
        self.is_running = False
        self.trades = None

        # 创建界面
        self._create_widgets()

    def _create_widgets(self):
        """创建界面控件"""
        # 参数设置区域
        settings_frame = ttk.LabelFrame(self.frame, text="参数设置")
        settings_frame.pack(fill=tk.X, padx=10, pady=10)

        # 日止盈参数
        profit_frame = ttk.Frame(settings_frame)
        profit_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(profit_frame, text="日止盈范围 ($):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)

        self.profit_min_var = tk.StringVar(value="100")
        ttk.Label(profit_frame, text="最小值:").grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(profit_frame, textvariable=self.profit_min_var, width=10).grid(row=0, column=2, padx=5, pady=5,
                                                                                 sticky=tk.W)

        self.profit_max_var = tk.StringVar(value="1000")
        ttk.Label(profit_frame, text="最大值:").grid(row=0, column=3, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(profit_frame, textvariable=self.profit_max_var, width=10).grid(row=0, column=4, padx=5, pady=5,
                                                                                 sticky=tk.W)

        self.profit_step_var = tk.StringVar(value="100")
        ttk.Label(profit_frame, text="步长:").grid(row=0, column=5, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(profit_frame, textvariable=self.profit_step_var, width=10).grid(row=0, column=6, padx=5, pady=5,
                                                                                  sticky=tk.W)

        # 日止损参数
        loss_frame = ttk.Frame(settings_frame)
        loss_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(loss_frame, text="日止损范围 ($):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)

        self.loss_min_var = tk.StringVar(value="100")
        ttk.Label(loss_frame, text="最小值:").grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(loss_frame, textvariable=self.loss_min_var, width=10).grid(row=0, column=2, padx=5, pady=5,
                                                                             sticky=tk.W)

        self.loss_max_var = tk.StringVar(value="1000")
        ttk.Label(loss_frame, text="最大值:").grid(row=0, column=3, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(loss_frame, textvariable=self.loss_max_var, width=10).grid(row=0, column=4, padx=5, pady=5,
                                                                             sticky=tk.W)

        self.loss_step_var = tk.StringVar(value="100")
        ttk.Label(loss_frame, text="步长:").grid(row=0, column=5, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(loss_frame, textvariable=self.loss_step_var, width=10).grid(row=0, column=6, padx=5, pady=5,
                                                                              sticky=tk.W)

        # 添加一些默认配置按钮
        presets_frame = ttk.Frame(settings_frame)
        presets_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(presets_frame, text="预设:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)

        ttk.Button(presets_frame, text="精细分析",
                   command=lambda: self._set_preset(100, 1000, 50, 100, 1000, 50)
                   ).grid(row=0, column=1, padx=5, pady=5)

        ttk.Button(presets_frame, text="快速分析",
                   command=lambda: self._set_preset(100, 1000, 100, 100, 1000, 100)
                   ).grid(row=0, column=2, padx=5, pady=5)

        ttk.Button(presets_frame, text="广范围分析",
                   command=lambda: self._set_preset(100, 2000, 100, 100, 2000, 100)
                   ).grid(row=0, column=3, padx=5, pady=5)

        # 运行优化按钮
        buttons_frame = ttk.Frame(self.frame)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)

        self.run_button = ttk.Button(buttons_frame, text="运行优化", command=self._run_optimization)
        self.run_button.pack(side=tk.LEFT, padx=5)

        self.preview_button = ttk.Button(buttons_frame, text="预览参数", command=self._preview_parameters)
        self.preview_button.pack(side=tk.LEFT, padx=5)

        # 参数预览区域
        preview_frame = ttk.LabelFrame(self.frame, text="参数预览")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 创建参数预览的滚动文本框
        preview_scroll = ttk.Scrollbar(preview_frame)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.preview_text = tk.Text(preview_frame, yscrollcommand=preview_scroll.set, height=10)
        self.preview_text.pack(fill=tk.BOTH, expand=True)

        preview_scroll.config(command=self.preview_text.yview)

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.frame, orient=tk.HORIZONTAL,
                                            length=100, mode='determinate',
                                            variable=self.progress_var)
        self.progress_bar.pack(fill=tk.X, padx=10, pady=10)

        # 进度文本
        self.progress_text = ttk.Label(self.frame, text="")
        self.progress_text.pack(padx=10)

    def _set_preset(self, profit_min, profit_max, profit_step, loss_min, loss_max, loss_step):
        """设置预设参数"""
        self.profit_min_var.set(str(profit_min))
        self.profit_max_var.set(str(profit_max))
        self.profit_step_var.set(str(profit_step))
        self.loss_min_var.set(str(loss_min))
        self.loss_max_var.set(str(loss_max))
        self.loss_step_var.set(str(loss_step))

        # 自动预览参数
        self._preview_parameters()

    def _preview_parameters(self):
        """预览参数设置"""
        try:
            # 获取参数
            profit_min = float(self.profit_min_var.get())
            profit_max = float(self.profit_max_var.get())
            profit_step = float(self.profit_step_var.get())

            loss_min = float(self.loss_min_var.get())
            loss_max = float(self.loss_max_var.get())
            loss_step = float(self.loss_step_var.get())

            # 验证参数
            if profit_min <= 0 or profit_max <= 0 or profit_step <= 0:
                messagebox.showerror("错误", "日止盈参数必须大于0")
                return

            if loss_min <= 0 or loss_max <= 0 or loss_step <= 0:
                messagebox.showerror("错误", "日止损参数必须大于0")
                return

            if profit_min > profit_max:
                messagebox.showerror("错误", "日止盈最小值不能大于最大值")
                return

            if loss_min > loss_max:
                messagebox.showerror("错误", "日止损最小值不能大于最大值")
                return

            # 生成参数列表
            profit_limits = generate_range(profit_min, profit_max, profit_step)
            loss_limits = generate_range(loss_min, loss_max, loss_step)

            # 计算组合数
            combinations = len(profit_limits) * len(loss_limits)

            # 清空预览文本
            self.preview_text.delete(1.0, tk.END)

            # 显示参数预览
            preview_text = f"参数预览: 共 {combinations} 个组合\n\n"
            preview_text += f"日止盈额范围: ${profit_min} 到 ${profit_max}, 步长: ${profit_step}\n"
            preview_text += f"生成的日止盈值: {', '.join([f'${pl}' for pl in profit_limits])}\n\n"
            preview_text += f"日止损额范围: ${loss_min} 到 ${loss_max}, 步长: ${loss_step}\n"
            preview_text += f"生成的日止损值: {', '.join([f'${ll}' for ll in loss_limits])}\n\n"

            preview_text += f"预计运行时间: "
            if combinations > 1000:
                preview_text += "较长 (建议减小范围或增加步长)"
            elif combinations > 500:
                preview_text += "中等 (可能需要几分钟)"
            else:
                preview_text += "较短 (通常在一分钟内)"

            self.preview_text.insert(tk.END, preview_text)

            # 保存参数以供运行时使用
            self.profit_limits = profit_limits
            self.loss_limits = loss_limits

        except ValueError:
            messagebox.showerror("错误", "请输入有效的数值")

    def _run_optimization(self):
        """运行优化"""
        if self.is_running:
            messagebox.showinfo("提示", "优化已在运行中")
            return

        if not hasattr(self, 'profit_limits') or not hasattr(self, 'loss_limits'):
            self._preview_parameters()

        # 再次检查参数
        if not hasattr(self, 'profit_limits') or not hasattr(self, 'loss_limits'):
            messagebox.showerror("错误", "无法生成参数，请检查输入")
            return

        if not self.main_window.optimizer:
            messagebox.showerror("错误", "请先加载数据")
            return

        # 开始优化
        self.is_running = True
        self.run_button.config(state=tk.DISABLED)
        self.preview_button.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.progress_text.config(text="开始优化...")

        # 在后台线程中运行优化
        def optimization_thread():
            try:
                self.main_window.run_optimization(self.profit_limits, self.loss_limits)
            finally:
                # 在主线程中更新UI
                self.frame.after(0, self._optimization_finished)

        # 启动后台线程
        threading.Thread(target=optimization_thread).start()

    def _optimization_finished(self):
        """优化完成后的处理"""
        self.is_running = False
        self.run_button.config(state=tk.NORMAL)
        self.preview_button.config(state=tk.NORMAL)
        self.progress_var.set(100)
        self.progress_text.config(text="优化完成!")

    def update_for_data(self, trades: TradeCollection):
        """根据加载的数据更新界面"""
        self.trades = trades

        # 重置进度
        self.progress_var.set(0)
        self.progress_text.config(text="")

        # 分析数据，设置合理的默认值
        if trades and trades.trades:
            # 找出最大单笔盈利和亏损，用于设置默认范围
            max_profit = max(t.profit_usd for t in trades.trades if t.profit_usd > 0) if any(
                t.profit_usd > 0 for t in trades.trades) else 500
            max_loss = abs(min(t.profit_usd for t in trades.trades if t.profit_usd < 0)) if any(
                t.profit_usd < 0 for t in trades.trades) else 500

            # 将最大单笔盈亏四舍五入到最近的百位
            max_profit_rounded = int(np.ceil(max_profit / 100) * 100)
            max_loss_rounded = int(np.ceil(max_loss / 100) * 100)

            # 设置合理的默认值
            self.profit_min_var.set(str(max_profit_rounded // 2))
            self.profit_max_var.set(str(max_profit_rounded * 2))
            self.profit_step_var.set(str(max_profit_rounded // 5))

            self.loss_min_var.set(str(max_loss_rounded // 2))
            self.loss_max_var.set(str(max_loss_rounded * 2))
            self.loss_step_var.set(str(max_loss_rounded // 5))

            # 自动预览参数
            self._preview_parameters()