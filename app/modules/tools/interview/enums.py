"""
面试模拟器模块的枚举类型定义

此模块定义了面试模拟器功能所需的各种枚举类型，包括场景状态、问题难度、会话状态等。
"""
from enum import Enum, IntEnum


class InterviewScenarioStatus(IntEnum):
    """面试场景状态枚举"""
    INIT = 0        # 初始化
    PENDING = 1     # 待处理
    ANALYZING = 2   # 分析中
    READY = 3       # 已就绪
    FAILED = 4      # 分析失败


class QuestionDifficulty(IntEnum):
    """问题难度枚举"""
    JUNIOR = 1        # 初级
    INTERMEDIATE = 2  # 中级
    SENIOR = 3        # 高级
    EXPERT = 4        # 专家


class InterviewSessionStatus(IntEnum):
    """面试状态枚举"""
    NOT_STARTED = 0  # 未开始
    IN_PROGRESS = 1  # 进行中
    COMPLETED = 2    # 已完成
    EVALUATED = 3    # 已评估
    INTERRUPTED = 4  # 已中断


class InterviewerGender(IntEnum):
    """面试官性别枚举"""
    MALE = 1    # 男性
    FEMALE = 2  # 女性


class InterviewContentType(IntEnum):
    """面试场景内容项类型"""
    TEXT = 1  # 文本
    FILE = 2  # 文档文件
    URL = 3   # 网页地址


class JobPositionQuestionStatusType(IntEnum):
    """职位面试问题的生成状态枚举"""
    PENDING = 0     # 待生成
    PROCESSING = 1  # 生成中
    COMPLETED = 2   # 生成完成
    FAILED = 3      # 生成失败


class InterviewSessionEvaluateStatusType(IntEnum):
    """面试结果评估状态"""
    INIT = 0        # 初始化
    PENDING = 1     # 待处理
    PROCESSING = 2  # 生成中
    COMPLETED = 3   # 生成完成
    FAILED = 4      # 生成失败