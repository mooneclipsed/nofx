#!/usr/bin/env python3
"""
A股测试数据生成器
生成符合格式的mock数据用于测试
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
import random

# A股上证50成分股（测试用3只核心股票）
TEST_STOCKS = {
    "600519.SH": "贵州茅台",
    "601318.SH": "中国平安",
    "600036.SH": "招商银行"
}

def generate_ohlcv(base_price: float, volatility: float = 0.02) -> dict:
    """生成单根K线数据"""
    change = random.uniform(-volatility, volatility)
    open_price = base_price * (1 + change)
    high_price = open_price * (1 + random.uniform(0, volatility * 0.8))
    low_price = open_price * (1 - random.uniform(0, volatility * 0.8))
    close_price = random.uniform(low_price, high_price)
    volume = random.randint(1_000_000, 5_000_000)
    
    return {
        "1. buy price": round(open_price, 2),
        "2. high": round(high_price, 2),
        "3. low": round(low_price, 2),
        "4. sell price": round(close_price, 2),
        "5. volume": volume
    }

def generate_test_data(start_date: str, days: int = 5) -> str:
    """
    生成测试数据并保存到文件
    
    Args:
        start_date: 开始日期 "YYYY-MM-DD"
        days: 生成天数
    
    Returns:
        生成的文件路径
    """
    
    # 创建数据目录
    data_dir = Path("data/A_stock")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = data_dir / "merged.jsonl"
    
    # 基础价格（接近真实A股价格）
    base_prices = {
        "600519.SH": 1800.0,
        "601318.SH": 45.0,
        "600036.SH": 38.0
    }
    
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    
    print(f"📊 生成A股测试数据: {days}天，股票: {list(TEST_STOCKS.keys())}")
    
    with open(file_path, "w", encoding="utf-8") as f:
        for i in range(days):
            current_date = start_dt + timedelta(days=i)
            
            # 跳过周末（简单模拟）
            if current_date.weekday() >= 5:
                continue
            
            date_str = current_date.strftime("%Y-%m-%d")
            
            for symbol, name in TEST_STOCKS.items():
                # 生成价格波动（随机游走）
                base_price = base_prices[symbol]
                daily_data = generate_ohlcv(base_price)
                
                # 更新基础价格用于下一天
                base_prices[symbol] = daily_data["4. sell price"]
                
                record = {
                    "Meta Data": {
                        "2. Symbol": symbol,
                        "2.1. Name": name
                    },
                    "Time Series (Daily)": {
                        date_str: daily_data
                    }
                }
                
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    print(f"✅ 测试数据已生成: {file_path.absolute()}")
    print(f"📁 文件大小: {file_path.stat().st_size / 1024:.2f} KB")
    
    return str(file_path)

def verify_data(file_path: str):
    """验证生成的数据格式"""
    print(f"\n🔍 验证数据格式...")
    
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        print(f"📄 共 {len(lines)} 条记录")
        
        for i, line in enumerate(lines[:3]):  # 检查前3条
            try:
                data = json.loads(line)
                symbol = data["Meta Data"]["2. Symbol"]
                date = list(data["Time Series (Daily)"].keys())[0]
                ohlcv = list(data["Time Series (Daily)"].values())[0]
                
                print(f"  记录{i+1}: {symbol} {date}")
                print(f"    开盘: ¥{ohlcv['1. buy price']}")
                print(f"    收盘: ¥{ohlcv['4. sell price']}")
                print(f"    成交量: {ohlcv['5. volume']:,}")
                
            except Exception as e:
                print(f"❌ 记录{i+1}格式错误: {e}")
                return False
    
    print("✅ 数据格式验证通过")
    return True

if __name__ == "__main__":
    # 生成从10月9日开始的5个交易日数据
    test_file = generate_test_data("2025-10-09", days=7)
    verify_data(test_file)