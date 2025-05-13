# app/core/ai/chat/factory.py
import logging
import httpx
from functools import lru_cache # 用于缓存服务实例
from enum import Enum # 导入 Enum
from typing import Optional, TYPE_CHECKING # 导入 Optional 和 TYPE_CHECKING

# 导入项目配置
from app.core.config.settings import settings
# 导入 AI 服务协议 (接口)
from app.core.ai.chat.base import IChatAIService
# 导入具体的 OpenAI 服务实现
from app.core.ai.chat.openai_service import OpenAIService

# --- 导入 FastAPI Depends 和获取共享客户端的依赖 ---
from fastapi import Depends
from app.api.dependencies import get_http_client_from_state
# --- 未来其他服务实现的导入 ---
# from app.core.ai.chat.claude_service import ClaudeAIService
# from app.core.ai.chat.gemini_service import GeminiAIService
# ----------------------------

# 类型检查时导入协议 (避免运行时问题)
if TYPE_CHECKING:
    pass # IChatAIService 已经在上面导入了

logger = logging.getLogger(__name__)

# 定义支持的 AI 提供者类型枚举
class ChatAIProviderType(str, Enum):
    """支持的 AI 聊天服务提供者类型"""
    OPENAI = "OpenAI"
    CLAUDE = "Claude" # 占位符，尚未实现
    GEMINI = "Gemini" # 占位符，尚未实现

# 使用 lru_cache 缓存服务实例，避免重复创建客户端
# maxsize=None 表示不限制缓存大小
# 注意：如果服务的配置（如 API Key）可能在运行时改变且需要立即生效，则不能使用缓存
@lru_cache(maxsize=None)
def get_chat_ai_service(
    provider_type_str: Optional[str] = None,
    shared_http_client: Optional[httpx.AsyncClient] = None
) -> IChatAIService:
    """
    获取指定类型的 AI 聊天服务实例。
    使用 LRU 缓存来复用服务实例。

    Args:
        provider_type_str: AI 提供者的名称 (例如 "OpenAI", "Claude", "Gemini")。
                           如果为 None，则尝试使用 OpenAI 作为默认。
                           (未来可以从配置 settings.DEFAULT_CHAT_AI_PROVIDER 读取)
        shared_http_client: (可选) 预配置的共享 httpx 客户端。

    Returns:
        实现了 IChatAIService 协议的服务实例。

    Raises:
        ValueError: 如果提供者类型不支持或相关配置无效。
        RuntimeError: 如果服务初始化失败。
    """
    if provider_type_str is None:
        # 当前默认使用 OpenAI
        provider_type_str = ChatAIProviderType.OPENAI.value
        logger.debug(f"未指定 AI 提供者，使用默认值: {provider_type_str}")

    # 尝试将字符串转换为枚举成员
    try:
        provider_type = ChatAIProviderType(provider_type_str)
    except ValueError:
        # 如果传入的字符串不是有效的枚举成员值
        valid_providers = [p.value for p in ChatAIProviderType]
        logger.error(f"不支持的 ChatAI 提供程序: '{provider_type_str}'. 支持的类型: {valid_providers}")
        raise ValueError(f"不支持的 ChatAI 提供程序: '{provider_type_str}'. 支持的类型: {valid_providers}")

    logger.info(f"正在获取/创建 '{provider_type.value}' 聊天服务实例...")

    # 根据枚举类型选择并创建服务实例
    if provider_type == ChatAIProviderType.OPENAI:
        # 检查 OpenAI Key 是否配置
        if not settings.OPENAI_API_KEY:
            logger.error("OpenAI API Key 未在配置中设置，无法创建 OpenAI 服务。")
            raise ValueError("OpenAI API Key 未配置，无法创建 OpenAI 服务。")
        try:
            # 返回缓存的或新创建的 OpenAI 服务实例
            # OpenAIService 的 __init__ 会处理客户端创建和异常
            return OpenAIService(http_client=shared_http_client)
        except Exception as e:
             logger.error(f"创建 OpenAI 服务实例时出错: {e}", exc_info=True)
             raise RuntimeError(f"创建 OpenAI 服务实例失败: {e}") from e

    # --- 未来其他提供者的实现 ---
    elif provider_type == ChatAIProviderType.CLAUDE:
        logger.error("Claude 服务尚未实现。")
        raise NotImplementedError("Claude 服务尚未实现。")
        # if not settings.CLAUDE_API_KEY: # 假设有此配置
        #     raise ValueError("Claude API Key 未配置。")
        # return ClaudeAIService() # 需要实现

    elif provider_type == ChatAIProviderType.GEMINI:
        logger.error("Gemini 服务尚未实现。")
        raise NotImplementedError("Gemini 服务尚未实现。")
        # if not settings.GEMINI_API_KEY: # 假设有此配置
        #     raise ValueError("Gemini API Key 未配置。")
        # return GeminiAIService() # 需要实现

    else:
        # 这部分理论上不会执行，因为枚举已经限制了类型
        valid_providers = [p.value for p in ChatAIProviderType]
        logger.error(f"内部错误：无法处理的 AI 提供者类型 '{provider_type.value}'. 支持的类型: {valid_providers}")
        raise ValueError(f"内部错误：无法处理的 AI 提供者类型 {provider_type.value}")

# --- 提供一个 FastAPI 依赖项，方便在 API 路由中注入 ---
def chat_ai_service_dependency(
    provider: Optional[ChatAIProviderType] = None, # 可以通过查询参数等指定 provider
    # --- 注入共享 HTTP 客户端 ---
    http_client: Optional[httpx.AsyncClient] = Depends(get_http_client_from_state) # <--- 从 state 获取
) -> IChatAIService:
    """
    FastAPI 依赖项，用于注入 AI 聊天服务实例。

    Args:
        provider (Optional[ChatAIProviderType]): (可选) 指定要使用的 AI 提供者。
                                                如果为 None，则使用默认提供者。
    """
    provider_str = provider.value if provider else None
    return get_chat_ai_service(provider_str, shared_http_client=http_client)