def test_fetch_data():
    fetcher = StockDataFetcher(api_url="http://localhost:5000")
    data = fetcher.fetch_data("AAPL")
    assert "symbol" in data
    assert data["symbol"] == "AAPL"
