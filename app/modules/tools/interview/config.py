"""
面试模拟器模块的配置

此模块定义了面试模拟器功能的配置项，从设置中加载并提供给模块使用。
"""
from typing import Dict, Any

from app.core.config.settings import Settings


class InterviewConfig:
    """面试模拟器配置类"""
    
    def __init__(self, settings: Settings):
        """
        初始化面试模拟器配置
        
        Args:
            settings: 应用配置实例
        """
        self.chat_ai_provider_type = getattr(settings, "INTERVIEW_CHAT_AI_PROVIDER_TYPE", "OpenAI")
        
        # 可添加其他面试模拟器特定配置项
        
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        
        Returns:
            配置字典
        """
        return {
            "chat_ai_provider_type": self.chat_ai_provider_type
        }


def get_interview_config(settings: Settings) -> InterviewConfig:
    """
    获取面试模拟器配置
    
    Args:
        settings: 应用配置实例
        
    Returns:
        面试模拟器配置实例
    """
    return InterviewConfig(settings)