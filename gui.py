#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
图形用户界面模块
负责创建用户界面并处理用户交互
"""

import sys
import os
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QProgressBar, QTableWidget, QTableWidgetItem, QTabWidget,
    QGroupBox, QFormLayout, QLineEdit, QDoubleSpinBox, QSpinBox,
    QCheckBox, QMessageBox, QSplitter, QApplication, QHeaderView, QMenu,
    QAbstractItemView
)
from PyQt5.QtCore import Qt, pyqtSlot, QTimer, QPoint  # 添加 QPoint 导入
from PyQt5.QtGui import QIcon, QFont, QCursor

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

from data_parser import DataParser
from data_processor import DataProcessor
from optimizer import Optimizer, OptimizerThread
from visualizer import Visualizer


class MainWindow(QMainWindow):
    """主窗口类"""

    def __init__(self):
        super().__init__()

        # 设置窗口属性
        self.setWindowTitle("TradingView回测优化器 - 日止盈止损分析工具")
        self.setGeometry(100, 100, 1280, 800)

        # 初始化数据处理组件
        self.parser = DataParser()
        self.parser.progress_signal.connect(self.update_progress)
        self.parser.status_signal.connect(self.update_status)

        self.optimizer = Optimizer()
        self.optimizer.progress_signal.connect(self.update_progress)
        self.optimizer.status_signal.connect(self.update_status)
        self.optimizer.result_signal.connect(self.update_optimization_results)

        self.visualizer = Visualizer()

        # 存储当前加载的数据和结果
        self.current_file = None
        self.trades = None
        self.optimization_results = []
        self.selected_results = []

        # 初始化UI
        self.init_ui()

    def init_ui(self):
        """初始化用户界面"""
        # 创建中央窗口部件
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(self.central_widget)

        # 创建控制面板
        control_panel = self.create_control_panel()
        main_layout.addLayout(control_panel)

        # 创建进度条和状态栏
        status_layout = QHBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        status_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("就绪")
        status_layout.addWidget(self.status_label)

        main_layout.addLayout(status_layout)

        # 创建主要内容区域
        content_splitter = QSplitter(Qt.Horizontal)

        # 左侧：结果表格
        self.results_table = QTableWidget()
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.results_table.setColumnCount(14)
        self.results_table.setHorizontalHeaderLabels([
            '日止盈 USD', '日止损 USD', '净盈利 USD', '盈利因子', '胜率 %',
            '交易数', '执行交易数', '盈利交易', '亏损交易',
            '盈利日', '亏损日', '触发止盈日', '触发止损日', '最大回撤 USD'
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.verticalHeader().setVisible(True)
        self.results_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.results_table.customContextMenuRequested.connect(self.show_results_context_menu)
        self.results_table.itemSelectionChanged.connect(self.on_result_selection_changed)

        # 右侧：图表和详细信息选项卡
        self.tabs = QTabWidget()

        # 图表选项卡
        self.chart_tab = QWidget()
        chart_layout = QVBoxLayout(self.chart_tab)

        # 图表类型选择
        chart_selection_layout = QHBoxLayout()
        chart_selection_layout.addWidget(QLabel("图表类型:"))

        self.equity_chart_btn = QPushButton("权益曲线")
        self.equity_chart_btn.clicked.connect(self.show_equity_chart)
        chart_selection_layout.addWidget(self.equity_chart_btn)

        self.daily_profit_chart_btn = QPushButton("每日盈亏")
        self.daily_profit_chart_btn.clicked.connect(self.show_daily_profit_chart)
        chart_selection_layout.addWidget(self.daily_profit_chart_btn)

        self.comparison_chart_btn = QPushButton("结果比较")
        self.comparison_chart_btn.clicked.connect(self.show_comparison_chart)
        chart_selection_layout.addWidget(self.comparison_chart_btn)

        chart_selection_layout.addStretch()
        chart_layout.addLayout(chart_selection_layout)

        # 图表区域
        self.chart_widget = QWidget()
        self.chart_layout = QVBoxLayout(self.chart_widget)
        self.chart_canvas = None
        self.chart_toolbar = None

        chart_layout.addWidget(self.chart_widget)

        # 交易明细选项卡
        self.trades_tab = QWidget()
        trades_layout = QVBoxLayout(self.trades_tab)

        self.trades_table = QTableWidget()
        self.trades_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.trades_table.setColumnCount(7)
        self.trades_table.setHorizontalHeaderLabels([
            '交易#', '入场时间', '出场时间', '获利 USD', '原始获利 USD', '执行', '原因'
        ])
        self.trades_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        trades_layout.addWidget(self.trades_table)

        # 添加选项卡
        self.tabs.addTab(self.chart_tab, "图表")
        self.tabs.addTab(self.trades_tab, "交易明细")

        # 添加到分割器
        content_splitter.addWidget(self.results_table)
        content_splitter.addWidget(self.tabs)
        content_splitter.setSizes([400, 800])

        main_layout.addWidget(content_splitter)

    def create_control_panel(self):
        """创建控制面板"""
        control_layout = QHBoxLayout()

        # 文件选择部分
        file_group = QGroupBox("数据文件")
        file_layout = QHBoxLayout(file_group)

        self.file_path_label = QLabel("未选择文件")
        file_layout.addWidget(self.file_path_label)

        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(self.browse_btn)

        control_layout.addWidget(file_group)

        # 优化参数部分
        optimization_group = QGroupBox("优化参数")
        optimization_layout = QFormLayout(optimization_group)

        # 日止盈范围设置
        profit_layout = QHBoxLayout()
        self.profit_start_spin = QDoubleSpinBox()
        self.profit_start_spin.setRange(1, 10000)
        self.profit_start_spin.setValue(200)
        self.profit_start_spin.setSingleStep(50)
        profit_layout.addWidget(QLabel("从:"))
        profit_layout.addWidget(self.profit_start_spin)

        self.profit_end_spin = QDoubleSpinBox()
        self.profit_end_spin.setRange(1, 10000)
        self.profit_end_spin.setValue(2000)
        self.profit_end_spin.setSingleStep(50)
        profit_layout.addWidget(QLabel("到:"))
        profit_layout.addWidget(self.profit_end_spin)

        self.profit_step_spin = QDoubleSpinBox()
        self.profit_step_spin.setRange(1, 1000)
        self.profit_step_spin.setValue(100)
        self.profit_step_spin.setSingleStep(10)
        profit_layout.addWidget(QLabel("步长:"))
        profit_layout.addWidget(self.profit_step_spin)

        optimization_layout.addRow("日止盈范围 (USD):", profit_layout)

        # 日止损范围设置
        loss_layout = QHBoxLayout()
        self.loss_start_spin = QDoubleSpinBox()
        self.loss_start_spin.setRange(1, 10000)
        self.loss_start_spin.setValue(100)
        self.loss_start_spin.setSingleStep(50)
        loss_layout.addWidget(QLabel("从:"))
        loss_layout.addWidget(self.loss_start_spin)

        self.loss_end_spin = QDoubleSpinBox()
        self.loss_end_spin.setRange(1, 10000)
        self.loss_end_spin.setValue(1000)
        self.loss_end_spin.setSingleStep(50)
        loss_layout.addWidget(QLabel("到:"))
        loss_layout.addWidget(self.loss_end_spin)

        self.loss_step_spin = QDoubleSpinBox()
        self.loss_step_spin.setRange(1, 1000)
        self.loss_step_spin.setValue(100)
        self.loss_step_spin.setSingleStep(10)
        loss_layout.addWidget(QLabel("步长:"))
        loss_layout.addWidget(self.loss_step_spin)

        optimization_layout.addRow("日止损范围 (USD):", loss_layout)

        control_layout.addWidget(optimization_group)

        # 操作按钮部分
        button_group = QGroupBox("操作")
        button_layout = QHBoxLayout(button_group)

        self.start_btn = QPushButton("开始优化")
        self.start_btn.clicked.connect(self.start_optimization)
        button_layout.addWidget(self.start_btn)

        self.export_btn = QPushButton("导出结果")
        self.export_btn.clicked.connect(self.export_results)
        self.export_btn.setEnabled(False)
        button_layout.addWidget(self.export_btn)

        control_layout.addWidget(button_group)

        return control_layout

    @pyqtSlot()
    def browse_file(self):
        """浏览文件对话框"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择TradingView回测数据文件", "", "Excel文件 (*.xlsx)"
        )

        if file_path:
            self.current_file = file_path
            self.file_path_label.setText(os.path.basename(file_path))
            self.status_label.setText("正在加载数据文件...")
            self.progress_bar.setValue(0)

            # 加载文件
            if self.parser.load_file(file_path):
                self.trades = self.parser.get_trades()
                self.optimizer.set_trades(self.trades)
                self.status_label.setText(f"已加载文件: {os.path.basename(file_path)}")
                self.start_btn.setEnabled(True)
            else:
                self.status_label.setText("文件加载失败")

    @pyqtSlot()
    def start_optimization(self):
        """开始优化计算"""
        if self.trades is None:
            QMessageBox.warning(self, "警告", "请先加载交易数据文件")
            return

        # 获取优化参数范围
        profit_start = self.profit_start_spin.value()
        profit_end = self.profit_end_spin.value()
        profit_step = self.profit_step_spin.value()

        loss_start = self.loss_start_spin.value()
        loss_end = self.loss_end_spin.value()
        loss_step = self.loss_step_spin.value()

        # 验证参数
        if profit_start >= profit_end:
            QMessageBox.warning(self, "参数错误", "日止盈结束值必须大于开始值")
            return

        if loss_start >= loss_end:
            QMessageBox.warning(self, "参数错误", "日止损结束值必须大于开始值")
            return

        # 禁用界面控件
        self.start_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)

        # 清空之前的结果
        self.results_table.setRowCount(0)
        self.optimization_results = []
        self.selected_results = []

        # 如果图表已存在，清除
        if self.chart_canvas:
            self.chart_layout.removeWidget(self.chart_canvas)
            self.chart_canvas.deleteLater()
            self.chart_canvas = None

        if self.chart_toolbar:
            self.chart_layout.removeWidget(self.chart_toolbar)
            self.chart_toolbar.deleteLater()
            self.chart_toolbar = None

        # 清空交易明细表
        self.trades_table.setRowCount(0)

        # 重置进度条
        self.progress_bar.setValue(0)
        self.status_label.setText("正在进行优化计算...")

        # 创建并启动优化线程
        self.optimizer_thread = OptimizerThread(
            self.optimizer,
            (profit_start, profit_end, profit_step),
            (loss_start, loss_end, loss_step)
        )
        self.optimizer_thread.finished.connect(self.on_optimization_finished)
        self.optimizer_thread.start()

    @pyqtSlot()
    def on_optimization_finished(self):
        """优化完成后的处理"""
        # 重新启用界面控件
        self.start_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)

        # 如果有结果，启用导出按钮
        if self.optimization_results:
            self.export_btn.setEnabled(True)

        self.status_label.setText("优化计算完成")
        self.progress_bar.setValue(100)

    @pyqtSlot(list)
    def update_optimization_results(self, results):
        """更新优化结果表格"""
        self.optimization_results = results

        # 清空表格
        self.results_table.setRowCount(0)

        # 添加优化结果
        for i, result in enumerate(results):
            row_position = self.results_table.rowCount()
            self.results_table.insertRow(row_position)

            self.results_table.setItem(row_position, 0, QTableWidgetItem(f"{result['daily_profit_limit']:.2f}"))
            self.results_table.setItem(row_position, 1, QTableWidgetItem(f"{result['daily_loss_limit']:.2f}"))
            self.results_table.setItem(row_position, 2, QTableWidgetItem(f"{result['total_profit']:.2f}"))
            self.results_table.setItem(row_position, 3, QTableWidgetItem(f"{result['profit_factor']:.2f}"))
            self.results_table.setItem(row_position, 4, QTableWidgetItem(f"{result['win_rate']:.2f}"))
            self.results_table.setItem(row_position, 5, QTableWidgetItem(f"{result['total_trades']}"))
            self.results_table.setItem(row_position, 6, QTableWidgetItem(f"{result['executed_trades']}"))
            self.results_table.setItem(row_position, 7, QTableWidgetItem(f"{result['winning_trades']}"))
            self.results_table.setItem(row_position, 8, QTableWidgetItem(f"{result['losing_trades']}"))
            self.results_table.setItem(row_position, 9, QTableWidgetItem(f"{result['profitable_days']}"))
            self.results_table.setItem(row_position, 10, QTableWidgetItem(f"{result['loss_days']}"))
            self.results_table.setItem(row_position, 11, QTableWidgetItem(f"{result['profit_limit_triggered_days']}"))
            self.results_table.setItem(row_position, 12, QTableWidgetItem(f"{result['loss_limit_triggered_days']}"))
            self.results_table.setItem(row_position, 13, QTableWidgetItem(f"{result['max_drawdown']:.2f}"))

            # 为单元格添加排序用的数据
            for col in range(self.results_table.columnCount()):
                item = self.results_table.item(row_position, col)
                if item:
                    try:
                        value = float(item.text().replace(',', ''))
                        item.setData(Qt.UserRole, value)
                    except ValueError:
                        pass

        # 如果有结果，选中第一行
        if self.results_table.rowCount() > 0:
            self.results_table.selectRow(0)
            # 并自动显示第一个结果的权益曲线
            self.show_equity_chart()

    @pyqtSlot(int)
    def update_progress(self, progress):
        """更新进度条"""
        self.progress_bar.setValue(progress)

    @pyqtSlot(str)
    def update_status(self, status):
        """更新状态栏"""
        self.status_label.setText(status)

    @pyqtSlot()
    def on_result_selection_changed(self):
        """结果选择改变时更新显示"""
        selected_rows = self.results_table.selectionModel().selectedRows()
        if not selected_rows:
            return

        # 获取选中的结果索引
        self.selected_results = [index.row() for index in selected_rows]

        # 如果选中了单个结果，显示其交易明细
        if len(self.selected_results) == 1:
            self.show_trade_details(self.selected_results[0])
            # 更新图表显示
            if self.tabs.currentIndex() == 0:  # 图表选项卡
                self.show_equity_chart()

        # 如果选中了多个结果，启用比较图表按钮
        self.comparison_chart_btn.setEnabled(len(self.selected_results) > 1)

    def show_trade_details(self, result_index):
        """显示选中结果的交易明细"""
        if result_index < 0 or result_index >= len(self.optimization_results):
            return

        result = self.optimization_results[result_index]
        trades = result['trade_details']

        # 清空表格
        self.trades_table.setRowCount(0)

        # 添加交易记录
        for trade in trades:
            row_position = self.trades_table.rowCount()
            self.trades_table.insertRow(row_position)

            # 设置单元格内容
            self.trades_table.setItem(row_position, 0, QTableWidgetItem(str(trade['交易#'])))

            # 处理日期时间显示
            entry_time = trade['入场时间']
            exit_time = trade['出场时间']

            if isinstance(entry_time, pd.Timestamp):
                entry_time = entry_time.strftime('%Y-%m-%d %H:%M:%S')
            if isinstance(exit_time, pd.Timestamp):
                exit_time = exit_time.strftime('%Y-%m-%d %H:%M:%S')

            self.trades_table.setItem(row_position, 1, QTableWidgetItem(str(entry_time)))
            self.trades_table.setItem(row_position, 2, QTableWidgetItem(str(exit_time)))

            # 设置盈亏单元格，根据盈亏设置不同颜色
            profit_item = QTableWidgetItem(f"{trade['获利 USD']:.2f}")
            if trade['获利 USD'] > 0:
                profit_item.setForeground(Qt.darkGreen)
            elif trade['获利 USD'] < 0:
                profit_item.setForeground(Qt.red)
            self.trades_table.setItem(row_position, 3, profit_item)

            # 原始盈亏
            orig_profit_item = QTableWidgetItem(f"{trade['原始获利 USD']:.2f}")
            if trade['原始获利 USD'] > 0:
                orig_profit_item.setForeground(Qt.darkGreen)
            elif trade['原始获利 USD'] < 0:
                orig_profit_item.setForeground(Qt.red)
            self.trades_table.setItem(row_position, 4, orig_profit_item)

            # 是否执行
            executed_item = QTableWidgetItem("是" if trade['执行'] else "否")
            executed_item.setTextAlignment(Qt.AlignCenter)
            self.trades_table.setItem(row_position, 5, executed_item)

            # 原因
            reason_item = QTableWidgetItem(trade['原因'])
            if '止盈' in trade['原因']:
                reason_item.setForeground(Qt.blue)
            elif '止损' in trade['原因']:
                reason_item.setForeground(Qt.darkRed)
            self.trades_table.setItem(row_position, 6, reason_item)

    @pyqtSlot()
    def show_equity_chart(self):
        """显示权益曲线图"""
        if not self.selected_results or self.selected_results[0] >= len(self.optimization_results):
            return

        # 获取选中的第一个结果
        result = self.optimization_results[self.selected_results[0]]

        # 创建权益曲线图
        fig = self.visualizer.create_equity_curve_figure(result)

        # 显示图表
        self.display_chart(fig)

    @pyqtSlot()
    def show_daily_profit_chart(self):
        """显示每日盈亏柱状图"""
        if not self.selected_results or self.selected_results[0] >= len(self.optimization_results):
            return

        # 获取选中的第一个结果
        result = self.optimization_results[self.selected_results[0]]

        # 创建每日盈亏图
        fig = self.visualizer.create_daily_profit_figure(result)

        # 显示图表
        self.display_chart(fig)

    @pyqtSlot()
    def show_comparison_chart(self):
        """显示多个结果比较图"""
        if not self.selected_results or len(self.selected_results) < 2:
            return

        # 创建比较图
        fig = self.visualizer.create_comparison_figure(self.optimization_results, self.selected_results)

        if fig:
            # 显示图表
            self.display_chart(fig)

    def display_chart(self, fig):
        """在图表区域显示matplotlib图形"""
        # 清除之前的图表
        if self.chart_canvas:
            self.chart_layout.removeWidget(self.chart_canvas)
            self.chart_canvas.deleteLater()
            self.chart_canvas = None

        if self.chart_toolbar:
            self.chart_layout.removeWidget(self.chart_toolbar)
            self.chart_toolbar.deleteLater()
            self.chart_toolbar = None

        # 创建新的图表画布和工具栏
        self.chart_canvas = FigureCanvas(fig)
        self.chart_toolbar = NavigationToolbar(self.chart_canvas, self.chart_widget)

        # 添加到布局
        self.chart_layout.addWidget(self.chart_toolbar)
        self.chart_layout.addWidget(self.chart_canvas)

    @pyqtSlot(QPoint)
    def show_results_context_menu(self, position):
        """显示结果表格的上下文菜单"""
        menu = QMenu()

        # 添加菜单项
        view_equity_action = menu.addAction("查看权益曲线")
        view_daily_profit_action = menu.addAction("查看每日盈亏")
        if len(self.selected_results) > 1:
            compare_action = menu.addAction("比较选中结果")

        menu.addSeparator()
        view_trades_action = menu.addAction("查看交易明细")

        # 显示菜单
        action = menu.exec_(self.results_table.mapToGlobal(position))

        # 处理菜单动作
        if action == view_equity_action:
            self.show_equity_chart()
            self.tabs.setCurrentIndex(0)  # 切换到图表选项卡
        elif action == view_daily_profit_action:
            self.show_daily_profit_chart()
            self.tabs.setCurrentIndex(0)  # 切换到图表选项卡
        elif len(self.selected_results) > 1 and action == compare_action:
            self.show_comparison_chart()
            self.tabs.setCurrentIndex(0)  # 切换到图表选项卡
        elif action == view_trades_action:
            if len(self.selected_results) == 1:
                self.show_trade_details(self.selected_results[0])
                self.tabs.setCurrentIndex(1)  # 切换到交易明细选项卡

    @pyqtSlot()
    def export_results(self):
        """导出优化结果到Excel文件"""
        if not self.optimization_results:
            QMessageBox.warning(self, "警告", "没有可导出的优化结果")
            return

        # 获取保存文件路径
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出优化结果", "", "Excel文件 (*.xlsx)"
        )

        if not file_path:
            return

        try:
            # 获取结果数据框
            results_df = self.optimizer.get_results_dataframe()

            # 创建Excel写入器
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # 写入优化结果
                results_df.to_excel(writer, sheet_name='优化结果', index=True)

                # 为每个选中的结果创建单独的表格
                for i, result_idx in enumerate(self.selected_results):
                    if result_idx < len(self.optimization_results):
                        result = self.optimization_results[result_idx]

                        # 创建交易明细表
                        trade_details = pd.DataFrame(result['trade_details'])
                        sheet_name = f"交易明细_{i + 1}"
                        trade_details.to_excel(writer, sheet_name=sheet_name, index=False)

                        # 创建每日结果表
                        daily_results = pd.DataFrame(result['daily_results'])
                        sheet_name = f"每日结果_{i + 1}"
                        daily_results.to_excel(writer, sheet_name=sheet_name, index=False)

            self.status_label.setText(f"结果已导出至: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出错误", f"导出结果时发生错误: {str(e)}")