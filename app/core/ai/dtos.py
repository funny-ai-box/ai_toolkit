# app/core/ai/dtos.py
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum, IntEnum
from typing import List, Optional, Union

# --- 枚举 ---
class ChatRoleType(IntEnum):
    """对话角色类型 - 使用整型以便数据库存储"""
    SYSTEM = 0      # 系统
    USER = 1        # 用户  
    ASSISTANT = 2   # AI助手
    
    @property
    def openai_role(self) -> str:
        """获取 OpenAI API 需要的字符串角色"""
        role_map = {
            ChatRoleType.SYSTEM: "system",
            ChatRoleType.USER: "user", 
            ChatRoleType.ASSISTANT: "assistant"
        }
        return role_map[self]
    
    @classmethod
    def from_openai_role(cls, role_str: str) -> 'ChatRoleType':
        """从 OpenAI 角色字符串转换为枚举"""
        role_map = {
            "system": cls.SYSTEM,
            "user": cls.USER,
            "assistant": cls.ASSISTANT
        }
        return role_map.get(role_str, cls.USER)
    
    def __str__(self) -> str:
        """返回字符串表示，用于向后兼容"""
        return self.openai_role

# --- DTOs ---
class ChatAIUploadFileDto(BaseModel):
    """AI 上传文件结果 DTO"""
    mime_type: Optional[str] = Field(None, description="文件 MIME 类型", alias="mimeType")
    uri: Optional[str] = Field(None, description="文件 URI 或标识符")

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda field_name: field_name.replace('_', ' ').title().replace(' ', ''),
        json_schema_extra={
            "example": {
                "mimeType": "image/png",
                "uri": "file-xyzabc123"
            }
        }
    )

class UserDocsVectorSearchResult(BaseModel):
    """用户文档向量搜索结果 DTO"""
    id: int = Field(..., description="向量数据库中的唯一 ID")
    document_id: int = Field(..., description="关联的文档 ID", alias="documentId")
    content: Optional[str] = Field(None, description="匹配到的文本内容片段")
    score: float = Field(..., description="相似度得分")

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda field_name: field_name.replace('_', ' ').title().replace(' ', ''),
        json_schema_extra={
            "example": {
                "id": 9876543210,
                "documentId": 1234567890,
                "content": "这是一个示例文本片段...",
                "score": 0.85
            }
        }
    )

# --- 输入消息结构 ---
class InputContentType(str, Enum):
    """输入内容块的类型"""
    TEXT = "text"
    IMAGE = "image"

class InputImageSourceType(str, Enum):
    """输入图片源的类型"""
    BASE64 = "base64"
    URL = "url"

class InputImageSource(BaseModel):
    """输入图片的来源定义"""
    type: InputImageSourceType = Field(..., description="图片来源类型")
    media_type: str = Field(..., description="图片的 MIME 类型", alias="mediaType")
    url: Optional[str] = Field(None, description="图片 URL")
    data: Optional[str] = Field(None, description="Base64 编码的图片数据")

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda field_name: field_name.replace('_', ' ').title().replace(' ', ''),
    )

class InputContentBase(BaseModel):
    """输入内容块的基类"""
    pass

class InputTextContent(InputContentBase):
    """文本类型的输入内容"""
    type: InputContentType = Field(InputContentType.TEXT, description="内容类型")
    text: str = Field(..., description="文本内容")

class InputImageContent(InputContentBase):
    """图片类型的输入内容"""
    type: InputContentType = Field(InputContentType.IMAGE, description="内容类型")
    source: InputImageSource = Field(..., description="图片来源信息")

