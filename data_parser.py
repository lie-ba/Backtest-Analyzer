import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from typing import List, Dict, Tuple, Optional
from trade_model import Trade, TradeCollection
import traceback


class TradingViewDataParser:
    """TradingView回测数据解析器"""

    def __init__(self):
        self.raw_data = None
        self.trades_df = None
        self.parsed_trades = None
        self.sheet_name = None
        self.debug = True  # 开启调试模式以输出更多信息

    def log(self, message):
        """输出日志信息（如果调试模式开启）"""
        if self.debug:
            print(message)

    def load_excel(self, file_path: str) -> bool:
        """加载Excel文件"""
        try:
            # 读取Excel文件的所有工作表
            self.log(f"尝试加载文件: {file_path}")
            xls = pd.ExcelFile(file_path)
            sheet_names = xls.sheet_names

            self.log(f"Excel文件包含以下工作表: {sheet_names}")

            # 首先尝试查找名为"交易列表"或"Trade List"的工作表
            trade_sheet_names = ["交易列表", "交易清单", "Trade List", "Trades"]
            for name in trade_sheet_names:
                if name in sheet_names:
                    self.log(f"找到匹配的交易工作表: {name}")
                    self.raw_data = pd.read_excel(file_path, sheet_name=name)
                    self.sheet_name = name
                    if self._check_trade_data_format():
                        return self._process_raw_data()

            # 如果没有找到匹配的工作表名，尝试每个工作表
            for sheet in sheet_names:
                self.log(f"尝试加载工作表: {sheet}")
                try:
                    self.raw_data = pd.read_excel(file_path, sheet_name=sheet)
                    self.log(f"工作表 '{sheet}' 的列名: {list(self.raw_data.columns)}")
                    self.log(f"工作表 '{sheet}' 的前两行数据:\n{self.raw_data.head(2)}")

                    # 检查是否包含交易数据
                    if self._check_trade_data_format():
                        self.sheet_name = sheet
                        self.log(f"找到有效的交易数据工作表: {sheet}")
                        return self._process_raw_data()
                except Exception as e:
                    self.log(f"读取工作表 {sheet} 时出错: {e}")
                    continue

            # 如果没有找到有效的工作表，尝试第四个工作表（通常TradingView将交易数据放在sheet4）
            if len(sheet_names) >= 4:
                try:
                    sheet = sheet_names[3]  # 第四个工作表
                    self.log(f"尝试加载第四个工作表: {sheet}")
                    self.raw_data = pd.read_excel(file_path, sheet_name=sheet)
                    self.sheet_name = sheet
                    if len(self.raw_data) > 0:
                        self.log(f"使用第四个工作表: {sheet}")
                        return self._process_raw_data()
                except Exception as e:
                    self.log(f"读取第四个工作表时出错: {e}")

            self.log("在Excel文件中未找到有效的TradingView交易数据")
            self.log("期望的数据应包含: 交易号码、时间、价格、类型、规模等必要信息")
            return False

        except Exception as e:
            self.log(f"加载Excel文件时出错: {e}")
            traceback.print_exc()
            return False

    def _check_trade_data_format(self) -> bool:
        """检查数据是否符合交易数据格式"""
        if self.raw_data is None or self.raw_data.empty:
            return False

        # 检查必要的列是否存在（使用模糊匹配）
        columns = [str(col) for col in self.raw_data.columns]
        self.log(f"检查列名: {columns}")

        # 以下是交易数据通常包含的关键词
        trade_id_keywords = ['交易', '序号', 'trade', '#', 'id', 'num']
        time_keywords = ['时间', 'time', '日期']
        price_keywords = ['价格', 'price']
        type_keywords = ['类型', 'type', '方向', '买卖']

        # 检查是否至少包含关键列
        has_trade_id = any(any(kw in col.lower() for kw in trade_id_keywords) for col in columns)
        has_time = any(any(kw in col.lower() for kw in time_keywords) for col in columns)
        has_price = any(any(kw in col.lower() for kw in price_keywords) for col in columns)
        has_type = any(any(kw in col.lower() for kw in type_keywords) for col in columns)

        self.log(f"列检查结果: trade_id={has_trade_id}, time={has_time}, price={has_price}, type={has_type}")

        # 如果有足够的关键列，认为是交易数据
        return has_trade_id and has_time and (has_price or has_type)

    def _find_column_by_keywords(self, keywords: List[str]) -> Optional[str]:
        """根据关键词列表查找匹配的列名"""
        if self.raw_data is None:
            return None

        columns = self.raw_data.columns

        # 首先尝试精确匹配
        for kw in keywords:
            if kw in columns:
                self.log(f"找到精确匹配列: {kw}")
                return kw

        # 然后尝试部分匹配
        for kw in keywords:
            for col in columns:
                col_str = str(col).lower()
                if kw.lower() in col_str:
                    self.log(f"找到部分匹配列: {col} (匹配关键词: {kw})")
                    return col

        return None

    def _process_raw_data(self) -> bool:
        """处理原始数据"""
        if self.raw_data is None or self.raw_data.empty:
            self.log("没有原始数据或数据为空")
            return False

        try:
            # 识别必要的列
            trade_id_col = self._find_column_by_keywords(
                ['交易#', '交易 #', 'Trade #', '交易ID', '交易号', '序号', 'ID', '交易'])
            time_col = self._find_column_by_keywords(['时间', 'Time', '日期', '日期时间', 'Date/Time'])
            price_col = self._find_column_by_keywords(['价格', 'Price'])
            type_col = self._find_column_by_keywords(['类型', 'Type', '交易类型', '方向', '买卖'])
            size_col = self._find_column_by_keywords(['规模', 'Size', '数量', '手数', '合约数'])
            profit_col = self._find_column_by_keywords(
                ['获利 USD', 'Profit USD', '盈亏 USD', '盈利 USD', '盈亏', '盈利'])
            max_profit_col = self._find_column_by_keywords(
                ['最大交易获利 USD', 'Max Trade Profit USD', '最大获利 USD', '最大获利'])
            max_loss_col = self._find_column_by_keywords(
                ['最大交易亏损 USD', 'Max Trade Loss USD', '最大亏损 USD', '最大亏损'])

            # 检查并输出找到的列
            self.log(f"找到的列映射:")
            self.log(f"交易ID列: {trade_id_col}")
            self.log(f"时间列: {time_col}")
            self.log(f"价格列: {price_col}")
            self.log(f"类型列: {type_col}")
            self.log(f"规模列: {size_col}")
            self.log(f"盈亏列: {profit_col}")
            self.log(f"最大获利列: {max_profit_col}")
            self.log(f"最大亏损列: {max_loss_col}")

            # 检查必要的列是否都找到了
            required_columns = [trade_id_col, time_col]
            if not all(required_columns):
                missing = []
                if not trade_id_col:
                    missing.append("交易ID")
                if not time_col:
                    missing.append("时间")

                self.log(f"缺少必要的列: {', '.join(missing)}")
                return False

            # 复制数据以避免修改原始数据
            self.trades_df = self.raw_data.copy()

            # 如果列名包含"Unnamed"，可能是因为Excel有合并单元格或格式问题
            # 此时需要尝试使用第一行作为列名
            if any("Unnamed" in str(col) for col in self.trades_df.columns):
                self.log("检测到Unnamed列，尝试使用第一行作为列名")
                try:
                    # 保存原始列名以便稍后重新识别列
                    original_columns = list(self.trades_df.columns)

                    # 使用第一行作为列名
                    self.trades_df.columns = self.trades_df.iloc[0]
                    self.trades_df = self.trades_df.iloc[1:].reset_index(drop=True)

                    # 重新识别列
                    trade_id_col = self._find_column_by_keywords(
                        ['交易#', '交易 #', 'Trade #', '交易ID', '交易号', '序号'])
                    time_col = self._find_column_by_keywords(['时间', 'Time', '日期', '日期时间'])
                    price_col = self._find_column_by_keywords(['价格', 'Price'])
                    type_col = self._find_column_by_keywords(['类型', 'Type', '交易类型', '方向'])
                    size_col = self._find_column_by_keywords(['规模', 'Size', '数量', '手数'])
                    profit_col = self._find_column_by_keywords(
                        ['获利 USD', 'Profit USD', '盈亏 USD', '盈利 USD', '盈亏', '盈利'])
                    max_profit_col = self._find_column_by_keywords(
                        ['最大交易获利 USD', 'Max Trade Profit USD', '最大获利 USD', '最大获利'])
                    max_loss_col = self._find_column_by_keywords(
                        ['最大交易亏损 USD', 'Max Trade Loss USD', '最大亏损 USD', '最大亏损'])

                    self.log("重新识别列:")
                    self.log(f"交易ID列: {trade_id_col}")
                    self.log(f"时间列: {time_col}")
                except Exception as e:
                    self.log(f"尝试使用第一行作为列名时出错: {e}")
                    # 恢复原始数据
                    self.trades_df = self.raw_data.copy()

            # 尝试转换时间列为日期时间格式
            if time_col:
                try:
                    # 保留原始时间列的备份
                    self.trades_df['_original_time'] = self.trades_df[time_col]
                    # 尝试转换为日期时间格式
                    self.trades_df[time_col] = pd.to_datetime(self.trades_df[time_col], errors='coerce')

                    # 检查转换是否成功
                    if self.trades_df[time_col].isna().all():
                        self.log(f"时间列 '{time_col}' 无法转换为日期时间格式，尝试其他格式")
                        # 尝试不同的格式转换
                        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S', '%d.%m.%Y %H:%M:%S', '%m/%d/%Y %H:%M:%S']:
                            try:
                                self.trades_df[time_col] = pd.to_datetime(self.trades_df['_original_time'], format=fmt,
                                                                          errors='coerce')
                                if not self.trades_df[time_col].isna().all():
                                    self.log(f"成功使用格式 '{fmt}' 转换时间")
                                    break
                            except:
                                pass

                    # 如果仍然无法转换，使用当前日期作为默认值
                    if self.trades_df[time_col].isna().all():
                        self.log("无法转换时间列，使用当前日期作为默认值")
                        self.trades_df[time_col] = pd.to_datetime('today')
                except Exception as e:
                    self.log(f"转换时间列时出错: {e}")

            # 保存列名映射
            self.column_mapping = {
                'trade_id': trade_id_col,
                'time': time_col,
                'price': price_col,
                'type': type_col,
                'size': size_col,
                'profit': profit_col,
                'max_profit': max_profit_col,
                'max_loss': max_loss_col
            }

            # 解析交易记录
            self._parse_trades()
            return True

        except Exception as e:
            self.log(f"处理数据时出错: {e}")
            traceback.print_exc()
            return False

    def _parse_trades(self):
        """解析交易记录"""
        if not hasattr(self, 'column_mapping'):
            self.log("没有列映射信息，无法解析交易")
            self.parsed_trades = TradeCollection([])
            return

        trades = []
        invalid_trades = 0

        # 获取列名
        trade_id_col = self.column_mapping['trade_id']
        time_col = self.column_mapping['time']
        price_col = self.column_mapping.get('price')
        type_col = self.column_mapping.get('type')
        size_col = self.column_mapping.get('size')
        profit_col = self.column_mapping.get('profit')
        max_profit_col = self.column_mapping.get('max_profit')
        max_loss_col = self.column_mapping.get('max_loss')

        # 尝试处理可能的缺失列
        if not price_col and 'price' in self.trades_df.columns:
            price_col = 'price'
        if not type_col and 'type' in self.trades_df.columns:
            type_col = 'type'
        if not size_col and 'size' in self.trades_df.columns:
            size_col = 'size'

        self.log(f"开始解析交易记录，共 {len(self.trades_df)} 行")

        # 按交易ID分组处理
        try:
            # 确保交易ID列是有效的
            self.trades_df[trade_id_col] = self.trades_df[trade_id_col].astype(str)

            # 交易ID可能不是数字，而是某种编码
            unique_ids = self.trades_df[trade_id_col].unique()
            self.log(f"找到 {len(unique_ids)} 个唯一交易ID")

            # 创建交易记录字典，键为交易ID
            trades_dict = {}

            # 首先按交易ID分组
            for trade_id in unique_ids:
                trade_rows = self.trades_df[self.trades_df[trade_id_col] == trade_id]

                # 排序以确保入场在前，出场在后
                if time_col in trade_rows.columns:
                    trade_rows = trade_rows.sort_values(by=time_col)

                # 检查是否有足够的行
                if len(trade_rows) == 2:  # 正常情况：一行入场，一行出场
                    entry_row = trade_rows.iloc[0]
                    exit_row = trade_rows.iloc[1]

                    try:
                        # 处理交易方向
                        direction = 'long'  # 默认做多
                        if type_col and type_col in entry_row:
                            type_value = str(entry_row[type_col]).lower()
                            if '卖' in type_value or 'sell' in type_value or 'short' in type_value:
                                direction = 'short'

                        # 处理价格
                        entry_price = 0.0
                        exit_price = 0.0
                        if price_col and price_col in entry_row and price_col in exit_row:
                            entry_price = float(entry_row[price_col])
                            exit_price = float(exit_row[price_col])

                        # 处理数量
                        quantity = 1.0
                        if size_col and size_col in entry_row:
                            try:
                                size_value = entry_row[size_col]
                                if isinstance(size_value, str):
                                    size_value = size_value.replace(',', '')
                                quantity = float(size_value)
                            except:
                                self.log(f"无法转换规模值: {entry_row.get(size_col, 'N/A')}")

                        # 处理盈亏
                        profit_usd = 0.0
                        if profit_col and profit_col in exit_row:
                            try:
                                profit_value = exit_row[profit_col]
                                if isinstance(profit_value, str):
                                    profit_value = profit_value.replace('$', '').replace(',', '')
                                profit_usd = float(profit_value)
                            except:
                                self.log(f"无法转换盈亏值: {exit_row.get(profit_col, 'N/A')}")

                        # 处理最大获利和最大亏损
                        max_profit_usd = 0.0
                        max_loss_usd = 0.0

                        if max_profit_col and max_profit_col in exit_row:
                            try:
                                max_profit_value = exit_row[max_profit_col]
                                if isinstance(max_profit_value, str):
                                    max_profit_value = max_profit_value.replace('$', '').replace(',', '')
                                max_profit_usd = float(max_profit_value)
                            except:
                                self.log(f"无法转换最大获利值: {exit_row.get(max_profit_col, 'N/A')}")

                        if max_loss_col and max_loss_col in exit_row:
                            try:
                                max_loss_value = exit_row[max_loss_col]
                                if isinstance(max_loss_value, str):
                                    max_loss_value = max_loss_value.replace('$', '').replace(',', '')
                                max_loss_usd = float(max_loss_value)
                            except:
                                self.log(f"无法转换最大亏损值: {exit_row.get(max_loss_col, 'N/A')}")

                        # 创建交易对象
                        trade_id_numeric = 0
                        try:
                            trade_id_numeric = int(trade_id)
                        except:
                            trade_id_numeric = hash(str(trade_id)) % 10000  # 使用哈希值作为数字ID

                        trade = Trade(
                            trade_id=trade_id_numeric,
                            entry_time=entry_row[time_col],
                            exit_time=exit_row[time_col],
                            direction=direction,
                            entry_price=entry_price,
                            exit_price=exit_price,
                            quantity=quantity,
                            profit_usd=profit_usd,
                            max_profit_usd=max_profit_usd,
                            max_loss_usd=max_loss_usd
                        )

                        trades.append(trade)

                    except Exception as e:
                        self.log(f"处理交易 #{trade_id} 时出错: {e}")
                        invalid_trades += 1
                elif len(trade_rows) > 0:
                    self.log(f"交易 #{trade_id} 有 {len(trade_rows)} 条记录，不是标准的2条")
                    invalid_trades += 1

            # 如果没有标准的2行记录交易，则尝试按行依次解析
            if len(trades) == 0 and len(self.trades_df) > 0:
                self.log("没有找到标准的两行一组交易记录，尝试逐行解析...")

                # 确保数据按时间排序
                if time_col in self.trades_df.columns:
                    self.trades_df = self.trades_df.sort_values(by=time_col)

                # 按照单行解析
                for idx in range(len(self.trades_df)):
                    try:
                        row = self.trades_df.iloc[idx]

                        # 只处理包含有效时间的行
                        if time_col not in row or pd.isna(row[time_col]):
                            continue

                        # 提取基本信息
                        trade_id_str = str(row.get(trade_id_col, idx))
                        trade_id_numeric = 0
                        try:
                            trade_id_numeric = int(trade_id_str)
                        except:
                            trade_id_numeric = hash(trade_id_str) % 10000

                        # 方向和价格
                        direction = 'long'
                        if type_col and type_col in row:
                            type_value = str(row[type_col]).lower()
                            if '卖' in type_value or 'sell' in type_value or 'short' in type_value:
                                direction = 'short'

                        price = 0.0
                        if price_col and price_col in row:
                            try:
                                price = float(row[price_col])
                            except:
                                pass

                        # 规模
                        quantity = 1.0
                        if size_col and size_col in row:
                            try:
                                size_value = row[size_col]
                                if isinstance(size_value, str):
                                    size_value = size_value.replace(',', '')
                                quantity = float(size_value)
                            except:
                                pass

                        # 盈亏
                        profit_usd = 0.0
                        if profit_col and profit_col in row:
                            try:
                                profit_value = row[profit_col]
                                if isinstance(profit_value, str):
                                    profit_value = profit_value.replace('$', '').replace(',', '')
                                profit_usd = float(profit_value)
                            except:
                                pass

                        # 最大获利和亏损
                        max_profit_usd = 0.0
                        max_loss_usd = 0.0
                        if max_profit_col and max_profit_col in row:
                            try:
                                max_profit_value = row[max_profit_col]
                                if isinstance(max_profit_value, str):
                                    max_profit_value = max_profit_value.replace('$', '').replace(',', '')
                                max_profit_usd = float(max_profit_value)
                            except:
                                pass

                        if max_loss_col and max_loss_col in row:
                            try:
                                max_loss_value = row[max_loss_col]
                                if isinstance(max_loss_value, str):
                                    max_loss_value = max_loss_value.replace('$', '').replace(',', '')
                                max_loss_usd = float(max_loss_value)
                            except:
                                pass

                        # 入场和出场时间（对于单行记录，两者相同）
                        trade_time = row[time_col]

                        # 创建交易对象
                        trade = Trade(
                            trade_id=trade_id_numeric,
                            entry_time=trade_time,
                            exit_time=trade_time + timedelta(minutes=1),  # 添加1分钟作为出场时间
                            direction=direction,
                            entry_price=price,
                            exit_price=price,
                            quantity=quantity,
                            profit_usd=profit_usd,
                            max_profit_usd=max_profit_usd,
                            max_loss_usd=max_loss_usd
                        )

                        trades.append(trade)

                    except Exception as e:
                        self.log(f"处理第 {idx} 行时出错: {e}")
                        invalid_trades += 1

            # 按入场时间排序
            trades.sort(key=lambda x: x.entry_time)
            self.parsed_trades = TradeCollection(trades)

            self.log(f"成功解析 {len(trades)} 笔交易, 无效交易: {invalid_trades}")

        except Exception as e:
            self.log(f"解析交易记录时出错: {e}")
            traceback.print_exc()
            self.parsed_trades = TradeCollection([])

    def get_trades(self) -> TradeCollection:
        """获取解析后的交易记录"""
        return self.parsed_trades if self.parsed_trades else TradeCollection([])

    def get_trade_summary(self) -> Dict:
        """获取交易汇总信息"""
        if self.parsed_trades is None or len(self.parsed_trades.trades) == 0:
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
        profitable_trades = sum(1 for t in self.parsed_trades.trades if t.is_profitable)
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