# app/modules/tools/dataanalysis/router.py
import logging
import uuid
import json
from typing import List, Optional, Dict, Any, Union, Tuple
from fastapi import (
    APIRouter, Depends, UploadFile, File, Form, Body, Query, Path, 
    HTTPException, BackgroundTasks, Request, Response
)
from fastapi.responses import StreamingResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from app.core.utils import json_utils
from app.core.dtos import ApiResponse, BaseIdRequestDto, BasePageRequestDto, PagedResultDto
from app.core.exceptions import BusinessException
from app.core.database.session import get_db
from app.core.job.decorators import job_endpoint
from app.core.storage.base import IStorageService
from app.core.ai.chat.base import IChatAIService
from app.core.utils.snowflake import generate_id

from app.api.dependencies import (
    get_chatai_service_from_state,
    get_prompt_template_service,
    get_storage_service_from_state,
    get_current_active_user_id,
    get_job_persistence_service
)

from app.modules.base.prompts.services import PromptTemplateService
from app.modules.tools.dataanalysis.dtos import (
    AddDynamicPageSqlDto, AiResponseDto, AnalysisSessionDto, ConversationDto, 
    CreateDynamicPageDto, CreateSessionDto, DynamicPageDto, DynamicPageListItemDto, 
    FileDetailItemDto, FileListItemDto, FileUploadResultDto, GetSessionHistoryDto, 
    SessionListItemDto, SqlExecutionDto, TempDataDto, UserQueryDto
)

# --- 导入 Job 相关依赖 ---
from app.core.job.services import JobPersistenceService

# 类型提示导入
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.modules.tools.dataanalysis.repositories.analysis_session_repository import AnalysisSessionRepository
    from app.modules.tools.dataanalysis.repositories.conversation_repository import ConversationRepository
    from app.modules.tools.dataanalysis.repositories.data_table_repository import DataTableRepository
    from app.modules.tools.dataanalysis.repositories.dynamic_page_repository import DynamicPageRepository
    from app.modules.tools.dataanalysis.repositories.import_log_repository import ImportLogRepository
    from app.modules.tools.dataanalysis.repositories.page_component_repository import PageComponentRepository
    from app.modules.tools.dataanalysis.repositories.sql_execution_repository import SqlExecutionRepository
    from app.modules.tools.dataanalysis.repositories.table_column_repository import TableColumnRepository
    from app.modules.tools.dataanalysis.repositories.temp_data_table_repository import TempDataTableRepository
    from app.modules.tools.dataanalysis.repositories.upload_file_repository import UploadFileRepository
    from app.modules.tools.dataanalysis.repositories.visualization_repository import VisualizationRepository
    from app.modules.tools.dataanalysis.services.ai_analysis_service import AIAnalysisService
    from app.modules.tools.dataanalysis.services.data_analysis_service import DataAnalysisService
    from app.modules.tools.dataanalysis.services.data_file_processor import DataFileProcessor
    from app.modules.tools.dataanalysis.services.file_parser_service import FileParserService
    from app.modules.tools.dataanalysis.services.file_upload_service import FileUploadService
    from app.modules.tools.dataanalysis.services.visualiz_html_service import VisualizHtmlService

# 获取 Logger
logger = logging.getLogger(__name__)

# 创建数据分析 API Router
router = APIRouter(
    prefix="/dta",
    tags=["Data Analysis"]
)

# --- 内部依赖项工厂函数 ---

