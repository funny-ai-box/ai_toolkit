# app/modules/dataanalysis/dtos.py
import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict

# 基础请求 DTOs
class BaseIdRequestDto(BaseModel):
    """基础ID请求DTO"""
    id: int = Field(..., alias="id")
    
    model_config = ConfigDict(populate_by_name=True)

class BasePageRequestDto(BaseModel):
    """基础分页请求DTO"""
    page_index: int = Field(1, alias="pageIndex")
    page_size: int = Field(20, alias="pageSize")
    
    model_config = ConfigDict(populate_by_name=True)

# 文件上传 DTOs
class FileUploadResultDto(BaseModel):
    """文件上传结果DTO"""
    id: int = Field(..., alias="id")
    original_file_name: Optional[str] = Field(None, alias="originalFileName")
    file_type: Optional[str] = Field(None, alias="fileType")
    file_size: int = Field(..., alias="fileSize")
    status: str = Field(..., alias="status")
    upload_time: datetime.datetime = Field(..., alias="uploadTime")
    
    model_config = ConfigDict(populate_by_name=True)

class FileColumnDto(BaseModel):
    """文件列信息DTO"""
    id: int = Field(..., alias="id")
    column_name: Optional[str] = Field(None, alias="columnName")
    original_name: Optional[str] = Field(None, alias="originalName")
    description: Optional[str] = Field(None, alias="description")
    data_type: Optional[str] = Field(None, alias="dataType")
    column_index: int = Field(..., alias="columnIndex")
    
    model_config = ConfigDict(populate_by_name=True)

class FileDetailItemDto(BaseModel):
    """文件详情DTO"""
    id: int = Field(..., alias="id")
    original_file_name: Optional[str] = Field(None, alias="originalFileName")
    file_type: Optional[str] = Field(None, alias="fileType")
    file_size: int = Field(..., alias="fileSize")
    status: int = Field(..., alias="status")
    upload_time: datetime.datetime = Field(..., alias="uploadTime")
    table_id: Optional[int] = Field(None, alias="tableId")
    table_name: Optional[str] = Field(None, alias="tableName")
    display_name: Optional[str] = Field(None, alias="displayName")
    row_count: Optional[int] = Field(None, alias="rowCount")
    columns: Optional[List[FileColumnDto]] = Field(None, alias="columns")
    
    model_config = ConfigDict(populate_by_name=True)

class FileListItemDto(BaseModel):
    """文件列表项DTO"""
    id: int = Field(..., alias="id")
    original_file_name: Optional[str] = Field(None, alias="originalFileName")
    file_type: Optional[str] = Field(None, alias="fileType")
    file_size: int = Field(..., alias="fileSize")
    status: int = Field(..., alias="status")
    upload_time: datetime.datetime = Field(..., alias="uploadTime")
    table_id: Optional[int] = Field(None, alias="tableId")
    table_name: Optional[str] = Field(None, alias="tableName")
    display_name: Optional[str] = Field(None, alias="displayName")
    row_count: Optional[int] = Field(None, alias="rowCount")
    
    model_config = ConfigDict(populate_by_name=True)

# 临时数据表 DTOs
class TempDataDto(BaseModel):
    """临时数据表DTO"""
    data_json: Optional[str] = Field(None, alias="dataJson")
    row_count: Optional[int] = Field(None, alias="rowCount")
    table_name: Optional[str] = Field(None, alias="tableName")
    display_name: Optional[str] = Field(None, alias="displayName")
    total_row_count: Optional[int] = Field(None, alias="totalRowCount")
    execution_duration: Optional[int] = Field(None, alias="executionDuration")
    columns: Optional[List[FileColumnDto]] = Field(None, alias="columns")
    
    model_config = ConfigDict(populate_by_name=True)

# 数据表 DTOs
class DataTableListItemDto(BaseModel):
    """数据表列表项DTO"""
    id: int = Field(..., alias="id")
    upload_file_id: int = Field(..., alias="uploadFileId")
    table_name: Optional[str] = Field(None, alias="tableName")
    display_name: Optional[str] = Field(None, alias="displayName")
    row_count: int = Field(..., alias="rowCount")
    storage_type: Optional[str] = Field(None, alias="storageType")
    status: int = Field(..., alias="status")
    column_count: int = Field(..., alias="columnCount")
    create_time: datetime.datetime = Field(..., alias="createTime")
    
    model_config = ConfigDict(populate_by_name=True)

# 会话 DTOs
class CreateSessionDto(BaseModel):
    """创建会话请求DTO"""
    session_name: Optional[str] = Field(None, alias="sessionName")
    
    model_config = ConfigDict(populate_by_name=True)

