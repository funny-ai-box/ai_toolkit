# app/modules/tools/prototype/dtos.py
import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from app.core.dtos import BaseIdRequestDto, BasePageRequestDto, PagedResultDto
from app.modules.tools.prototype.constants import (
    PrototypeMessageType, PrototypePageStatus, PrototypeSessionStatus, CurrentStageType
)


# 会话相关DTOs
class CreateSessionRequestDto(BaseModel):
    """创建原型会话请求DTO"""
    model_config = ConfigDict(alias_generator=lambda s: s[0].lower() + s[1:])

    name: str = Field(default="", max_length=255, description="会话名称，若为空，后面将自动赋值")
    description: Optional[str] = Field(default=None, max_length=1000, description="会话描述")


class GetSessionDetailRequestDto(BaseIdRequestDto):
    """获取会话详情的DTO"""
    model_config = ConfigDict(alias_generator=lambda s: s[0].lower() + s[1:])
    
    include_pages: bool = Field(default=False, description="是否包含页面")


class UpdateSessionRequestDto(BaseModel):
    """更新会话请求DTO"""
    model_config = ConfigDict(alias_generator=lambda s: s[0].lower() + s[1:])
    
    id: int = Field(..., description="会话ID")
    name: str = Field(..., max_length=255, description="会话名称")
    description: Optional[str] = Field(default=None, max_length=1000, description="会话描述")


class SessionListItemDto(BaseModel):
    """原型会话列表项DTO"""
    model_config = ConfigDict(alias_generator=lambda s: s[0].lower() + s[1:])
    
    id: int = Field(..., description="会话ID")
    name: Optional[str] = Field(default=None, description="会话名称")
    status: PrototypeSessionStatus = Field(..., description="会话状态")
    status_description: Optional[str] = Field(default=None, description="会话状态描述")
    page_count: int = Field(..., description="页面数量")
    create_date: datetime.datetime = Field(..., description="创建时间")
    last_modify_date: datetime.datetime = Field(..., description="最后修改时间")


class PageDetailDto(BaseModel):
    """页面详情DTO"""
    model_config = ConfigDict(alias_generator=lambda s: s[0].lower() + s[1:])
    
    id: int = Field(..., description="页面ID")
    session_id: int = Field(..., description="会话ID")
    name: Optional[str] = Field(default=None, description="页面名称")
    path: Optional[str] = Field(default=None, description="页面路径（用于路由）")
    description: Optional[str] = Field(default=None, description="页面描述")
    content: Optional[str] = Field(default=None, description="页面内容（HTML/React代码）")
    status: PrototypePageStatus = Field(..., description="页面状态")
    status_description: Optional[str] = Field(default=None, description="页面状态描述")
    error_message: Optional[str] = Field(default=None, description="错误消息")
    order: int = Field(..., description="页面顺序")
    version: int = Field(..., description="版本号")
    history: Optional[List["PageHistoryDto"]] = Field(default=None, description="历史版本列表")
    create_date: datetime.datetime = Field(..., description="创建时间")
    last_modify_date: datetime.datetime = Field(..., description="最后修改时间")


class PageHistoryDto(BaseModel):
    """页面历史版本DTO"""
    model_config = ConfigDict(alias_generator=lambda s: s[0].lower() + s[1:])
    
    id: int = Field(..., description="历史记录ID")
    page_id: int = Field(..., description="页面ID")
    version: int = Field(..., description="版本号")
    change_description: Optional[str] = Field(default=None, description="修改描述")
    create_date: datetime.datetime = Field(..., description="创建时间")


class SessionDetailDto(BaseModel):
    """会话详情DTO"""
    model_config = ConfigDict(alias_generator=lambda s: s[0].lower() + s[1:])
    
    id: int = Field(..., description="会话ID")
    name: Optional[str] = Field(default=None, description="会话名称")
    description: Optional[str] = Field(default=None, description="会话描述")
    status: PrototypeSessionStatus = Field(..., description="会话状态")
    status_description: Optional[str] = Field(default=None, description="会话状态描述")
    requirements: Optional[str] = Field(default=None, description="需求描述（结构化JSON）")
    page_structure: Optional[str] = Field(default=None, description="页面结构（结构化JSON）")
    is_generating_code: bool = Field(..., description="是否正在生成代码")
    pages: Optional[List[PageDetailDto]] = Field(default=None, description="页面列表")
    create_date: datetime.datetime = Field(..., description="创建时间")
    last_modify_date: datetime.datetime = Field(..., description="最后修改时间")


# AI聊天相关DTOs
class AIChatRequestDto(BaseModel):
    """AI对话请求DTO"""
    model_config = ConfigDict(alias_generator=lambda s: s[0].lower() + s[1:])
    
    session_id: int = Field(..., description="会话ID")
    user_message: str = Field(..., description="用户输入")
    attachments: Optional[List[int]] = Field(default=None, description="附件ID列表")
    mode: str = Field(default="normal", description="对话模式")


