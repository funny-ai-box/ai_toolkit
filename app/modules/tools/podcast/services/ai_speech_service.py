"""
AI语音合成服务 - 负责文本转语音功能
"""
import os
import logging
from typing import List, Tuple, Optional, Dict, Any
from datetime import timedelta

from app.core.ai.speech.base import ISpeechService
from app.core.ai.speech.factory import get_speech_service
from app.core.storage.base import IStorageService, StorageProviderType
from app.core.exceptions import BusinessException
from app.modules.tools.podcast.repositories import PodcastVoiceRepository
from app.modules.tools.podcast.models import PodcastVoiceDefinition
from app.modules.tools.podcast.dtos import TtsVoiceDefinition
from app.modules.tools.podcast.constants import VoicePlatformType, VoiceGenderType
from app.modules.tools.podcast.config import podcast_settings

logger = logging.getLogger(__name__)


class AISpeechService:
    """AI语音合成服务"""
    
    def __init__(
        self,
        db,
        voice_repository: PodcastVoiceRepository,
        storage_service: Optional[IStorageService] = None
    ):
        """
        初始化AI语音服务
        
        Args:
            db: 数据库会话
            voice_repository: 语音仓储
            storage_service: 存储服务
        """
        self.db = db
        self.voice_repository = voice_repository
        self.storage_service = storage_service
        
        # 从配置中获取设置
        self.storage_provider = podcast_settings.voice_cdn_storage_provider
        self.voice_type = podcast_settings.voice_platform_type
        
        # 创建语音目录
        self.audio_local_dir = os.path.join(
            podcast_settings.voice_local_storage_path, "voice"
        )
        os.makedirs(self.audio_local_dir, exist_ok=True)
        
        # 初始化语音服务
        self.speech_service = get_speech_service(self.voice_type)
    
    async def text_to_speech_async(
        self, task_id: int, ssml_text: str, plain_text: str, voice_symbol: str
    ) -> Tuple[bool, str, float]:
        """
        文本转语音
        
        Args:
            task_id: 任务ID
            ssml_text: 文本内容，带SSML标记
            plain_text: 纯文本内容
            voice_symbol: 语音类型
        
        Returns:
            (成功标志, 音频URL, 音频时长)
        """
        # 创建临时文件用于保存语音
        encoding = "mp3"
        audio_filename = f"{task_id}_{voice_symbol}_{os.urandom(4).hex()}.{encoding}"
        audio_path = os.path.join(self.audio_local_dir, audio_filename)
        
        try:
            # 生成语音文件
            result = await self.speech_service.text_to_speech_async(
                ssml_text, plain_text, voice_symbol, audio_path
            )
            
            if not result.success:
                logger.error(f"语音生成失败: {result.error_message}")
                return False, "", 0
            
            # 上传到存储服务
            if self.storage_provider != StorageProviderType.LOCAL and self.storage_service:
                # 上传到CDN存储
                storage_key = f"podcast/voice/{audio_filename}"
                
                with open(audio_path, "rb") as f:
                    cdn_url = await self.storage_service.upload_async(
                        file_stream=f,
                        file_key=storage_key,
                        content_type="audio/mpeg"
                    )
                
                # 删除本地临时文件
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                
                return True, cdn_url, result.duration_seconds
            else:
                # 本地存储，返回相对路径
                relative_path = f"uploads/podcast/voice/{audio_filename}"
                return True, relative_path, result.duration_seconds
        
        except Exception as e:
            logger.exception(f"处理语音时出错: {e}")
            if os.path.exists(audio_path):
                os.remove(audio_path)
            return False, "", 0
    
    async def get_supported_voices_async(self) -> List[TtsVoiceDefinition]:
        """
        获取所有支持的语音角色
        
        Returns:
            语音角色列表
        """
        try:
            voices = await self.voice_repository.get_all_active_voices_async(self.voice_type)
            return self._map_to_voice_definition_dtos(voices)
        except Exception as e:
            logger.exception(f"获取支持的语音角色列表失败: {e}")
            raise BusinessException(f"获取语音角色列表失败: {str(e)}")
    
    async def get_voices_by_locale_async(self, locale: str) -> List[TtsVoiceDefinition]:
        """
        获取指定语言的语音角色
        
        Args:
            locale: 语言/地区
        
        Returns:
            语音角色列表
        """
        try:
            if not locale:
                raise BusinessException("语言/地区参数不能为空")
            
            voices = await self.voice_repository.get_active_voices_by_locale_async(
                self.voice_type, locale
            )
            return self._map_to_voice_definition_dtos(voices)
        except Exception as e:
            if not isinstance(e, BusinessException):
                logger.exception(f"获取指定语言的语音角色列表失败，语言: {locale}: {e}")
                raise BusinessException(f"获取语音角色列表失败: {str(e)}")
            raise
    
    def _map_to_voice_definition_dtos(
        self, voices: List[PodcastVoiceDefinition]
    ) -> List[TtsVoiceDefinition]:
        """
        将实体对象映射为DTO
        
        Args:
            voices: 语音角色实体列表
        
        Returns:
            语音角色DTO列表
        """
        return [
            TtsVoiceDefinition(
                id=v.id,
                voiceSymbol=v.voice_symbol,
                name=v.name,
                locale=v.locale,
                gender=v.gender,
                description=v.description
            )
            for v in voices
        ]