def _get_file_upload_service(
    db: AsyncSession = Depends(get_db),
    storage_service: IStorageService = Depends(get_storage_service_from_state),
    file_parser_service: "FileParserService" = Depends(lambda: _get_file_parser_service())
) -> "FileUploadService":
    """创建并返回 FileUploadService"""
    # 在函数内部导入，避免循环依赖
    from app.modules.tools.dataanalysis.repositories.upload_file_repository import UploadFileRepository
    from app.modules.tools.dataanalysis.repositories.data_table_repository import DataTableRepository
    from app.modules.tools.dataanalysis.repositories.table_column_repository import TableColumnRepository
    from app.modules.tools.dataanalysis.repositories.import_log_repository import ImportLogRepository
    from app.modules.tools.dataanalysis.services.file_upload_service import FileUploadService
    
    upload_file_repository = UploadFileRepository(db)
    data_table_repository = DataTableRepository(db)
    table_column_repository = TableColumnRepository(db)
    import_log_repository = ImportLogRepository(db)
    
    return FileUploadService(
        upload_file_repository=upload_file_repository,
        data_table_repository=data_table_repository,
        table_column_repository=table_column_repository,
        import_log_repository=import_log_repository,
        file_parser_service=file_parser_service,
        storage_service=storage_service
    )

def _get_file_parser_service(
    ai_service: IChatAIService = Depends(get_chatai_service_from_state)
) -> "FileParserService":
    """创建并返回 FileParserService"""
    from app.modules.tools.dataanalysis.services.file_parser_service import FileParserService
    
    return FileParserService(
        ai_service=ai_service
    )

def _get_ai_analysis_service(
    ai_service: IChatAIService = Depends(get_chatai_service_from_state),
    prompt_template_service: PromptTemplateService = Depends(get_prompt_template_service)
) -> "AIAnalysisService":
    """创建并返回 AIAnalysisService"""
    from app.modules.tools.dataanalysis.services.ai_analysis_service import AIAnalysisService
    
    return AIAnalysisService(
        ai_service=ai_service,
        prompt_template_service=prompt_template_service
    )

def _get_visualiz_html_service() -> "VisualizHtmlService":
    """创建并返回 VisualizHtmlService"""
    from app.modules.tools.dataanalysis.services.visualiz_html_service import VisualizHtmlService
    
    return VisualizHtmlService()

def _get_data_analysis_service(
    db: AsyncSession = Depends(get_db),
    ai_analysis_service: "AIAnalysisService" = Depends(_get_ai_analysis_service),
    visualiz_html_service: "VisualizHtmlService" = Depends(_get_visualiz_html_service),
    job_persistence_service: JobPersistenceService = Depends(get_job_persistence_service)
) -> "DataAnalysisService":
    """创建并返回 DataAnalysisService"""
    from app.modules.tools.dataanalysis.repositories.analysis_session_repository import AnalysisSessionRepository
    from app.modules.tools.dataanalysis.repositories.data_table_repository import DataTableRepository
    from app.modules.tools.dataanalysis.repositories.temp_data_table_repository import TempDataTableRepository
    from app.modules.tools.dataanalysis.repositories.table_column_repository import TableColumnRepository
    from app.modules.tools.dataanalysis.repositories.conversation_repository import ConversationRepository
    from app.modules.tools.dataanalysis.repositories.sql_execution_repository import SqlExecutionRepository
    from app.modules.tools.dataanalysis.repositories.visualization_repository import VisualizationRepository
    from app.modules.tools.dataanalysis.repositories.dynamic_page_repository import DynamicPageRepository
    from app.modules.tools.dataanalysis.repositories.page_component_repository import PageComponentRepository
    from app.modules.tools.dataanalysis.services.data_analysis_service import DataAnalysisService
    
    session_repository = AnalysisSessionRepository(db)
    data_table_repository = DataTableRepository(db)
    temp_data_table_repository = TempDataTableRepository(db)
    table_column_repository = TableColumnRepository(db)
    conversation_repository = ConversationRepository(db)
    sql_execution_repository = SqlExecutionRepository(db)
    visualization_repository = VisualizationRepository(db, visualiz_html_service)
    dynamic_page_repository = DynamicPageRepository(db)
    page_component_repository = PageComponentRepository(db)
    
    return DataAnalysisService(
        session_repository=session_repository,
        data_table_repository=data_table_repository,
        temp_data_table_repository=temp_data_table_repository,
        table_column_repository=table_column_repository,
        conversation_repository=conversation_repository,
        sql_execution_repository=sql_execution_repository,
        visualization_repository=visualization_repository,
        dynamic_page_repository=dynamic_page_repository,
        page_component_repository=page_component_repository,
        ai_analysis_service=ai_analysis_service,
        job_persistence_service=job_persistence_service
    )

