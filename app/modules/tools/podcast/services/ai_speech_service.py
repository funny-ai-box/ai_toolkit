# app/modules/tools/podcast/services/ai_speech_service.py
import logging
import os
import uuid
import datetime
from typing import List, Tuple, Optional
import httpx

from app.core.config.settings import Settings
from app.core.exceptions import BusinessException
from app.core.storage.base import StorageProviderType, IStorageService
# Import the factory FUNCTION directly
from app.core.storage.factory import get_storage_service
from app.core.ai.speech.base import VoicePlatformType, ISpeechService as CoreAISpeechServiceInterface
# Import the factory FUNCTION for speech service
from app.core.ai.speech.factory import get_speech_service as get_core_speech_service_instance # Renamed to avoid clash

from app.modules.tools.podcast.repositories import PodcastVoiceRepository
from app.modules.tools.podcast.dtos import TtsVoiceDefinitionDto
from app.modules.tools.podcast.models import PodcastVoiceDefinition as PodcastVoiceDefinitionModel

logger = logging.getLogger(__name__)

class AISpeechService: # This is the podcast-specific wrapper/service
    """AI语音服务 (播客模块特定封装)"""

    def __init__(
        self,
        settings: Settings,
        # http_client is not directly used by this service now, but might be by factories if they take it
        voice_repository: PodcastVoiceRepository,
        # No factories are injected here anymore, we use the factory functions directly
    ):
        self.global_settings = settings
        self.podcast_settings = settings.podcast
        self.voice_repository = voice_repository

        self._voice_type: VoicePlatformType = self.podcast_settings.voice_platform_type
        self._storage_provider_type: StorageProviderType = self.podcast_settings.voice_cdn_storage_provider
        
        base_upload_dir = os.path.join(self.global_settings.static_files_path, "uploads")
        self._audio_local_dir_base = os.path.join(base_upload_dir, "Podcast", "voice")
        
        self._physical_audio_local_dir = self._audio_local_dir_base
        if not os.path.exists(self._physical_audio_local_dir):
            os.makedirs(self._physical_audio_local_dir, exist_ok=True)

    def _map_model_to_dto(self, voice_model: PodcastVoiceDefinitionModel) -> TtsVoiceDefinitionDto:
         return TtsVoiceDefinitionDto.model_validate(voice_model)

    def _map_models_to_dtos(self, voice_models: List[PodcastVoiceDefinitionModel]) -> List[TtsVoiceDefinitionDto]:
         return [self._map_model_to_dto(vm) for vm in voice_models]

    async def text_to_speech_and_upload_async(
        self, 
        task_id: int,
        ssml_text: str, 
        plain_text: str,
        voice_symbol: str
    ) -> Tuple[bool, Optional[str], datetime.timedelta]:
        encoding = "mp3"
        audio_file_name = f"{uuid.uuid4()}.{encoding}"
        local_audio_file_path = os.path.join(self._physical_audio_local_dir, audio_file_name)

        try:
            # Get speech provider instance using the factory function
            # Your core speech factory returns AISpeechService or DummySpeechService.
            # We need to ensure it's compatible with CoreAISpeechServiceInterface
            speech_provider_instance = get_core_speech_service_instance(
                provider_type_str=self._voice_type.value # Pass the string value of the enum
            )
            if not speech_provider_instance:
                raise BusinessException(f"无法创建语音服务实例对于类型: {self._voice_type.value}")

            # The core ISpeechService has text_to_speech_async
            # Your DummySpeechService has synthesize_speech_async which writes to a file.
            # We need to align these. Let's assume your core `get_speech_service` returns an object
            # that implements the `CoreAISpeechServiceInterface.text_to_speech_async` method,
            # which returns (bool, Optional[bytes], datetime.timedelta).

            # If your `get_core_speech_service_instance` returns the AISpeechService from `app.core.ai.speech.speech_service.py`
            # then that service has `synthesize_speech_async` which writes to a file.
            # This is a mismatch with the `ISpeechService` protocol defined in `app/core/ai/speech/base.py`.

            # --- OPTION 1: Adapt to existing DummySpeechService behavior (writes file directly) ---
            # This requires changing how we handle audio bytes.
            # For now, let's assume DummySpeechService is temporary and a real service
            # would align with CoreAISpeechServiceInterface.
            # If DummySpeechService is the only one for now:
            if isinstance(speech_provider_instance, CoreAISpeechServiceInterface): # Check if it's the protocol
                 tts_success, audio_bytes, audio_duration = await speech_provider_instance.text_to_speech_async(
                    ssml_text=ssml_text,
                    plain_text=plain_text,
                    voice_name=voice_symbol,
                    output_format=encoding
                )
                 if not tts_success or not audio_bytes:
                    logger.error(f"TTS generation failed for task {task_id}, voice {voice_symbol}.")
                    return False, None, datetime.timedelta(0)
                 with open(local_audio_file_path, "wb") as f:
                    f.write(audio_bytes)

            elif hasattr(speech_provider_instance, 'synthesize_speech_async'): # Check for DummySpeechService like method
                # This is the method from your app.core.ai.speech.speech_service.py's DummySpeechService
                # It writes to output_path directly and returns (bool, timedelta)
                tts_success, audio_duration = await speech_provider_instance.synthesize_speech_async(
                    text=plain_text, # Dummy takes plain_text
                    output_path=local_audio_file_path,
                    voice_name=voice_symbol
                )
                if not tts_success:
                    logger.error(f"TTS generation (using synthesize_speech_async) failed for task {task_id}, voice {voice_symbol}.")
                    return False, None, datetime.timedelta(0)
            else:
                raise TypeError("Speech provider does not have a recognized text-to-speech method.")


            # --- Contine with upload logic ---
            audio_url: Optional[str] = None
            cdn_file_key = os.path.join("Podcast", "voice", audio_file_name)

            if self._storage_provider_type not in [StorageProviderType.LOCAL, StorageProviderType.NONE]:
                # Get storage service instance using the factory function
                storage_service: Optional[IStorageService] = get_storage_service(
                    provider_type_str=self._storage_provider_type.value
                )
                if not storage_service:
                    raise BusinessException(f"无法创建存储服务实例对于类型: {self._storage_provider_type.value}")
                
                content_type = f"audio/{encoding}"
                with open(local_audio_file_path, "rb") as f_stream:
                    audio_url = await storage_service.upload_async(
                        file_stream=f_stream, 
                        file_key=cdn_file_key, 
                        content_type=content_type
                    )
            elif self._storage_provider_type == StorageProviderType.LOCAL:
                path_for_url = os.path.relpath(local_audio_file_path, self.global_settings.static_files_path)
                audio_url = f"{self.global_settings.api_base_url.strip('/')}/{self.global_settings.static_url_prefix.strip('/')}/{path_for_url}".replace("\\", "/")
            else:
                logger.warning(f"Storage provider is NONE for task {task_id}. Audio not uploaded to CDN.")

            if not audio_url:
                logger.error(f"Audio URL generation failed for task {task_id}.")
                return False, None, audio_duration # audio_duration might be set if TTS succeeded
            
            if self._storage_provider_type not in [StorageProviderType.LOCAL, StorageProviderType.NONE] and os.path.exists(local_audio_file_path):
                 try:
                     os.remove(local_audio_file_path)
                 except OSError as e:
                     logger.error(f"Failed to remove temporary local audio file {local_audio_file_path}: {e}")

            return True, audio_url, audio_duration

        except Exception as e:
            logger.error(f"Error in TextToSpeechAsync for task {task_id}, voice {voice_symbol}: {e}", exc_info=True)
            if os.path.exists(local_audio_file_path):
                try:
                    os.remove(local_audio_file_path)
                except OSError as e_rem:
                    logger.error(f"Failed to remove temporary local audio file on error {local_audio_file_path}: {e_rem}")
            return False, None, datetime.timedelta(0)

    async def get_supported_voices_async(self) -> List[TtsVoiceDefinitionDto]:
        try:
            # _voice_type is VoicePlatformType from app.core.ai.speech.base
            voices_models = await self.voice_repository.get_all_active_voices_async(self._voice_type)
            return self._map_models_to_dtos(voices_models)
        except Exception as e:
            logger.error(f"获取支持的语音角色列表失败: {e}", exc_info=True)
            raise BusinessException(f"获取语音角色列表失败: {str(e)}")

    async def get_voices_by_locale_async(self, locale: str) -> List[TtsVoiceDefinitionDto]:
        if not locale:
            raise BusinessException("语言/地区参数不能为空")
        try:
            voices_models = await self.voice_repository.get_active_voices_by_locale_async(self._voice_type, locale)
            return self._map_models_to_dtos(voices_models)
        except BusinessException:
            raise
        except Exception as e:
            logger.error(f"获取指定语言 {locale} 的语音角色列表失败: {e}", exc_info=True)
            raise BusinessException(f"获取语音角色列表失败: {str(e)}")