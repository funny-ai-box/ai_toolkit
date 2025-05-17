"""
聊天相关数据传输对象
"""
from typing import List, Optional, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from app.core.ai.dtos import ChatRoleType

class ChatSessionListRequestDto(BaseModel):
    """聊天会话列表请求DTO"""
    page_index: int = Field(1, description="页码", ge=1)
    page_size: int = Field(20, description="每页大小", ge=1, le=100)
    include_ended: bool = Field(True, description="是否包含已结束的会话")
    
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_')))
    )

class ChatSessionListItemDto(BaseModel):
    """聊天会话列表项DTO"""
    id: int = Field(..., description="会话ID")
    user_name: Optional[str] = Field(None, description="用户姓名")
    session_name: Optional[str] = Field(None, description="会话名称")
    status: int = Field(..., description="会话状态，1-进行中，0-已结束")
    session_key: Optional[str] = Field(None, description="会话唯一标识")
    last_message: Optional[str] = Field(None, description="最后一条消息内容")
    last_message_time: Optional[datetime] = Field(None, description="最后消息时间")
    create_date: datetime = Field(..., description="创建时间")
    last_modify_date: datetime = Field(..., description="更新时间")
    
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_')))
    )

class ChatSessionDto(BaseModel):
    """聊天会话DTO"""
    id: int = Field(..., description="会话ID")
    user_id: int = Field(..., description="用户ID")
    user_name: Optional[str] = Field(None, description="用户姓名")
    session_name: Optional[str] = Field(None, description="会话名称")
    status: int = Field(..., description="会话状态，1-进行中，0-已结束")
    session_key: Optional[str] = Field(None, description="会话唯一标识")
    recent_history: List["ChatHistoryDto"] = Field(default_factory=list, description="最近消息历史")
    create_date: datetime = Field(..., description="创建时间")
    last_modify_date: datetime = Field(..., description="更新时间")
    
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_')))
    )

class ChatSessionCreateDto(BaseModel):
    """聊天会话创建请求DTO"""
    user_name: Optional[str] = Field(None, description="用户姓名", max_length=50)
    
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_')))
    )

class ChatHistoryListRequestDto(BaseModel):
    """聊天历史列表请求DTO"""
    session_id: int = Field(..., description="会话ID")
    page_index: int = Field(1, description="页码", ge=1)
    page_size: int = Field(20, description="每页大小", ge=1, le=100)
    
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_')))
    )

class ChatHistoryDto(BaseModel):
    """聊天历史DTO"""
    id: int = Field(..., description="记录ID")
    session_id: int = Field(..., description="会话ID")
    role: ChatRoleType = Field(..., description="角色(user/assistant)")
    content: Optional[str] = Field(None, description="对话内容")
    intent: Optional[str] = Field(None, description="用户意图")
    call_datas: Optional[str] = Field(None, description="调用的函数返回的关键数据")
    image_url: Optional[str] = Field(None, description="图片URL")
    create_date: datetime = Field(..., description="创建时间")
    
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_')))
    )

class ChatMessageRequestDto(BaseModel):
    """聊天消息请求DTO"""
    session_id: int = Field(..., description="会话ID")
    content: str = Field(..., description="消息内容")
    
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_')))
    )

class ChatMessageResultDto(BaseModel):
    """聊天消息结果DTO"""
    message_id: int = Field(0, description="消息ID")
    session_id: int = Field(..., description="会话ID")
    reply: Optional[str] = Field(None, description="回复内容")
    intent: Optional[str] = Field(None, description="识别到的意图")
    call_datas: Optional[str] = Field(None, description="调用的函数")
    success: bool = Field(True, description="是否成功")
    error_message: Optional[str] = Field(None, description="错误消息")
    
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_')))
    )

class MessageChunkDto(BaseModel):
    """消息块DTO"""
    id: Optional[str] = Field(None, description="事件ID")
    session_id: int = Field(..., description="会话ID")
    event: Optional[str] = Field(None, description="事件类型")
    data: Optional[str] = Field(None, description="数据内容")
    
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_')))
    )

class IntentRecognitionResultDto(BaseModel):
    """意图识别结果DTO"""
    intent: Optional[str] = Field(None, description="识别到的意图")
    context: Optional[str] = Field(None, description="工具的响应结果")
    id_datas: Optional[List[str]] = Field(None, description="响应的结果，ID")
    
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_')))
    )

class ImageAnalysisResultDto(BaseModel):
    """图片分析结果DTO"""
    description: Optional[str] = Field(None, description="图片描述")
    tags: Optional[List[str]] = Field(None, description="识别到的标签")
    
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_')))
    )

class ConnectionRequestDto(BaseModel):
    """实时连接建立请求DTO"""
    session_id: int = Field(..., description="会话ID")
    connection_id: str = Field(..., description="连接ID")
    client_type: str = Field(..., description="客户端类型")
    
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_')))
    )

class MessageEventType(str, Enum):
    """流式消息事件类型"""
    START = "start"        # 开始事件
    CHUNK = "chunk"        # 消息块事件
    DONE = "done"          # 完成事件
    ERROR = "error"        # 错误事件
    CANCELED = "canceled"  # 取消事件
    END = "end"            # 结束事件