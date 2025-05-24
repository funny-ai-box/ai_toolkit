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


# 初始化配置 - 修复方案
def _get_podcast_config():
    """获取播客配置"""
    try:
        # 方案1: 如果settings有Podcast属性
        if hasattr(settings, 'Podcast'):
            podcast_config = settings.Podcast
            if isinstance(podcast_config, dict):
                return podcast_config
            else:
                # 如果Podcast是对象，转换为字典
                return podcast_config.__dict__ if hasattr(podcast_config, '__dict__') else {}
        
        # 方案2: 如果settings是字典形式的配置
        elif hasattr(settings, '__dict__'):
            return getattr(settings, 'Podcast', {})
        
        # 方案3: 使用默认配置
        else:
            return {}
            
    except Exception:
        # 发生任何错误都使用默认配置
        return {}


# 初始化配置
podcast_settings = PodcastSettings(**_get_podcast_config())