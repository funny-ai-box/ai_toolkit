# app/modules/tools/social_content/dtos/task_dtos.py
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
from enum import IntEnum

from app.core.dtos import BaseIdRequestDto, BaseIdResponseDto, ApiResponse, BasePageRequestDto, PagedResultDto


class PromptType(IntEnum):
    """Prompt类型枚举"""
    SYSTEM = 1  # 系统默认
    USER = 2  # 用户自定义


class GenerationTaskStatus(IntEnum):
    """任务状态枚举"""
    PENDING = 0  # 待处理
    PROCESSING = 1  # 处理中
    COMPLETED = 2  # 处理完成
    FAILED = 3  # 处理失败


class CreateTaskRequestDto(BaseModel):
    """创建任务请求DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    task_name: str = Field(min_length=2, max_length=100, alias="taskName")
    keywords: str = Field(min_length=2, max_length=4500, alias="keywords")
    product_info: Optional[str] = Field(default="", max_length=4500, alias="productInfo")
    platform_id: int = Field(alias="platformId")
    prompt_id: int = Field(alias="promptId")
    prompt_type: PromptType = Field(alias="promptType")
    content_count: int = Field(default=2, ge=1, le=5, alias="contentCount")


class TaskImageDto(BaseModel):
    """任务图片DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(alias="id")
    image_path: Optional[str] = Field(default=None, alias="imagePath")
    image_description: Optional[str] = Field(default=None, alias="imageDescription")


class TaskPlatformDto(BaseModel):
    """任务平台DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(alias="id")
    platform_id: int = Field(alias="platformId")
    platform_name: Optional[str] = Field(default=None, alias="platformName")
    platform_code: Optional[str] = Field(default=None, alias="platformCode")
    prompt_id: int = Field(alias="promptId")
    prompt_template_name: Optional[str] = Field(default=None, alias="promptTemplateName")
    prompt_type: PromptType = Field(alias="promptType")
    template_content: Optional[str] = Field(default=None, alias="templateContent")
    system_prompt: Optional[str] = Field(default=None, alias="systemPrompt")
    status: GenerationTaskStatus = Field(alias="status")
    status_name: str = Field(alias="statusName")
    content_count: int = Field(alias="contentCount")


class GeneratedContentDto(BaseModel):
    """生成内容DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(alias="id")
    task_platform_id: int = Field(alias="taskPlatformId")
    prompt_template_name: Optional[str] = Field(default=None, alias="promptTemplateName")
    platform_id: int = Field(alias="platformId")
    platform_name: Optional[str] = Field(default=None, alias="platformName")
    content_index: int = Field(alias="contentIndex")
    content: Optional[str] = Field(default=None, alias="content")
    create_date: datetime = Field(alias="createDate")


class TaskDetailResponseDto(BaseModel):
    """任务详情响应DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(alias="id")
    task_name: Optional[str] = Field(default=None, alias="taskName")
    keywords: Optional[str] = Field(default=None, alias="keywords")
    product_info: Optional[str] = Field(default=None, alias="productInfo")
    status: GenerationTaskStatus = Field(alias="status")
    status_name: str = Field(alias="statusName")
    process_message: Optional[str] = Field(default=None, alias="processMessage")
    completion_rate: float = Field(alias="completionRate")
    create_date: datetime = Field(alias="createDate")
    platforms: Optional[List[TaskPlatformDto]] = Field(default=None, alias="platforms")
    images: Optional[List[TaskImageDto]] = Field(default=None, alias="images")
    contents: Optional[List[GeneratedContentDto]] = Field(default=None, alias="contents")
    
    @field_validator('status_name', mode='after')
    def set_status_name(cls, v, values):
        status = values.data.get('status')
        if status is not None:
            if status == GenerationTaskStatus.PENDING:
                return "PENDING"
            elif status == GenerationTaskStatus.PROCESSING:
                return "PROCESSING"
            elif status == GenerationTaskStatus.COMPLETED:
                return "COMPLETED"
            elif status == GenerationTaskStatus.FAILED:
                return "FAILED"
        return v


class TaskListItemDto(BaseModel):
    """任务列表项DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(alias="id")
    task_name: Optional[str] = Field(default=None, alias="taskName")
    platform_count: int = Field(alias="platformCount")
    image_count: int = Field(alias="imageCount")
    content_count: int = Field(alias="contentCount")
    status: GenerationTaskStatus = Field(alias="status")
    status_name: str = Field(alias="statusName")
    completion_rate: float = Field(alias="completionRate")
    create_date: datetime = Field(alias="createDate")


class TaskListRequestDto(BasePageRequestDto):
    """任务列表请求DTO"""
    pass


class TaskStatusRequestDto(BaseIdRequestDto):
    """任务状态查询请求DTO"""
    pass