class SessionListItemDto(BaseModel):
    """会话列表项DTO"""
    id: int = Field(..., alias="id")
    session_name: Optional[str] = Field(None, alias="sessionName")
    status: int = Field(..., alias="status")
    create_time: datetime.datetime = Field(..., alias="createTime")
    last_active_time: Optional[datetime.datetime] = Field(None, alias="lastActiveTime")
    
    model_config = ConfigDict(populate_by_name=True)

class AnalysisSessionDto(BaseModel):
    """分析会话DTO"""
    id: int = Field(..., alias="id")
    session_name: Optional[str] = Field(None, alias="sessionName")
    status: int = Field(..., alias="status")
    create_time: datetime.datetime = Field(..., alias="createTime")
    last_active_time: datetime.datetime = Field(..., alias="lastActiveTime")
    available_tables: Optional[List[DataTableListItemDto]] = Field(None, alias="availableTables")
    
    model_config = ConfigDict(populate_by_name=True)

# 查询 DTOs
class UserQueryDto(BaseModel):
    """用户查询DTO"""
    session_id: int = Field(..., alias="sessionId")
    file_id: int = Field(0, alias="fileId")
    query: str = Field(..., alias="query")
    
    model_config = ConfigDict(populate_by_name=True)

# 可视化 DTOs
class VisualizationDto(BaseModel):
    """可视化DTO"""
    id: int = Field(..., alias="id")
    sql_execution_id: int = Field(..., alias="sqlExecutionId")
    visualization_type: Optional[str] = Field(None, alias="visualizationType")
    chart_config: Optional[str] = Field(None, alias="chartConfig")
    html_path: Optional[str] = Field(None, alias="htmlPath")
    html_url: Optional[str] = Field(None, alias="htmlUrl")
    
    model_config = ConfigDict(populate_by_name=True)

# SQL执行 DTOs
class SqlExecutionDto(BaseModel):
    """SQL执行DTO"""
    id: int = Field(..., alias="id")
    sql_statement: Optional[str] = Field(None, alias="sqlStatement")
    data_json: Optional[str] = Field(None, alias="dataJson")
    execution_status: int = Field(..., alias="executionStatus")
    error_message: Optional[str] = Field(None, alias="errorMessage")
    execution_time: Optional[datetime.datetime] = Field(None, alias="executionTime")
    execution_duration: Optional[int] = Field(None, alias="executionDuration")
    row_count: Optional[int] = Field(None, alias="rowCount")
    visualization: Optional[VisualizationDto] = Field(None, alias="visualization")
    
    model_config = ConfigDict(populate_by_name=True)

# 会话 DTOs
class ConversationDto(BaseModel):
    """对话DTO"""
    id: int = Field(..., alias="id")
    session_id: int = Field(..., alias="sessionId")
    user_query: Optional[str] = Field(None, alias="userQuery")
    ai_response: Optional[str] = Field(None, alias="aiResponse")
    create_time: datetime.datetime = Field(..., alias="createTime")
    sql_executions: Optional[List[SqlExecutionDto]] = Field(None, alias="sqlExecutions")
    
    model_config = ConfigDict(populate_by_name=True)

class AiResponseDto(BaseModel):
    """AI响应DTO"""
    conversation_id: int = Field(..., alias="conversationId")
    response: Optional[str] = Field(None, alias="response")
    sql_executions: Optional[List[SqlExecutionDto]] = Field(None, alias="sqlExecutions")
    
    model_config = ConfigDict(populate_by_name=True)

class GetSessionHistoryDto(BaseModel):
    """获取会话历史DTO"""
    session_id: int = Field(..., alias="sessionId")
    page: BasePageRequestDto = Field(..., alias="page")
    
    model_config = ConfigDict(populate_by_name=True)

# 动态页面 DTOs
class CreateDynamicPageDto(BaseModel):
    """创建动态页面DTO"""
    page_name: Optional[str] = Field(None, alias="pageName")
    description: Optional[str] = Field(None, alias="description")
    is_public: bool = Field(False, alias="isPublic")
    
    model_config = ConfigDict(populate_by_name=True)

class AddDynamicPageSqlDto(BaseModel):
    """添加动态页面SQL DTO"""
    id: int = Field(..., alias="id")
    sql_execution_ids: Optional[List[int]] = Field(None, alias="sqlExecutionIds")
    
    model_config = ConfigDict(populate_by_name=True)

class PageComponentDto(BaseModel):
    """页面组件DTO"""
    id: int = Field(..., alias="id")
    page_id: int = Field(..., alias="pageId")
    component_type: Optional[str] = Field(None, alias="componentType")
    component_name: Optional[str] = Field(None, alias="componentName")
    component_config: Optional[str] = Field(None, alias="componentConfig")
    sql_template: Optional[str] = Field(None, alias="sqlTemplate")
    sql_execution_id: Optional[int] = Field(None, alias="sqlExecutionId")
    
    model_config = ConfigDict(populate_by_name=True)


