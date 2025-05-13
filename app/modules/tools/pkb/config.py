"""
个人知识库配置文件
"""
from pydantic import BaseModel
from typing import Optional


class PKBChatConfig(BaseModel):
    """聊天配置"""
    chat_ai_provider_type: str = "OpenAI"  # AI 提供者类型
    max_context_messages: int = 10  # 最大上下文消息数
    max_vector_search_results: int = 5  # 最大向量搜索结果数
    min_vector_score: float = 0.7  # 最小向量得分