"""
播客模块 DTO(数据传输对象)定义
"""
import datetime
from typing import List, Optional, Union
from pydantic import BaseModel, Field, HttpUrl, validator, StringConstraints, conint

from app.core.dtos import ApiResponse, PagedResultDto, BaseIdRequestDto
from app.modules.tools.podcast.constants import (
    PodcastTaskStatus, PodcastRoleType, AudioStatusType, 
    PodcastTaskContentType, VoiceGenderType
)


class CreatePodcastRequestDto(BaseModel):
    """创建播客请求DTO"""
    title: str = Field(
        description="播客标题", 
        min_length=2, 
        max_length=255
    )
    description: str = Field(
        description="播客描述", 
        max_length=1000
    )
    scene: str = Field(
        description="播客场景/主题", 
        min_length=2, 
        max_length=100
    )
    atmosphere: str = Field(
        description="播客氛围", 
        min_length=2, 
        max_length=100
    )
    guest_count: int = Field(
        default=1, 
        description="嘉宾数量", 
        ge=0, 
        le=3, 
        alias="guestCount"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "AI科技前沿探讨",
                "description": "探讨最新的AI技术发展和应用",
                "scene": "科技讨论",
                "atmosphere": "轻松专业",
                "guestCount": 2
            }
        }
    }


class ImportPodcastUrlRequestDto(BaseModel):
    """播客导入网页请求DTO"""
    id: int = Field(description="播客ID")
    url: HttpUrl = Field(description="网页URL")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 123456789,
                "url": "https://example.com/article"
            }
        }
    }


class ImportPodcastTextRequestDto(BaseModel):
    """播客导入文本请求DTO"""
    id: int = Field(description="播客ID")
    text: str = Field(
        description="文本内容", 
        max_length=20000
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 123456789,
                "text": "这是要导入的文本内容..."
            }
        }
    }


class PodcastListRequestDto(BaseModel):
    """播客列表请求DTO"""
    page_index: int = Field(
        default=1, 
        description="页码", 
        ge=1, 
        alias="pageIndex"
    )
    page_size: int = Field(
        default=20, 
        description="每页大小", 
        ge=1, 
        le=100, 
        alias="pageSize"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "pageIndex": 1,
                "pageSize": 20
            }
        }
    }


class GetVoicesByLocaleRequestDto(BaseModel):
    """获取指定语言语音列表请求DTO"""
    locale: str = Field(description="语言/地区（如zh-CN, en-US等）")

    model_config = {
        "json_schema_extra": {
            "example": {
                "locale": "zh-CN"
            }
        }
    }


class TtsVoiceDefinition(BaseModel):
    """语音角色定义DTO"""
    id: int
    voice_symbol: str = Field(alias="voiceSymbol")
    name: str
    locale: str
    gender: VoiceGenderType
    description: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 123456789,
                "voiceSymbol": "zh-CN-XiaoxiaoNeural",
                "name": "晓晓",
                "locale": "zh-CN",
                "gender": 2,
                "description": "女声，亲切自然"
            }
        }
    }


class PodcastContentItemDto(BaseModel):
    """播客内容项DTO"""
    id: int
    content_type: PodcastTaskContentType = Field(alias="contentType")
    source_document_id: int = Field(alias="sourceDocumentId")
    source_content: Optional[str] = Field(default=None, alias="sourceContent")
    source_document_title: Optional[str] = Field(default=None, alias="sourceDocumentTitle")
    source_document_original_name: Optional[str] = Field(default=None, alias="sourceDocumentOriginalName")
    source_document_source_url: Optional[str] = Field(default=None, alias="sourceDocumentSourceUrl")
    source_document_status: int = Field(alias="sourceDocumentStatus")
    source_document_process_message: Optional[str] = Field(default=None, alias="sourceDocumentProcessMessage")
    create_date: datetime.datetime = Field(alias="createDate")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 123456789,
                "contentType": 2,
                "sourceDocumentId": 987654321,
                "sourceContent": "文档内容...",
                "sourceDocumentTitle": "AI发展白皮书",
                "sourceDocumentOriginalName": "ai_whitepaper.pdf",
                "sourceDocumentSourceUrl": None,
                "sourceDocumentStatus": 2,
                "sourceDocumentProcessMessage": None,
                "createDate": "2023-10-01T12:00:00"
            }
        }
    }