def _get_data_file_processor(
    db: AsyncSession = Depends(get_db),
    job_persistence_service: JobPersistenceService = Depends(get_job_persistence_service)
) -> "DataFileProcessor":
    """创建并返回 DataFileProcessor"""
    from app.modules.tools.dataanalysis.repositories.upload_file_repository import UploadFileRepository
    from app.modules.tools.dataanalysis.repositories.data_table_repository import DataTableRepository
    from app.modules.tools.dataanalysis.repositories.table_column_repository import TableColumnRepository
    from app.modules.tools.dataanalysis.repositories.import_log_repository import ImportLogRepository
    from app.modules.tools.dataanalysis.services.file_parser_service import FileParserService
    from app.modules.tools.dataanalysis.services.data_file_processor import DataFileProcessor
    
    upload_file_repository = UploadFileRepository(db)
    data_table_repository = DataTableRepository(db)
    table_column_repository = TableColumnRepository(db)
    import_log_repository = ImportLogRepository(db)
    file_parser_service = _get_file_parser_service()
    
    return DataFileProcessor(
        upload_file_repository=upload_file_repository,
        data_table_repository=data_table_repository,
        table_column_repository=table_column_repository,
        import_log_repository=import_log_repository,
        file_parser_service=file_parser_service,

    )

# 文件上传与管理
@router.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user_id: int = Depends(get_current_active_user_id),
    file_upload_service: "FileUploadService" = Depends(_get_file_upload_service)
) -> ApiResponse[FileUploadResultDto]:
    """
    上传数据文件
    
    Args:
        file: 文件
    
    Returns:
        上传结果
    """
    result = await file_upload_service.upload_and_process_file_async(file, current_user_id)
    return ApiResponse[FileUploadResultDto](code=200, message="文件上传成功", data=result)

@router.post("/files/dtl")
async def get_file_details(
    request: BaseIdRequestDto,
    current_user_id: int = Depends(get_current_active_user_id),
    file_upload_service: "FileUploadService" = Depends(_get_file_upload_service)
) -> ApiResponse[FileDetailItemDto]:
    """
    获取文件详情
    
    Args:
        request: 文件ID
    
    Returns:
        文件详情
    """
    result = await file_upload_service.get_file_details_async(request.id)
    return ApiResponse[FileDetailItemDto](code=200, message="获取成功", data=result)

@router.post("/files/list")
async def get_user_files(
    request: BasePageRequestDto,
    current_user_id: int = Depends(get_current_active_user_id),
    file_upload_service: "FileUploadService" = Depends(_get_file_upload_service)
) -> ApiResponse[PagedResultDto[FileListItemDto]]:
    """
    获取用户文件列表
    
    Args:
        request: 分页请求
    
    Returns:
        文件列表
    """
    result = await file_upload_service.get_user_files_async(current_user_id, request.page_index, request.page_size)
    return ApiResponse[PagedResultDto[FileListItemDto]](code=200, message="获取成功", data=result)

@router.post("/files/datas")
async def get_file_datas(
    request: BaseIdRequestDto,
    current_user_id: int = Depends(get_current_active_user_id),
    data_analysis_service: "DataAnalysisService" = Depends(_get_data_analysis_service)
) -> ApiResponse[TempDataDto]:
    """
    获取文件里面的表数据
    
    Args:
        request: 文件ID
    
    Returns:
        文件里面的数据
    """
    result = await data_analysis_service.get_table_datas_async(current_user_id, request.id)
    return ApiResponse[TempDataDto](code=200, message="获取成功", data=result)

