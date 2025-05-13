"""
原型设计模块的枚举类型定义
"""
from enum import Enum


class PrototypeSessionStatus(int, Enum):
    """原型会话状态枚举"""
    NONE = 0
    REQUIREMENT_GATHERING = 1
    REQUIREMENT_ANALYZING = 2
    STRUCTURE_CONFIRMATION = 3
    PAGE_GENERATION = 4
    COMPLETED = 5
    ABANDONED = 6


class PrototypePageStatus(int, Enum):
    """原型页面状态枚举"""
    PENDING = 0
    GENERATING = 1
    GENERATED = 2
    FAILED = 3
    MODIFIED = 4


class PrototypeMessageType(int, Enum):
    """原型消息类型枚举"""
    USER = 0
    AI = 1
    SYSTEM = 2


class CurrentStageType(int, Enum):
    """对话消息设计状态"""
    NONE = 0
    COLLECTING = 1
    ANALYZING = 2
    DESIGNING = 3
    GENERATING = 4
    COMPLETED = 5
    EDITING = 6


class StorageProviderType(str, Enum):
    """存储服务类型枚举"""
    LOCAL = "Local"
    ALIYUN_OSS = "AliyunOSS"
    AZURE_BLOB = "AzureBlob"


class ChatAIProviderType(str, Enum):
    """聊天AI服务类型枚举"""
    OPENAI = "OpenAI"
    GEMINI = "Gemini"