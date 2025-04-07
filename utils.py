import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import filedialog, messagebox
import os
from typing import List, Dict, Tuple, Optional, Any


def format_currency(value: float) -> str:
    """格式化货币值"""
    return f"${value:.2f}"


def format_percentage(value: float) -> str:
    """格式化百分比值"""
    return f"{value * 100:.2f}%"


def generate_range(start: float, end: float, step: float) -> List[float]:
    """生成数值范围列表"""
    result = []
    current = start
    while current <= end:
        result.append(current)
        current += step
    return result


def ask_open_file(title: str = "选择文件",
                  filetypes: List[Tuple[str, str]] = [("Excel文件", "*.xlsx"), ("所有文件", "*.*")]) -> str:
    """显示文件选择对话框"""
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    file_path = filedialog.askopenfilename(title=title, filetypes=filetypes)
    root.destroy()
    return file_path


def show_message(title: str, message: str, message_type: str = "info") -> None:
    """显示消息框"""
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口

    if message_type.lower() == "info":
        messagebox.showinfo(title, message)
    elif message_type.lower() == "warning":
        messagebox.showwarning(title, message)
    elif message_type.lower() == "error":
        messagebox.showerror(title, message)

    root.destroy()


def create_scrollable_frame(parent: Any) -> Tuple[Any, Any]:
    """创建可滚动的框架"""
    # 创建Canvas
    canvas = tk.Canvas(parent)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)

    # 添加滚动条
    scrollbar = tk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # 配置Canvas
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    # 创建Frame
    frame = tk.Frame(canvas)
    canvas.create_window((0, 0), window=frame, anchor="nw")

    return canvas, frame


def export_to_excel(data: pd.DataFrame, file_path: str) -> bool:
    """导出数据到Excel文件"""
    try:
        data.to_excel(file_path, index=False)
        return True
    except Exception as e:
        print(f"Error exporting to Excel: {e}")
        return False


def calculate_statistics(values: List[float]) -> Dict[str, float]:
    """计算统计数据"""
    if not values:
        return {
            'mean': 0.0,
            'median': 0.0,
            'std': 0.0,
            'min': 0.0,
            'max': 0.0
        }

    return {
        'mean': np.mean(values),
        'median': np.median(values),
        'std': np.std(values),
        'min': np.min(values),
        'max': np.max(values)
    }