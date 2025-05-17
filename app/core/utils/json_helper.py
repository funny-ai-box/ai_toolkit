"""
JSON 帮助工具类 - 提供安全的 JSON 解析函数
"""
import json
import logging
from typing import Any, Dict, List, Optional, Union, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')

def safe_parse_json(json_str: str) -> Union[Dict[str, Any], List[Any], None]:
    """
    安全地解析 JSON 字符串
    
    Args:
        json_str: JSON 字符串
    
    Returns:
        解析后的 JSON 对象，失败时返回 None
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning(f"JSON 解析失败: {e}")
        return None