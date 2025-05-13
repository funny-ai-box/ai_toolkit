"""
聊天消息相关的数据传输对象
"""
import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class SourceReferenceDto(BaseModel):
    """引用来源DTO"""
    document_id: int = Field(..., alias="documentId")
    document_title: Optional[str] = Field(None, alias="documentTitle")
    content: Optional[str] = Field(None, alias="content")
    score: float = Field(...)

    model_config = ConfigDict(populate_by_name=True)


class ChatMessageDto(BaseModel):
    """聊天消息DTO"""
    id: int = Field(...)
    session_id: int = Field(..., alias="sessionId")
    role: Optional[str] = Field(None, alias="role")
    content: Optional[str] = Field(None, alias="content")
    create_date: datetime.datetime = Field(..., alias="createDate")
    sources: Optional[List[SourceReferenceDto]] = Field(None, alias="sources")

    model_config = ConfigDict(populate_by_name=True)


class ChatRequestDto(BaseModel):
    """聊天请求DTO"""
    session_id: int = Field(..., alias="sessionId")
    message: Optional[str] = Field(None, alias="message")

    model_config = ConfigDict(populate_by_name=True)


class ChatReplyDto(BaseModel):
    """聊天回复DTO"""
    reply: Optional[str] = Field(None, alias="reply")
    sources: Optional[List[SourceReferenceDto]] = Field(None, alias="sources")

    model_config = ConfigDict(populate_by_name=True)


class ChatStreamReplyDto(BaseModel):
    """聊天流式回复DTO"""
    id: Optional[str] = Field(None, alias="id")
    session: int = Field(..., alias="session")
    event: Optional[str] = Field(None, alias="event")
    data: Optional[str] = Field(None, alias="data")

    model_config = ConfigDict(populate_by_name=True)


class PagedChatHistoryDto(BaseModel):
    """分页聊天历史响应DTO"""
    messages: Optional[List[ChatMessageDto]] = Field(None, alias="messages")
    next_last_id: Optional[int] = Field(None, alias="nextLastId")
    has_more: bool = Field(..., alias="hasMore")

    model_config = ConfigDict(populate_by_name=True)


class ChatSessionHistory(BaseModel):
    """聊天会话历史请求DTO"""
    session_id: int = Field(..., alias="sessionId")
    limit: int = Field(20, alias="limit")

    model_config = ConfigDict(populate_by_name=True)


class ChatHistoryPaginated(BaseModel):
    """聊天历史分页请求DTO"""
    session_id: int = Field(..., alias="sessionId")
    page_size: int = Field(..., alias="pageSize")
    last_id: Optional[int] = Field(None, alias="lastId")

    model_config = ConfigDict(populate_by_name=True)