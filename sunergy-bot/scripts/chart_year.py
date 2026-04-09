#!/usr/bin/env python3
"""
年统计柱状图生成
用法: python3 chart_year.py <site_id> <YYYY>
示例: python3 chart_year.py 1872845402077761538 2026
"""
import sys, os
from pathlib import Path

# 直接调用 chart_month.py 的 chart_year 函数
sys.path.insert(0, str(Path(__file__).parent))
from chart_month import chart_year as do_chart_year

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python3 chart_year.py <site_id> <YYYY>")
        sys.exit(1)
    do_chart_year(sys.argv[1], sys.argv[2])
