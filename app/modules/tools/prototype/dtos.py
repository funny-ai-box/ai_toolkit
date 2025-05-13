"""
原型设计模块的数据传输对象定义
"""
from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import Field, BaseModel, ConfigDict

from app.core.dtos import BaseIdRequestDto, BasePageRequestDto
from app.modules.tools.prototype.enums import (
    PrototypeSessionStatus, 
    PrototypePageStatus, 
    PrototypeMessageType,
    CurrentStageType
)


# 会话相关 DTOs
class CreateSessionRequestDto(BaseModel):
    """创建原型会话请求DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    name: str = Field(default="", alias="name", max_length=255, description="会话名称，若为空，后面将自动赋值")
    description: Optional[str] = Field(default=None, alias="description", max_length=1000, description="会话描述")


class UpdateSessionRequestDto(BaseModel):
    """更新原型会话请求DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(..., alias="id", description="会话ID")
    name: str = Field(..., alias="name", max_length=255, description="会话名称")
    description: Optional[str] = Field(default=None, alias="description", max_length=1000, description="会话描述")


class GetSessionDetailRequestDto(BaseIdRequestDto):
    """获取会话详情请求DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    include_pages: bool = Field(default=False, alias="includePages", description="是否包含页面详情")


class SessionListItemDto(BaseModel):
    """原型会话列表项DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(..., alias="id", description="会话ID")
    name: Optional[str] = Field(default=None, alias="name", description="会话名称")
    status: PrototypeSessionStatus = Field(..., alias="status", description="会话状态")
    status_description: Optional[str] = Field(default=None, alias="statusDescription", description="会话状态描述")
    page_count: int = Field(..., alias="pageCount", description="页面数量")
    create_date: datetime = Field(..., alias="createDate", description="创建时间")
    last_modify_date: datetime = Field(..., alias="lastModifyDate", description="最后修改时间")


class SessionDetailDto(BaseModel):
    """会话详情DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(..., alias="id", description="会话ID")
    name: Optional[str] = Field(default=None, alias="name", description="会话名称")
    description: Optional[str] = Field(default=None, alias="description", description="会话描述")
    status: PrototypeSessionStatus = Field(..., alias="status", description="会话状态")
    status_description: Optional[str] = Field(default=None, alias="statusDescription", description="会话状态描述")
    requirements: Optional[str] = Field(default=None, alias="requirements", description="需求描述（结构化JSON）")
    page_structure: Optional[str] = Field(default=None, alias="pageStructure", description="页面结构（结构化JSON）")
    is_generating_code: bool = Field(..., alias="isGeneratingCode", description="是否正在生成代码")
    pages: Optional[List["PageDetailDto"]] = Field(default=None, alias="pages", description="页面列表")
    create_date: datetime = Field(..., alias="createDate", description="创建时间")
    last_modify_date: datetime = Field(..., alias="lastModifyDate", description="最后修改时间")


# 页面相关 DTOs
class PageHistoryDto(BaseModel):
    """页面历史版本DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(..., alias="id", description="历史记录ID")
    page_id: int = Field(..., alias="pageId", description="页面ID")
    version: int = Field(..., alias="version", description="版本号")
    change_description: Optional[str] = Field(default=None, alias="changeDescription", description="修改描述")
    create_date: datetime = Field(..., alias="createDate", description="创建时间")


class PageDetailDto(BaseModel):
    """页面详情DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(..., alias="id", description="页面ID")
    session_id: int = Field(..., alias="sessionId", description="会话ID")
    name: Optional[str] = Field(default=None, alias="name", description="页面名称")
    path: Optional[str] = Field(default=None, alias="path", description="页面路径（用于路由）")
    description: Optional[str] = Field(default=None, alias="description", description="页面描述")
    content: Optional[str] = Field(default=None, alias="content", description="页面内容（React代码）")
    status: PrototypePageStatus = Field(..., alias="status", description="页面状态")
    status_description: Optional[str] = Field(default=None, alias="statusDescription", description="页面状态描述")
    error_message: Optional[str] = Field(default=None, alias="errorMessage", description="错误消息")
    order: int = Field(..., alias="order", description="页面顺序")
    version: int = Field(..., alias="version", description="版本号")
    history: Optional[List[PageHistoryDto]] = Field(default=None, alias="history", description="历史版本列表")
    create_date: datetime = Field(..., alias="createDate", description="创建时间")
    last_modify_date: datetime = Field(..., alias="lastModifyDate", description="最后修改时间")


# 消息相关 DTOs
class MessageListRequestDto(BasePageRequestDto):
    """消息列表请求DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    session_id: int = Field(..., alias="sessionId", description="会话ID")


