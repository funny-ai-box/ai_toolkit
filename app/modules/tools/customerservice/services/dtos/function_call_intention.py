"""
函数调用意图枚举
"""
from enum import Enum

class FunctionCallIntention(str, Enum):
    """Function调用的意图"""
    QUERY_PRODUCT = "QUERY_PRODUCT"      # 查询商品
    KNOWLEDGE_BASE = "KNOWLEDGE_BASE"    # 知识库检索