import tkinter as tk
import sys
import os
import traceback
from tkinter import messagebox

# 添加模块路径
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# 导入主窗口
from gui.main_window import MainWindow


def exception_handler(exc_type, exc_value, exc_traceback):
    """全局异常处理器"""
    # 构建错误信息
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

    # 显示错误对话框
    messagebox.showerror("错误", f"应用发生了未处理的异常:\n\n{error_msg}\n\n请报告这个问题给开发者。")

    # 写入错误日志
    try:
        with open('error_log.txt', 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.datetime.now()}] 异常:\n")
            f.write(error_msg)
            f.write("\n\n")
    except:
        pass

    # 调用原始的异常处理器
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def main():
    """程序入口"""
    # 设置全局异常处理器
    sys.excepthook = exception_handler

    # 创建主窗口
    root = tk.Tk()
    app = MainWindow(root)

    # 运行应用
    root.mainloop()

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
            # 更新信息显示
            trades = self.data_parser.get_trades()
            if not trades or len(trades.trades) == 0:
                messagebox.showerror("错误", "未能从文件中提取任何有效的交易记录")
                self.status_var.set("数据加载失败 - 无有效交易记录")
                return

            summary = self.data_parser.get_trade_summary()

            info_text = (
                f"已加载数据: {os.path.basename(file_path)}\n"
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
            messagebox.showerror("错误", "无法加载数据文件，请检查文件格式和列名")
            self.status_var.set("加载数据失败")
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        messagebox.showerror("错误", f"加载数据时出错: \n{str(e)}\n\n详细信息已记录到控制台")
        print("详细错误信息:")
        print(error_details)
        self.status_var.set("加载数据出错")

if __name__ == "__main__":
    import datetime

    main()