# 分析会话管理
@router.post("/chat/sessions/create")
async def create_session(
    create_session_dto: CreateSessionDto,
    current_user_id: int = Depends(get_current_active_user_id),
    data_analysis_service: "DataAnalysisService" = Depends(_get_data_analysis_service)
) -> ApiResponse[AnalysisSessionDto]:
    """
    创建分析会话
    
    Args:
        create_session_dto: 创建会话DTO
    
    Returns:
        会话信息
    """
    result = await data_analysis_service.create_session_async(current_user_id, create_session_dto.session_name)
    return ApiResponse[AnalysisSessionDto](code=200, message="会话创建成功", data=result)

@router.post("/chat/sessions/dtl")
async def get_session(
    request: BaseIdRequestDto,
    current_user_id: int = Depends(get_current_active_user_id),
    data_analysis_service: "DataAnalysisService" = Depends(_get_data_analysis_service)
) -> ApiResponse[AnalysisSessionDto]:
    """
    获取会话信息
    
    Args:
        request: 会话ID
    
    Returns:
        会话信息
    """
    result = await data_analysis_service.get_session_async(request.id, current_user_id)
    return ApiResponse[AnalysisSessionDto](code=200, message="获取成功", data=result)

@router.post("/chat/sessions/list")
async def get_user_sessions(
    request: BasePageRequestDto,
    current_user_id: int = Depends(get_current_active_user_id),
    data_analysis_service: "DataAnalysisService" = Depends(_get_data_analysis_service)
) -> ApiResponse[PagedResultDto[SessionListItemDto]]:
    """
    获取用户会话列表
    
    Args:
        request: 分页请求
    
    Returns:
        会话列表
    """
    result = await data_analysis_service.get_user_sessions_async(current_user_id, request.page_index, request.page_size)
    return ApiResponse[PagedResultDto[SessionListItemDto]](code=200, message="获取成功", data=result)

# 对话管理
@router.post("/chat/sessions/conversationstream")
async def process_user_query_stream(
    request: Request,
    response: Response,
    query_dto: UserQueryDto = Body(...),
    current_user_id: int = Depends(get_current_active_user_id),
    data_analysis_service: "DataAnalysisService" = Depends(_get_data_analysis_service)
):
    """
    流式处理用户查询
    
    Args:
        query_dto: 查询DTO
    
    Returns:
        流式响应
    """
    # 设置响应头
    response.headers["Content-Type"] = "text/event-stream"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    
    # 创建事件ID
    event_id = str(uuid.uuid4())
    
    # 创建响应流
    async def event_generator():
        try:
            # 发送开始事件
            yield f"id: {event_id}\nevent: start\ndata: {json.dumps({'message': '开始生成回复'})}\n\n"
            
            # 处理回调函数
            async def on_chunk_received(chunk: str):
                # 发送数据块
                yield f"id: {event_id}\nevent: chunk\ndata: {chunk}\n\n"
            
            # 使用数据分析服务处理流式查询
            final_reply = await data_analysis_service.process_user_query_stream_async(
                current_user_id, 
                query_dto,
                on_chunk_received
            )
            
            # 发送完成事件
            yield f"id: {event_id}\nevent: done\ndata: {json.dumps(final_reply)}\n\n"
        
        except asyncio.CancelledError:
            # 用户取消请求
            yield f"id: {event_id}\nevent: canceled\ndata: 请求已取消\n\n"
        
        except Exception as ex:
            # 发生错误
            yield f"id: {event_id}\nevent: error\ndata: {str(ex)}\n\n"
        
        finally:
            # 发送结束事件
            yield f"id: {event_id}\nevent: end\ndata: \n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/chat/sessions/conversation")
async def process_user_query(
    query_dto: UserQueryDto,
    current_user_id: int = Depends(get_current_active_user_id),
    data_analysis_service: "DataAnalysisService" = Depends(_get_data_analysis_service)
) -> ApiResponse[AiResponseDto]:
    """
    处理用户查询
    
    Args:
        query_dto: 查询DTO
    
    Returns:
        AI响应
    """
    result = await data_analysis_service.process_user_query_async(current_user_id, query_dto)
    return ApiResponse[AiResponseDto](code=200, message="处理成功", data=result)

