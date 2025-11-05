class DecisionMakerAgent:
    def __init__(self):
        pass

    def make_decision(self, analysis_result: dict) -> dict:
        # 根据分析结果进行判断
        decision = {}

        # 判断是否符合预定的决策标准
        if analysis_result["confidence"] > 0.7:
            decision["status"] = "Approved"
            decision["recommendation"] = analysis_result
        else:
            decision["status"] = "Rejected"
            decision["reason"] = "Low confidence"

        return decision
