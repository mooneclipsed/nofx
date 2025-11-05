def test_mcp_server():
    server = MCPBaostockServer(base_url="http://localhost:5000")
    data = server.get_stock_data("AAPL")
    assert "symbol" in data
    assert data["symbol"] == "AAPL"
