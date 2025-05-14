# app/modules/tools/podcast/config.py
from pydantic_settings import BaseSettings
from pydantic import Field
from app.core.ai.speech.base import VoicePlatformType # Assuming Doubao is added to this enum
from app.core.storage.base import StorageProviderType

class PodcastSettings(BaseSettings):
    """
    播客工具特定配置
    Corresponds to C# Tool_Podcast.json
    These settings will be nested under a 'podcast' key in the global Settings object.
    e.g., settings.podcast.voice_local_storage_path
    """
    voice_local_storage_path: str = Field("uploads/Podcast", description="语音本地存储路径")
    voice_cdn_storage_provider: StorageProviderType = Field(StorageProviderType.AZURE_BLOB, description="语音上传的CDN类型")
    voice_platform_type: VoicePlatformType = Field(VoicePlatformType.DOUBAO, description="语音平台类型 (e.g., Doubao, Azure)") # Make sure Doubao is in VoicePlatformType enum
    chat_ai_provider_type: str = Field("OpenAI", description="播客脚本生成使用的聊天AI提供商类型")

    class Config:
        env_prefix = "PODCAST_" # Example: PODCAST_VOICE_LOCAL_STORAGE_PATH
        # If these are to be loaded from a specific section of a larger config or .env,
        # the main settings loader would handle that.
        # For now, this defines the structure.