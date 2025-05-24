from enum import Enum, IntEnum

class SurveyTaskStatus(IntEnum):
    """问卷任务状态枚举"""
    DRAFT = 0       # 草稿
    PUBLISHED = 1   # 已发布
    CLOSED = 2      # 已关闭


class SurveyFieldType(str, Enum):
    """问卷字段类型枚举"""
    SINGLE_LINE_TEXT = "SingleLineText"   # 单行文本
    MULTI_LINE_TEXT = "MultiLineText"     # 多行文本
    RADIO = "Radio"                       # 单选框
    CHECKBOX = "Checkbox"                 # 多选框
    SELECT = "Select"                     # 下拉选择
    DATE = "Date"                         # 日期选择
    TIME = "Time"                         # 时间选择
    DATETIME = "DateTime"                 # 日期时间选择
    NUMBER = "Number"                     # 数字输入
    IMAGE_UPLOAD = "ImageUpload"          # 图片上传
    RATING = "Rating"                     # 评分
    SLIDER = "Slider"                     # 滑块


class FieldOperationType(str, Enum):
    """字段变更操作类型枚举"""
    ADD = "add"          # 新增
    UPDATE = "update"    # 更新
    DELETE = "delete"    # 删除


class ChatRoleType(str, Enum):
    """聊天角色类型"""
    SYSTEM = "system"      # 系统
    USER = "user"          # 用户
    ASSISTANT = "assistant" # AI助手

from app.core.ai.dtos import ChatRoleType