class PodcastScriptItemDto(BaseModel):
    """播客脚本项DTO"""
    id: int
    sequence_number: int = Field(alias="sequenceNumber")
    role_type: PodcastRoleType = Field(alias="roleType")
    role_type_description: str = Field(alias="roleTypeDescription")
    role_name: str = Field(alias="roleName")
    voice_symbol: Optional[str] = Field(default=None, alias="voiceSymbol")
    voice_name: Optional[str] = Field(default=None, alias="voiceName")
    voice_description: Optional[str] = Field(default=None, alias="voiceDescription")
    content: Optional[str] = None
    audio_duration: Union[datetime.timedelta, float] = Field(alias="audioDuration")
    audio_url: Optional[str] = Field(default=None, alias="audioUrl")
    audio_status: AudioStatusType = Field(alias="audioStatus")
    audio_status_description: str = Field(alias="audioStatusDescription")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 123456789,
                "sequenceNumber": 1,
                "roleType": 1,
                "roleTypeDescription": "主持人",
                "roleName": "李主持",
                "voiceSymbol": "zh-CN-YunyangNeural",
                "voiceName": "云扬",
                "voiceDescription": "男声，专业",
                "content": "大家好，欢迎收听今天的播客...",
                "audioDuration": 12.5,
                "audioUrl": "https://example.com/audio/123.mp3",
                "audioStatus": 2,
                "audioStatusDescription": "已生成"
            }
        }
    }

    @validator("audio_duration", pre=True)
    def parse_duration(cls, v):
        """解析时长，支持timedelta对象或秒数"""
        if isinstance(v, datetime.timedelta):
            return v.total_seconds()
        return float(v)


class PodcastDetailDto(BaseModel):
    """播客详情DTO"""
    id: int
    title: str
    description: str
    scene: str
    atmosphere: str
    guest_count: int = Field(alias="guestCount")
    generate_count: int = Field(alias="generateCount")
    progress_step: int = Field(alias="progressStep")
    status: PodcastTaskStatus
    status_description: str = Field(alias="statusDescription")
    error_message: Optional[str] = Field(default=None, alias="errorMessage")
    content_items: List[PodcastContentItemDto] = Field(alias="contentItems")
    script_items: List[PodcastScriptItemDto] = Field(alias="scriptItems")
    create_date: datetime.datetime = Field(alias="createDate")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 123456789,
                "title": "AI科技前沿探讨",
                "description": "探讨最新的AI技术发展和应用",
                "scene": "科技讨论",
                "atmosphere": "轻松专业",
                "guestCount": 2,
                "generateCount": 1,
                "progressStep": 100,
                "status": 3,
                "statusDescription": "已完成",
                "errorMessage": None,
                "contentItems": [],  # 示例中省略具体内容
                "scriptItems": [],   # 示例中省略具体内容
                "createDate": "2023-10-01T12:00:00"
            }
        }
    }


class PodcastListItemDto(BaseModel):
    """播客列表项DTO"""
    id: int
    title: str
    description: str
    scene: str
    atmosphere: str
    guest_count: int = Field(alias="guestCount")
    progress_step: int = Field(alias="progressStep")
    generate_count: int = Field(alias="generateCount")
    status: PodcastTaskStatus
    status_description: str = Field(alias="statusDescription")
    content_item_count: int = Field(alias="contentItemCount")
    script_item_count: int = Field(alias="scriptItemCount")
    create_date: datetime.datetime = Field(alias="createDate")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 123456789,
                "title": "AI科技前沿探讨",
                "description": "探讨最新的AI技术发展和应用",
                "scene": "科技讨论",
                "atmosphere": "轻松专业",
                "guestCount": 2,
                "progressStep": 100,
                "generateCount": 1,
                "status": 3,
                "statusDescription": "已完成",
                "contentItemCount": 3,
                "scriptItemCount": 10,
                "createDate": "2023-10-01T12:00:00"
            }
        }
    }


class PodcastScriptRawItemDto(BaseModel):
    """播客脚本原始数据DTO (用于从AI获取的JSON脚本)"""
    role_type: str = Field(alias="roleType")
    role_name: str = Field(alias="roleName")
    voice_symbol: str = Field(alias="voiceSymbol")
    content: Optional[str] = None
    no_ssml_content: Optional[str] = Field(default=None, alias="noSsmlContent")

    model_config = {
        "json_schema_extra": {
            "example": {
                "roleType": "host",
                "roleName": "李主持",
                "voiceSymbol": "zh-CN-YunyangNeural",
                "content": "<speak><p>大家好，欢迎收听今天的播客...</p></speak>",
                "noSsmlContent": "大家好，欢迎收听今天的播客..."
            }
        }
    }


# API响应类型
PodcastDetailResponse = ApiResponse[PodcastDetailDto]
PodcastListResponse = ApiResponse[PagedResultDto[PodcastListItemDto]]
PodcastContentItemResponse = ApiResponse[PodcastContentItemDto]
TtsVoiceDefinitionListResponse = ApiResponse[List[TtsVoiceDefinition]]
BaseIdResponse = ApiResponse[BaseIdRequestDto]