import requests

class MCPBaostockServer:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def get_stock_data(self, symbol: str) -> dict:
        # 获取指定股票的实时数据
        response = requests.get(f"{self.base_url}/get_stock_data", params={"symbol": symbol})
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception("Failed to fetch data from mcp-baostock-server")
