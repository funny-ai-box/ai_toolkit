import datetime
from typing import Optional, List, Annotated # Added Annotated
from pydantic import (
    BaseModel, Field, HttpUrl, ConfigDict, # Added ConfigDict, removed conint, constr
    StringConstraints # Added StringConstraints
)
from pydantic.alias_generators import to_camel # For consistent camelCase aliasing

from app.modules.tools.podcast.models import (
    PodcastTaskStatus, PodcastTaskContentType, AudioStatusType, PodcastRoleType, VoiceGenderType
)
# Assuming DocumentStatus is imported from knowledge module's DTOs or models
from app.modules.base.knowledge.dtos import  DocumentStatus # Or directly from knowledge.models if preferred

model_config = ConfigDict(alias_generator=lambda s: ''.join([s[0].lower(), *[c if c.islower() else f'{c}' for c in s[1:]]]), populate_by_name=True)
class CreatePodcastRequestDto(BaseModel):
    """创建播客请求DTO"""
    title: Annotated[str, StringConstraints(min_length=2, max_length=255)] = Field(..., description="播客标题")
    description: Annotated[str, StringConstraints(max_length=1000)] = Field(..., description="播客描述")
    scene: Annotated[str, StringConstraints(min_length=2, max_length=100)] = Field(..., description="播客场景/主题")
    atmosphere: Annotated[str, StringConstraints(min_length=2, max_length=100)] = Field(..., description="播客氛围")
    guest_count: int = Field(1, ge=0, le=3, description="嘉宾数量 (默认为1)")

    model_config = model_config


class ImportPodcastUrlRequestDto(BaseModel):
    """播客导入网页请求DTO"""
    id: int = Field(..., description="播客ID")
    url: HttpUrl = Field(..., description="网页URL")

    model_config = model_config

class ImportPodcastTextRequestDto(BaseModel):
    """播客导入文本请求DTO"""
    id: int = Field(..., description="播客ID")
    text: Annotated[str, StringConstraints(max_length=20000)] = Field(..., description="文本内容")

    model_config = model_config


class PodcastContentItemDto(BaseModel):
    """播客内容项DTO"""
    id: int = Field(..., description="内容项ID")
    content_type: PodcastTaskContentType = Field(..., description="内容类型") # Alias contentType by to_camel
    source_document_id: Optional[int] = Field(None, description="源文档ID (如果是上传文档或URL)") # Alias sourceDocumentId
    source_content: Optional[str] = Field(None, description="文本或文件或网页的内容摘要或URL") # Alias sourceContent
    source_document_title: Optional[str] = Field(None, description="文档标题") # Alias sourceDocumentTitle
    source_document_original_name: Optional[str] = Field(None, description="文档原始文件名") # Alias sourceDocumentOriginalName
    source_document_source_url: Optional[HttpUrl] = Field(None, description="文档来源链接") # Alias sourceDocumentSourceUrl
    source_document_status: Optional[DocumentStatus] = Field(None, description="文档处理进度") # Alias sourceDocumentStatus
    source_document_process_message: Optional[str] = Field(None, description="文档处理进度消息") # Alias sourceDocumentProcessMessage
    create_date: datetime.datetime = Field(..., description="创建时间") # Alias createDate

    model_config = model_config



class PodcastScriptItemDto(BaseModel):
    """播客脚本项DTO"""
    id: int = Field(..., description="脚本项ID")
    sequence_number: int = Field(..., description="顺序号") # Alias sequenceNumber
    role_type: PodcastRoleType = Field(..., description="角色类型") # Alias roleType
    role_type_description: Optional[str] = Field(None, description="角色类型描述") # Alias roleTypeDescription
    role_name: Optional[str] = Field(None, description="角色名称") # Alias roleName
    voice_symbol: Optional[str] = Field(None, description="语音角色标识符") # Alias voiceSymbol
    voice_name: Optional[str] = Field(None, description="语音名称") # Alias voiceName
    voice_description: Optional[str] = Field(None, description="语音描述") # Alias voiceDescription
    audio_duration: datetime.timedelta = Field(..., description="语音时长") # Alias audioDuration
    content: Optional[str] = Field(None, description="脚本内容 (无SSML)")
    audio_url: Optional[str] = Field(None, description="语音文件URL") # Alias audioUrl
    audio_status: AudioStatusType = Field(..., description="语音生成状态") # Alias audioStatus
    audio_status_description: Optional[str] = Field(None, description="语音状态描述") # Alias audioStatusDescription

    model_config = model_config



