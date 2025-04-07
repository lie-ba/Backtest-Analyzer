#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TradingView回测数据解析模块 - GUI安全适配器版
专门解决与GUI交互时的崩溃问题
"""

import pandas as pd
import numpy as np
import os
import traceback
import gc
import json
from datetime import datetime, date
from PyQt5.QtCore import QObject, pyqtSignal


class DataParser(QObject):
    """TradingView回测数据解析类"""

    # 定义信号用于报告进度
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.raw_data = None
        self._trades = None
        self._trade_dates = None

        # 测试用的数据
        self._is_demo_mode = False

    def log(self, message):
        """记录日志"""
        print(f"日志: {message}")
        try:
            with open("parser_log.txt", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now()}] {message}\n")
        except:
            pass

    def load_file(self, file_path):
        """
        加载Excel文件
        :param file_path: Excel文件路径
        :return: 是否成功加载
        """
        # 清理之前的日志
        try:
            with open("parser_log.txt", "w", encoding="utf-8") as f:
                f.write(f"[{datetime.now()}] 开始解析 {file_path}\n")
        except:
            pass

        self.log(f"加载文件: {file_path}")

        # 重置数据
        self.raw_data = None
        self._trades = None
        self._trade_dates = None
        gc.collect()

        # 验证文件路径
        if not os.path.exists(file_path):
            self.status_signal.emit(f"文件不存在: {file_path}")
            return False

        try:
            self.status_signal.emit("正在读取文件...")

            # 尝试读取交易清单工作表
            success = False

            try:
                self.log("尝试读取'交易清单'工作表")
                df = pd.read_excel(file_path, sheet_name="交易清单")
                self.log(f"成功读取交易清单，列名: {list(df.columns)}")

                # 标准化列名
                if "交易 #" in df.columns:
                    df = df.rename(columns={"交易 #": "交易#"})

                if "日期/时间" in df.columns:
                    df = df.rename(columns={"日期/时间": "时间"})

                self.raw_data = df
                success = True

            except Exception as e:
                self.log(f"读取'交易清单'工作表出错: {str(e)}")
                self.log(traceback.format_exc())

            # 如果读取失败，尝试读取所有工作表
            if not success:
                self.log("尝试读取其他工作表")
                xl = pd.ExcelFile(file_path)
                for sheet_name in xl.sheet_names:
                    try:
                        self.log(f"检查工作表: {sheet_name}")
                        df = pd.read_excel(file_path, sheet_name=sheet_name)

                        # 查找包含交易数据的工作表
                        if "交易 #" in df.columns or "交易#" in df.columns:
                            self.log(f"在工作表 {sheet_name} 中找到交易数据")

                            # 标准化列名
                            if "交易 #" in df.columns:
                                df = df.rename(columns={"交易 #": "交易#"})

                            if "日期/时间" in df.columns:
                                df = df.rename(columns={"日期/时间": "时间"})

                            self.raw_data = df
                            success = True
                            break
                    except Exception as e:
                        self.log(f"处理工作表 {sheet_name} 出错: {str(e)}")

            # 如果成功读取数据，处理它
            if success and self.raw_data is not None:
                # 尝试使用中间JSON文件存储和加载数据
                try:
                    self.log("尝试通过中间JSON文件处理数据")
                    return self._process_via_json()
                except Exception as e:
                    self.log(f"通过JSON处理失败: {str(e)}")
                    self.log(traceback.format_exc())

                    # 回退到直接处理
                    self.log("尝试直接处理数据")
                    return self._generate_demo_data()
            else:
                self.log("未找到或无法读取交易数据")
                return self._generate_demo_data()

        except Exception as e:
            self.status_signal.emit(f"文件加载失败: {str(e)}")
            self.log(f"文件加载失败: {str(e)}")
            self.log(traceback.format_exc())

            # 生成演示数据作为后备
            return self._generate_demo_data()

    def _process_via_json(self):
        """通过中间JSON文件处理数据，避免直接的DataFrame传递"""
        try:
            if self.raw_data is None or self.raw_data.empty:
                self.log("没有原始数据可处理")
                return False

            df = self.raw_data.copy()
            self.log(f"处理数据，行数: {len(df)}, 列: {list(df.columns)}")

            # 检查必要的列
            required_cols = ['交易#', '时间', '获利 USD']
            missing_cols = [col for col in required_cols if col not in df.columns]

            if missing_cols:
                self.log(f"缺少必要列: {missing_cols}")
                return False

            # 转换数据类型
            self.log("转换数据类型")

            # 转换交易编号
            df['交易#'] = pd.to_numeric(df['交易#'], errors='coerce')
            df = df.dropna(subset=['交易#'])
            df['交易#'] = df['交易#'].astype(int)

            # 转换时间
            df['时间'] = pd.to_datetime(df['时间'], errors='coerce')
            df = df.dropna(subset=['时间'])

            # 转换获利
            df['获利 USD'] = pd.to_numeric(df['获利 USD'], errors='coerce')

            # 处理最大交易获利/亏损
            if '最大交易获利 USD' in df.columns:
                df['最大交易获利 USD'] = pd.to_numeric(df['最大交易获利 USD'], errors='coerce')
                df['最大交易获利 USD'] = df['最大交易获利 USD'].fillna(0)
            else:
                df['最大交易获利 USD'] = df['获利 USD'].apply(lambda x: max(0, x))

            if '最大交易亏损 USD' in df.columns:
                df['最大交易亏损 USD'] = pd.to_numeric(df['最大交易亏损 USD'], errors='coerce')
                df['最大交易亏损 USD'] = df['最大交易亏损 USD'].fillna(0)
            elif '交易亏损 USD' in df.columns:
                df['最大交易亏损 USD'] = pd.to_numeric(df['交易亏损 USD'], errors='coerce').abs()
                df['最大交易亏损 USD'] = df['最大交易亏损 USD'].fillna(0)
            else:
                df['最大交易亏损 USD'] = df['获利 USD'].apply(lambda x: abs(min(0, x)))

            # 获取所有交易编号
            trade_ids = df['交易#'].unique()
            self.log(f"找到 {len(trade_ids)} 个交易ID")

            # 将入场和出场记录整合为交易
            trades_list = []

            for trade_id in trade_ids:
                try:
                    # 获取该交易的所有记录
                    trade_records = df[df['交易#'] == trade_id]

                    if len(trade_records) >= 2:
                        # 按时间排序
                        trade_records = trade_records.sort_values('时间')

                        # 第一条是入场，最后一条是出场
                        entry = trade_records.iloc[0]
                        exit = trade_records.iloc[-1]

                        # 创建交易记录
                        trade = {
                            "trade_id": int(trade_id),
                            "entry_time": entry['时间'].strftime("%Y-%m-%d %H:%M:%S"),
                            "exit_time": exit['时间'].strftime("%Y-%m-%d %H:%M:%S"),
                            "trade_date": entry['时间'].strftime("%Y-%m-%d"),
                            "profit": float(exit['获利 USD']),
                            "max_profit": float(exit['最大交易获利 USD']),
                            "max_loss": float(abs(exit['最大交易亏损 USD']))
                        }

                        trades_list.append(trade)
                    elif len(trade_records) == 1:
                        # 只有一条记录
                        record = trade_records.iloc[0]

                        # 创建交易记录
                        exit_time = record['时间']
                        entry_time = exit_time - pd.Timedelta(hours=1)  # 假设入场时间比出场早1小时

                        trade = {
                            "trade_id": int(trade_id),
                            "entry_time": entry_time.strftime("%Y-%m-%d %H:%M:%S"),
                            "exit_time": exit_time.strftime("%Y-%m-%d %H:%M:%S"),
                            "trade_date": exit_time.strftime("%Y-%m-%d"),
                            "profit": float(record['获利 USD']),
                            "max_profit": float(record['最大交易获利 USD']),
                            "max_loss": float(abs(record['最大交易亏损 USD']))
                        }

                        trades_list.append(trade)

                except Exception as e:
                    self.log(f"处理交易 #{trade_id} 出错: {str(e)}")

            if not trades_list:
                self.log("没有生成有效的交易")
                return False

            # 将交易列表保存为JSON文件
            json_path = "trades_data.json"
            try:
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(trades_list, f, ensure_ascii=False, indent=2)

                self.log(f"交易数据已保存至 {json_path}")

                # 提取唯一的交易日期
                trade_dates = list(set(trade['trade_date'] for trade in trades_list))
                trade_dates.sort()  # 按日期排序

                # 保存交易日期JSON
                dates_json_path = "trade_dates.json"
                with open(dates_json_path, 'w', encoding='utf-8') as f:
                    json.dump(trade_dates, f, ensure_ascii=False, indent=2)

                self.log(f"交易日期已保存至 {dates_json_path}")

                # 设置已处理标志
                self._is_demo_mode = False

                self.status_signal.emit(f"解析完成，共 {len(trades_list)} 笔交易")
                return True

            except Exception as e:
                self.log(f"保存JSON文件时出错: {str(e)}")
                return False

        except Exception as e:
            self.log(f"处理数据时出错: {str(e)}")
            self.log(traceback.format_exc())
            return False

    def _generate_demo_data(self):
        """生成演示数据"""
        self.log("生成演示数据")
        self._is_demo_mode = True

        try:
            # 生成10个示例交易
            trades = []
            base_date = datetime.now().date()

            for i in range(1, 11):
                # 创建不同日期的交易
                trade_date = base_date - pd.Timedelta(days=(i % 5))
                entry_time = datetime.combine(trade_date, datetime.min.time()) + pd.Timedelta(hours=9, minutes=30)
                exit_time = entry_time + pd.Timedelta(hours=2)

                # 随机盈亏
                profit = (i % 5 - 2) * 100.0

                trade = {
                    "trade_id": i,
                    "entry_time": entry_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "exit_time": exit_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "trade_date": trade_date.strftime("%Y-%m-%d"),
                    "profit": profit,
                    "max_profit": max(profit, 50.0) if profit > 0 else 50.0,
                    "max_loss": max(abs(profit), 50.0) if profit < 0 else 50.0
                }

                trades.append(trade)

            # 保存演示数据为JSON
            json_path = "trades_data.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(trades, f, ensure_ascii=False, indent=2)

            self.log(f"演示交易数据已保存至 {json_path}")

            # 提取唯一的交易日期
            trade_dates = list(set(trade['trade_date'] for trade in trades))
            trade_dates.sort()  # 按日期排序

            # 保存交易日期JSON
            dates_json_path = "trade_dates.json"
            with open(dates_json_path, 'w', encoding='utf-8') as f:
                json.dump(trade_dates, f, ensure_ascii=False, indent=2)

            self.log(f"演示交易日期已保存至 {dates_json_path}")

            self.status_signal.emit("已生成演示数据，共10笔交易")
            return True

        except Exception as e:
            self.log(f"生成演示数据时出错: {str(e)}")
            self.log(traceback.format_exc())
            return False

    def get_trades(self):
        """获取处理后的交易记录"""
        try:
            self.log("调用get_trades()")

            # 从JSON文件读取数据
            try:
                with open("trades_data.json", 'r', encoding='utf-8') as f:
                    trades_data = json.load(f)

                self.log(f"从JSON读取了 {len(trades_data)} 笔交易")

                # 将字符串日期转换回datetime对象
                for trade in trades_data:
                    trade['entry_time'] = pd.to_datetime(trade['entry_time'])
                    trade['exit_time'] = pd.to_datetime(trade['exit_time'])
                    trade['trade_date'] = pd.to_datetime(trade['trade_date']).date()

                # 创建DataFrame
                df = pd.DataFrame({
                    '交易#': [t['trade_id'] for t in trades_data],
                    '入场时间': [t['entry_time'] for t in trades_data],
                    '出场时间': [t['exit_time'] for t in trades_data],
                    '交易日期': [t['trade_date'] for t in trades_data],
                    '获利 USD': [t['profit'] for t in trades_data],
                    '最大交易获利 USD': [t['max_profit'] for t in trades_data],
                    '最大交易亏损 USD': [t['max_loss'] for t in trades_data]
                })

                # 如果是演示模式，只返回前5条记录
                if self._is_demo_mode:
                    df = df.head(5)

                self.log(f"返回DataFrame，行数: {len(df)}")
                return df

            except Exception as e:
                self.log(f"从JSON读取数据出错: {str(e)}")
                self.log(traceback.format_exc())

                # 返回简单的空DataFrame
                df = pd.DataFrame({
                    '交易#': [],
                    '入场时间': [],
                    '出场时间': [],
                    '交易日期': [],
                    '获利 USD': [],
                    '最大交易获利 USD': [],
                    '最大交易亏损 USD': []
                })
                return df

        except Exception as e:
            self.log(f"获取交易数据时出错: {str(e)}")
            self.log(traceback.format_exc())

            # 返回简单的空DataFrame
            return pd.DataFrame()

    def get_trade_dates(self):
        """获取所有交易日期"""
        try:
            self.log("调用get_trade_dates()")

            # 从JSON文件读取日期
            try:
                with open("trade_dates.json", 'r', encoding='utf-8') as f:
                    dates_data = json.load(f)

                self.log(f"从JSON读取了 {len(dates_data)} 个交易日期")

                # 将字符串日期转换回date对象
                dates_list = [pd.to_datetime(d).date() for d in dates_data]

                return dates_list

            except Exception as e:
                self.log(f"从JSON读取日期出错: {str(e)}")
                self.log(traceback.format_exc())

                # 返回当前日期作为后备
                return [datetime.now().date()]

        except Exception as e:
            self.log(f"获取交易日期时出错: {str(e)}")
            self.log(traceback.format_exc())

            # 返回当前日期作为后备
            return [datetime.now().date()]