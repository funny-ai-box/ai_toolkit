# app/modules/tools/social_content/dtos/platform_dtos.py
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime


class PlatformDto(BaseModel):
    """平台信息DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(alias="id")
    name: Optional[str] = Field(default=None, alias="name")
    code: Optional[str] = Field(default=None, alias="code")
    icon: Optional[str] = Field(default=None, alias="icon")
    description: Optional[str] = Field(default=None, alias="description")


class PlatformPromptDto(BaseModel):
    """平台模板DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(alias="id")
    platform_id: int = Field(alias="platformId")
    template_name: Optional[str] = Field(default=None, alias="templateName")
    template_content: Optional[str] = Field(default=None, alias="templateContent")
    system_prompt: Optional[str] = Field(default=None, alias="systemPrompt")


class UserPromptDto(BaseModel):
    """用户模板DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(alias="id")
    platform_id: int = Field(alias="platformId")
    platform_name: Optional[str] = Field(default=None, alias="platformName")
    template_name: Optional[str] = Field(default=None, alias="templateName")
    template_content: Optional[str] = Field(default=None, alias="templateContent")
    system_prompt: Optional[str] = Field(default=None, alias="systemPrompt")
    create_date: datetime = Field(alias="createDate")


class AddUserPromptRequestDto(BaseModel):
    """添加用户模板请求DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    platform_id: int = Field(alias="platformId")
    template_name: str = Field(min_length=2, max_length=100, alias="templateName")
    template_content: str = Field(alias="templateContent")
    system_prompt: str = Field(alias="systemPrompt")


class UpdateUserPromptRequestDto(BaseModel):
    """更新用户模板请求DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(alias="id")
    template_name: str = Field(min_length=2, max_length=100, alias="templateName")
    template_content: str = Field(alias="templateContent")
    system_prompt: Optional[str] = Field(default=None, alias="systemPrompt")