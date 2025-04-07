#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
工具函数模块
提供各种辅助功能
"""

import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import os


def format_money(value):
    """
    格式化金额显示
    :param value: 金额数值
    :return: 格式化的金额字符串
    """
    return f"${value:.2f}"


def format_percentage(value):
    """
    格式化百分比显示
    :param value: 百分比数值 (已乘以100)
    :return: 格式化的百分比字符串
    """
    return f"{value:.2f}%"


def calculate_drawdown(equity_curve):
    """
    计算回撤数据
    :param equity_curve: 权益曲线数据列表
    :return: 带有回撤数据的列表
    """
    if not equity_curve:
        return []

    result = []
    max_equity = equity_curve[0]['equity']

    for point in equity_curve:
        max_equity = max(max_equity, point['equity'])
        drawdown = max_equity - point['equity']
        drawdown_pct = (drawdown / max_equity * 100) if max_equity > 0 else 0

        result.append({
            'date': point['date'],
            'equity': point['equity'],
            'drawdown': drawdown,
            'drawdown_pct': drawdown_pct
        })

    return result


def is_same_trading_day(dt1, dt2):
    """
    判断两个日期时间是否属于同一个交易日
    :param dt1: 第一个日期时间
    :param dt2: 第二个日期时间
    :return: 是否为同一交易日
    """
    # 如果日期相同，直接返回True
    if dt1.date() == dt2.date():
        return True

    # 如果第一个时间是当天晚上，而第二个是次日凌晨，也可能是同一交易日
    if dt1.time() >= time(18, 0) and dt2.date() == (dt1.date() + timedelta(days=1)) and dt2.time() < time(6, 0):
        return True

    return False


def get_trading_day(dt):
    """
    获取日期时间对应的交易日
    :param dt: 日期时间
    :return: 交易日日期
    """
    # 如果时间是凌晨6点前，认为属于前一个交易日
    if dt.time() < time(6, 0):
        return (dt.date() - timedelta(days=1))
    return dt.date()


def safe_division(numerator, denominator, default=0):
    """
    安全除法，避免除零错误
    :param numerator: 分子
    :param denominator: 分母
    :param default: 分母为零时的默认值
    :return: 除法结果或默认值
    """
    return numerator / denominator if denominator != 0 else default


def memory_usage(pandas_obj):
    """
    计算Pandas对象的内存使用情况
    :param pandas_obj: Pandas DataFrame或Series
    :return: 内存使用量字符串
    """
    if isinstance(pandas_obj, pd.DataFrame):
        usage_bytes = pandas_obj.memory_usage(deep=True).sum()
    else:  # Series
        usage_bytes = pandas_obj.memory_usage(deep=True)

    # 转换为合适的单位
    units = ['bytes', 'KB', 'MB', 'GB', 'TB']

    unit_index = 0
    while usage_bytes >= 1024 and unit_index < len(units) - 1:
        usage_bytes /= 1024.0
        unit_index += 1

    return f"{usage_bytes:.2f} {units[unit_index]}"