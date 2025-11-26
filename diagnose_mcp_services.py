#!/usr/bin/env python3
"""
MCP服务诊断脚本
"""

import asyncio
import os
import json
from typing import Dict, Any
from datetime import datetime

try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    MCP_AVAILABLE = True
except ImportError:
    print("❌ langchain_mcp_adapters 未安装")
    MCP_AVAILABLE = False

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    print("❌ aiohttp 未安装")
    AIOHTTP_AVAILABLE = False

async def check_mcp_service(name: str, url: str) -> Dict[str, Any]:
    """检查单个MCP服务状态"""
    print(f"🔍 检查 {name} 服务: {url}")
    
    result = {
        "name": name,
        "url": url,
        "status": "unknown",
        "error": None,
        "response_time": None,
        "tools_count": 0
    }
    
    try:
        if not AIOHTTP_AVAILABLE:
            result["status"] = "error"
            result["error"] = "aiohttp未安装"
            return result
            
        start_time = datetime.now()
        
        # 尝试HTTP连接
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(url + "/health") as response:
                    response_time = (datetime.now() - start_time).total_seconds()
                    result["response_time"] = response_time
                    
                    if response.status == 200:
                        result["status"] = "healthy"
                        print(f"   ✅ {name} 服务健康 (响应时间: {response_time:.2f}s)")
                    else:
                        result["status"] = "unhealthy"
                        result["error"] = f"HTTP {response.status}"
                        print(f"   ⚠️  {name} 服务异常: HTTP {response.status}")
                        
            except aiohttp.ClientError as e:
                response_time = (datetime.now() - start_time).total_seconds()
                result["response_time"] = response_time
                result["status"] = "error"
                result["error"] = f"连接失败: {str(e)}"
                print(f"   ❌ {name} 服务连接失败: {e}")
                
    except Exception as e:
        result["status"] = "error"
        result["error"] = f"检查失败: {type(e).__name__}: {e}"
        print(f"   ❌ {name} 服务检查异常: {e}")
    
    return result

async def test_mcp_client(mcp_config: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """测试MCP客户端初始化"""
    print(f"\n🔧 测试MCP客户端初始化...")
    
    result = {
        "client_created": False,
        "tools_loaded": False,
        "tools_count": 0,
        "error": None,
        "services_status": {}
    }
    
    try:
        if not MCP_AVAILABLE:
            result["error"] = "langchain_mcp_adapters未安装"
            return result
            
        # 首先检查各个服务
        print("📋 检查MCP服务状态:")
        for name, config in mcp_config.items():
            if config.get("transport") == "streamable_http":
                service_result = await check_mcp_service(name, config["url"])
                result["services_status"][name] = service_result
        
        # 尝试创建MCP客户端
        print(f"\n🔧 创建MCP客户端...")
        client = MultiServerMCPClient(mcp_config)
        result["client_created"] = True
        print("✅ MCP客户端创建成功")
        
        # 尝试获取工具
        print(f"🔧 获取MCP工具...")
        tools = await client.get_tools()
        result["tools_loaded"] = True
        result["tools_count"] = len(tools) if tools else 0
        print(f"✅ 成功获取 {result['tools_count']} 个工具")
        
        if tools:
            print("📋 可用工具:")
            for i, tool in enumerate(tools[:10]):  # 只显示前10个
                tool_name = getattr(tool, 'name', f'tool_{i}')
                print(f"   - {tool_name}")
            if len(tools) > 10:
                print(f"   ... 还有 {len(tools) - 10} 个工具")
                
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        print(f"❌ MCP客户端测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    return result

def get_default_mcp_config() -> Dict[str, Dict[str, Any]]:
    """获取默认MCP配置"""
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

async def main():
    """主诊断函数"""
    print("🔍 MCP服务诊断工具")
    print("=" * 60)
    
    # 环境检查
    print("🔧 环境检查:")
    print(f"   - langchain_mcp_adapters: {'✅ 可用' if MCP_AVAILABLE else '❌ 不可用'}")
    print(f"   - aiohttp: {'✅ 可用' if AIOHTTP_AVAILABLE else '❌ 不可用'}")
    
    # 环境变量
    print(f"\n🔍 环境变量:")
    mcp_ports = ["MATH_HTTP_PORT", "GETPRICE_HTTP_PORT", "SEARCH_HTTP_PORT", "TRADE_HTTP_PORT"]
    for port_var in mcp_ports:
        port = os.getenv(port_var, "未设置")
        print(f"   {port_var}: {port}")
    
    # 默认配置
    mcp_config = get_default_mcp_config()
    print(f"\n📋 MCP配置:")
    for name, config in mcp_config.items():
        print(f"   {name}: {config['url']}")
    
    print("\n" + "=" * 60)
    
    # 运行MCP客户端测试
    result = await test_mcp_client(mcp_config)
    
    # 总结报告
    print("\n" + "=" * 60)
    print("📊 诊断报告:")
    print(f"   MCP客户端创建: {'✅ 成功' if result['client_created'] else '❌ 失败'}")
    print(f"   工具加载: {'✅ 成功' if result['tools_loaded'] else '❌ 失败'}")
    print(f"   工具数量: {result['tools_count']}")
    
    if result['error']:
        print(f"   错误: {result['error']}")
    
    print(f"\n   服务状态:")
    for name, service_status in result['services_status'].items():
        status_icon = "✅" if service_status['status'] == 'healthy' else "❌"
        print(f"     {status_icon} {name}: {service_status['status']}")
        if service_status['error']:
            print(f"       错误: {service_status['error']}")
    
    # 建议
    print(f"\n💡 建议:")
    if not result['client_created']:
        print("   - 检查MCP服务是否已启动")
        print("   - 检查端口配置是否正确")
        print("   - 检查网络连接")
    elif not result['tools_loaded']:
        print("   - MCP客户端已创建但工具加载失败")
        print("   - 检查MCP服务端是否返回了工具列表")
    elif result['tools_count'] == 0:
        print("   - MCP客户端和工具加载成功，但未获取到任何工具")
        print("   - 检查MCP服务端配置")
    else:
        print("   - MCP服务运行正常")
        print("   - 如果Agent初始化仍有问题，请检查Agent代码逻辑")

if __name__ == "__main__":
    asyncio.run(main())