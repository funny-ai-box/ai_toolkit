# app/modules/tools/prototype/config.py
"""
原型设计模块的配置
"""
from pydantic import BaseModel, Field
from app.modules.tools.prototype.enums import ChatAIProviderType
from app.core.config.settings import settings

class PrototypeConfig(BaseModel):
    """原型设计配置类"""
    # AI模型提供者类型
    chat_ai_provider_type: ChatAIProviderType = Field(
        default=ChatAIProviderType.OPENAI,
        description="聊天AI服务提供者类型"
    )
    
    # 上传文件配置
    upload_path: str = Field(
        default="prototype/uploads/",
        description="上传文件路径前缀"
    )
    
    max_upload_file_size_mb: int = Field(
        default=5,
        description="单个上传文件最大大小(MB)"
    )
    
    allowed_image_extensions: list[str] = Field(
        default=[".jpg", ".jpeg", ".png", ".gif", ".webp"],
        description="允许上传的图片扩展名"
    )

def get_prototype_config() -> PrototypeConfig:
    """
    获取原型设计模块配置
    
    Returns:
        PrototypeConfig: 配置对象
    """
    # 从settings中获取配置或使用默认值
    provider_type_str = getattr(settings, "PROTOTYPE_AI_PROVIDER", "OpenAI")
    
    # 尝试转换为枚举值
    try:
        provider_type = ChatAIProviderType(provider_type_str)
    except ValueError:
        # 默认使用OpenAI
        provider_type = ChatAIProviderType.OPENAI
    
    return PrototypeConfig(
        chat_ai_provider_type=provider_type,
        upload_path=getattr(settings, "PROTOTYPE_UPLOAD_PATH", "prototype/uploads/"),
        max_upload_file_size_mb=getattr(settings, "PROTOTYPE_MAX_UPLOAD_SIZE_MB", 5),
        allowed_image_extensions=getattr(settings, "PROTOTYPE_ALLOWED_EXTENSIONS", 
                                        [".jpg", ".jpeg", ".png", ".gif", ".webp"])
    )