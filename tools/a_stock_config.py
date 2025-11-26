"""
A股配置管理模块
提供跨进程配置持久化和AI对话解析功能
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

def _resolve_runtime_env_path() -> str:
    """
    解析运行时配置路径
    
    策略：
    1. 从环境变量 RUNTIME_ENV_PATH 读取
    2. 未设置则使用默认值 "data/.runtime_env.json"
    3. 相对路径则基于项目根目录解析
    4. 自动创建目录
    """
    path = os.environ.get("RUNTIME_ENV_PATH")
    
    if not path:
        # 回退到默认值
        path = "data/.runtime_env.json"
    
    # 如果是相对路径，从项目根目录解析
    if not os.path.isabs(path):
        base_dir = Path(__file__).resolve().parents[1]  # 项目根目录
        path = str(base_dir / path)
    
    # 确保目录存在
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    
    return path

def _load_runtime_env() -> dict:
    """加载运行时配置"""
    path = _resolve_runtime_env_path()
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    return {}

def get_config_value(key: str, default=None):
    """
    获取配置值（优先级：运行时文件 > 环境变量）
    
    Args:
        key: 配置键名
        default: 默认值
    
    Returns:
        配置值或默认值
    """
    runtime_env = _load_runtime_env()
    if key in runtime_env:
        return runtime_env[key]
    return os.getenv(key, default)

def write_config_value(key: str, value: Any):
    """
    写入配置值到运行时文件
    
    Args:
        key: 配置键名
        value: 配置值（必须是可JSON序列化的）
    
    Note:
        如果 RUNTIME_ENV_PATH 未设置或无法写入，将打印警告
    """
    path = _resolve_runtime_env_path()
    
    if path is None:
        print(f"⚠️ 警告: RUNTIME_ENV_PATH未设置，配置'{key}'无法持久化")
        return
    
    runtime_env = _load_runtime_env()
    runtime_env[key] = value
    
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(runtime_env, f, ensure_ascii=False, indent=4)
            f.flush()  # 确保立即写入磁盘
    except Exception as e:
        print(f"❌ 写入配置到 {path} 失败: {e}")

def extract_conversation(conversation: dict, output_type: str):
    """
    从对话中提取AI回复
    
    Args:
        conversation: 对话字典（包含'messages'列表）
        output_type: "final"提取最终回复，"all"提取所有消息
    
    Returns:
        str: 最终回复内容（output_type='final'）
        list: 所有消息列表（output_type='all'）
        None: 未找到有效内容
    """
    def get_field(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def get_nested(obj, path, default=None):
        current = obj
        for key in path:
            current = get_field(current, key, None)
            if current is None:
                return default
        return current

    messages = get_field(conversation, "messages", []) or []

    if output_type == "all":
        return messages

    if output_type == "final":
        # 优先返回finish_reason=stop的最终消息
        for msg in reversed(messages):
            finish_reason = get_nested(msg, ["response_metadata", "finish_reason"])
            content = get_field(msg, "content")
            if finish_reason == "stop" and isinstance(content, str) and content.strip():
                return content

        # 回退：返回最后一条非工具调用的AI消息
        for msg in reversed(messages):
            content = get_field(msg, "content")
            additional_kwargs = get_field(msg, "additional_kwargs", {}) or {}
            tool_calls = additional_kwargs.get("tool_calls") if isinstance(additional_kwargs, dict) else None
            tool_call_id = get_field(msg, "tool_call_id")
            tool_name = get_field(msg, "name")
            
            is_tool_invoke = isinstance(tool_calls, list)
            is_tool_message = tool_call_id is not None or isinstance(tool_name, str)

            if not is_tool_invoke and not is_tool_message and isinstance(content, str) and content.strip():
                return content

        return None

    raise ValueError("output_type必须是'final'或'all'")

def extract_tool_messages(conversation: dict):
    """
    提取工具消息列表
    
    工具消息特征：
    - 包含 tool_call_id
    - 或包含 name 且无 finish_reason
    
    Args:
        conversation: 对话字典
    
    Returns:
        工具消息对象列表
    """
    def get_field(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    messages = get_field(conversation, "messages", []) or []
    tool_messages = []

    for msg in messages:
        tool_call_id = get_field(msg, "tool_call_id")
        name = get_field(msg, "name")
        finish_reason = get_field(msg, "response_metadata", {}).get("finish_reason") if isinstance(get_field(msg, "response_metadata", {}), dict) else None
        
        if tool_call_id or (isinstance(name, str) and not finish_reason):
            tool_messages.append(msg)

    return tool_messages

def extract_first_tool_message_content(conversation: dict):
    """
    提取第一条工具消息的内容
    
    Args:
        conversation: 对话字典
    
    Returns:
        str: 工具消息内容
        None: 无工具消息
    """
    msgs = extract_tool_messages(conversation)
    if not msgs:
        return None
    
    first = msgs[0]
    return first.get("content") if isinstance(first, dict) else getattr(first, "content", None)