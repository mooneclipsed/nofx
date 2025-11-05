def test_analyze():
    # 假设有模拟的测试数据和模型实例
    stock_data = {"symbol": "AAPL", "price": 150, "volume": 100000}
    model = None  # 模拟 Qwen3Model
    agent = StockAnalyzerAgent(model)
    result = agent.analyze(stock_data)
    assert result["stock"] == "AAPL"
    assert "confidence" in result
