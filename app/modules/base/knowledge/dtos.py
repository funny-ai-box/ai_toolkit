# app/modules/base/knowledge/dtos.py
from pydantic import BaseModel, Field, ConfigDict, AnyHttpUrl, field_validator, model_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum, IntEnum 

from app.core.dtos import BasePageRequestDto # 导入核心分页请求 DTO
from app.core.dtos import DocumentAppType # 导入核心应用类型枚举

# --- 枚举 (从 models.py 移到这里或共享 core DTO，这里先放 DTO) ---
class DocumentStatus(IntEnum):
    """文档状态枚举"""
    PENDING = 0         # 待处理
    PROCESSING = 1      # 处理中
    COMPLETED = 2       # 处理完成
    FAILED = 3          # 处理失败

class DocumentLogType(IntEnum):
    """文档日志类型枚举"""
    DOCUMENT_PARSING = 1    # 文档解析
    VECTORIZATION = 2       # 向量化
    GRAPH = 3               # 图谱化

# --- 请求 DTOs ---
class PageUrlImportRequestDto(BaseModel):
    """网页导入请求 DTO"""
    url: AnyHttpUrl = Field(..., description="要导入的网页 URL") # 使用 AnyHttpUrl 进行验证
    title: Optional[str] = Field(None, max_length=255, description="文档标题 (可选，默认使用网页标题或域名)")
    app_type: DocumentAppType = Field(..., description="知识所属应用源", alias="appType")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "url": "https://www.example.com/article",
                "title": "示例文章标题",
                "appType": "PKB"
            }
        }
    )

class DocumentListRequestDto(BasePageRequestDto): # 继承核心分页 DTO
    """获取文档列表请求 DTO"""
    app_type: DocumentAppType = Field(..., description="要查询的应用类型", alias="appType")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "appType": "PKB",
                "pageIndex": 1,
                "pageSize": 10
            }
        }
    )

# --- 响应 DTOs ---

class KnowledgeGraphDto(BaseModel):
    """知识图谱响应 DTO"""
    id: int = Field(..., description="知识图谱数据库 ID")
    document_id: int = Field(..., description="关联的文档 ID", alias="documentId")
    summary: Optional[str] = Field(None, description="AI 生成的内容摘要")
    keywords: Optional[str] = Field(None, description="提取的关键词列表")
    mind_map: Optional[str] = Field(None, description="知识脑图结构 (JSON 对象)", alias="mindMap")

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda field_name: field_name.replace('_', ' ').title().replace(' ', '')
    )


class DocumentDetailResponseDto(BaseModel):
    """文档详情响应 DTO"""
    id: int = Field(..., description="文档 ID")
    title: Optional[str] = Field(None, description="文档标题")
    type: Optional[str] = Field(None, description="来源类型 (file, url)")
    app_type: DocumentAppType = Field(..., description="所属应用源", alias="appType")
    original_name: Optional[str] = Field(None, description="原始文件名 (如果是文件类型)", alias="originalName")
    cdn_url: Optional[str] = Field(None, description="文件 CDN 或本地访问 URL", alias="cdnUrl")
    source_url: Optional[str] = Field(None, description="来源网页 URL (如果是 URL 类型)", alias="sourceUrl")
    file_size: int = Field(0, description="文件大小 (字节)", alias="fileSize") # C# 是 long
    content_length: int = Field(0, description="解析后的内容字符数", alias="contentLength")
    status: DocumentStatus = Field(..., description="文档解析状态")
    status_name: str = Field("", description="状态名称", alias="statusName")
    process_message: Optional[str] = Field(None, description="文档解析处理消息", alias="processMessage")
    vector_status: DocumentStatus = Field(..., description="向量化状态", alias="vectorStatus")
    vector_status_name: str = Field("", description="向量化状态名称", alias="vectorStatusName")
    vector_message: Optional[str] = Field(None, description="向量化处理消息", alias="vectorMessage")
    graph_status: DocumentStatus = Field(..., description="图谱化状态", alias="graphStatus")
    graph_status_name: str = Field("", description="图谱化状态名称", alias="graphStatusName")
    graph_message: Optional[str] = Field(None, description="图谱化处理消息", alias="graphMessage")
    create_date: datetime = Field(..., description="文档创建时间", alias="createDate")
    content: Optional[str] = Field(None, description="解析后的文档内容 (可选)")
    knowledge_graph: Optional[KnowledgeGraphDto] = Field(None, description="知识图谱信息", alias="knowledgeGraph")

    # 使用 model_validator 计算 name 字段
    @model_validator(mode='after')
    def set_status_names(self) -> 'DocumentDetailResponseDto':
        self.status_name = self.status.name if self.status else ""
        self.vector_status_name = self.vector_status.name if self.vector_status else ""
        self.graph_status_name = self.graph_status.name if self.graph_status else ""
        return self

    model_config = ConfigDict(
        populate_by_name=True,
        # use_enum_values=False,
        # # alias_generator=lambda field_name: field_name.replace('_', ' ').title().replace(' ', ''), # 使用 Field alias 更好控制
        # json_encoders={ # 定义 JSON 编码器，将枚举转为名称字符串
        #      DocumentStatus: lambda v: v.name,
        #      DocumentLogType: lambda v: v.name,
        #      DocumentAppType: lambda v: v.name, # 也可以在这里处理 AppType
        # }
        # json_schema_extra={
        #     "example": {
        #         "id": 123,
        #         "title": "示例文件",
        #         "type": "file",
        #         "appType": "PKB",
        #         "originalName": "example.pdf",
        #         "cdnUrl": "http://localhost:57460/uploads/documents/1/guid.pdf",
        #         "sourceUrl": None,
        #         "fileSize": 102400,
        #         "contentLength": 5000,
        #         "status": "Completed",
        #         "statusName": "Completed",
        #         "processMessage": None,
        #         "vectorStatus": "Completed",
        #         "vectorStatusName": "Completed",
        #         "vectorMessage": None,
        #         "graphStatus": "Pending",
        #         "graphStatusName": "Pending",
        #         "graphMessage": None,
        #         "createDate": "2023-10-27T11:00:00",
        #         "content": "这是提取的文档内容...",
        #         "knowledgeGraph": KnowledgeGraphDto.model_config['json_schema_extra']['example']
        #     }
        # }
    )

