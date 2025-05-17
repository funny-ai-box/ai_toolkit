"""
播客模块常量定义
"""
from enum import Enum, IntEnum


class PodcastTaskStatus(IntEnum):
    """播客处理状态枚举"""
    INIT = 0        # 初始化
    PENDING = 1     # 待处理
    PROCESSING = 2  # 开始处理
    COMPLETED = 3   # 处理完成
    FAILED = 4      # 处理失败


class PodcastRoleType(IntEnum):
    """播客角色类型枚举"""
    HOST = 1        # 主持人
    GUEST = 2       # 嘉宾


class PodcastTaskContentType(IntEnum):
    """播客内容项类型枚举"""
    TEXT = 1        # 文本
    FILE = 2        # 文档文件
    URL = 3         # 网页地址


class AudioStatusType(IntEnum):
    """语音生成状态枚举"""
    PENDING = 0     # 待生成
    PROCESSING = 1  # 生成中
    COMPLETED = 2   # 生成完成
    FAILED = 3      # 生成失败


class VoiceGenderType(IntEnum):
    """语音性别类型枚举"""
    MALE = 1        # 男声
    FEMALE = 2      # 女声


class VoicePlatformType(str, Enum):
    """语音平台类型枚举"""
    MICROSOFT = "Microsoft"  # 微软语音
    DOUBAO = "Doubao"        # 豆包语音