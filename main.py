#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TradingView回测优化器 - 主程序入口
"""

import sys
from PyQt5.QtWidgets import QApplication
from gui import MainWindow

def main():
    """主程序入口"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 设置应用程序风格
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()