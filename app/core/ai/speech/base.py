# app/core/ai/speech/base.py
import datetime
from enum import Enum
from typing import Dict, Protocol, Tuple, Optional, List, runtime_checkable, AsyncGenerator, Any
from pydantic import BaseModel


class VoicePlatformType(str, Enum):
    """
    支持的语音合成平台类型。
    Matches C# enum implicitly used.
    """
    AZURE = "Azure"      # Microsoft Azure Speech Service
    OPENAI = "OpenAI"    # OpenAI TTS
    DOUBAO = "Doubao"    # Doubao (e.g., ByteDance Doubao TTS)
    # Add other platforms as needed


class VoiceQuality(str, Enum):
    """语音质量选项"""
    STANDARD = "Standard"
    PREMIUM = "Premium" # Or specific model names like 'Neural'


class SpeechOutputType(str, Enum):
    """语音合成输出类型"""
    MP3 = "mp3"
    WAV = "wav"
    OGG = "ogg"
    # etc.


@runtime_checkable
class ISpeechService(Protocol):
    """
    语音合成服务接口。
    """

    async def text_to_speech_async(
        self,
        ssml_text: Optional[str] = None,
        plain_text: Optional[str] = None,
        voice_name: Optional[str] = None, # Platform-specific voice identifier
        language_code: Optional[str] = None, # e.g., "en-US"
        output_format: str = SpeechOutputType.MP3, # e.g., "mp3", "wav"
        quality: VoiceQuality = VoiceQuality.STANDARD,
        speaking_rate: Optional[float] = None, # e.g., 1.0 for normal, 0.5 for half speed
        pitch: Optional[float] = None, # e.g., 0 for normal
        # Add other common parameters if needed
        **kwargs: Any # For provider-specific extra parameters
    ) -> Tuple[bool, Optional[bytes], datetime.timedelta]:
        """
        将文本转换为语音。至少需要 ssml_text 或 plain_text 之一。

        Args:
            ssml_text: 使用 SSML 标记的文本。
            plain_text: 纯文本内容。
            voice_name: 要使用的语音名称/标识符 (平台特定)。
            language_code: 语言代码 (例如 "en-US", "zh-CN")，如果 SSML 未指定。
            output_format: 请求的音频输出格式 (例如 "mp3", "wav")。
            quality: 请求的语音质量。
            speaking_rate: 语速调整。
            pitch: 音高调整。
            kwargs: 其他特定于提供商的参数。

        Returns:
            Tuple[bool, Optional[bytes], datetime.timedelta]:
            - success (bool): 操作是否成功。
            - audio_content (Optional[bytes]): 音频内容的字节流，如果成功。
            - audio_duration (datetime.timedelta): 音频时长，如果成功且可获取。
        """
        ...

    async def get_available_voices_async(
        self,
        language_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取指定语言可用的语音列表（可选）。

        Args:
            language_code: 可选的语言代码 (例如 "en-US") 来过滤语音。

        Returns:
            List[Dict[str, Any]]: 语音列表，每个语音是一个包含详细信息的字典
                                   (例如, 'name', 'gender', 'languageCode', 'provider_id').
        """
        ...

# You might also have DTOs for voice definitions if needed by the core service
# For example, if get_available_voices_async returns structured objects:

class CoreVoiceDefinitionDto(BaseModel):
    """核心语音定义DTO，用于ISpeechService.get_available_voices_async"""
    name: str # Platform-specific voice name/ID
    language_code: str # e.g., "en-US", "zh-CN"
    gender: Optional[str] = None # e.g., "Male", "Female", "Neutral"
    description: Optional[str] = None
    provider_specific_id: Optional[str] = None # Actual ID used by the TTS provider

    class Config:
        from_attributes = True # For Pydantic v2 orm_mode for v1
        alias_generator = lambda string: string[0].lower() + string[1:] if string else ''
        populate_by_name = True