class MessageDto(BaseModel):
    """消息详情DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(..., alias="id", description="消息ID")
    session_id: int = Field(..., alias="sessionId", description="会话ID")
    message_type: PrototypeMessageType = Field(..., alias="messageType", description="消息类型")
    message_type_description: Optional[str] = Field(default=None, alias="messageTypeDescription", description="消息类型描述")
    content: Optional[str] = Field(default=None, alias="content", description="消息内容")
    is_code: bool = Field(default=False, alias="isCode", description="是否是代码内容")
    attachment_urls: Optional[str] = Field(default=None, alias="attachmentUrls", description="附件URL（如果有）")
    attachment_ids: Optional[str] = Field(default=None, alias="attachmentIds", description="附件ID列表（如果有）")
    create_date: datetime = Field(..., alias="createDate", description="创建时间")


# AI 聊天相关 DTOs
class AIChatRequestDto(BaseModel):
    """AI对话请求DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    session_id: int = Field(..., alias="sessionId", description="会话ID")
    user_message: str = Field(..., alias="userMessage", description="用户输入")
    attachments: Optional[List[int]] = Field(default=None, alias="attachments", description="附件ID列表（如果有）")
    mode: str = Field(default="normal", alias="mode", description="对话模式")


class AIChatUploadReferenceDto(BaseModel):
    """对话中上传文件的Dto"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(..., alias="id", description="文件编号")
    url: str = Field(..., alias="url", description="文件Url")


# 资源相关 DTOs
class ResourceDto(BaseModel):
    """原型资源DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(..., alias="id", description="资源ID")
    session_id: int = Field(..., alias="sessionId", description="会话ID")
    name: Optional[str] = Field(default=None, alias="name", description="资源名称")
    resource_type: Optional[str] = Field(default=None, alias="resourceType", description="资源类型")
    url: Optional[str] = Field(default=None, alias="url", description="资源URL")
    content: Optional[str] = Field(default=None, alias="content", description="资源内容（可选，如果是自定义资源）")
    create_date: datetime = Field(..., alias="createDate", description="创建时间")


# 页面结构相关 DTOs
class PageInfoDto(BaseModel):
    """页面信息DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    name: str = Field(default="", alias="name", description="页面名称")
    path: str = Field(default="", alias="path", description="页面路径")
    description: str = Field(default="", alias="description", description="页面描述")


class PageStructureDto(BaseModel):
    """页面结构DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    pages: List[PageInfoDto] = Field(default_factory=list, alias="pages", description="页面列表")
    design_style: str = Field(default="", alias="designStyle", description="设计风格")
    color_scheme: str = Field(default="", alias="colorScheme", description="配色方案")
    target_device: str = Field(default="", alias="targetDevice", description="目标设备：mobile-app, desktop, responsive")
    interaction_style: str = Field(default="", alias="interactionStyle", description="交互风格")


# 会话阶段相关DTO
class SessionStageDto(BaseModel):
    """会话中状态数据"""
    model_config = ConfigDict(populate_by_name=True)
    
    current_stage: CurrentStageType = Field(..., alias="currentStage", description="当前阶段")
    next_stage: CurrentStageType = Field(..., alias="nextStage", description="下个阶段")
    current_page: Optional[str] = Field(default=None, alias="currentPage", description="当前页面")
    modified_page: Optional[str] = Field(default=None, alias="modifiedPage", description="修改页面")


# 应用预览 DTOs
class AppPreviewDto(BaseModel):
    """应用预览DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    session_id: int = Field(..., alias="sessionId", description="会话ID")
    name: Optional[str] = Field(default=None, alias="name", description="会话名称")
    pages: Optional[List[PageDetailDto]] = Field(default=None, alias="pages", description="页面列表")
    resources: Optional[List[ResourceDto]] = Field(default=None, alias="resources", description="资源列表")
    entry_url: Optional[str] = Field(default=None, alias="entryUrl", description="应用入口URL")