class DynamicPageDto(BaseModel):
    """动态页面DTO"""
    id: int = Field(..., alias="id")
    page_name: Optional[str] = Field(None, alias="pageName")
    description: Optional[str] = Field(None, alias="description")
    layout_config: Optional[str] = Field(None, alias="layoutConfig")
    is_public: bool = Field(False, alias="isPublic")
    components: Optional[List[PageComponentDto]] = Field(None, alias="components")
    create_time: datetime.datetime = Field(..., alias="createTime")
    last_modify_time: datetime.datetime = Field(..., alias="lastModifyTime")
    
    model_config = ConfigDict(populate_by_name=True)

class DynamicPageListItemDto(BaseModel):
    """动态页面列表项DTO"""
    id: int = Field(..., alias="id")
    page_name: Optional[str] = Field(None, alias="pageName")
    description: Optional[str] = Field(None, alias="description")
    is_public: bool = Field(False, alias="isPublic")
    component_count: int = Field(0, alias="componentCount")
    create_time: datetime.datetime = Field(..., alias="createTime")
    
    model_config = ConfigDict(populate_by_name=True)

# OpenAI响应 DTOs
class EChartsTitle(BaseModel):
    text: Optional[str] = Field(None, alias="text")
    
    model_config = ConfigDict(populate_by_name=True)

class EChartsTooltip(BaseModel):
    trigger: Optional[str] = Field(None, alias="trigger")
    
    model_config = ConfigDict(populate_by_name=True)

class EChartsLegend(BaseModel):
    data: Optional[List[str]] = Field(None, alias="data")
    
    model_config = ConfigDict(populate_by_name=True)

class EChartsItemStyle(BaseModel):
    color: Optional[str] = Field(None, alias="color")
    
    model_config = ConfigDict(populate_by_name=True)

class EChartsAxis(BaseModel):
    type: Optional[str] = Field(None, alias="type")
    data: Optional[List[Any]] = Field(None, alias="data")
    name: Optional[str] = Field(None, alias="name")
    
    model_config = ConfigDict(populate_by_name=True)

class EChartsSeries(BaseModel):
    name: Optional[str] = Field(None, alias="name")
    type: Optional[str] = Field(None, alias="type")
    data: Optional[List[Any]] = Field(None, alias="data")
    item_style: Optional[EChartsItemStyle] = Field(None, alias="itemStyle")
    
    model_config = ConfigDict(populate_by_name=True)

class EChartsDataFormat(BaseModel):
    x_axis: Optional[str] = Field(None, alias="xAxis")
    series: Optional[Dict[str, str]] = Field(None, alias="series")
    
    model_config = ConfigDict(populate_by_name=True)

class EChartsConfigDetails(BaseModel):
    """ECharts配置详情"""
    title: Optional[EChartsTitle] = Field(None, alias="title")
    legend: Optional[EChartsLegend] = Field(None, alias="legend")
    tooltip: Optional[EChartsTooltip] = Field(None, alias="tooltip")
    x_axis: Optional[EChartsAxis] = Field(None, alias="xAxis")
    y_axis: Optional[EChartsAxis] = Field(None, alias="yAxis")
    series: Optional[List[EChartsSeries]] = Field(None, alias="series")
    
    model_config = ConfigDict(populate_by_name=True)

class EChartsConfig(BaseModel):
    type: Optional[str] = Field(None, alias="type")
    config: Optional[EChartsConfigDetails] = Field(None, alias="config")
    data_format: Optional[EChartsDataFormat] = Field(None, alias="dataFormat")
    
    model_config = ConfigDict(populate_by_name=True)

class TableConfigDetails(BaseModel):
    columns: Optional[List[str]] = Field(None, alias="columns") 
    rows: Optional[List[List[Optional[Any]]]] = Field(None, alias="rows")
    
    model_config = ConfigDict(populate_by_name=True)

class TableConfig(BaseModel):
    type: Optional[str] = Field(None, alias="type")
    config: Optional[TableConfigDetails] = Field(None, alias="config")
    
    model_config = ConfigDict(populate_by_name=True)

class SqlQueryDto(BaseModel):
    type: Optional[str] = Field(None, alias="type")
    sql: Optional[str] = Field(None, alias="sql")
    echarts: Optional[EChartsConfig] = Field(None, alias="echarts")
    table: Optional[TableConfig] = Field(None, alias="table")
    
    model_config = ConfigDict(populate_by_name=True)

class OpenAiResponseDto(BaseModel):
    queries: Optional[List[SqlQueryDto]] = Field(None, alias="queries")
    message: Optional[str] = Field(None, alias="message")
    
    model_config = ConfigDict(populate_by_name=True)