"""
语音服务工厂
"""
import logging
from typing import Optional

from app.core.config.settings import settings
from app.core.ai.speech.speech_service import AISpeechService, DummySpeechService

logger = logging.getLogger(__name__)

def get_speech_service() -> Optional[AISpeechService]:
    """
    获取配置的语音服务实例
    
    Returns:
        配置的语音服务实例，如果未配置则返回测试用的DummySpeechService
    """
    speech_service_type = settings.SPEECH_SERVICE_TYPE
    
    if speech_service_type == "Dummy" or not speech_service_type:
        logger.info("使用 DummySpeechService 作为语音服务")
        return DummySpeechService()
    
    # 这里可以添加其他语音服务的实现
    # elif speech_service_type == "Azure":
    #     return AzureSpeechService(
    #         subscription_key=settings.AZURE_SPEECH_KEY,
    #         region=settings.AZURE_SPEECH_REGION
    #     )
    # elif speech_service_type == "Google":
    #     return GoogleSpeechService(...)
    
    logger.warning(f"未知的语音服务类型: {speech_service_type}，使用默认的DummySpeechService")
    return DummySpeechService()