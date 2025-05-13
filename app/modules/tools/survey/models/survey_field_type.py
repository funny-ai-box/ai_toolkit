from enum import Enum

class SurveyFieldType(str, Enum):
    """问卷字段类型枚举"""
    SINGLE_LINE_TEXT = "SingleLineText"  # 单行文本
    MULTI_LINE_TEXT = "MultiLineText"    # 多行文本
    RADIO = "Radio"                      # 单选框
    CHECKBOX = "Checkbox"                # 多选框
    SELECT = "Select"                    # 下拉选择
    DATE = "Date"                        # 日期选择
    TIME = "Time"                        # 时间选择
    DATETIME = "DateTime"                # 日期时间选择
    NUMBER = "Number"                    # 数字输入
    IMAGE_UPLOAD = "ImageUpload"         # 图片上传
    RATING = "Rating"                    # 评分
    SLIDER = "Slider"                    # 滑块
