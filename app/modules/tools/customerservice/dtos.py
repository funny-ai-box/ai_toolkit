"""
客服模块的数据传输对象
"""
import datetime
from enum import Enum
from typing import List, Optional, Any, Dict

from pydantic import BaseModel, Field, validator, HttpUrl


class ChatSessionListRequestDto(BaseModel):
    """聊天会话列表请求DTO"""
    page_index: int = Field(1, alias="pageIndex")
    page_size: int = Field(20, alias="pageSize")
    include_ended: bool = Field(True, alias="includeEnded")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "pageIndex": 1,
                "pageSize": 20,
                "includeEnded": True
            }
        }


class ChatSessionListItemDto(BaseModel):
    """聊天会话列表项DTO"""
    id: int
    user_name: Optional[str] = Field(None, alias="userName")
    session_name: Optional[str] = Field(None, alias="sessionName")
    status: int
    session_key: Optional[str] = Field(None, alias="sessionKey")
    last_message: Optional[str] = Field(None, alias="lastMessage")
    last_message_time: Optional[datetime.datetime] = Field(None, alias="lastMessageTime")
    create_date: datetime.datetime = Field(..., alias="createDate")
    last_modify_date: datetime.datetime = Field(..., alias="lastModifyDate")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": 1234567890,
                "userName": "张三",
                "sessionName": "张三的会话",
                "status": 1,
                "sessionKey": "abc123def456",
                "lastMessage": "有什么可以帮您的吗？",
                "lastMessageTime": "2023-01-01T12:00:00",
                "createDate": "2023-01-01T10:00:00",
                "lastModifyDate": "2023-01-01T12:00:00"
            }
        }


class ChatSessionDto(BaseModel):
    """聊天会话DTO"""
    id: int
    user_id: int = Field(..., alias="userId")
    user_name: Optional[str] = Field(None, alias="userName")
    session_name: Optional[str] = Field(None, alias="sessionName")
    status: int
    session_key: Optional[str] = Field(None, alias="sessionKey")
    recent_history: Optional[List["ChatHistoryDto"]] = Field(None, alias="recentHistory")
    create_date: datetime.datetime = Field(..., alias="createDate")
    last_modify_date: datetime.datetime = Field(..., alias="lastModifyDate")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": 1234567890,
                "userId": 987654321,
                "userName": "张三",
                "sessionName": "张三的会话",
                "status": 1,
                "sessionKey": "abc123def456",
                "recentHistory": [],
                "createDate": "2023-01-01T10:00:00",
                "lastModifyDate": "2023-01-01T12:00:00"
            }
        }


class ChatSessionCreateDto(BaseModel):
    """聊天会话创建请求DTO"""
    user_name: Optional[str] = Field(None, alias="userName")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "userName": "张三"
            }
        }


class ChatHistoryListRequestDto(BaseModel):
    """聊天历史列表请求DTO"""
    session_id: int = Field(..., alias="sessionId")
    page_index: int = Field(1, alias="pageIndex")
    page_size: int = Field(20, alias="pageSize")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "sessionId": 1234567890,
                "pageIndex": 1,
                "pageSize": 20
            }
        }


class ChatHistoryDto(BaseModel):
    """聊天历史DTO"""
    id: int
    session_id: int = Field(..., alias="sessionId")
    role: str
    content: Optional[str] = None
    intent: Optional[str] = None
    call_datas: Optional[str] = Field(None, alias="callDatas")
    image_url: Optional[str] = Field(None, alias="imageUrl")
    create_date: datetime.datetime = Field(..., alias="createDate")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": 1234567890,
                "sessionId": 987654321,
                "role": "assistant",
                "content": "有什么可以帮您的吗？",
                "intent": "GREETING",
                "callDatas": "",
                "imageUrl": None,
                "createDate": "2023-01-01T10:00:00"
            }
        }


class ChatMessageRequestDto(BaseModel):
    """聊天消息请求DTO"""
    session_id: int = Field(..., alias="sessionId")
    content: str

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "sessionId": 1234567890,
                "content": "我想了解一下你们的商品"
            }
        }


class ChatMessageResultDto(BaseModel):
    """聊天消息结果DTO"""
    message_id: Optional[int] = Field(None, alias="messageId")
    session_id: int = Field(..., alias="sessionId")
    reply: Optional[str] = None
    intent: Optional[str] = None
    call_datas: Optional[str] = Field(None, alias="callDatas")
    success: bool
    error_message: Optional[str] = Field(None, alias="errorMessage")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "messageId": 1234567890,
                "sessionId": 987654321,
                "reply": "我们有很多商品，您想了解哪类商品呢？",
                "intent": "PRODUCT_INQUIRY",
                "callDatas": "",
                "success": True,
                "errorMessage": None
            }
        }


class MessageChunkDto(BaseModel):
    """消息块DTO"""
    id: Optional[str] = None
    session_id: int = Field(..., alias="sessionId")
    event: Optional[str] = None
    data: Optional[str] = None

    class Config:
        populate_by_name = True


class IntentRecognitionResultDto(BaseModel):
    """意图识别结果DTO"""
    intent: Optional[str] = None
    context: Optional[str] = None
    id_datas: Optional[List[str]] = Field(None, alias="idDatas")

    class Config:
        populate_by_name = True


