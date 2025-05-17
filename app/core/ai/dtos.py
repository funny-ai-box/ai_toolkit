# app/core/ai/dtos.py
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
from typing import List, Optional, Union

# --- 枚举 ---
class ChatRoleType(str, Enum):
    """对话角色类型"""
    SYSTEM = 0
    ASSISTANT = 1
    USER = 2
    # OpenAI 还支持 Tool Role，如果需要可以添加
    # TOOL = "tool"

# --- DTOs ---
class ChatAIUploadFileDto(BaseModel):
    """AI 上传文件结果 DTO"""
    mime_type: Optional[str] = Field(None, description="文件 MIME 类型", alias="mimeType")
    uri: Optional[str] = Field(None, description="文件 URI 或标识符") # 不同服务返回的可能不同

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda field_name: field_name.replace('_', ' ').title().replace(' ', ''),
        json_schema_extra={
            "example": {
                "mimeType": "image/png",
                "uri": "file-xyzabc123" # 示例 ID
            }
        }
    )

class UserDocsVectorSearchResult(BaseModel):
    """用户文档向量搜索结果 DTO"""
    id: int = Field(..., description="向量数据库中的唯一 ID") # Milvus 返回的是 long/int
    document_id: int = Field(..., description="关联的文档 ID", alias="documentId") # C# 是 long
    content: Optional[str] = Field(None, description="匹配到的文本内容片段")
    score: float = Field(..., description="相似度得分 (通常在 0 到 1 或更高，取决于度量)")

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

# --- 输入消息结构 (对应 C# InputMessage) ---
class InputContentType(str, Enum):
    """输入内容块的类型"""
    TEXT = "text"
    IMAGE = "image"
    # C# 中还有 tool_use, tool_result 等，按需添加
    # TOOL_USE = "tool_use"
    # TOOL_RESULT = "tool_result"

class InputImageSourceType(str, Enum):
    """输入图片源的类型"""
    BASE64 = "base64"
    URL = "url"

class InputImageSource(BaseModel):
    """输入图片的来源定义"""
    type: InputImageSourceType = Field(..., description="图片来源类型 (base64 或 url)")
    media_type: str = Field(..., description="图片的 MIME 类型 (例如 'image/jpeg', 'image/png')", alias="mediaType")
    # 根据 type 选择 url 或 data
    url: Optional[str] = Field(None, description="图片 URL (如果 type 是 'url')")
    data: Optional[str] = Field(None, description="Base64 编码的图片数据 (如果 type 是 'base64')")

    # 添加验证逻辑，确保 url 或 data 至少有一个，且与 type 匹配
    # ... (可以使用 Pydantic 的 root_validator 或 model_validator)

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda field_name: field_name.replace('_', ' ').title().replace(' ', ''),
    )

class InputContentBase(BaseModel):
    """输入内容块的基类 (Pydantic 不直接支持抽象基类，用 Union 代替)"""
    # Pydantic 中通常使用 Union 来表示多种可能的类型
    # 这里我们为 Text 和 Image 创建具体类
    pass

class InputTextContent(InputContentBase):
    """文本类型的输入内容"""
    type: InputContentType = Field(InputContentType.TEXT, description="内容类型", Literal=True)
    text: str = Field(..., description="文本内容")

class InputImageContent(InputContentBase):
    """图片类型的输入内容"""
    type: InputContentType = Field(InputContentType.IMAGE, description="内容类型", Literal=True)
    source: InputImageSource = Field(..., description="图片来源信息")

# 使用 Union 来定义 InputMessage 中的 content 字段可以包含哪些类型
AnyInputContent = Union[InputTextContent, InputImageContent]

class InputMessage(BaseModel):
    """发送给 AI 的单条输入消息"""
    role: ChatRoleType = Field(..., description="消息发送者的角色 (system, user, assistant)")
    content: List[AnyInputContent] = Field(..., description="消息内容块列表 (可以包含文本和图片)")

    # 便捷构造函数 (可以在服务层或调用处创建)
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