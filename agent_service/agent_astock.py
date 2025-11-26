"""
BaseAgentAStock class - A股专用交易Agent基类
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient

# 加载环境变量
load_dotenv()

# 导入优化后的A股专用工具
from tools.a_stock_data_tools import (
    add_no_trade_record,
    get_today_init_position,
    is_trading_day,
    all_sse_50_symbols,
)
from tools.a_stock_config import get_config_value, write_config_value, extract_conversation, extract_tool_messages


class DeepSeekChatOpenAI(ChatOpenAI):
    """DeepSeek API兼容层 - 处理tool_calls参数格式差异"""
    
    def _generate(self, messages: list, stop: Optional[list] = None, **kwargs):
        result = super()._generate(messages, stop, **kwargs)
        for generation in result.generations:
            for gen in generation:
                if hasattr(gen, "message") and hasattr(gen.message, "additional_kwargs"):
                    tool_calls = gen.message.additional_kwargs.get("tool_calls")
                    if tool_calls:
                        for tool_call in tool_calls:
                            if "function" in tool_call and "arguments" in tool_call["function"]:
                                args = tool_call["function"]["arguments"]
                                if isinstance(args, str):
                                    try:
                                        tool_call["function"]["arguments"] = json.loads(args)
                                    except json.JSONDecodeError:
                                        pass
        return result


# A股专用系统提示词
def get_agent_system_prompt_astock(today_date: str, signature: str, stock_symbols: List[str]) -> str:
    return f"""你是专业的A股量化交易AI Agent，名为{signature}。

当前日期：{today_date}
可交易标的：{', '.join(stock_symbols[:10])} 等{len(stock_symbols)}只上证50成分股

交易规则：
- 最小单位：100股（手）
- T+1制度
- 涨跌停限制：普通股±10%，ST股±5%
- 手续费：万分之三，最低5元

任务：分析持仓→获取行情→制定决策→执行交易→记录理由