class InputMessage(BaseModel):
    """发送给 AI 的单条输入消息"""
    role: ChatRoleType = Field(..., description="消息发送者的角色")
    content: List[Union[InputTextContent, InputImageContent]] = Field(..., description="消息内容块列表")

    @classmethod
    def from_text(cls, role: ChatRoleType, text: str) -> 'InputMessage':
        """从纯文本创建 InputMessage"""
        return cls(role=role, content=[InputTextContent(text=text)])

    @classmethod
    def from_text_and_image_urls(cls, role: ChatRoleType, text: Optional[str], image_urls: List[str], media_type: str = "image/jpeg") -> 'InputMessage':
        """从文本和图片 URL 创建 InputMessage"""
        content_parts: List[Union[InputTextContent, InputImageContent]] = []
        if text:
            content_parts.append(InputTextContent(text=text))
        for url in image_urls:
            content_parts.append(InputImageContent(
                source=InputImageSource(
                    type=InputImageSourceType.URL,
                    mediaType=media_type,
                    url=url
                )
            ))
        return cls(role=role, content=content_parts)

    @classmethod
    def from_text_and_image_base64(cls, role: ChatRoleType, text: Optional[str], image_base64s: List[str], media_type: str = "image/jpeg") -> 'InputMessage':
        """从文本和 Base64 图片数据创建 InputMessage"""
        content_parts: List[Union[InputTextContent, InputImageContent]] = []
        if text:
            content_parts.append(InputTextContent(text=text))
        for b64_data in image_base64s:
            content_parts.append(InputImageContent(
                source=InputImageSource(
                    type=InputImageSourceType.BASE64,
                    mediaType=media_type,
                    data=b64_data
                )
            ))
        return cls(role=role, content=content_parts)

# 其他内容保持不变...
class InputContentType(str, Enum):
    """输入内容块的类型"""
    TEXT = "text"
    IMAGE = "image"

class InputImageSourceType(str, Enum):
    """输入图片源的类型"""
    BASE64 = "base64"
    URL = "url"

class InputImageSource(BaseModel):
    """输入图片的来源定义"""
    type: InputImageSourceType = Field(..., description="图片来源类型 (base64 或 url)")
    media_type: str = Field(..., description="图片的 MIME 类型 (例如 'image/jpeg', 'image/png')", alias="mediaType")
    url: Optional[str] = Field(None, description="图片 URL (如果 type 是 'url')")
    data: Optional[str] = Field(None, description="Base64 编码的图片数据 (如果 type 是 'base64')")

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda field_name: field_name.replace('_', ' ').title().replace(' ', ''),
    )

class InputContentBase(BaseModel):
    """输入内容块的基类"""
    pass

class InputTextContent(InputContentBase):
    """文本类型的输入内容"""
    type: InputContentType = Field(InputContentType.TEXT, description="内容类型")
    text: str = Field(..., description="文本内容")

class InputImageContent(InputContentBase):
    """图片类型的输入内容"""
    type: InputContentType = Field(InputContentType.IMAGE, description="内容类型")
    source: InputImageSource = Field(..., description="图片来源信息")

AnyInputContent = Union[InputTextContent, InputImageContent]

class InputMessage(BaseModel):
    """发送给 AI 的单条输入消息"""
    role: ChatRoleType = Field(..., description="消息发送者的角色")
    content: List[AnyInputContent] = Field(..., description="消息内容块列表")

    @classmethod
    def from_text(cls, role: ChatRoleType, text: str) -> 'InputMessage':
        """从纯文本创建 InputMessage"""
        return cls(role=role, content=[InputTextContent(text=text)])


    @classmethod
    def from_text_and_image_urls(cls, role: ChatRoleType, text: Optional[str], image_urls: List[str], media_type: str = "image/jpeg") -> 'InputMessage':
        """从文本和图片 URL 创建 InputMessage"""
        content_parts: List[AnyInputContent] = []
        if text:
            content_parts.append(InputTextContent(text=text))
        for url in image_urls:
            content_parts.append(InputImageContent(
                source=InputImageSource(
                    type=InputImageSourceType.URL,
                    mediaType=media_type,
                    url=url
                )
            ))
        return cls(role=role, content=content_parts)

    @classmethod
    def from_text_and_image_base64(cls, role: ChatRoleType, text: Optional[str], image_base64s: List[str], media_type: str = "image/jpeg") -> 'InputMessage':
        """从文本和 Base64 图片数据创建 InputMessage"""
        content_parts: List[AnyInputContent] = []
        if text:
            content_parts.append(InputTextContent(text=text))
        for b64_data in image_base64s:
            content_parts.append(InputImageContent(
                source=InputImageSource(
                    type=InputImageSourceType.BASE64,
                    mediaType=media_type,
                    data=b64_data
                )
            ))
        return cls(role=role, content=content_parts)