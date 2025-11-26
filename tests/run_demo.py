#!/usr/bin/env python3
"""
A股交易Agent一键测试Demo
完整流程：生成数据 → 启动服务 → 运行Agent → 输出报告
"""

import os
import sys
import asyncio
import shutil
import subprocess
import time
import json
from pathlib import Path
from datetime import datetime

# 确保项目根目录在sys.path中
project_root = Path(__file__).resolve().parent.parent
print(project_root)
sys.path.insert(0, str(project_root))

# 导入Agent类
from agent_service.agent_astock import BaseAgentAStock


class AStockDemoRunner:
    def __init__(self, signature: str = "demo_agent", model: str = "gpt-4o-mini"):
        self.signature = signature
        self.model = model
        self.base_dir = project_root
        self.data_dir = self.base_dir / "data" / "A_stock"
        self.log_dir = self.base_dir / "data" / "agent_data_astock"
        self.runtime_env = self.base_dir / "data" / ".runtime_env.json"

        print("=" * 80)
        print("🚀 A股交易Agent测试Demo")
        print("=" * 80)
        print(f"📅 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🤖 Agent: {signature} (模型: {model})")
        print(f"📂 项目目录: {self.base_dir}")

    def prepare_environment(self):
        """准备测试环境"""
        print("\n【步骤1】准备测试环境")

        # 清理旧数据（可选）
        if self.log_dir.exists():
            print(f"  🧹 清理旧日志: {self.log_dir}")
            shutil.rmtree(self.log_dir)

        # 确保数据目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 生成测试数据
        print("  📊 生成测试数据...")
        from generate_test_data import generate_test_data, verify_data

        test_file = generate_test_data("2025-10-09", days=7)
        if not verify_data(test_file):
            print("❌ 数据验证失败，请检查generate_test_data.py")
            sys.exit(1)

        print("✅ 环境准备完成")

    def setup_configuration(self):
        """设置运行时配置"""
        print("\n【步骤2】配置运行时参数")

        # 设置今天的日期（测试用10月15日）
        today_date = "2025-10-15"

        # 写入运行时配置
        from tools.a_stock_config import write_config_value

        write_config_value("TODAY_DATE", today_date)
        write_config_value("SIGNATURE", self.signature)
        write_config_value("LOG_PATH", str(self.log_dir.relative_to(self.base_dir)))

        print(f"  📅 交易日期: {today_date}")
        print(f"  📝 Agent签名: {self.signature}")
        print(f"  📁 日志路径: {self.log_dir}")
        print("✅ 配置完成")

    async def initialize_agent(self) -> BaseAgentAStock:
        """初始化Agent（异步版本）"""
        print("\n【步骤3】初始化交易Agent")

        # 使用上证50前5只股票测试
        test_symbols = [
            "600519.SH",  # 贵州茅台
            "601318.SH",  # 中国平安
            "600036.SH",  # 招商银行
            "601899.SH",  # 紫金矿业
            "600900.SH",  # 长江电力
        ]

        agent = BaseAgentAStock(
            signature=self.signature,
            basemodel=self.model,
            stock_symbols=test_symbols[:3],  # 先用3只减少API调用
            initial_cash=100000.0,
            init_date="2025-10-09",
        )

        # 注册Agent（创建初始持仓）
        agent.register_agent()
        
        # 初始化Agent（连接MCP服务和AI模型）
        await agent.initialize()

        print(f"  🤖 Agent: {agent}")
        print(f"  💰 初始资金: ¥{agent.initial_cash:,.2f}")
        print(f"  📊 交易标的: {len(agent.stock_symbols)}只股票")
        print(f"    └─ {', '.join(agent.stock_symbols)}")
        print("✅ Agent初始化完成")

        return agent

    async def run_trading_session(self, agent: BaseAgentAStock):
        """运行单个交易日"""
        print("\n【步骤4】运行交易会话")

        # 运行10月15日的交易
        target_date = "2025-10-15"

        try:
            await agent.run_with_retry(target_date)
            print(f"✅ 交易会话完成: {target_date}")

        except Exception as e:
            print(f"❌ 交易会话失败: {e}")
            import traceback

            traceback.print_exc()
            return False

        return True

    def generate_report(self):
        """生成交易报告"""
        print("\n【步骤5】生成交易报告")

        # 读取持仓历史
        pos_file = self.log_dir / self.signature / "position" / "position.jsonl"

        if not pos_file.exists():
            print("❌ 未找到持仓记录文件")
            return

        print(f"  📄 读取持仓记录: {pos_file}")

        records = []
        with open(pos_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))

        if not records:
            print("⚠️  无交易记录")
            return

        # 显示关键信息
        print(f"\n{'='*80}")
        print("📈 交易报告")
        print(f"{'='*80}")

        initial = records[0]
        latest = records[-1]

        initial_cash = initial["positions"]["CASH"]
        final_cash = latest["positions"]["CASH"]
        total_return = (final_cash - initial_cash) / initial_cash

        print(f"起始日期: {initial['date']}")
        print(f"结束日期: {latest['date']}")
        print(f"交易次数: {len(records) - 1}")  # 扣除初始记录
        print(f"起始现金: ¥{initial_cash:,.2f}")
        print(f"期末现金: ¥{final_cash:,.2f}")
        print(f"总收益率: {total_return:.2%}")

        # 显示持仓变化
        print(f"\n持仓变化:")
        for symbol in ["600519.SH", "601318.SH", "600036.SH"]:
            initial_qty = initial["positions"].get(symbol, 0)
            final_qty = latest["positions"].get(symbol, 0)
            if initial_qty != final_qty:
                print(f"  {symbol}: {initial_qty} → {final_qty} 股")
            elif final_qty > 0:
                print(f"  {symbol}: {final_qty} 股 (持仓未变)")

        # 显示最后持仓详情
        print(f"\n最终持仓详情:")
        for symbol, qty in latest["positions"].items():
            if symbol == "CASH":
                print(f"  💰 {symbol}: ¥{qty:,.2f}")
            elif qty > 0:
                print(f"  📊 {symbol}: {qty} 股")

        print(f"\n{'='*80}")

    async def run(self):
        """主运行流程"""
        try:
            # 步骤1: 准备环境
            self.prepare_environment()

            # 步骤2: 配置参数
            self.setup_configuration()

            # 步骤3: 初始化Agent
            agent = await self.initialize_agent()

            # 步骤4: 运行交易
            success = await self.run_trading_session(agent)

            if success:
                # 步骤5: 生成报告
                self.generate_report()

                print("\n🎉 Demo运行成功！")
                print(f"\n📂 查看详细日志: {self.log_dir / self.signature}")
            else:
                print("\n❌ Demo运行失败，请检查错误信息")
                sys.exit(1)

        except Exception as e:
            print(f"\n💥 Demo运行异常: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="A股交易Agent测试Demo")
    parser.add_argument("--model", default="qwen-turbo", help="AI模型名称")
    parser.add_argument("--signature", default="demo_agent", help="Agent标识")

    args = parser.parse_args()
    envPath=project_root / ".env"
    # 检查.env文件
    if not Path(envPath).exists():
        print("❌ 未找到.env配置文件，请从下面的模板创建：")
        print("-" * 50)
        print(
            """OPENAI_API_KEY=sk-your-key
MATH_HTTP_PORT=8000
TRADE_HTTP_PORT=8002
GETPRICE_HTTP_PORT=8003
SEARCH_HTTP_PORT=8004"""
        )
        print("-" * 50)
        sys.exit(1)

    # 检查API密钥
    from dotenv import load_dotenv

    load_dotenv(envPath)

    if not os.getenv("OPENAI_API_KEY"):
        print("❌ 请先在.env中设置OPENAI_API_KEY")
        sys.exit(1)

    # 运行Demo
    demo = AStockDemoRunner(signature=args.signature, model=args.model)
    asyncio.run(demo.run())


if __name__ == "__main__":
    main()