@router.post("/chat/sessions/conversation/history")
async def get_session_history(
    request: GetSessionHistoryDto,
    data_analysis_service: "DataAnalysisService" = Depends(_get_data_analysis_service)
) -> ApiResponse[PagedResultDto[ConversationDto]]:
    """
    获取会话对话历史
    
    Args:
        request: 会话历史请求
    
    Returns:
        对话历史
    """
    result = await data_analysis_service.get_session_history_async(
        request.session_id,
        request.page.page_index,
        request.page.page_size
    )
    return ApiResponse[PagedResultDto[ConversationDto]](code=200, message="获取成功", data=result)

@router.post("/chat/sessions/conversation/refreshdata")
async def refresh_session_data(
    request: BaseIdRequestDto,
    data_analysis_service: "DataAnalysisService" = Depends(_get_data_analysis_service)
) -> ApiResponse[SqlExecutionDto]:
    """
    对对话中的图表，重新执行刷新数据的动作
    
    Args:
        request: SQL执行ID
    
    Returns:
        SQL执行结果
    """
    result = await data_analysis_service.refresh_conversation_data(request.id)
    return ApiResponse[SqlExecutionDto](code=200, message="刷新成功", data=result)

@router.post("/chat/sessions/conversation/dtl")
async def get_conversation(
    request: BaseIdRequestDto,
    data_analysis_service: "DataAnalysisService" = Depends(_get_data_analysis_service)
) -> ApiResponse[ConversationDto]:
    """
    获取对话详情
    
    Args:
        request: 对话ID
    
    Returns:
        对话详情
    """
    result = await data_analysis_service.get_conversation_async(request.id)
    return ApiResponse[ConversationDto](code=200, message="获取成功", data=result)

# 可视化处理
@router.get("/visualization/{id}")
async def get_visualization_html(
    id: int,
    data_analysis_service: "DataAnalysisService" = Depends(_get_data_analysis_service)
) -> HTMLResponse:
    """
    获取可视化HTML
    
    Args:
        id: 可视化ID
    
    Returns:
        HTML内容
    """
    try:
        html_content = await data_analysis_service.get_visualization_html_async(id)
        return HTMLResponse(content=html_content)
    except Exception as ex:
        return HTMLResponse(content=f"获取可视化内容失败: {str(ex)}")

# 动态页面管理
@router.post("/pages/create")
async def create_dynamic_page(
    create_page_dto: CreateDynamicPageDto,
    current_user_id: int = Depends(get_current_active_user_id),
    data_analysis_service: "DataAnalysisService" = Depends(_get_data_analysis_service)
) -> ApiResponse[DynamicPageDto]:
    """
    创建动态页面
    
    Args:
        create_page_dto: 创建页面DTO
    
    Returns:
        动态页面信息
    """
    result = await data_analysis_service.create_dynamic_page_async(current_user_id, create_page_dto)
    return ApiResponse[DynamicPageDto](code=200, message="动态页面创建成功", data=result)

@router.post("/pages/addsqldata")
async def dynamic_page_add_sql_data(
    request: AddDynamicPageSqlDto,
    current_user_id: int = Depends(get_current_active_user_id),
    data_analysis_service: "DataAnalysisService" = Depends(_get_data_analysis_service)
) -> ApiResponse[int]:
    """
    给动态页面增加sql数据
    
    Args:
        request: 添加SQL请求
    
    Returns:
        添加的组件数量
    """
    result = await data_analysis_service.dynamic_page_add_sql_async(request)
    return ApiResponse[int](code=200, message="SQL数据添加成功", data=result)

@router.post("/pages/dtl")
async def get_dynamic_page(
    request: BaseIdRequestDto,
    current_user_id: int = Depends(get_current_active_user_id),
    data_analysis_service: "DataAnalysisService" = Depends(_get_data_analysis_service)
) -> ApiResponse[DynamicPageDto]:
    """
    获取动态页面信息
    
    Args:
        request: 页面ID
    
    Returns:
        动态页面信息
    """
    result = await data_analysis_service.get_dynamic_page_async(request.id, current_user_id)
    return ApiResponse[DynamicPageDto](code=200, message="获取成功", data=result)