class PodcastDetailDto(BaseModel):
    """播客详情DTO"""
    id: int = Field(..., description="播客ID")
    title: Optional[str] = Field(None, description="播客标题")
    description: Optional[str] = Field(None, description="播客描述")
    scene: Optional[str] = Field(None, description="播客场景/主题")
    atmosphere: Optional[str] = Field(None, description="播客氛围")
    guest_count: int = Field(..., description="嘉宾数量") # Alias guestCount
    generate_count: int = Field(..., description="生成次数") # Alias generateCount
    progress_step: int = Field(..., description="进度 (0-100)") # Alias progressStep
    status: PodcastTaskStatus = Field(..., description="处理状态")
    status_description: Optional[str] = Field(None, description="状态描述") # Alias statusDescription
    error_message: Optional[str] = Field(None, description="错误消息") # Alias errorMessage
    content_items: Optional[List[PodcastContentItemDto]] = Field(None, description="内容项列表") # Alias contentItems
    script_items: Optional[List[PodcastScriptItemDto]] = Field(None, description="脚本项列表") # Alias scriptItems
    create_date: datetime.datetime = Field(..., description="创建时间") # Alias createDate

    model_config = model_config
  


class PodcastListRequestDto(BaseModel):
    """播客列表请求DTO"""
    page_index: int = Field(1, ge=1, description="页码") # Alias pageIndex
    page_size: int = Field(20, ge=1, le=100, description="每页数量") # Alias pageSize

    model_config = model_config

class PodcastListItemDto(BaseModel):
    """播客列表项DTO"""
    id: int
    title: Optional[str] = None
    description: Optional[str] = None
    scene: Optional[str] = None
    atmosphere: Optional[str] = None
    guest_count: int = Field(..., description="嘉宾数量") # Alias guestCount
    progress_step: int = Field(..., description="进度") # Alias progressStep
    generate_count: int = Field(..., description="生成次数") # Alias generateCount
    status: PodcastTaskStatus
    status_description: Optional[str] = Field(None, description="状态描述") # Alias statusDescription
    content_item_count: int = Field(..., description="内容项数量") # Alias contentItemCount
    script_item_count: int = Field(..., description="脚本项数量") # Alias scriptItemCount
    create_date: datetime.datetime = Field(..., description="创建时间") # Alias createDate

    model_config = model_config

class TtsVoiceDefinitionDto(BaseModel):
    """TTS语音角色定义DTO (for API response)"""
    id: int
    voice_symbol: Optional[str] = Field(None, description="语音角色标识符") # Alias voiceSymbol
    name: Optional[str] = None
    locale: Optional[str] = None
    gender: VoiceGenderType
    description: Optional[str] = None

    model_config = model_config


class GetVoicesByLocaleRequestDto(BaseModel):
    """获取指定语言语音列表请求DTO"""
    locale: Optional[str] = Field(None, description="语言/地区 (如zh-CN, en-US等)")

    model_config = model_config




class PodcastScriptRawItemDto(BaseModel):
    """AI生成的播客脚本原始数据DTO"""
    role_type: Optional[str] = Field(None, description="角色类型：host 或 guest") # Alias roleType
    role_name: Optional[str] = Field(None, description="角色名称") # Alias roleName
    voice_symbol: Optional[str] = Field(None, description="语音角色标识符") # Alias voiceSymbol
    content: Optional[str] = Field(None, description="脚本内容 (可能包含SSML)")
    no_ssml_content: Optional[str] = Field(None, description="脚本内容 (无SSML标记)") # Alias noSsmlContent

    model_config = model_config

