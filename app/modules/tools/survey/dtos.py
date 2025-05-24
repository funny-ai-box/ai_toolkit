from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, validator
from app.core.dtos import BasePageRequestDto, PagedResultDto
from app.modules.tools.survey.enums import ChatRoleType

# 修复的alias_generator函数
def to_camel_case(snake_str: str) -> str:
    """将snake_case转换为camelCase"""
    components = snake_str.split('_')
    return components[0] + ''.join(word.capitalize() for word in components[1:])

# 基础配置，使用正确的 camelCase 转换
model_config = ConfigDict(
    alias_generator=to_camel_case, 
    populate_by_name=True
)


class OptionDto(BaseModel):
    """选项DTO"""
    value: Optional[str] = Field(None, description="选项值")
    label: Optional[str] = Field(None, description="选项标签")
    
    model_config = model_config


class FieldConfigDto(BaseModel):
    """字段配置DTO"""
    options: Optional[List[OptionDto]] = Field(None, description="选项数据源（适用于单选、多选等）")
    min: Optional[float] = Field(None, description="最小值（适用于数字、评分、滑块等）")
    max: Optional[float] = Field(None, description="最大值（适用于数字、评分、滑块等）")
    step: Optional[float] = Field(None, description="步长（适用于数字、滑块等）")
    max_length: Optional[int] = Field(None, description="文本最大长度")
    max_file_size: Optional[int] = Field(None, description="最大文件大小（适用于图片上传），单位KB")
    allowed_file_types: Optional[List[str]] = Field(None, description="允许的文件类型（适用于图片上传）")
    
    model_config = model_config


class FieldDesignDto(BaseModel):
    """字段设计DTO"""
    field_key: Optional[str] = Field(None, description="字段标识符")
    name: Optional[str] = Field(None, description="字段名称")
    type: Optional[str] = Field(None, description="字段类型")
    is_required: bool = Field(False, description="是否必填")
    config: Optional[FieldConfigDto] = Field(None, description="字段配置")
    placeholder: Optional[str] = Field(None, description="字段提示信息")
    order_no: int = Field(0, description="排序号")
    operation: Optional[str] = Field(None, description="操作类型（增加/修改/删除）")
    
    model_config = model_config


class TabDesignDto(BaseModel):
    """Tab设计DTO"""
    name: Optional[str] = Field(None, description="Tab名称")
    order_no: int = Field(0, description="排序号")
    operation: Optional[str] = Field(None, description="操作类型（增加/修改/删除）")
    fields: Optional[List[FieldDesignDto]] = Field(None, description="字段列表")
    
    model_config = model_config


class AIDesignRequestDto(BaseModel):
    """AI设计请求DTO"""
    task_id: int = Field(..., description="任务ID")
    message: Optional[str] = Field(None, description="用户消息")
    
    model_config = model_config
    
    @validator('message')
    def message_not_empty(cls, v):
        if v is None or v.strip() == '':
            raise ValueError('消息不能为空')
        return v


class AIDesignHistoryRequestDto(BasePageRequestDto):
    """AI设计历史请求DTO"""
    task_id: int = Field(..., description="任务ID")
    
    model_config = model_config


class AIDesignResponseDto(BaseModel):
    """AI设计响应DTO"""
    message: Optional[str] = Field(None, description="AI回复消息")
    tabs: Optional[List[TabDesignDto]] = Field(None, description="生成的Tab页")
    
    model_config = model_config


class DesignHistoryMessageDto(BaseModel):
    """设计历史消息DTO"""
    id: int = Field(..., description="消息ID")
    role: ChatRoleType = Field(..., description="消息角色（用户/AI）")
    content: Optional[str] = Field(None, description="消息内容")
    complete_json_config: Optional[str] = Field(None, description="完整JSON配置")
    create_date: datetime = Field(..., description="创建时间")
    
    model_config = model_config


class CreateSurveyTaskRequestDto(BaseModel):
    """创建问卷任务请求DTO"""
    name: str = Field(..., min_length=1, max_length=100, description="任务名称")
    description: Optional[str] = Field(None, max_length=500, description="任务描述")
    
    model_config = model_config


class UpdateSurveyTaskRequestDto(BaseModel):
    """更新问卷任务请求DTO"""
    id: int = Field(..., description="任务ID")
    name: str = Field(..., min_length=1, max_length=100, description="任务名称")
    description: Optional[str] = Field(None, max_length=500, description="任务描述")
    
    model_config = model_config


class SurveyTaskListItemDto(BaseModel):
    """问卷任务列表项DTO"""
    id: int = Field(..., description="任务ID")
    name: Optional[str] = Field(None, description="任务名称")
    description: Optional[str] = Field(None, description="任务描述")
    status: int = Field(..., description="状态")
    status_name: Optional[str] = Field(None, description="状态名称")
    share_code: Optional[str] = Field(None, description="共享码")
    response_count: int = Field(0, description="回答数量")
    create_date: datetime = Field(..., description="创建时间")
    last_modify_date: datetime = Field(..., description="最后修改时间")
    
    model_config = model_config


class SurveyFieldDto(BaseModel):
    """问卷字段DTO"""
    id: int = Field(..., description="字段ID")
    task_id: int = Field(..., description="任务ID")
    tab_id: int = Field(..., description="Tab页ID")
    field_key: Optional[str] = Field(None, description="字段标识符")
    name: Optional[str] = Field(None, description="字段名称")
    type: Optional[str] = Field(None, description="字段类型")
    is_required: bool = Field(False, description="是否必填")
    config: Optional[FieldConfigDto] = Field(None, description="字段配置")
    placeholder: Optional[str] = Field(None, description="字段提示信息")
    order_no: int = Field(0, description="排序号")
    operation: Optional[str] = Field(None, description="操作类型（增加/修改/删除）")
    
    model_config = model_config