@router.post("/pages/list")
async def get_user_dynamic_pages(
    request: BasePageRequestDto,
    current_user_id: int = Depends(get_current_active_user_id),
    data_analysis_service: "DataAnalysisService" = Depends(_get_data_analysis_service)
) -> ApiResponse[PagedResultDto[DynamicPageListItemDto]]:
    """
    获取用户动态页面列表
    
    Args:
        request: 分页请求
    
    Returns:
        动态页面列表
    """
    result = await data_analysis_service.get_user_dynamic_pages_async(current_user_id, request.page_index, request.page_size)
    return ApiResponse[PagedResultDto[DynamicPageListItemDto]](code=200, message="获取成功", data=result)

@router.post("/pages/delete")
async def delete_dynamic_page(
    request: BaseIdRequestDto,
    current_user_id: int = Depends(get_current_active_user_id),
    data_analysis_service: "DataAnalysisService" = Depends(_get_data_analysis_service)
) -> ApiResponse:
    """
    删除动态页面
    
    Args:
        request: 页面ID
    
    Returns:
        操作结果
    """
    await data_analysis_service.delete_dynamic_page_async(request.id, current_user_id)
    return ApiResponse(code=200, message="页面已删除")

# --- 后台任务处理 ---

@router.post(
    "/files/tasks/process/{job_id}/{params_id}",
    summary="[内部] 执行文件解析任务",
    description="由调度器调用，自动处理锁和状态更新。",
    response_model=ApiResponse[None]
)
@job_endpoint(default_can_retry=True)
async def execute_process_file_task(
    job_id: int,
    params_id: int,
    job_service: JobPersistenceService = Depends(get_job_persistence_service),
    data_file_processor: "DataFileProcessor" = Depends(_get_data_file_processor)
):
    """
    执行文件解析任务
    
    Args:
        job_id: 任务ID
        params_id: 文件ID
        job_service: 任务持久化服务
        data_file_processor: 数据文件处理器
    
    Returns:
        处理结果
    """
    await data_file_processor.process_file_async(params_id, "mysql")
    return ApiResponse(code=200, message="文件处理成功")

@router.post(
    "/tasks/process-pending-files/{job_id}",
    summary="[内部] 定时处理待处理文档",
    description="由调度器调用，处理队列中的待处理文档",
    response_model=ApiResponse[None]
)
@job_endpoint(default_can_retry=True)
async def process_pending_data_files(
    job_id: int,
    data_file_processor: "DataFileProcessor" = Depends(_get_data_file_processor)
):
    """
    处理待处理的文档
    
    Args:
        job_id: 任务ID
        data_file_processor: 数据文件处理器
    
    Returns:
        处理结果
    """
    # 限制每次处理的文档数量
    batch_size = 5
    pending_files = await data_file_processor.get_pending_files_async(batch_size)
    logger.info(f"找到 {len(pending_files)} 个待处理文档")

    for file in pending_files:
        logger.info(f"为文档 {file.id} 创建处理任务")
        # 创建文件处理任务
        await data_file_processor.create_processing_job(file.id)
    
    return ApiResponse(code=200, message=f"已为 {len(pending_files)} 个文档创建处理任务")

@router.post(
    "/tasks/refresh-visualization/{job_id}/{params_id}",
    summary="[内部] 刷新可视化任务",
    description="由调度器调用，刷新可视化数据",
    response_model=ApiResponse[None]
)
@job_endpoint(default_can_retry=True)
async def refresh_visualization_task(
    job_id: int,
    params_id: int,
    data_analysis_service: "DataAnalysisService" = Depends(_get_data_analysis_service)
):
    """
    刷新可视化任务
    
    Args:
        job_id: 任务ID
        params_id: SQL执行ID
        data_analysis_service: 数据分析服务
    
    Returns:
        处理结果
    """
    await data_analysis_service.refresh_conversation_data(params_id)
    return ApiResponse(code=200, message="可视化数据刷新成功")