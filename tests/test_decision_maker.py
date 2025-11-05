def test_make_decision():
    agent = DecisionMakerAgent()
    analysis_result = {"stock": "AAPL", "confidence": 0.85, "position": "50%"}
    decision = agent.make_decision(analysis_result)
    assert decision["status"] == "Approved"
    assert decision["recommendation"] == analysis_result