class DocumentStatusResponseDto(BaseModel):
    """文档处理状态响应 DTO"""
    id: int = Field(..., description="文档 ID")
    title: Optional[str] = Field(None, description="文档标题")
    type: Optional[str] = Field(None, description="来源类型 (file, url)")
    app_type: DocumentAppType = Field(..., description="所属应用源", alias="appType")
    status: DocumentStatus = Field(..., description="文档解析状态")
    status_name: str = Field("", description="状态名称", alias="statusName")
    process_message: Optional[str] = Field(None, description="文档解析处理消息", alias="processMessage")
    vector_status: DocumentStatus = Field(..., description="向量化状态", alias="vectorStatus")
    vector_status_name: str = Field("", description="向量化状态名称", alias="vectorStatusName")
    vector_message: Optional[str] = Field(None, description="向量化处理消息", alias="vectorMessage")
    graph_status: DocumentStatus = Field(..., description="图谱化状态", alias="graphStatus")
    graph_status_name: str = Field("", description="图谱化状态名称", alias="graphStatusName")
    graph_message: Optional[str] = Field(None, description="图谱化处理消息", alias="graphMessage")

    # @model_validator(mode='after')
    # def set_status_names(self) -> 'DocumentStatusResponseDto':
    #     self.status_name = self.status.value if self.status else ""
    #     self.vector_status_name = self.vector_status.value if self.vector_status else ""
    #     self.graph_status_name = self.graph_status.value if self.graph_status else ""
    #     return self

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=False,
        # alias_generator=lambda fn: fn.replace('_n','N'), # 示例
        json_encoders={DocumentStatus: lambda v: v.name, DocumentAppType: lambda v: v.name}
        #  json_schema_extra={
        #      "example": {
        #          "id": 123, "title": "示例", "type": "file", "appType": "PKB",
        #          "status": "Processing", "statusName": "Processing", "processMessage": "正在解析...",
        #          "vectorStatus": "Pending", "vectorStatusName": "Pending", "vectorMessage": None,
        #          "graphStatus": "Pending", "graphStatusName": "Pending", "graphMessage": None
        #     }
        # }
    )


class DocumentListItemDto(BaseModel):
    """文档列表项响应 DTO"""
    id: int = Field(..., description="文档 ID")
    title: Optional[str] = Field(None, description="文档标题")
    type: Optional[str] = Field(None, description="来源类型 (file, url)")
    app_type: DocumentAppType = Field(..., description="所属应用源", alias="appType")
    original_name: Optional[str] = Field(None, description="原始文件名", alias="originalName")
    content_length: int = Field(0, description="内容字符数", alias="contentLength")
    file_size: int = Field(0, description="文件大小 (字节)", alias="fileSize")
    source_url: Optional[str] = Field(None, description="来源网页 URL", alias="sourceUrl")
    status: DocumentStatus = Field(..., description="文档解析状态")
    status_name: str = Field("", description="状态名称", alias="statusName")
    vector_status: DocumentStatus = Field(..., description="向量化状态", alias="vectorStatus")
    vector_status_name: str = Field("", description="向量化状态名称", alias="vectorStatusName")
    create_date: datetime = Field(..., description="创建时间", alias="createDate")
     
    @model_validator(mode='after')
    def set_status_names(self) -> 'DocumentListItemDto':
        self.status_name = self.status.name if self.status else ""
        self.vector_status_name = self.vector_status.name if self.vector_status else ""
        return self

    # model_config = ConfigDict(
    #     populate_by_name=True,
    #     # use_enum_values=False,
    #     # json_encoders={DocumentStatus: lambda v: v.name, DocumentAppType: lambda v: v.name}
    #     #  json_schema_extra={
    #     #      "example": {
    #     #          "id": 123, "title": "示例文件", "type": "file", "appType": "PKB",
    #     #          "originalName": "example.pdf", "contentLength": 5000, "fileSize": 102400,
    #     #          "sourceUrl": None, "status": "Completed", "statusName": "Completed",
    #     #          "vectorStatus": "Completed", "vectorStatusName": "Completed",
    #     #          "createDate": "2023-10-27T11:00:00"
    #     #     }
    #     # }
    # )

class DocumentLogItemDto(BaseModel):
    """文档日志列表项响应 DTO"""
    id: int = Field(..., description="日志 ID")
    log_type: DocumentLogType = Field(..., description="日志类型", alias="logType")
    log_type_name: str = Field("", description="日志类型名称", alias="logTypeName")
    message: Optional[str] = Field(None, description="日志消息")
    create_date: datetime = Field(..., description="日志创建时间", alias="createDate")

    @model_validator(mode='after')
    def set_log_type_name(self) -> 'DocumentLogItemDto':
        self.log_type_name = self.log_type.name if self.log_type else ""
        return self

class DocumentContentDto(BaseModel):
    """文档内容响应 DTO"""
    id: int = Field(..., description="文档 ID")
    content: Optional[str] = Field(None, description="文档内容")