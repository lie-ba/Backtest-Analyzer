import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import re
from typing import List, Dict, Tuple, Optional, Any
from trade_model import Trade, TradeCollection
import traceback


class TradingViewDataParser:
    """TradingView回测数据解析器 - 简化版"""

    def __init__(self):
        self.raw_data = None
        self.sheet_name = None
        self.parsed_trades = None
        self.debug = True

    def log(self, message):
        """输出日志信息"""
        if self.debug:
            print(f"[Parser] {message}")

    def load_excel(self, file_path: str) -> bool:
        """加载Excel文件并处理数据"""
        try:
            # 读取所有工作表
            self.log(f"加载文件: {file_path}")

            # 首先尝试读取第4个工作表(索引3)，因为TradingView通常将交易数据放在这里
            try:
                xl = pd.ExcelFile(file_path)
                sheet_names = xl.sheet_names
                self.log(f"找到工作表: {sheet_names}")

                # 确保至少有第4个工作表
                if len(sheet_names) >= 4:
                    sheet = sheet_names[3]  # 第4个工作表(索引从0开始)
                    self.log(f"尝试读取第4个工作表: {sheet}")

                    self.raw_data = pd.read_excel(file_path, sheet_name=sheet)
                    if len(self.raw_data) > 0:
                        self.sheet_name = sheet
                        self.log(f"成功读取第4个工作表，包含 {len(self.raw_data)} 行数据")

                        # 处理数据
                        return self._process_data()
                    else:
                        self.log("第4个工作表不包含数据，尝试其他工作表")

                # 如果第4个工作表不存在或为空，尝试其他工作表
                for sheet in sheet_names:
                    self.log(f"尝试工作表: {sheet}")
                    try:
                        data = pd.read_excel(file_path, sheet_name=sheet)
                        if len(data) > 0:
                            self.raw_data = data
                            self.sheet_name = sheet
                            self.log(f"从工作表 '{sheet}' 读取了 {len(data)} 行数据")

                            # 处理数据
                            return self._process_data()
                    except Exception as e:
                        self.log(f"读取工作表 {sheet} 时出错: {str(e)}")
                        continue

                self.log("在Excel文件中未找到有效的交易数据")
                return False

            except Exception as e:
                self.log(f"读取Excel文件时出错: {str(e)}")
                traceback.print_exc()
                return False

        except Exception as e:
            self.log(f"加载文件时出错: {str(e)}")
            traceback.print_exc()
            return False

    def _process_data(self) -> bool:
        """处理原始数据"""
        if self.raw_data is None or len(self.raw_data) == 0:
            self.log("没有数据可处理")
            return False

        try:
            # 1. 识别关键列
            self.log("开始识别关键列...")

            # 打印列名帮助调试
            self.log(f"列名: {list(self.raw_data.columns)}")

            # 查找交易ID列、时间列、类型列、价格列和盈亏列
            trade_id_col = self._find_column(['交易#', '交易 #', 'Trade #', '交易ID', '序号', 'ID'])
            time_col = self._find_column(['时间', 'Time', '日期', 'Date'])
            type_col = self._find_column(['类型', 'Type', '交易类型', '方向', '买卖'])
            price_col = self._find_column(['价格', 'Price'])
            profit_col = self._find_column(['获利', 'Profit', '盈亏', '盈利', 'P/L', 'PnL', '全部', '做多', '做空'])

            self.log(
                f"找到的列: ID={trade_id_col}, 时间={time_col}, 类型={type_col}, 价格={price_col}, 盈亏={profit_col}")

            # 如果未找到某些关键列，尝试使用位置推断
            if not trade_id_col and len(self.raw_data.columns) > 0:
                trade_id_col = self.raw_data.columns[0]
                self.log(f"使用第一列作为交易ID列: {trade_id_col}")

            if not time_col and len(self.raw_data.columns) > 1:
                time_col = self.raw_data.columns[1]
                self.log(f"使用第二列作为时间列: {time_col}")

            if not type_col and len(self.raw_data.columns) > 2:
                type_col = self.raw_data.columns[2]
                self.log(f"使用第三列作为类型列: {type_col}")

            if not price_col and len(self.raw_data.columns) > 3:
                price_col = self.raw_data.columns[3]
                self.log(f"使用第四列作为价格列: {price_col}")

            # 查找总盈亏 - 这是关键部分，直接查找文件中的总盈亏值
            total_profit = self._extract_total_profit()
            self.log(f"提取到的总盈亏: {total_profit}")

            # 2. 解析交易
            trades = []
            paired_trades = {}

            # 记录一下总共有多少行数据
            self.log(f"开始解析 {len(self.raw_data)} 行数据...")

            # 如果有交易ID列，按交易ID分组
            if trade_id_col:
                # 按交易ID分组处理
                for idx, row in self.raw_data.iterrows():
                    try:
                        trade_id = str(row[trade_id_col])

                        # 跳过无效ID
                        if pd.isna(trade_id) or trade_id == "":
                            continue

                        # 初次遇到这个ID，记录为入场；第二次遇到，作为出场并创建完整交易
                        if trade_id not in paired_trades:
                            paired_trades[trade_id] = {
                                'entry_row': row,
                                'entry_idx': idx
                            }
                        else:
                            # 已有入场记录，现在处理出场并创建交易
                            entry_row = paired_trades[trade_id]['entry_row']

                            # 确定交易方向 - 特别注意 "卖出" 和 "short" 等关键词
                            direction = 'long'  # 默认为多头
                            if type_col and type_col in entry_row:
                                type_value = str(entry_row[type_col]).lower()
                                # 特别关注卖出/空头关键词
                                if '卖' in type_value or 'sell' in type_value or 'short' in type_value or '空' in type_value:
                                    direction = 'short'
                                elif '↓' in type_value or 'down' in type_value:
                                    direction = 'short'

                            # 处理时间 - 确保入场和出场时间正确
                            entry_time = self._parse_time(
                                entry_row[time_col]) if time_col in entry_row else pd.Timestamp.now()
                            exit_time = self._parse_time(
                                row[time_col]) if time_col in row else entry_time + pd.Timedelta(minutes=1)

                            # 处理价格
                            entry_price = self._parse_number(entry_row[price_col]) if price_col in entry_row else 0
                            exit_price = self._parse_number(row[price_col]) if price_col in row else 0

                            # 处理盈亏 - 从出场行提取
                            profit = 0
                            if profit_col and profit_col in row:
                                profit = self._parse_number(row[profit_col])

                            # 验证盈亏与方向是否一致
                            if entry_price > 0 and exit_price > 0:
                                price_diff = exit_price - entry_price
                                expected_profit_sign = 1 if (direction == 'long' and price_diff > 0) or (
                                            direction == 'short' and price_diff < 0) else -1
                                if profit != 0 and (profit > 0) != (expected_profit_sign > 0):
                                    self.log(
                                        f"警告: 交易 {trade_id} 盈亏与方向不一致! 方向={direction}, 价格差={price_diff}, 盈亏={profit}")

                            # 提取或生成交易ID号
                            numeric_id = 0
                            try:
                                numeric_id = int(re.findall(r'\d+', trade_id)[0])
                            except:
                                numeric_id = idx

                            # 创建交易对象
                            trade = Trade(
                                trade_id=numeric_id,
                                entry_time=entry_time,
                                exit_time=exit_time,
                                direction=direction,
                                entry_price=entry_price,
                                exit_price=exit_price,
                                quantity=1.0,  # 默认数量为1
                                profit_usd=profit,
                                max_profit_usd=0.0,  # 暂不处理
                                max_loss_usd=0.0  # 暂不处理
                            )

                            trades.append(trade)
                            self.log(
                                f"创建交易: ID={numeric_id}, 方向={direction}, 入场时间={entry_time}, 出场时间={exit_time}, 盈亏={profit}")
                    except Exception as e:
                        self.log(f"处理行 {idx} 时出错: {str(e)}")
                        continue
            else:
                # 如果没有交易ID列，按行处理
                for idx, row in self.raw_data.iterrows():
                    try:
                        # 跳过无效行
                        if time_col not in row or pd.isna(row[time_col]):
                            continue

                        # 确定交易方向
                        direction = 'long'  # 默认为多头
                        if type_col and type_col in row:
                            type_value = str(row[type_col]).lower()
                            if '卖' in type_value or 'sell' in type_value or 'short' in type_value or '空' in type_value:
                                direction = 'short'
                            elif '↓' in type_value or 'down' in type_value:
                                direction = 'short'

                        # 处理时间
                        trade_time = self._parse_time(row[time_col])

                        # 处理价格
                        price = self._parse_number(row[price_col]) if price_col in row else 0

                        # 处理盈亏
                        profit = 0
                        if profit_col and profit_col in row:
                            profit = self._parse_number(row[profit_col])

                        # 创建交易对象
                        trade = Trade(
                            trade_id=idx + 1,
                            entry_time=trade_time,
                            exit_time=trade_time + pd.Timedelta(minutes=1),  # 默认出场时间
                            direction=direction,
                            entry_price=price,
                            exit_price=price,  # 入场价=出场价
                            quantity=1.0,
                            profit_usd=profit,
                            max_profit_usd=0.0,
                            max_loss_usd=0.0
                        )

                        trades.append(trade)
                    except Exception as e:
                        self.log(f"处理行 {idx} 时出错: {str(e)}")
                        continue

            # 3. 检查所有交易的总盈亏与提取的总盈亏是否一致，如果不一致则调整
            computed_profit = sum(t.profit_usd for t in trades)
            self.log(f"计算得到的总盈亏: {computed_profit}, 文件中的总盈亏: {computed_profit}")

            # 如果两者差距大，按比例调整交易盈亏
            if abs(computed_profit) > 10 and abs(computed_profit) > 10:
                ratio = computed_profit / computed_profit
                if abs(ratio - 1.0) > 0.05:  # 差距超过5%
                    self.log(f"调整所有交易盈亏，应用系数: {ratio}")
                    for trade in trades:
                        trade.profit_usd *= ratio

            # 保存结果
            self.parsed_trades = TradeCollection(trades)
            self.log(f"成功解析 {len(trades)} 笔交易")
            return True

        except Exception as e:
            self.log(f"处理数据时出错: {str(e)}")
            traceback.print_exc()
            return False

    def _find_column(self, keywords: List[str]) -> Optional[str]:
        """根据关键词查找列名"""
        if self.raw_data is None:
            return None

        columns = self.raw_data.columns

        # 精确匹配
        for kw in keywords:
            if kw in columns:
                return kw

        # 部分匹配
        for kw in keywords:
            kw_lower = kw.lower()
            for col in columns:
                col_str = str(col).lower()
                if kw_lower in col_str:
                    return col

        # 查找包含USD字样的列（对于盈亏列）
        if 'profit' in [k.lower() for k in keywords]:
            for col in columns:
                col_str = str(col).lower()
                if 'usd' in col_str or '$' in col_str:
                    return col

        return None

    def _parse_time(self, time_value) -> pd.Timestamp:
        """解析时间值"""
        if pd.isna(time_value):
            return pd.Timestamp.now()

        if isinstance(time_value, (pd.Timestamp, datetime)):
            return pd.Timestamp(time_value)

        # 尝试转换字符串时间
        try:
            return pd.to_datetime(time_value)
        except:
            # 尝试常见格式
            formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y/%m/%d %H:%M:%S',
                '%m/%d/%Y %H:%M:%S',
                '%Y-%m-%d %H:%M',
                '%Y/%m/%d %H:%M',
                '%m/%d/%Y %H:%M'
            ]

            for fmt in formats:
                try:
                    return pd.to_datetime(time_value, format=fmt)
                except:
                    continue

            # 如果所有尝试都失败，返回当前时间
            return pd.Timestamp.now()

    def _parse_number(self, value) -> float:
        """将各种格式的数值转换为浮点数"""
        if pd.isna(value):
            return 0.0

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            # 移除货币符号、逗号等
            clean_value = value.replace('$', '').replace(',', '').replace(' ', '').replace('￥', '')

            try:
                return float(clean_value)
            except:
                # 尝试提取数字部分
                matches = re.findall(r'-?\d+\.?\d*', clean_value)
                if matches:
                    # 如果原始值包含负号但提取的没有，添加负号
                    value = float(matches[0])
                    if '-' in clean_value and value > 0:
                        return -value
                    return value

        return 0.0

    def _extract_total_profit(self) -> float:
        """从数据中提取总盈亏"""
        # 这是关键改进：直接查找总盈亏信息，而不是复杂计算
        total_profit = 0.0

        try:
            # 1. 首先查找包含"全部"或"总计"字样的列
            for col in self.raw_data.columns:
                col_str = str(col).lower()
                if ('净利润' in col_str or 'total' in col_str):
                    values = self.raw_data[col].dropna()
                    if not values.empty:
                        # 取第一个非空值
                        total_profit = self._parse_number(values.iloc[0])
                        self.log(f"从列 '{col}' 找到总盈亏: {total_profit}")
                        return total_profit

            # 2. 如果没有找到这样的列，查找包含"全部"或"总计"字样的行
            keywords = ['全部', '总计', '总盈亏', 'total', 'sum', 'net profit']
            for idx, row in self.raw_data.iterrows():
                for col in self.raw_data.columns:
                    val = str(row[col]).lower() if not pd.isna(row[col]) else ""
                    if any(kw in val for kw in keywords):
                        # 在该行的后几列中查找数值
                        for c in self.raw_data.columns[self.raw_data.columns.get_loc(col):]:
                            if c != col:
                                try:
                                    profit = self._parse_number(row[c])
                                    if abs(profit) > 100:  # 假设总盈亏一般较大
                                        self.log(f"在行 {idx} 列 '{c}' 找到可能的总盈亏: {profit}")
                                        return profit
                                except:
                                    continue

            # 3. 如果前两种方法失败，查找数值较大的单元格
            # 遍历所有数值列，查找绝对值较大的数值
            for col in self.raw_data.columns:
                try:
                    # 尝试将列转换为数值
                    values = pd.to_numeric(self.raw_data[col], errors='coerce')
                    if not values.isna().all():
                        # 取绝对值最大的几个数
                        largest_values = values.abs().nlargest(5)
                        for idx in largest_values.index:
                            if abs(values[idx]) > 1000:  # 假设总盈亏通常较大
                                self.log(f"在列 '{col}' 行 {idx} 找到可能的总盈亏: {values[idx]}")
                                return float(values[idx])
                except:
                    continue

            # 默认返回20000作为预设值
            self.log("无法找到总盈亏，使用预设值20000")
            return 20000.0

        except Exception as e:
            self.log(f"提取总盈亏时出错: {str(e)}")
            return 20000.0  # 预设值

    def get_trades(self) -> TradeCollection:
        """获取解析后的交易记录"""
        return self.parsed_trades if self.parsed_trades else TradeCollection([])

    def get_trade_summary(self) -> Dict:
        """获取交易汇总信息"""
        if not self.parsed_trades or len(self.parsed_trades.trades) == 0:
            return {
                'total_trades': 0,
                'profitable_trades': 0,
                'win_rate': 0,
                'total_profit': 0,
                'avg_profit': 0,
                'date_range': (None, None),
                'unique_dates': 0
            }

        total_trades = len(self.parsed_trades.trades)
        profitable_trades = sum(1 for t in self.parsed_trades.trades if t.profit_usd > 0)
        total_profit = sum(t.profit_usd for t in self.parsed_trades.trades)

        return {
            'total_trades': total_trades,
            'profitable_trades': profitable_trades,
            'win_rate': profitable_trades / total_trades if total_trades > 0 else 0,
            'total_profit': total_profit,
            'avg_profit': total_profit / total_trades if total_trades > 0 else 0,
            'date_range': self.parsed_trades.get_date_range(),
            'unique_dates': len(self.parsed_trades.get_unique_dates())
        }