完成后输出"ANALYSIS_COMPLETE"并停止。"""

from config.constants import STOP_SIGNAL


class BaseAgentAStock:
    """A股专用交易Agent基类"""
    
    DEFAULT_SSE50_SYMBOLS = all_sse_50_symbols

    def __init__(
        self,
        signature: str,
        basemodel: str,
        stock_symbols: Optional[List[str]] = None,
        mcp_config: Optional[Dict[str, Dict[str, Any]]] = None,
        log_path: Optional[str] = None,
        max_steps: int = 10,
        max_retries: int = 3,
        base_delay: float = 0.5,
        openai_base_url: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        initial_cash: float = 100000.0,
        init_date: str = "2025-10-09",
    ):
        self.signature = signature
        self.basemodel = basemodel
        self.market = "cn"  # 专注A股
        
        self.stock_symbols = stock_symbols or self.DEFAULT_SSE50_SYMBOLS
        self.max_steps = max_steps
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.initial_cash = initial_cash
        self.init_date = init_date
        
        self.mcp_config = mcp_config or self._get_default_mcp_config()
        self.base_log_path = log_path or "./data/agent_data_astock"
        
        self.openai_base_url = openai_base_url or os.getenv("OPENAI_API_BASE")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        
        self.client: Optional[MultiServerMCPClient] = None
        self.tools: Optional[List] = None
        self.model: Optional[ChatOpenAI] = None
        self.agent: Optional[Any] = None
        
        self.data_path = Path(self.base_log_path) / self.signature
        self.position_file = self.data_path / "position" / "position.jsonl"

    def _get_default_mcp_config(self) -> Dict[str, Dict[str, Any]]:
        return {
            "math": {
                "transport": "streamable_http",
                "url": f"http://localhost:{os.getenv('MATH_HTTP_PORT', '8000')}/mcp",
            },
            "stock_local": {
                "transport": "streamable_http",
                "url": f"http://localhost:{os.getenv('GETPRICE_HTTP_PORT', '8003')}/mcp",
            },
            "search": {
                "transport": "streamable_http",
                "url": f"http://localhost:{os.getenv('SEARCH_HTTP_PORT', '8004')}/mcp",
            },
            "trade": {
                "transport": "streamable_http",
                "url": f"http://localhost:{os.getenv('TRADE_HTTP_PORT', '8002')}/mcp",
            },
        }

    async def initialize(self) -> None:
        """初始化MCP客户端和AI模型"""
        print(f"🚀 初始化A股Agent: {self.signature}")
        print(f"📋 初始化参数检查:")
        print(f"   - API Key: {'已设置' if self.openai_api_key else '未设置'}")
        print(f"   - Base Model: {self.basemodel}")
        print(f"   - Base URL: {self.openai_base_url}")
        print(f"   - MCP Config: {json.dumps(self.mcp_config, indent=2)}")
        
        if not self.openai_api_key:
            raise ValueError("❌ 未设置OPENAI_API_KEY")
        
        # 初始化MCP客户端和工具
        try:
            print(f"🔧 开始初始化MCP客户端...")
            self.client = MultiServerMCPClient(self.mcp_config)
            print(f"✅ MCP客户端创建成功")
            
            print(f"🔧 开始获取MCP工具...")
            self.tools = await self.client.get_tools()
            print(f"✅ 成功加载 {len(self.tools) if self.tools else 0} 个MCP工具")
            
            if not self.tools:
                print("⚠️ 警告: MCP工具列表为空")
            else:
                print(f"📋 加载的工具:")
                for i, tool in enumerate(self.tools):
                    print(f"   - 工具 {i+1}: {getattr(tool, 'name', 'unknown')}")
                    
        except Exception as e:
            print(f"❌ MCP初始化失败: {type(e).__name__}: {e}")
            self.tools = None  # 确保tools为None以触发后续检查
            raise RuntimeError(f"❌ MCP初始化失败: {e}")
        
        # 初始化AI模型
        try:
            print(f"🔧 开始初始化AI模型: {self.basemodel}")
            if "deepseek" in self.basemodel.lower():
                self.model = DeepSeekChatOpenAI(
                    model=self.basemodel,
                    base_url=self.openai_base_url,
                    api_key=self.openai_api_key,
                    max_retries=3,
                    timeout=30,
                )
                print(f"✅ DeepSeek模型初始化成功")
            else:
                self.model = ChatOpenAI(
                    model=self.basemodel,
                    base_url=self.openai_base_url,
                    api_key=self.openai_api_key,
                    max_retries=3,
                    timeout=30,
                )
                print(f"✅ OpenAI模型初始化成功")
                
            print(f"✅ AI模型 {self.basemodel} 初始化完成")
            
        except Exception as e:
            print(f"❌ AI模型初始化失败: {type(e).__name__}: {e}")
            self.model = None  # 确保model为None以触发后续检查
            raise RuntimeError(f"❌ AI模型初始化失败: {e}")
        
        print(f"✅ A股Agent {self.signature} 初始化完成")
        
    def get_debug_status(self) -> Dict[str, Any]:
        """获取调试状态信息"""
        return {
            "signature": self.signature,
            "basemodel": self.basemodel,
            "market": self.market,
            "openai_api_key_set": bool(self.openai_api_key),
            "openai_base_url": self.openai_base_url,
            "mcp_client_initialized": bool(self.client),
            "tools_loaded": bool(self.tools),
            "tools_count": len(self.tools) if self.tools else 0,
            "model_initialized": bool(self.model),
            "agent_created": bool(self.agent),
            "stock_symbols_count": len(self.stock_symbols),
            "data_path_exists": self.data_path.exists(),
            "position_file_exists": self.position_file.exists(),
        }
        
    def print_debug_status(self) -> None:
        """打印调试状态信息"""
        status = self.get_debug_status()
        print(f"\n🔍 Agent调试状态 - {status['signature']}:")
        print(f"   基础信息:")
        print(f"     - 模型: {status['basemodel']}")
        print(f"     - 市场: {status['market']}")
        print(f"     - API Key: {'✅ 已设置' if status['openai_api_key_set'] else '❌ 未设置'}")
        print(f"     - Base URL: {status['openai_base_url'] or '未设置'}")
        print(f"   MCP状态:")
        print(f"     - 客户端: {'✅ 已连接' if status['mcp_client_initialized'] else '❌ 未连接'}")
        print(f"     - 工具: {'✅ 已加载' if status['tools_loaded'] else '❌ 未加载'} ({status['tools_count']}个)")
        print(f"   AI状态:")
        print(f"     - 模型: {'✅ 已初始化' if status['model_initialized'] else '❌ 未初始化'}")
        print(f"     - Agent: {'✅ 已创建' if status['agent_created'] else '❌ 未创建'}")
        print(f"   数据状态:")
        print(f"     - 股票数量: {status['stock_symbols_count']}只")
        print(f"     - 数据目录: {'✅ 存在' if status['data_path_exists'] else '❌ 不存在'}")
        print(f"     - 持仓文件: {'✅ 存在' if status['position_file_exists'] else '❌ 不存在'}")
        print()
        
    async def safe_initialize(self) -> bool:
        """安全初始化，返回成功状态而不是抛出异常"""
        try:
            await self.initialize()
            return True
        except Exception as e:
            print(f"❌ 初始化失败: {type(e).__name__}: {e}")
            return False
        print(f"📊 初始化状态总结:")
        print(f"   - MCP客户端: {'✅ 正常' if self.client else '❌ 失败'}")
        print(f"   - MCP工具: {'✅ 已加载' if self.tools else '❌ 未加载'} ({len(self.tools) if self.tools else 0}个)")
        print(f"   - AI模型: {'✅ 正常' if self.model else '❌ 失败'}")

    def _setup_logging(self, today_date: str) -> Path:
        """设置日志路径"""
        log_path = Path(self.base_log_path) / self.signature / "log" / today_date
        log_path.mkdir(parents=True, exist_ok=True)
        return log_path / "log.jsonl"

    def _log_message(self, log_file: Path, new_messages: List[Dict[str, str]]) -> None:
        """记录日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "signature": self.signature,
            "new_messages": new_messages
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    async def _ainvoke_with_retry(self, message: List[Dict[str, str]]) -> Any:
        """带重试的Agent调用"""
        # 关键检查：确保Agent已创建
        if not self.agent:
            error_msg = "❌ Agent未创建，无法调用ainvoke()"
            print(f"💥 {error_msg}")
            print(f"🔍 Agent状态检查:")
            print(f"   - self.agent: {self.agent} (类型: {type(self.agent)})")
            print(f"   - self.model: {'✅ 已初始化' if self.model else '❌ 未初始化'}")
            print(f"   - self.tools: {'✅ 已加载' if self.tools else '❌ 未加载'}")
            raise RuntimeError(error_msg)
            
        print(f"🎯 开始Agent调用，消息长度: {len(message)}")
        
        for attempt in range(1, self.max_retries + 1):
            try:
                print(f"🚀 第{attempt}次尝试调用Agent.ainvoke()...")
                result = await self.agent.ainvoke({"messages": message}, {"recursion_limit": 100})
                print(f"✅ 第{attempt}次尝试成功")
                return result
                
            except AttributeError as ae:
                # 特别处理AttributeError（如'NoneType' object has no attribute 'bind'）
                error_msg = f"💥 第{attempt}次尝试失败 - AttributeError: {ae}"
                print(f"❌ {error_msg}")
                print(f"🔍 AttributeError详情:")
                print(f"   - Agent对象: {self.agent} (类型: {type(self.agent)})")
                print(f"   - 错误信息: {ae}")
                print(f"   - 可能原因: Agent创建失败或self.agent为None")
                
                if attempt == self.max_retries:
                    print(f"💥 所有重试失败，抛出AttributeError")
                    raise ae
                    
                wait_time = self.base_delay * attempt
                print(f"⏳ {wait_time}秒后重试...")
                await asyncio.sleep(wait_time)
                
            except Exception as e:
                error_msg = f"❌ 第{attempt}次尝试失败 - {type(e).__name__}: {e}"
                print(f"💥 {error_msg}")
                
                if attempt == self.max_retries:
                    print(f"💥 所有重试失败，抛出异常")
                    raise e
                    
                wait_time = self.base_delay * attempt
                print(f"⏳ {wait_time}秒后重试...")
                await asyncio.sleep(wait_time)

    async def run_trading_session(self, today_date: str) -> None:
        """运行单日交易会话"""
        print(f"📈 启动A股交易会话: {today_date}")
        
        # 关键检查点：确保所有必需组件已初始化
        print(f"🔍 交易会话前检查:")
        print(f"   - self.model: {'✅ 已初始化' if self.model else '❌ 未初始化'}")
        print(f"   - self.tools: {'✅ 已加载' if self.tools else '❌ 未加载'} ({len(self.tools) if self.tools else 0}个)")
        print(f"   - self.client: {'✅ 已连接' if self.client else '❌ 未连接'}")
        
        # 验证必需组件
        if not self.model:
            error_msg = "❌ AI模型未初始化，请先调用initialize()方法"
            print(f"💥 {error_msg}")
            raise RuntimeError(error_msg)
            
        if not self.tools:
            error_msg = "❌ MCP工具未加载，请检查MCP客户端初始化"
            print(f"💥 {error_msg}")
            raise RuntimeError(error_msg)
            
        if not self.client:
            error_msg = "❌ MCP客户端未连接，请检查网络连接和MCP服务状态"
            print(f"💥 {error_msg}")
            raise RuntimeError(error_msg)
        
        log_file = self._setup_logging(today_date)
        
        try:
            print(f"🔧 创建交易Agent...")
            system_prompt = get_agent_system_prompt_astock(today_date, self.signature, self.stock_symbols)
            print(f"📋 系统提示词长度: {len(system_prompt)} 字符")
            print(f"🛠️  可用工具数量: {len(self.tools)}")
            
            self.agent = create_agent(
                self.model,
                tools=self.tools,
                system_prompt=system_prompt,
            )
            
            if not self.agent:
                error_msg = "❌ Agent创建失败，返回None"
                print(f"💥 {error_msg}")
                raise RuntimeError(error_msg)
                
            print(f"✅ 交易Agent创建成功")
            
        except Exception as e:
            error_msg = f"❌ 创建交易Agent失败: {type(e).__name__}: {e}"
            print(f"💥 {error_msg}")
            print(f"🔍 失败详情:")
            print(f"   - 模型类型: {type(self.model)}")
            print(f"   - 工具数量: {len(self.tools) if self.tools else 'None'}")
            print(f"   - 工具类型: {type(self.tools) if self.tools else 'None'}")
            raise RuntimeError(error_msg)
        
        user_query = [{"role": "user", "content": f"请分析并更新今日({today_date})持仓"}]
        message = user_query.copy()
        self._log_message(log_file, user_query)
        
        current_step = 0
        while current_step < self.max_steps:
            current_step += 1
            print(f"🔄 第{current_step}/{self.max_steps}步")
            
            try:
                response = await self._ainvoke_with_retry(message)
                agent_response = extract_conversation(response, "final")
                
                if STOP_SIGNAL in agent_response:
                    print("✅ 收到停止信号，交易结束")
                    self._log_message(log_file, [{"role": "assistant", "content": agent_response}])
                    break
                
                tool_msgs = extract_tool_messages(response)
                tool_response = "\n".join([msg.content for msg in tool_msgs])
                
                new_messages = [
                    {"role": "assistant", "content": agent_response},
                    {"role": "user", "content": f"工具结果: {tool_response}"},
                ]
                message.extend(new_messages)
                
                self._log_message(log_file, new_messages[0])
                self._log_message(log_file, new_messages[1])
                
            except Exception as e:
                print(f"❌ 交易会话错误: {type(e).__name__}: {e}")
                print(f"🔍 错误详情:")
                print(f"   - 当前步骤: {current_step}/{self.max_steps}")
                print(f"   - Agent状态: {'✅ 已创建' if self.agent else '❌ 未创建'}")
                print(f"   - 消息长度: {len(message)}")
                raise
        
        await self._handle_trading_result(today_date)

    async def _handle_trading_result(self, today_date: str) -> None:
        """处理交易结果"""
        if_trade = get_config_value("IF_TRADE")
        if if_trade:
            write_config_value("IF_TRADE", False)
            print("✅ 交易执行完成")
        else:
            print("📊 无交易指令，保持持仓")
            add_no_trade_record(today_date, self.signature)
            write_config_value("IF_TRADE", False)

    def register_agent(self) -> None:
        """注册新Agent，创建初始持仓"""
        if self.position_file.exists():
            print(f"⚠️ 持仓文件已存在，跳过注册: {self.position_file}")
            return
        
        self.position_file.parent.mkdir(parents=True, exist_ok=True)
        
        init_position = {symbol: 0 for symbol in self.stock_symbols}
        init_position["CASH"] = self.initial_cash
        
        with open(self.position_file, "w") as f:
            f.write(json.dumps({
                "date": self.init_date,
                "id": 0,
                "positions": init_position
            }) + "\n")
        
        print(f"✅ Agent注册完成: {self.signature}")
        print(f"💰 初始资金: ¥{self.initial_cash:,.2f}")
        print(f"📊 股票数量: {len(self.stock_symbols)}")

    def get_trading_dates(self, init_date: str, end_date: str) -> List[str]:
        """获取A股交易日列表（自动过滤节假日）"""
        if not self.position_file.exists():
            self.register_agent()
            max_date = init_date
        else:
            with open(self.position_file, "r") as f:
                dates = [json.loads(line)["date"] for line in f if line.strip()]
                max_date = max(dates) if dates else init_date
        
        max_date_obj = datetime.strptime(max_date, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        
        if end_date_obj <= max_date_obj:
            return []
        
        trading_dates = []
        current_date = max_date_obj + timedelta(days=1)
        
        while current_date <= end_date_obj:
            date_str = current_date.strftime("%Y-%m-%d")
            if is_trading_day(date_str, market="cn"):
                trading_dates.append(date_str)
            current_date += timedelta(days=1)
        
        return trading_dates

    async def run_with_retry(self, today_date: str) -> None:
        """带重试的运行方法"""
        for attempt in range(1, self.max_retries + 1):
            try:
                print(f"🔄 运行 {self.signature} - {today_date} (第{attempt}次尝试)")
                await self.run_trading_session(today_date)
                print(f"✅ {self.signature} - {today_date} 运行成功")
                return
            except Exception as e:
                if attempt == self.max_retries:
                    print(f"💥 {self.signature} - {today_date} 所有重试失败")
                    raise
                wait_time = self.base_delay * attempt
                print(f"⏳ {wait_time}秒后重试...")
                await asyncio.sleep(wait_time)

    async def run_date_range(self, init_date: str, end_date: str) -> None:
        """运行日期范围内的所有交易日"""
        print(f"📅 运行A股日期范围: {init_date} 至 {end_date}")
        
        trading_dates = self.get_trading_dates(init_date, end_date)
        if not trading_dates:
            print("ℹ️ 无交易日需要处理")
            return
        
        print(f"📊 待处理交易日: {trading_dates}")
        
        for date in trading_dates:
            write_config_value("TODAY_DATE", date)
            write_config_value("SIGNATURE", self.signature)
            
            try:
                await self.run_with_retry(date)
            except Exception as e:
                print(f"❌ 处理失败 {self.signature} - 日期: {date}")
                raise
        
        print(f"✅ {self.signature} 处理完成")

    def get_position_summary(self) -> Dict[str, Any]:
        """获取持仓摘要"""
        if not self.position_file.exists():
            return {"error": "持仓文件不存在"}
        
        positions = []
        with open(self.position_file, "r") as f:
            for line in f:
                if line.strip():
                    positions.append(json.loads(line))
        
        if not positions:
            return {"error": "无持仓记录"}
        
        latest = positions[-1]
        return {
            "signature": self.signature,
            "latest_date": latest.get("date"),
            "positions": latest.get("positions", {}),
            "total_records": len(positions),
        }

    def __str__(self) -> str:
        return f"BaseAgentAStock(signature='{self.signature}', basemodel='{self.basemodel}', stocks={len(self.stock_symbols)})"

    def __repr__(self) -> str:
        return self.__str__()