class ImageAnalysisResultDto(BaseModel):
    """图片分析结果DTO"""
    description: Optional[str] = None
    tags: Optional[List[str]] = None

    class Config:
        populate_by_name = True


class ConnectionRequestDto(BaseModel):
    """实时连接建立请求DTO"""
    session_id: int = Field(..., alias="sessionId")
    connection_id: str = Field(..., alias="connectionId")
    client_type: str = Field(..., alias="clientType")

    class Config:
        populate_by_name = True


class ProductListRequestDto(BaseModel):
    """商品列表请求DTO"""
    keyword: Optional[str] = None
    page_index: int = Field(1, alias="pageIndex")
    page_size: int = Field(20, alias="pageSize")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "keyword": None,
                "pageIndex": 1,
                "pageSize": 20
            }
        }


class ProductListItemDto(BaseModel):
    """商品列表项DTO"""
    id: int
    code: Optional[str] = None
    name: Optional[str] = None
    price: float
    stock: int
    status: int
    main_image_url: Optional[str] = Field(None, alias="mainImageUrl")
    create_date: datetime.datetime = Field(..., alias="createDate")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": 1234567890,
                "code": "PRD001",
                "name": "智能手表",
                "price": 999.99,
                "stock": 100,
                "status": 1,
                "mainImageUrl": "https://example.com/images/watch.jpg",
                "createDate": "2023-01-01T10:00:00"
            }
        }


class ProductImageDto(BaseModel):
    """商品图片DTO"""
    id: int
    product_id: int = Field(..., alias="productId")
    image_url: Optional[str] = Field(None, alias="imageUrl")
    sort_order: int = Field(0, alias="sortOrder")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": 1234567890,
                "productId": 987654321,
                "imageUrl": "https://example.com/images/watch.jpg",
                "sortOrder": 0
            }
        }


class ProductDetailDto(BaseModel):
    """商品详情DTO"""
    id: int
    code: Optional[str] = None
    name: Optional[str] = None
    price: float
    description: Optional[str] = None
    selling_points: Optional[str] = Field(None, alias="sellingPoints")
    stock: int
    status: int
    images: Optional[List[ProductImageDto]] = None
    create_date: datetime.datetime = Field(..., alias="createDate")
    last_modify_date: datetime.datetime = Field(..., alias="lastModifyDate")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": 1234567890,
                "code": "PRD001",
                "name": "智能手表",
                "price": 999.99,
                "description": "一款智能手表，支持多种运动模式",
                "sellingPoints": "防水、续航长、健康监测",
                "stock": 100,
                "status": 1,
                "images": [
                    {
                        "id": 1,
                        "productId": 1234567890,
                        "imageUrl": "https://example.com/images/watch.jpg",
                        "sortOrder": 0
                    }
                ],
                "createDate": "2023-01-01T10:00:00",
                "lastModifyDate": "2023-01-01T12:00:00"
            }
        }


class GetProductByCodeRequestDto(BaseModel):
    """根据商品编码获取商品请求DTO"""
    code: str

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "code": "PRD001"
            }
        }


class ProductCreateDto(BaseModel):
    """商品创建DTO"""
    code: str
    name: str
    price: float
    description: Optional[str] = None
    selling_points: Optional[str] = Field(None, alias="sellingPoints")
    stock: int
    status: int = 1

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "code": "PRD001",
                "name": "智能手表",
                "price": 999.99,
                "description": "一款智能手表，支持多种运动模式",
                "sellingPoints": "防水、续航长、健康监测",
                "stock": 100,
                "status": 1
            }
        }


class ProductSearchRequestDto(BaseModel):
    """商品搜索请求DTO"""
    keyword: str
    page_index: int = Field(1, alias="pageIndex")
    page_size: int = Field(20, alias="pageSize")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "keyword": "手表",
                "pageIndex": 1,
                "pageSize": 20
            }
        }


class ProductUpdateDto(BaseModel):
    """商品更新DTO"""
    id: int
    code: Optional[str] = None
    name: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    selling_points: Optional[str] = Field(None, alias="sellingPoints")
    stock: Optional[int] = None
    status: Optional[int] = None

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": 1234567890,
                "code": "PRD001",
                "name": "智能手表Pro",
                "price": 1299.99,
                "description": "升级版智能手表，支持更多功能",
                "sellingPoints": "防水、续航长、健康监测、GPS定位",
                "stock": 50,
                "status": 1
            }
        }


class ProductStatusUpdateDto(BaseModel):
    """商品状态更新DTO"""
    id: int
    status: int

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": 1234567890,
                "status": 0
            }
        }


class ProductImageUploadDto(BaseModel):
    """商品图片上传DTO"""
    product_id: int = Field(..., alias="productId")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "productId": 1234567890
            }
        }


class ProductImageDeleteDto(BaseModel):
    """商品图片删除DTO"""
    product_id: int = Field(..., alias="productId")
    image_id: int = Field(..., alias="imageId")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "productId": 1234567890,
                "imageId": 9876543210
            }
        }


# 注册循环引用关系
ChatSessionDto.update_forward_refs()