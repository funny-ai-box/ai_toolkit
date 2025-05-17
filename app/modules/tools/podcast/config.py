"""
播客模块配置
"""
from typing import Optional, Literal
from pydantic import BaseModel, Field

from app.core.config.settings import settings
from app.core.storage.base import StorageProviderType


class PodcastSettings(BaseModel):
    """
    播客模块设置
    """
    # 语音本地存储路径
    voice_local_storage_path: str = Field(
        default="uploads/podcast",
        alias="VoiceLocalStoragePath"
    )
    
    # 语音上传的CDN类型
    voice_cdn_storage_provider: StorageProviderType = Field(
        default=StorageProviderType.LOCAL,
        alias="VoiceCdnStorageProvider"
    )
    
    # 语音平台类型
    voice_platform_type: str = Field(
        default="Doubao",
        alias="VoicePlatformType"
    )
    
    # 聊天AI提供者类型
    chat_ai_provider_type: str = Field(
        default="OpenAI",
        alias="ChatAIProviderType"
    )


# 初始化配置
podcast_settings = PodcastSettings(**settings.get("Podcast", {}))