class SurveyTabDto(BaseModel):
    """问卷Tab页DTO"""
    id: int = Field(..., description="Tab页ID")
    task_id: int = Field(..., description="任务ID")
    name: Optional[str] = Field(None, description="Tab名称")
    order_no: int = Field(0, description="排序号")
    fields: Optional[List[SurveyFieldDto]] = Field(None, description="字段列表")
    
    model_config = model_config


class SurveyTaskDetailDto(BaseModel):
    """问卷任务详情DTO"""
    id: int = Field(..., description="任务ID")
    name: Optional[str] = Field(None, description="任务名称")
    description: Optional[str] = Field(None, description="任务描述")
    status: int = Field(..., description="状态")
    status_name: Optional[str] = Field(None, description="状态名称")
    share_code: Optional[str] = Field(None, description="共享码")
    tabs: Optional[List[SurveyTabDto]] = Field(None, description="Tab页列表")
    create_date: datetime = Field(..., description="创建时间")
    last_modify_date: datetime = Field(..., description="最后修改时间")
    
    model_config = model_config


class SaveDesignRequestDto(BaseModel):
    """保存设计请求DTO"""
    task_id: int = Field(..., description="任务ID")
    tabs: Optional[List[TabDesignDto]] = Field(None, description="Tab页列表")
    
    model_config = model_config


class FieldValueDto(BaseModel):
    """字段值DTO"""
    field_id: int = Field(..., description="字段ID")
    value: Optional[str] = Field(None, description="字段值")
    
    model_config = model_config


class SubmitSurveyResponseRequestDto(BaseModel):
    """问卷填写请求DTO"""
    task_id: int = Field(..., description="任务ID")
    field_values: List[FieldValueDto] = Field(..., description="字段值列表")
    
    model_config = model_config


class SurveyResponseListItemDto(BaseModel):
    """问卷回答列表项DTO"""
    id: int = Field(..., description="回答ID")
    task_id: int = Field(..., description="任务ID")
    respondent_id: Optional[int] = Field(None, description="填写人ID")
    respondent_ip: Optional[str] = Field(None, description="填写人IP")
    submit_date: datetime = Field(..., description="提交时间")
    
    model_config = model_config


class ResponseFieldValueDto(BaseModel):
    """回答字段值DTO"""
    field_id: int = Field(..., description="字段ID")
    field_key: Optional[str] = Field(None, description="字段标识符")
    field_name: Optional[str] = Field(None, description="字段名称")
    field_type: Optional[str] = Field(None, description="字段类型")
    value: Optional[str] = Field(None, description="字段值")
    
    model_config = model_config


class SurveyResponseDetailDto(BaseModel):
    """问卷回答详情DTO"""
    id: int = Field(..., description="回答ID")
    task_id: int = Field(..., description="任务ID")
    respondent_id: Optional[int] = Field(None, description="填写人ID")
    respondent_ip: Optional[str] = Field(None, description="填写人IP")
    submit_date: datetime = Field(..., description="提交时间")
    field_values: Optional[List[ResponseFieldValueDto]] = Field(None, description="字段值列表")
    
    model_config = model_config


class ResponseListRequestDto(BasePageRequestDto):
    """回答列表请求DTO"""
    task_id: int = Field(..., description="任务ID")
    
    model_config = model_config


class OptionStatisticsDto(BaseModel):
    """选项统计DTO"""
    value: Optional[str] = Field(None, description="选项值")
    label: Optional[str] = Field(None, description="选项标签")
    count: int = Field(0, description="选择次数")
    percentage: float = Field(0, description="选择百分比")
    
    model_config = model_config


class NumericStatisticsDto(BaseModel):
    """数值统计DTO"""
    average: float = Field(0, description="平均值")
    min: float = Field(0, description="最小值")
    max: float = Field(0, description="最大值")
    median: float = Field(0, description="中位数")
    distribution: Optional[Dict[str, int]] = Field(None, description="数值分布")
    
    model_config = model_config


class FieldStatisticsDto(BaseModel):
    """字段统计DTO"""
    field_id: int = Field(..., description="字段ID")
    field_key: Optional[str] = Field(None, description="字段标识符")
    field_name: Optional[str] = Field(None, description="字段名称")
    field_type: Optional[str] = Field(None, description="字段类型")
    stat_type: Optional[str] = Field(None, description="统计类型（计数/百分比/平均值等）")
    option_stats: Optional[List[OptionStatisticsDto]] = Field(None, description="选项统计（适用于单选、多选等）")
    numeric_stats: Optional[NumericStatisticsDto] = Field(None, description="数值统计（适用于数字、评分、滑块等）")
    text_responses: Optional[List[str]] = Field(None, description="文本回答列表（适用于文本类型）")
    
    model_config = model_config


class SurveyReportDto(BaseModel):
    """问卷报表DTO"""
    task_id: int = Field(..., description="任务ID")
    task_name: Optional[str] = Field(None, description="任务名称")
    total_responses: int = Field(0, description="回答总数")
    field_statistics: Optional[List[FieldStatisticsDto]] = Field(None, description="字段统计列表")
    
    model_config = model_config