"""
聊天会话相关的数据传输对象
"""
import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator, StringConstraints
from typing_extensions import Annotated


class ChatSessionInfoDto(BaseModel):
    """聊天会话信息DTO"""
    id: int = Field(..., alias="id")
    document_id: int = Field(..., alias="documentId")
    session_name: Optional[str] = Field(None, alias="sessionName")
    share_code: Optional[str] = Field(None, alias="shareCode")
    is_shared: bool = Field(..., alias="isShared")
    prompt: Optional[str] = Field(None, alias="prompt")
    create_date: datetime.datetime = Field(..., alias="createDate")
    last_modify_date: datetime.datetime = Field(..., alias="lastModifyDate")

    model_config = ConfigDict(populate_by_name=True)


class ChatSessionCreateRequestDto(BaseModel):
    """聊天会话创建请求DTO"""
    session_name: Optional[str] = Field(None, alias="sessionName", 
                                        description="会话名称")
    prompt: Optional[str] = Field(None, alias="prompt", 
                                 description="自定义提示词")
    document_id: int = Field(0, alias="documentId", 
                          description="指定文档的对话，为0就是不限定")

    @field_validator('session_name')
    def validate_session_name(cls, v):
        if v and len(v) > 100:
            raise ValueError("会话名称长度不能超过100个字符")
        return v

    @field_validator('prompt')
    def validate_prompt(cls, v):
        if v and len(v) > 1000:
            raise ValueError("自定义提示词长度不能超过1000个字符")
        return v

    model_config = ConfigDict(populate_by_name=True)


class ChatSessionUpdateRequestDto(BaseModel):
    """聊天会话更新请求DTO"""
    session_id: int = Field(..., alias="sessionId", 
                          description="会话Id")
    session_name: Optional[str] = Field(None, alias="sessionName", 
                                       description="会话名称")
    prompt: Optional[str] = Field(None, alias="prompt", 
                                description="自定义提示词")

    @field_validator('session_name')
    def validate_session_name(cls, v):
        if v and len(v) > 100:
            raise ValueError("会话名称长度不能超过100个字符")
        return v

    model_config = ConfigDict(populate_by_name=True)