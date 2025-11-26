"""
A股数据与持仓管理工具（A股专用版）
提供完整的交易日管理、价格查询、持仓操作功能
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ========== A股核心配置 ==========
# 上证50成分股（A股核心资产）
all_sse_50_symbols = [
    "600519.SH", "601318.SH", "600036.SH", "601899.SH", "600900.SH",
    "601166.SH", "600276.SH", "600030.SH", "603259.SH", "688981.SH",
    "688256.SH", "601398.SH", "688041.SH", "601211.SH", "601288.SH",
    "601328.SH", "688008.SH", "600887.SH", "600150.SH", "601816.SH",
    "601127.SH", "600031.SH", "688012.SH", "603501.SH", "601088.SH",
    "600309.SH", "601601.SH", "601668.SH", "603993.SH", "601012.SH",
    "601728.SH", "600690.SH", "600809.SH", "600941.SH", "600406.SH",
    "601857.SH", "601766.SH", "601919.SH", "600050.SH", "600760.SH",
    "601225.SH", "600028.SH", "601988.SH", "688111.SH", "601985.SH",
    "601888.SH", "601628.SH", "601600.SH", "601658.SH", "600048.SH",
]


def get_market_type() -> str:
    """
    智能检测A股市场类型（A股专用）
    
    检测优先级：
    1. 配置中的 MARKET 值
    2. LOG_PATH 路径关键字（含astock/a_stock）
    3. 默认返回 "cn"
    
    Returns:
        "cn" (A股专用，其他市场被移除)
    """
    # 从配置读取
    market = get_config_value("MARKET", None)
    if market in ["cn", "us", "crypto"]:
        return market
    
    # 从路径推断
    log_path = get_config_value("LOG_PATH", "./data/agent_data_astock")
    if "astock" in log_path.lower() or "a_stock" in log_path.lower():
        return "cn"
    
    # A股专用，默认返回cn
    return "cn"


def get_config_value(key: str, default=None):
    """导入配置函数（避免循环依赖）"""
    try:
        from .a_stock_config import get_config_value as _get_config_value
    except ImportError:
        from a_stock_config import get_config_value as _get_config_value
    return _get_config_value(key, default)


def write_config_value(key: str, value: Any):
    """导入配置写入函数"""
    from a_stock_config import write_config_value as _write_config_value
    return _write_config_value(key, value)


def get_merged_file_path(market: str = "cn") -> Path:
    """
    获取A股合并数据文件路径
    
    Args:
        market: 市场类型（保持参数兼容，但仅cn有效）
    
    Returns:
        Path对象，指向A股数据文件
    """
    base_dir = Path(__file__).resolve().parent
    
    # A股专用路径
    if market == "cn":
        return base_dir / "data" / "A_stock" / "merged.jsonl"
    
    # 其他市场（兼容旧代码）
    elif market == "crypto":
        return base_dir / "data" / "crypto" / "crypto_merged.jsonl"
    else:
        return base_dir / "data" / "merged.jsonl"


def is_trading_day(date: str, market: str = "cn") -> bool:
    """
    检查是否为A股交易日（基于历史数据文件）
    
    降级策略：
    1. 数据文件存在时：查询是否有实际交易数据
    2. 数据文件缺失时：简单日历判断（跳过周末）
    
    Args:
        date: 日期字符串 "YYYY-MM-DD"
        market: 市场类型（A股专用）
    
    Returns:
        True - 是交易日
        False - 非交易日或数据不存在
    """
    merged_file = get_merged_file_path(market)
    
    # 降级方案：文件不存在时，简单判断周末
    if not merged_file.exists():
        print(f"⚠️ A股数据文件不存在: {merged_file}，降级为简单日历判断")
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            return dt.weekday() < 5  # 仅周末判断
        except:
            return False
    
    try:
        with open(merged_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    # 检查日线数据
                    time_series = data.get("Time Series (Daily)", {})
                    if date in time_series:
                        return True
                    
                    # 检查小时线数据（包含当天任意时间）
                    for key, value in data.items():
                        if key.startswith("Time Series") and isinstance(value, dict):
                            if any(timestamp.startswith(date) for timestamp in value.keys()):
                                return True
                except json.JSONDecodeError:
                    continue
        return False
    except Exception as e:
        print(f"⚠️ A股交易日判断失败: {e}，降级为简单日历判断")
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            return dt.weekday() < 5
        except:
            return False


def get_all_trading_days(market: str = "cn") -> List[str]:
    """
    从合并数据文件中提取所有A股交易日
    
    Returns:
        排序后的交易日列表 ["2025-01-02", "2025-01-03", ...]
    """
    merged_file = get_merged_file_path(market)
    
    if not merged_file.exists():
        print(f"⚠️ A股数据文件不存在: {merged_file}")
        return []
    
    trading_days = set()
    try:
        with open(merged_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    time_series = data.get("Time Series (Daily)", {})
                    trading_days.update(time_series.keys())
                except:
                    continue
        
        return sorted(list(trading_days))
    except Exception as e:
        print(f"⚠️ 读取A股交易日失败: {e}")
        return []


def get_stock_name_mapping(market: str = "cn") -> Dict[str, str]:
    """
    获取A股股票代码与中文名称映射字典
    
    Returns:
        {"600519.SH": "贵州茅台", "601318.SH": "中国平安", ...}
    """
    merged_file = get_merged_file_path(market)
    
    if not merged_file.exists():
        return {}
    
    name_map = {}
    try:
        with open(merged_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    meta = data.get("Meta Data", {})
                    symbol = meta.get("2. Symbol")
                    name = meta.get("2.1. Name", "")
                    if symbol and name:
                        name_map[symbol] = name
                except:
                    continue
        return name_map
    except Exception as e:
        print(f"⚠️ 读取A股股票名称映射失败: {e}")
        return {}


def format_price_dict_with_names(price_dict: Dict[str, Optional[float]], market: str = "cn") -> Dict[str, Optional[float]]:
    """
    A股专用：为价格字典添加中文股票名称，提升可读性
    
    Args:
        price_dict: {"600519.SH_price": 1800.5}
        market: 市场类型（A股专用）
    
    Returns:
        {"600519.SH (贵州茅台)_price": 1800.5}
    """
    if market != "cn":
        return price_dict
    
    name_map = get_stock_name_mapping(market)
    if not name_map:
        return price_dict
    
    formatted = {}
    for key, value in price_dict.items():
        if key.endswith("_price"):
            symbol = key[:-6]  # 移除"_price"
            stock_name = name_map.get(symbol, "")
            if stock_name:
                formatted[f"{symbol} ({stock_name})_price"] = value
                continue
        formatted[key] = value
    
    return formatted


def get_yesterday_date(today_date: str, merged_path: Optional[str] = None, market: str = "cn") -> str:
    """
    获取A股上一个交易日（智能降级）
    
    降级策略：
    1. 数据文件存在时：查询历史数据中的上一个交易日
    2. 数据文件缺失时：简单日历回退（跳过周末）
    
    Args:
        today_date: "YYYY-MM-DD" 或 "YYYY-MM-DD HH:MM:SS"
        merged_path: 自定义数据路径
        market: 市场类型（A股专用）
    
    Returns:
        上一个交易日字符串
    """
    # 解析输入
    date_only = " " not in today_date
    fmt = "%Y-%m-%d" if date_only else "%Y-%m-%d %H:%M:%S"
    
    try:
        input_dt = datetime.strptime(today_date, fmt)
    except ValueError:
        print(f"⚠️ 日期格式错误: {today_date}，降级处理")
        if date_only:
            return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            return (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    
    # 获取数据文件
    merged_file = Path(merged_path) if merged_path else get_merged_file_path(market)
    
    # 降级方案：文件不存在时，简单日历回退
    if not merged_file.exists():
        if date_only:
            yesterday = input_dt - timedelta(days=1)
            while yesterday.weekday() >= 5:  # 跳过周末
                yesterday -= timedelta(days=1)
            return yesterday.strftime("%Y-%m-%d")
        else:
            yesterday = input_dt - timedelta(hours=1)
            return yesterday.strftime("%Y-%m-%d %H:%M:%S")
    
    # 从历史数据查找最接近的上一个交易日
    all_timestamps = set()
    with open(merged_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                doc = json.loads(line)
                for key, value in doc.items():
                    if key.startswith("Time Series") and isinstance(value, dict):
                        all_timestamps.update(value.keys())
            except:
                continue
    
    if not all_timestamps:
        # 降级方案
        if date_only:
            yesterday = input_dt - timedelta(days=1)
            while yesterday.weekday() >= 5:
                yesterday -= timedelta(days=1)
            return yesterday.strftime("%Y-%m-%d")
        else:
            yesterday = input_dt - timedelta(hours=1)
            return yesterday.strftime("%Y-%m-%d %H:%M:%S")
    
    # 查找最接近且小于输入日期的时间戳
    previous = None
    for ts_str in all_timestamps:
        try:
            ts_dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            if ts_dt < input_dt:
                if previous is None or ts_dt > previous:
                    previous = ts_dt
        except:
            continue
    
    if previous is None:
        # 降级方案：日历回退
        if date_only:
            yesterday = input_dt - timedelta(days=1)
            while yesterday.weekday() >= 5:
                yesterday -= timedelta(days=1)
            return yesterday.strftime("%Y-%m-%d")
        else:
            yesterday = input_dt - timedelta(hours=1)
            return yesterday.strftime("%Y-%m-%d %H:%M:%S")
    
    return previous.strftime("%Y-%m-%d" if date_only else "%Y-%m-%d %H:%M:%S")


def get_open_prices(today_date: str, symbols: List[str], merged_path: Optional[str] = None, market: str = "cn") -> Dict[str, Optional[float]]:
    """
    获取A股开盘价（带异常降级）
    
    Args:
        today_date: 查询日期
        symbols: 股票代码列表
        merged_path: 数据路径
        market: 市场类型（A股专用）
    
    Returns:
        {"600519.SH_price": 1800.5, ...}
    """
    wanted = set(symbols)
    results = {}
    
    merged_file = Path(merged_path) if merged_path else get_merged_file_path(market)
    if not merged_file.exists():
        return results
    
    with open(merged_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                doc = json.loads(line)
                meta = doc.get("Meta Data", {})
                sym = meta.get("2. Symbol")
                
                if sym not in wanted:
                    continue
                
                # 查找时间序列数据
                series = None
                for key, value in doc.items():
                    if key.startswith("Time Series"):
                        series = value
                        break
                
                if not isinstance(series, dict):
                    continue
                
                bar = series.get(today_date)
                if isinstance(bar, dict):
                    open_val = bar.get("1. buy price")
                    try:
                        results[f"{sym}_price"] = float(open_val) if open_val is not None else None
                    except (ValueError, TypeError):
                        results[f"{sym}_price"] = None
            except Exception:
                continue
    
    return results


def get_yesterday_open_and_close_price(today_date: str, symbols: List[str], merged_path: Optional[str] = None, market: str = "cn") -> Tuple[Dict[str, Optional[float]], Dict[str, Optional[float]]]:
    """
    获取A股昨日开收盘价
    
    Returns:
        (买入价字典, 卖出价字典)
        示例: ({"600519.SH_price": 1790.0}, {"600519.SH_price": 1800.5})
    """
    wanted = set(symbols)
    buy_results = {}
    sell_results = {}
    
    merged_file = Path(merged_path) if merged_path else get_merged_file_path(market)
    if not merged_file.exists():
        return buy_results, sell_results
    
    yesterday_date = get_yesterday_date(today_date, merged_path=merged_path, market=market)
    
    with open(merged_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                doc = json.loads(line)
                meta = doc.get("Meta Data", {})
                sym = meta.get("2. Symbol")
                
                if sym not in wanted:
                    continue
                
                series = None
                for key, value in doc.items():
                    if key.startswith("Time Series"):
                        series = value
                        break
                
                if not isinstance(series, dict):
                    continue
                
                bar = series.get(yesterday_date)
                if isinstance(bar, dict):
                    buy_val = bar.get("1. buy price")
                    sell_val = bar.get("4. sell price")
                    
                    try:
                        buy_results[f"{sym}_price"] = float(buy_val) if buy_val is not None else None
                        sell_results[f"{sym}_price"] = float(sell_val) if sell_val is not None else None
                    except (ValueError, TypeError):
                        buy_results[f"{sym}_price"] = None
                        sell_results[f"{sym}_price"] = None
                else:
                    # 无数据
                    buy_results[f'{sym}_price'] = None
                    sell_results[f'{sym}_price'] = None
            except Exception:
                continue
    
    return buy_results, sell_results


def get_yesterday_profit(
    today_date: str,
    yesterday_buy_prices: Dict[str, Optional[float]],
    yesterday_sell_prices: Dict[str, Optional[float]],
    yesterday_init_position: Dict[str, float],
    stock_symbols: Optional[List[str]] = None,
) -> Dict[str, float]:
    """
    计算A股持仓昨日收益（A股专用）
    
    计算公式：(收盘价 - 开盘价) × 持仓数量
    
    Args:
        today_date: 今天日期
        yesterday_buy_prices: 昨日开盘价格
        yesterday_sell_prices: 昨日收盘价格
        yesterday_init_position: 昨日持仓
        stock_symbols: 股票列表（默认A股上证50）
    
    Returns:
        {"600519.SH": 1250.5, ...}
    """
    profit_dict = {}
    
    # A股专用：默认使用上证50
    if stock_symbols is None:
        stock_symbols = all_sse_50_symbols
    
    for symbol in stock_symbols:
        symbol_key = f"{symbol}_price"
        
        buy_price = yesterday_buy_prices.get(symbol_key)
        sell_price = yesterday_sell_prices.get(symbol_key)
        position_weight = yesterday_init_position.get(symbol, 0.0)
        
        if buy_price is not None and sell_price is not None and position_weight > 0:
            profit = (sell_price - buy_price) * position_weight
            profit_dict[symbol] = round(profit, 4)
        else:
            profit_dict[symbol] = 0.0
    
    return profit_dict


def get_today_init_position(today_date: str, signature: str) -> Dict[str, float]:
    """
    获取A股今日初始持仓（昨日最终持仓）
    
    Args:
        today_date: 今日日期 "YYYY-MM-DD"
        signature: Agent标识
    
    Returns:
        {"600519.SH": 100, "CASH": 50000.0}
    """
    base_dir = Path(__file__).resolve().parent
    
    # A股专用路径解析
    log_path = get_config_value("LOG_PATH", "./data/agent_data_astock")
    if os.path.isabs(log_path):
        position_file = Path(log_path) / signature / "position" / "position.jsonl"
    else:
        if log_path.startswith("./data/"):
            log_path = log_path[7:]  # 移除"./data/"前缀
        position_file = base_dir / "data" / log_path / signature / "position" / "position.jsonl"
    
    if not position_file.exists():
        print(f"⚠️ A股持仓文件不存在: {position_file}")
        return {}
    
    # 获取上一个交易日
    market = get_market_type()
    yesterday_date = get_yesterday_date(today_date, market=market)
    
    all_records = []
    with open(position_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                doc = json.loads(line)
                record_date = doc.get("date")
                if record_date and record_date < today_date:
                    all_records.append(doc)
            except:
                continue
    
    if not all_records:
        return {}
    
    # 按日期和ID降序，取最新记录
    all_records.sort(key=lambda x: (x.get("date", ""), x.get("id", 0)), reverse=True)
    return all_records[0].get("positions", {})


def get_latest_position(today_date: str, signature: str) -> Tuple[Dict[str, float], int]:
    """
    获取A股最新持仓（智能三级降级策略）
    
    优先级：
    1. 当日记录（最大ID）
    2. 上一个交易日记录（最大ID）
    3. 文件中最新记录（按日期+ID排序）
    
    Args:
        today_date: 查询日期
        signature: Agent标识
    
    Returns:
        (positions, max_id)
        示例: ({"600519.SH": 100, "CASH": 50000.0}, 5)
    """
    base_dir = Path(__file__).resolve().parent
    
    # A股专用路径
    log_path = get_config_value("LOG_PATH", "./data/agent_data_astock")
    if os.path.isabs(log_path):
        position_file = Path(log_path) / signature / "position" / "position.jsonl"
    else:
        if log_path.startswith("./data/"):
            log_path = log_path[7:]
        position_file = base_dir / "data" / log_path / signature / "position" / "position.jsonl"
    
    if not position_file.exists():
        return {}, -1
    
    market = get_market_type()
    
    # 步骤1: 查找当日记录（最新ID）
    max_id_today = -1
    latest_today = {}
    
    with open(position_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                doc = json.loads(line)
                if doc.get("date") == today_date:
                    current_id = doc.get("id", -1)
                    if current_id > max_id_today:
                        max_id_today = current_id
                        latest_today = doc.get("positions", {})
            except:
                continue
    
    if max_id_today >= 0 and latest_today:
        return latest_today, max_id_today
    
    # 步骤2: 回退到上一个交易日（最新ID）
    prev_date = get_yesterday_date(today_date, market=market)
    max_id_prev = -1
    latest_prev = {}
    
    with open(position_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                doc = json.loads(line)
                if doc.get("date") == prev_date:
                    current_id = doc.get("id", -1)
                    if current_id > max_id_prev:
                        max_id_prev = current_id
                        latest_prev = doc.get("positions", {})
            except:
                continue
    
    if max_id_prev >= 0 and latest_prev:
        return latest_prev, max_id_prev
    
    # 步骤3: 仍未找到，取文件中最新记录（全局排序）
    all_records = []
    with open(position_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                doc = json.loads(line)
                record_date = doc.get("date")
                if record_date and record_date < today_date:
                    all_records.append(doc)
            except:
                continue
    
    if all_records:
        # 按日期和ID降序排列，取第一条
        all_records.sort(key=lambda x: (x.get("date", ""), x.get("id", 0)), reverse=True)
        return all_records[0].get("positions", {}), all_records[0].get("id", -1)
    
    return {}, -1


def add_no_trade_record(today_date: str, signature: str):
    """
    添加A股不交易记录（保持持仓不变）
    
    操作：
    1. 获取最新持仓
    2. 创建新记录（ID+1）
    3. 追加到position.jsonl文件
    
    Args:
        today_date: 今日日期
        signature: Agent标识
    """
    current_position, current_action_id = get_latest_position(today_date, signature)
    
    # 如果没有持仓，创建初始空仓（仅现金）
    if not current_position:
        try:
            from .a_stock_agent import BaseAgentAStock
        except ImportError:
            from agent_service.agent_astock import BaseAgentAStock
        agent = BaseAgentAStock(signature=signature, basemodel="dummy")
        current_position = {"CASH": agent.initial_cash}
        current_action_id = 0
    
    save_item = {
        "date": today_date,
        "id": current_action_id + 1,
        "this_action": {"action": "no_trade", "symbol": "", "amount": 0},
        "positions": current_position
    }
    
    base_dir = Path(__file__).resolve().parent
    
    # A股专用路径
    log_path = get_config_value("LOG_PATH", "./data/agent_data_astock")
    if os.path.isabs(log_path):
        position_file = Path(log_path) / signature / "position" / "position.jsonl"
    else:
        if log_path.startswith("./data/"):
            log_path = log_path[7:]
        position_file = base_dir / "data" / log_path / signature / "position" / "position.jsonl"
    
    position_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(position_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(save_item, ensure_ascii=False) + "\n")
    
    print(f"📊 A股不交易记录已添加: {today_date} (ID: {current_action_id + 1})")

# 交易成本计算器
def calculate_trade_cost(
    symbol: str, 
    price: float, 
    amount: int, 
    direction: str
) -> Dict[str, float]:
    """
    计算A股交易成本
    - 印花税：卖出时收取 0.1%
    - 过户费：仅沪市 0.001%（双向）
    - 佣金：最高0.3%（双向），最低5元
    
    Returns:
        {
            "commission": 佣金,
            "stamp_tax": 印花税,
            "transfer_fee": 过户费,
            "total_cost": 总成本
        }
    """
    total_value = price * amount
    
    # 佣金（双向，最低5元）
    commission_rate = 0.0003  # 万分之三
    commission = max(total_value * commission_rate, 5.0)
    
    # 印花税（仅卖出）
    stamp_tax = total_value * 0.001 if direction == "sell" else 0.0
    
    # 过户费（沪市双向）
    transfer_fee = 0.0
    if symbol.endswith(".SH"):
        transfer_fee = total_value * 0.00001
    
    return {
        "commission": commission,
        "stamp_tax": stamp_tax,
        "transfer_fee": transfer_fee,
        "total_cost": commission + stamp_tax + transfer_fee
    }

# ========== 独立测试入口 ==========
if __name__ == "__main__":
    """A股数据工具独立测试"""
    import asyncio
    
    # 测试配置
    today_date = get_config_value("TODAY_DATE", "2025-10-15")
    signature = get_config_value("SIGNATURE", "test_agent")
    
    print(f"=" * 60)
    print(f"A股数据工具独立测试")
    print(f"=" * 60)
    print(f"今日日期: {today_date}")
    print(f"Agent标识: {signature}")
    print(f"市场类型: {get_market_type()}")
    print(f"数据文件: {get_merged_file_path()}")
    
    # 测试1: 上一个交易日
    print(f"\n【测试1】上一个交易日:")
    yesterday = get_yesterday_date(today_date, market="cn")
    print(f"   {today_date} → {yesterday}")
    
    # 测试2: 是否为交易日
    print(f"\n【测试2】交易日判断:")
    is_trading = is_trading_day(today_date, market="cn")
    print(f"   {today_date} 是交易日: {is_trading}")
    
    # 测试3: 获取最新持仓
    print(f"\n【测试3】最新持仓查询:")
    latest_pos, latest_id = get_latest_position(today_date, signature)
    print(f"   持仓ID: {latest_id}")
    print(f"   持仓数量: {len(latest_pos)}")
    if latest_pos:
        print(f"   现金: ¥{latest_pos.get('CASH', 0):,.2f}")
        # 显示持仓股票
        stock_holding = {k: v for k, v in latest_pos.items() if k != "CASH" and v > 0}
        if stock_holding:
            for sym, qty in list(stock_holding.items())[:5]:
                print(f"   {sym}: {qty}股")
            if len(stock_holding) > 5:
                print(f"   ... 共{len(stock_holding)}只持仓股票")
        else:
            print(f"   当前无股票持仓")
    else:
        print(f"   暂无持仓记录")
    
    # 测试4: 获取昨日开收盘价
    print(f"\n【测试4】昨日开收盘价:")
    ystd_buy, ystd_sell = get_yesterday_open_and_close_price(today_date, all_sse_50_symbols[:3], market="cn")
    print(f"   买入价: {ystd_buy}")
    print(f"   卖出价: {ystd_sell}")
    
    # 测试5: 添加不交易记录（可选）
    test_add = input(f"\n【测试5】是否测试添加不交易记录? (y/n): ").lower().strip()
    if test_add == 'y':
        add_no_trade_record(today_date, signature)
        print(f"   ✓ 已添加不交易记录")
    
    # 测试6: 股票名称映射
    print(f"\n【测试6】股票名称映射:")
    name_map = get_stock_name_mapping(market="cn")
    sample_stocks = list(all_sse_50_symbols[:3])
    for sym in sample_stocks:
        print(f"   {sym}: {name_map.get(sym, '未知')}")
    
    print(f"\n" + "=" * 60)
    print(f"测试完成")
    print(f"=" * 60)