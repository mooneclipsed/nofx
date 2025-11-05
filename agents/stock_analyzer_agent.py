import openai
from models.qwen3_235b_model import Qwen3Model

class StockAnalyzerAgent:
    def __init__(self, model: Qwen3Model):
        self.model = model

    def analyze(self, stock_data: dict) -> dict:
        # 将原始股票数据直接交给模型
        analysis_result = self.model.analyze(stock_data)

        # 返回分析结果，包含推荐的股票和仓位分配
        return analysis_result
