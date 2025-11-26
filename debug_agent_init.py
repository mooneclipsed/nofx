#!/usr/bin/env python3
"""
A股Agent初始化调试脚本
"""

import asyncio
import os
import sys
from pathlib import Path

# 将项目根目录添加到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from agent_service.agent_astock import BaseAgentAStock

async def debug_agent_initialization():
    """调试Agent初始化过程"""
    print("🚀 开始A股Agent初始化调试")
    print("=" * 60)
    
    # 检查环境变量
    print("🔍 环境变量检查:")
    required_env_vars = [
        "OPENAI_API_KEY", 
        "OPENAI_API_BASE",
        "MATH_HTTP_PORT",
        "GETPRICE_HTTP_PORT", 
        "SEARCH_HTTP_PORT",
        "TRADE_HTTP_PORT"
    ]
    
    for var in required_env_vars:
        value = os.getenv(var)
        print(f"   {var}: {'✅ 已设置' if value else '❌ 未设置'}")
        if value and 'KEY' in var:
            print(f"     值: {value[:10]}..." if len(value) > 10 else f"     值: {value}")
        elif value:
            print(f"     值: {value}")
    
    print()
    
    # 创建Agent实例
    try:
        print("🔧 创建Agent实例...")
        agent = BaseAgentAStock(
            signature="DEBUG_AGENT",
            basemodel="qwen-turbo",  # 使用通义千问模型，或 "gpt-4o-mini" 等
            stock_symbols=["600519", "000858"],  # 测试用少量股票
            initial_cash=100000.0,
            init_date="2025-10-09"
        )
        print("✅ Agent实例创建成功")
        
        # 打印初始状态
        agent.print_debug_status()
        
    except Exception as e:
        print(f"❌ Agent实例创建失败: {type(e).__name__}: {e}")
        return
    
    print("\n" + "=" * 60)
    print("🔄 开始初始化过程...")
    
    # 尝试安全初始化
    init_success = await agent.safe_initialize()
    
    if init_success:
        print("🎉 Agent初始化成功!")
        agent.print_debug_status()
        
        # 尝试运行一个简单的交易会话测试
        print("\n" + "=" * 60)
        print("🧪 测试交易会话...")
        
        try:
            # 注册Agent（创建初始持仓）
            print("📋 注册Agent...")
            agent.register_agent()
            
            # 尝试运行单日交易会话
            print("🔍 运行单日交易会话测试...")
            await agent.run_trading_session("2025-10-09")
            print("✅ 交易会话测试完成")
            
        except Exception as e:
            print(f"❌ 交易会话测试失败: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            
    else:
        print("💥 Agent初始化失败，请检查上述错误信息")
        agent.print_debug_status()
    
    print("\n" + "=" * 60)
    print("🔍 调试完成")

async def test_specific_issue():
    """测试特定的初始化问题"""
    print("🎯 测试特定的MCP/Agent初始化问题")
    print("=" * 60)
    
    # 创建一个Agent但不初始化，直接测试问题
    agent = BaseAgentAStock(
        signature="TEST_AGENT",
        basemodel="deepseek-chat",
        stock_symbols=["600519"],
    )
    
    print("🔍 未初始化状态:")
    agent.print_debug_status()
    
    # 尝试直接运行交易会话（应该失败）
    print("\n🧪 尝试在未初始化状态下运行交易会话...")
    try:
        await agent.run_trading_session("2025-10-09")
        print("⚠️  意外：交易会话成功运行（这可能表明问题已解决）")
    except Exception as e:
        print(f"✅ 预期错误: {type(e).__name__}: {e}")
        print("🔍 错误符合预期，说明检查机制正常工作")

if __name__ == "__main__":
    print("A股Agent初始化调试工具")
    print("运行模式: 完整初始化调试")
    
    # 默认运行完整调试
    asyncio.run(debug_agent_initialization())