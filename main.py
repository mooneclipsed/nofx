from agents.stock_analyzer_agent import StockAnalyzerAgent
from agents.decision_maker_agent import DecisionMakerAgent
from models.qwen3_235b_model import Qwen3Model
from mcp_server.mcp_baostock_server import MCPBaostockServer
from config.config import API_KEY, MCP_SERVER_URL

# 实例化模型与代理
model = Qwen3Model(API_KEY)
stock_analyzer = StockAnalyzerAgent(model)
decision_maker = DecisionMakerAgent()

# 获取股票数据
fetcher = MCPBaostockServer(MCP_SERVER_URL)
stock_data = fetcher.get_stock_data("AAPL")

# 分析数据
analysis_result = stock_analyzer.analyze(stock_data)

# 做决策
decision = decision_maker.make_decision(analysis_result)
print(decision)
