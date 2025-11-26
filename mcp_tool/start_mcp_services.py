#!/usr/bin/env python3
"""
A股专用MCP服务启动脚本
启动所有A股交易所需的MCP服务
"""

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class AStockMCPServiceManager:
    def __init__(self):
        self.services = {}
        self.running = True

        # ============= A股专用端口配置 =============
        self.ports = {
            "math": int(os.getenv("MATH_HTTP_PORT", "8000")),
            "search": int(os.getenv("SEARCH_HTTP_PORT", "8004")),  # 修改为8004适配Agent
            "trade": int(os.getenv("TRADE_HTTP_PORT", "8002")),
            "price": int(os.getenv("GETPRICE_HTTP_PORT", "8003")),
        }

        # ============= A股服务配置 =============
        mcp_server_dir = Path(__file__).resolve().parent
        self.service_configs = {
            "math": {
                "script": str(mcp_server_dir / "tool_math.py"),
                "name": "数学计算服务",
                "port": self.ports["math"],
                "description": "通用数学计算工具"
            },
            "price": {
                "script": str(mcp_server_dir / "tool_get_price_local.py"),
                "name": "A股行情服务",
                "port": self.ports["price"],
                "description": "提供A股实时/历史行情数据"
            },
            "search": {
                "script": str(mcp_server_dir / "tool_alphavantage_news.py"),  # 修改为A股新闻源
                "name": "A股资讯服务",
                "port": self.ports["search"],
                "description": "搜索A股新闻、公告、研报等信息"
            },
            "trade": {
                "script": str(mcp_server_dir / "tool_trade.py"),  # 修改为A股交易工具
                "name": "A股交易服务",
                "port": self.ports["trade"],
                "description": "执行A股买卖交易（支持T+1、涨跌停限制）"
            },
        }

        # ============= 日志配置 =============
        self.log_dir = Path("../logs/mcp_astock")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        """处理中断信号"""
        print("\n🛑 收到停止信号，正在关闭所有MCP服务...")
        self.stop_all_services()
        sys.exit(0)

    def is_port_available(self, port: int) -> bool:
        """检查端口是否可用"""
        import socket

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("localhost", port))
            sock.close()
            return result != 0  # 连接失败说明端口可用
        except:
            return False

    def check_port_conflicts(self) -> bool:
        """检查端口冲突"""
        conflicts = []
        for service_id, config in self.service_configs.items():
            port = config["port"]
            if not self.is_port_available(port):
                conflicts.append((config["name"], port))

        if conflicts:
            print("⚠️  检测到端口冲突:")
            for name, port in conflicts:
                print(f"   - {name}: 端口 {port} 已被占用")

            response = input("\n❓ 是否自动查找可用端口? (y/n): ")
            if response.lower() == "y":
                for service_id, config in self.service_configs.items():
                    port = config["port"]
                    if not self.is_port_available(port):
                        # 查找下一个可用端口
                        new_port = port
                        while not self.is_port_available(new_port):
                            new_port += 1
                            if new_port > port + 100:  # 限制搜索范围
                                print(f"❌ 无法为{config['name']}找到可用端口")
                                return False
                        print(f"   ✅ {config['name']}: 端口从 {port} 变更为 {new_port}")
                        config["port"] = new_port
                        self.ports[service_id] = new_port
                return True
            else:
                print("\n💡 提示: 停止占用端口的程序或修改.env配置")
                return False
        return True

    def start_service(self, service_id: str, config: dict) -> bool:
        """启动单个服务"""
        script_path = config["script"]
        service_name = config["name"]
        port = config["port"]

        # 检查脚本是否存在
        if not Path(script_path).exists():
            print(f"❌ 脚本文件不存在: {script_path}")
            
            # A股服务脚本提示
            if service_id == "price":
                print(f"💡 提示: 确保tool_get_price_local.py能提供A股数据")
            elif service_id == "trade":
                print(f"💡 提示: 确保tool_trade.py已实现A股T+1规则")
            elif service_id == "search":
                print(f"💡 提示: 确保tool_alphavantage_news.py能获取A股资讯")
            return False

        try:
            # 启动服务进程
            log_file = self.log_dir / f"{service_id}.log"
            with open(log_file, "w", encoding="utf-8") as f:
                # 设置工作目录为项目根目录
                cwd = Path(__file__).resolve().parent
                process = subprocess.Popen(
                    [sys.executable, script_path],
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    cwd=str(cwd),
                    env=os.environ.copy()  # 传递环境变量
                )

            self.services[service_id] = {
                "process": process,
                "name": service_name,
                "port": port,
                "log_file": log_file,
                "config": config
            }

            print(f"✅ [{service_name}] 已启动 (PID: {process.pid}, 端口: {port})")
            return True

        except Exception as e:
            print(f"❌ 启动 {service_name} 失败: {e}")
            return False

    def check_service_health(self, service_id: str) -> bool:
        """检查服务健康状态"""
        if service_id not in self.services:
            return False

        service = self.services[service_id]
        process = service["process"]
        port = service["port"]

        # 检查进程是否仍在运行
        if process.poll() is not None:
            return False

        # 检查端口是否响应
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)  # A股服务可能需要更长时间启动
            result = sock.connect_ex(("localhost", port))
            sock.close()
            return result == 0
        except:
            return False

    def start_all_services(self):
        """启动所有MCP服务"""
        print("🚀 启动A股MCP服务...")
        print("=" * 60)

        # 端口冲突检查
        if not self.check_port_conflicts():
            print("\n❌ 因端口冲突无法启动服务")
            return
        print()

        # 显示配置信息
        print("📊 A股MCP服务配置:")
        for service_id, config in self.service_configs.items():
            print(f"  - {config['name']}: 端口 {config['port']}")
            print(f"    └─ {config['description']}")
        print()

        # 启动所有服务
        print("🔄 正在启动服务...")
        success_count = 0
        
        # 按顺序启动（先启动基础服务）
        startup_order = ["math", "price", "trade", "search"]
        for service_id in startup_order:
            if service_id in self.service_configs:
                config = self.service_configs[service_id]
                if self.start_service(service_id, config):
                    success_count += 1
                    time.sleep(1)  #  staggered start to avoid resource competition

        if success_count == 0:
            print("\n❌ 所有服务启动失败")
            self.stop_all_services()
            return

        # 等待服务完全启动（A股服务需要更长时间加载数据）
        print("\n⏳ 等待A股服务初始化...")
        time.sleep(5)

        # 检查服务状态
        print("\n🔍 检查服务状态...")
        healthy_count = self.check_all_services()

        if healthy_count > 0:
            print(f"\n🎉 {healthy_count}/{len(self.services)} 个A股MCP服务运行成功!")
            self.print_service_info()
            self.keep_alive()
        else:
            print("\n❌ 所有服务启动异常")
            self.stop_all_services()

    def check_all_services(self) -> int:
        """检查所有服务状态"""
        healthy_count = 0
        for service_id, service in self.services.items():
            if self.check_service_health(service_id):
                print(f"✅ [{service['name']}] 运行正常")
                healthy_count += 1
            else:
                print(f"❌ [{service['name']}] 启动失败")
                print(f"   └─ 请查看日志: {service['log_file']}")
        return healthy_count

    def print_service_info(self):
        """显示服务信息"""
        print("\n📋 A股MCP服务信息:")
        for service_id, service in self.services.items():
            print(f"  - {service['name']}: http://localhost:{service['port']} (PID: {service['process'].pid})")

        print(f"\n📁 日志文件位置: {self.log_dir.absolute()}")
        print("\n🛑 按 Ctrl+C 停止所有服务")

    def keep_alive(self):
        """保持服务运行"""
        try:
            while self.running:
                time.sleep(10)  # 每10秒检查一次

                # 检查服务状态
                stopped_services = []
                for service_id, service in self.services.items():
                    if service["process"].poll() is not None:
                        stopped_services.append(service["name"])

                if stopped_services:
                    print(f"\n⚠️  以下服务异常停止: {', '.join(stopped_services)}")
                    print(f"📋 活跃服务: {len(self.services) - len(stopped_services)}/{len(self.services)}")

                    # 如果全部停止则退出
                    if len(stopped_services) == len(self.services):
                        print("❌ 所有服务已停止，正在退出...")
                        self.running = False
                        break

        except KeyboardInterrupt:
            print("\n🛑 用户中断，正在关闭...")
        finally:
            self.stop_all_services()

    def stop_all_services(self):
        """停止所有服务"""
        print("\n🛑 正在停止所有MCP服务...")

        for service_id, service in self.services.items():
            try:
                service["process"].terminate()
                service["process"].wait(timeout=5)
                print(f"✅ [{service['name']}] 已停止")
            except subprocess.TimeoutExpired:
                service["process"].kill()
                print(f"🔨 [{service['name']}] 强制停止")
            except Exception as e:
                print(f"❌ 停止 {service['name']} 失败: {e}")

        print("✅ 所有MCP服务已停止")

    def status(self):
        """显示服务状态"""
        print("📊 A股MCP服务状态检查")
        print("=" * 40)

        for service_id, config in self.service_configs.items():
            if service_id in self.services:
                service = self.services[service_id]
                if self.check_service_health(service_id):
                    print(f"✅ [{config['name']}] 运行正常 (端口: {config['port']})")
                else:
                    print(f"❌ [{config['name']}] 异常 (端口: {config['port']})")
                    if "log_file" in service:
                        print(f"   └─ 日志: {service['log_file']}")
            else:
                print(f"❌ [{config['name']}] 未启动 (端口: {config['port']})")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="A股MCP服务管理器")
    parser.add_argument("action", nargs="?", choices=["start", "status", "stop"], default="start",
                        help="操作: start(启动), status(状态), stop(停止)")
    parser.add_argument("--ports", action="store_true", help="显示端口配置")
    
    args = parser.parse_args()
    
    if args.ports:
        # 显示端口配置
        manager = AStockMCPServiceManager()
        print("📊 A股MCP服务端口配置:")
        for service_id, config in manager.service_configs.items():
            print(f"  - {config['name']}: {config['port']}")
        return
    
    if args.action == "status":
        # 状态检查模式
        manager = AStockMCPServiceManager()
        manager.status()
    elif args.action == "stop":
        # 停止所有服务
        print("🛑 停止MCP服务...")
        # 实现停止逻辑（需要保存PID文件）
    else:
        # 启动模式
        manager = AStockMCPServiceManager()
        manager.start_all_services()


if __name__ == "__main__":
    main()