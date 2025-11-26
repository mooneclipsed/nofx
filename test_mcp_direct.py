#!/usr/bin/env python3
"""直接测试MCP工具调用"""

import asyncio
import os
from langchain_mcp_adapters.client import MultiServerMCPClient

async def test_direct():
    """直接测试MCP客户端"""
    print("🔧 直接测试MCP客户端...")
    
    mcp_config = {
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
    
    try:
        client = MultiServerMCPClient(mcp_config)
        print("✅ MCP客户端创建成功")
        
        tools = await client.get_tools()
        print(f"✅ 成功获取 {len(tools)} 个工具")
        
        # 测试调用一个简单的工具
        for tool in tools:
            if tool.name == "add":
                print(f"🧪 测试工具: {tool.name}")
                try:
                    result = await tool.ainvoke({"a": 2, "b": 3})
                    print(f"✅ 工具调用成功: {result}")
                except Exception as e:
                    print(f"❌ 工具调用失败: {e}")
                break
        
        # await client.close()  # 这个方法不存在
        print("✅ MCP客户端测试完成")
        
    except Exception as e:
        print(f"❌ MCP测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_direct())