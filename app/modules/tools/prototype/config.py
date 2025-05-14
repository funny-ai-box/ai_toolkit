# app/modules/tools/prototype/config.py
from pydantic import BaseModel
from app.core.ai.chat.factory import ChatAIProviderType

from app.core.config.settings import settings

from app.core.storage.base import StorageProviderType


class PrototypeConfig(BaseModel):
    """原型工具配置"""
    image_storage_provider: StorageProviderType = StorageProviderType.AZURE_BLOB
    chat_ai_provider_type: ChatAIProviderType = ChatAIProviderType.GEMINI


# 初始化配置
prototype_config = PrototypeConfig(
    image_storage_provider=getattr(
        StorageProviderType, 
        settings.PROTOTYPE_IMAGE_STORAGE_PROVIDER.upper(), 
        StorageProviderType.AZURE_BLOB
    ),
    chat_ai_provider_type=getattr(
        ChatAIProviderType,
        settings.PROTOTYPE_CHAT_AI_PROVIDER_TYPE.upper(),
        ChatAIProviderType.GEMINI
    )
)