# app/base/dtos.py
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, validator, ConfigDict
from datetime import datetime
from enum import Enum
import re # 用于手机号验证

# --- 枚举 ---
class VerifiCodeSceneType(str, Enum):
    """验证码场景类型"""
    REGISTER = "Register"
    LOGIN = "Login" # C# 代码中有，但服务实现中似乎未使用
    UPDATE_PWD = "UpdatePwd"

# --- 请求 DTOs ---
class UserRegisterDto(BaseModel):
    """用户注册请求 DTO"""
    mobile_no: str = Field(..., description="手机号", alias="mobileNo")
    verifi_code: str = Field(..., min_length=4, max_length=20, description="验证码", alias="verifiCode")
    name: str = Field(..., min_length=2, max_length=50, description="用户名称")
    password: str = Field(..., min_length=6, max_length=20, description="密码")

    @validator('mobile_no')
    def validate_mobile_no(cls, v):
        """验证手机号格式"""
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('手机号格式不正确')
        return v

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "mobileNo": "13800138000",
                "verifiCode": "1234",
                "name": "测试用户",
                "password": "password123"
            }
        }
    )

class UserLoginDto(BaseModel):
    """用户登录请求 DTO"""
    mobile_no: str = Field(..., description="手机号", alias="mobileNo")
    password: str = Field(..., min_length=6, max_length=20, description="密码")

    @validator('mobile_no')
    def validate_mobile_no(cls, v):
        """验证手机号格式 (登录时也可以简单验证一下)"""
        # 登录时可能不需要严格验证格式，但至少确保非空
        if not v:
             raise ValueError('手机号不能为空')
        # if not re.match(r'^1[3-9]\d{9}$', v):
        #     raise ValueError('手机号格式不正确')
        return v

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "mobileNo": "13800138000",
                "password": "password123"
            }
        }
    )

class UserUpdatePwdDto(BaseModel):
    """用户修改密码请求 DTO"""
    verifi_code: str = Field(..., min_length=4, max_length=20, description="验证码", alias="verifiCode")
    password: str = Field(..., min_length=6, max_length=20, description="新密码")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "verifiCode": "5678",
                "password": "newpassword123"
            }
        }
    )

class SendVerifiCodeDto(BaseModel):
    """发送验证码通用请求 DTO"""
    scene_key: str = Field(..., min_length=2, max_length=20, description="场景 Key (手机号或用户 ID)", alias="sceneKey")
    scene_type: VerifiCodeSceneType = Field(..., description="场景类型", alias="sceneType")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "sceneKey": "13800138000", # 或者 "1234567890123456" (userId)
                "sceneType": "Register"   # 或 "UpdatePwd"
            }
        }
    )

# --- 响应 DTOs ---
class UserInfoDto(BaseModel):
    """用户信息响应 DTO"""
    id: int = Field(..., description="用户 ID") # C# 是 long
    mobile_no: Optional[str] = Field(None, description="手机号", alias="mobileNo")
    name: Optional[str] = Field(None, description="用户名称")
    create_date: datetime = Field(..., description="创建时间", alias="createDate")

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda field_name: field_name.replace('_', ' ').title().replace(' ', ''), # 自动转 camelCase
        json_schema_extra={
            "example": {
                "id": 1234567890123456,
                "mobileNo": "13800138000",
                "name": "测试用户",
                "createDate": "2023-10-27T10:30:00"
            }
        }
    )

class LoginResultDto(BaseModel):
    """登录结果响应 DTO"""
    user_info: UserInfoDto = Field(..., description="用户信息", alias="userInfo")
    access_token: str = Field(..., description="访问令牌", alias="accessToken")
    expires_in: int = Field(..., description="令牌过期时间 (秒)", alias="expiresIn")

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda field_name: field_name.replace('_', ' ').title().replace(' ', ''), # 自动转 camelCase
        json_schema_extra={
            "example": {
                "userInfo": UserInfoDto.model_config['json_schema_extra']['example'],
                "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "expiresIn": 3600
            }
        }
    )