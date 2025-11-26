#!/usr/bin/env python3
"""
快速诊断脚本 - 检查A股Agent环境
"""

import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime

# 确保项目根目录在path中
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_environment():
    """检查环境配置"""
    print("🔍 A股Agent环境诊断")
    print("=" * 60)
    
    # 检查.env文件
    env_file = project_root / ".env"
    print(f"📋 配置文件检查:")
    print(f"   .env文件: {'✅ 存在' if env_file.exists() else '❌ 不存在'}")
    
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)
        print(f"   ✅ .env文件已加载")
    
    # 检查必需的环境变量
    required_vars = {
        "OPENAI_API_KEY": "OpenAI API密钥",
        "OPENAI_API_BASE": "OpenAI API基础URL", 
        "MATH_HTTP_PORT": "数学服务端口",
        "TRADE_HTTP_PORT": "交易服务端口",
        "GETPRICE_HTTP_PORT": "行情服务端口",
        "SEARCH_HTTP_PORT": "搜索服务端口",
    }
    
    print(f"\n🔑 环境变量检查:")
    all_set = True
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            if "KEY" in var:
                print(f"   {var}: ✅ 已设置 ({description})")
            else:
                print(f"   {var}: ✅ {value} ({description})")
        else:
            print(f"   {var}: ❌ 未设置 ({description})")
            all_set = False
    
    return all_set

def check_dependencies():
    """检查依赖包"""
    print(f"\n📦 依赖包检查:")
    
    required_packages = [
        ("langchain", "LangChain框架"),
        ("langchain_openai", "OpenAI适配器"),
        ("langchain_mcp_adapters", "MCP适配器"),
        ("openai", "OpenAI客户端"),
        ("aiohttp", "异步HTTP客户端"),
        ("python-dotenv", "环境变量管理"),
    ]
    
    all_available = True
    for package, description in required_packages:
        try:
            __import__(package)
            print(f"   {package}: ✅ 已安装 ({description})")
        except ImportError:
            print(f"   {package}: ❌ 未安装 ({description})")
            all_available = False
    
    return all_available

async def check_mcp_services():
    """检查MCP服务状态"""
    print(f"\n🌐 MCP服务检查:")
    
    try:
        import aiohttp
        
        services = {
            "数学服务": os.getenv("MATH_HTTP_PORT", "8000"),
            "交易服务": os.getenv("TRADE_HTTP_PORT", "8002"),
            "行情服务": os.getenv("GETPRICE_HTTP_PORT", "8003"),
            "搜索服务": os.getenv("SEARCH_HTTP_PORT", "8004"),
        }
        
        all_running = True
        timeout = aiohttp.ClientTimeout(total=5)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for name, port in services.items():
                url = f"http://localhost:{port}/mcp"
                try:
                    async with session.get(url + "/health") as response:
                        if response.status == 200:
                            print(f"   {name}: ✅ 运行中 (端口{port})")
                        else:
                            print(f"   {name}: ⚠️  响应异常 HTTP {response.status} (端口{port})")
                            all_running = False
                except Exception as e:
                    print(f"   {name}: ❌ 未响应 (端口{port}) - {e}")
                    all_running = False
        
        return all_running
        
    except ImportError:
        print("   ❌ aiohttp未安装，无法检查服务状态")
        return False

async def test_agent_initialization():
    """测试Agent初始化"""
    print(f"\n🤖 Agent初始化测试:")
    
    try:
        from agent_service.agent_astock import BaseAgentAStock
        
        # 创建测试Agent
        agent = BaseAgentAStock(
            signature="DIAG_TEST",
            basemodel="gpt-4o-mini",  # 使用便宜模型测试
            stock_symbols=["600519"],  # 只用一只股票
            initial_cash=100000.0,
            init_date="2025-10-09"
        )
        
        print(f"   ✅ Agent实例创建成功")
        
        # 打印调试状态
        agent.print_debug_status()
        
        # 尝试安全初始化
        print(f"\n🔧 尝试初始化...")
        success = await agent.safe_initialize()
        
        if success:
            print(f"   ✅ Agent初始化成功")
            return True
        else:
            print(f"   ❌ Agent初始化失败")
            return False
            
    except Exception as e:
        print(f"   ❌ Agent测试失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主诊断函数"""
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 环境检查
    env_ok = check_environment()
    
    # 依赖检查
    deps_ok = check_dependencies()
    
    # 异步检查MCP服务和Agent
    async def run_async_checks():
        mcp_ok = await check_mcp_services()
        agent_ok = await test_agent_initialization()
        
        print("\n" + "=" * 60)
        print("📊 诊断总结:")
        print(f"   环境配置: {'✅ 正常' if env_ok else '❌ 异常'}")
        print(f"   依赖包: {'✅ 正常' if deps_ok else '❌ 异常'}")
        print(f"   MCP服务: {'✅ 正常' if mcp_ok else '❌ 异常'}")
        print(f"   Agent初始化: {'✅ 正常' if agent_ok else '❌ 异常'}")
        
        all_ok = env_ok and deps_ok and mcp_ok and agent_ok
        print(f"\n🎯 整体状态: {'✅ 系统正常' if all_ok else '❌ 需要修复'}")
        
        if not all_ok:
            print(f"\n💡 建议:")
            if not env_ok:
                print("   - 检查.env文件和环境变量配置")
            if not deps_ok:
                print("   - 安装缺失的Python包")
            if not mcp_ok:
                print("   - 启动MCP服务或检查端口配置")
            if not agent_ok:
                print("   - 检查Agent代码和依赖配置")
        
        return all_ok
    
    # 运行异步检查
    return asyncio.run(run_async_checks())

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)