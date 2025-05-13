"""
会话分享相关的数据传输对象
"""
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ShareSessionRequestDto(BaseModel):
    """分享会话请求DTO"""
    session_id: int = Field(..., alias="sessionId", description="会话ID")
    is_shared: bool = Field(..., alias="isShared", description="是否分享")

    model_config = ConfigDict(populate_by_name=True)


class ShareSessionResponseDto(BaseModel):
    """分享会话响应DTO"""
    share_code: Optional[str] = Field(None, alias="shareCode", description="分享码")
    share_url: Optional[str] = Field(None, alias="shareUrl", description="分享URL")

    model_config = ConfigDict(populate_by_name=True)


class GetSessionByShareCodeDto(BaseModel):
    """通过分享码获取会话请求DTO"""
    share_code: Optional[str] = Field(None, alias="shareCode", description="分享码")

    model_config = ConfigDict(populate_by_name=True)


class ChatWithSharedSession(BaseModel):
    """与分享会话聊天请求DTO"""
    share_code: Optional[str] = Field(None, alias="shareCode", description="分享码")
    message: Optional[str] = Field(None, alias="message", description="消息内容")

    model_config = ConfigDict(populate_by_name=True)