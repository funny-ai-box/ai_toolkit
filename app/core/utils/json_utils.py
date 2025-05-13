# app/core/utils/json_utils.py
import json
from typing import Any
from datetime import datetime

def _datetime_serializer(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def safe_serialize(data: Any) -> str:
    """将对象安全地序列化为 JSON 字符串，处理 datetime 等类型"""
    try:
        # 使用 default 参数处理无法直接序列化的类型
        return json.dumps(data, default=_datetime_serializer)
    except TypeError as e:
        print(f"序列化错误: {e}") # Log the error
        # 根据需要返回默认值或重新抛出异常
        return "{}" # 返回一个空的 JSON 对象字符串作为备用

def safe_deserialize(json_str: str) -> Any:
    """将 JSON 字符串安全地反序列化为 Python 对象"""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"JSON 反序列化错误: {e} for input: {json_str[:100]}...") # Log the error
        # 根据需要返回默认值或重新抛出异常
        return None
    except Exception as e: # Catch other potential errors during deserialization
        print(f"反序列化时发生未知错误: {e}")
        return None