class AIChatUploadReferenceDto(BaseModel):
    """对话中上传文件的Dto"""
    model_config = ConfigDict(alias_generator=lambda s: s[0].lower() + s[1:])
    
    id: int = Field(..., description="文件编号")
    url: str = Field(..., description="文件Url")


# 消息相关DTOs
class MessageListRequestDto(BasePageRequestDto):
    """消息列表请求DTO"""
    model_config = ConfigDict(alias_generator=lambda s: s[0].lower() + s[1:])
    
    session_id: int = Field(..., description="会话ID")


class MessageDto(BaseModel):
    """消息详情DTO"""
    model_config = ConfigDict(alias_generator=lambda s: s[0].lower() + s[1:])
    
    id: int = Field(..., description="消息ID")
    session_id: int = Field(..., description="会话ID")
    message_type: PrototypeMessageType = Field(..., description="消息类型")
    message_type_description: Optional[str] = Field(default=None, description="消息类型描述")
    content: Optional[str] = Field(default=None, description="消息内容")
    is_code: bool = Field(default=False, description="是否是代码内容")
    attachment_urls: Optional[str] = Field(default=None, description="附件URL（如果有）")
    attachment_ids: Optional[str] = Field(default=None, description="附件ID（如果有）")
    create_date: datetime.datetime = Field(..., description="创建时间")


# 页面结构相关DTOs
class PageInfoDto(BaseModel):
    """页面信息DTO"""
    model_config = ConfigDict(alias_generator=lambda s: s[0].lower() + s[1:])
    
    name: str = Field(default="", description="页面名称")
    path: str = Field(default="", description="页面路径")
    description: str = Field(default="", description="页面描述")


class PageStructureDto(BaseModel):
    """页面结构DTO"""
    model_config = ConfigDict(alias_generator=lambda s: s[0].lower() + s[1:])
    
    pages: List[PageInfoDto] = Field(default_factory=list, description="页面列表")
    design_style: str = Field(default="", description="设计风格")
    color_scheme: str = Field(default="", description="配色方案")
    target_device: str = Field(default="", description="目标设备")
    interaction_style: str = Field(default="", description="交互风格")


class NavigationInfoDto(BaseModel):
    """导航信息DTO"""
    model_config = ConfigDict(alias_generator=lambda s: s[0].lower() + s[1:])
    
    from_page: str = Field(default="", alias="from", description="来源页面")
    to: str = Field(default="", description="目标页面")
    description: str = Field(default="", description="导航描述")


class SessionStageDto(BaseModel):
    """会话中状态数据"""
    model_config = ConfigDict(alias_generator=lambda s: s[0].lower() + s[1:])
    
    current_stage: CurrentStageType = Field(..., description="当前阶段")
    next_stage: CurrentStageType = Field(..., description="下个阶段")
    current_page: Optional[str] = Field(default=None, description="当前页面")
    modified_page: Optional[str] = Field(default=None, description="修改页面")


# 资源相关DTOs
class ResourceDto(BaseModel):
    """原型资源DTO"""
    model_config = ConfigDict(alias_generator=lambda s: s[0].lower() + s[1:])
    
    id: int = Field(..., description="资源ID")
    session_id: int = Field(..., description="会话ID")
    name: Optional[str] = Field(default=None, description="资源名称")
    resource_type: Optional[str] = Field(default=None, description="资源类型")
    url: Optional[str] = Field(default=None, description="资源URL")
    content: Optional[str] = Field(default=None, description="资源内容")
    create_date: datetime.datetime = Field(..., description="创建时间")


class AddResourceRequestDto(BaseModel):
    """添加资源请求DTO"""
    model_config = ConfigDict(alias_generator=lambda s: s[0].lower() + s[1:])
    
    session_id: int = Field(..., description="会话ID")
    name: str = Field(..., max_length=255, description="资源名称")
    resource_type: str = Field(..., max_length=50, description="资源类型")
    url: Optional[str] = Field(default=None, max_length=500, description="资源URL")
    content: Optional[str] = Field(default=None, description="资源内容")


# 预览相关DTOs
class AppPreviewDto(BaseModel):
    """应用预览DTO"""
    model_config = ConfigDict(alias_generator=lambda s: s[0].lower() + s[1:])
    
    session_id: int = Field(..., description="会话ID")
    name: Optional[str] = Field(default=None, description="会话名称")
    pages: Optional[List[PageDetailDto]] = Field(default=None, description="页面列表")
    resources: Optional[List[ResourceDto]] = Field(default=None, description="资源列表")
    entry_url: Optional[str] = Field(default=None, description="应用入口URL")