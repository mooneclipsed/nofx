import requests

class StockDataFetcher:
    def __init__(self, api_url: str):
        self.api_url = api_url

    def fetch_data(self, stock_symbol: str) -> dict:
        # 通过mcp-baostock-server获取股票数据
        response = requests.get(f"{self.api_url}/get_stock_data", params={"symbol": stock_symbol})
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception("Failed to fetch stock data")
