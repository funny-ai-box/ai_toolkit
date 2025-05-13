import asyncio
import json
import logging
import uuid # For generating unique event IDs
from typing import Dict, List, AsyncGenerator, Optional, Callable, Any # Ensure Any is imported

from fastapi import (
    APIRouter, Depends, UploadFile, Form, Request, Response as FastAPIResponse, HTTPException, status
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import httpx # For AI service client

# 核心依赖
from app.core.database.session import get_db
from app.core.config.settings import settings

from app.api.dependencies import (
    get_current_active_user_id,
    get_http_client_from_state,
    get_prompt_template_service,
  
    # RateLimiter can be added if needed
)
from app.core.ai.chat.factory import get_chat_ai_service

# 核心 DTOs 和异常
from app.core.dtos import ApiResponse, BaseIdRequestDto # PagedResultDto is now local
from app.core.exceptions import BusinessException, NotFoundException
from app.modules.base.prompts.services import PromptTemplateService

# DataDesign 模块 DTOs
from .dtos import (
    CreateDesignTaskRequestDto, UpdateDesignTaskRequestDto, DesignTaskDetailDto,
    DesignTaskListItemDto, DesignTaskListRequestDto, DesignTaskPagedResultDto,
    TableDesignDetailDto, TableDesignListItemDto,
    DesignChatRequestDto, DesignChatMessageDto,
    GenerateDDLRequestDto, GenerateDDLResultDto,
    GenerateCodeRequestDto, GenerateCodeResultDto,
    CodeTemplateDto, CodeTemplateDetailDto, CreateCodeTemplateDto,
    GenerateCodeTemplateRequestDto, TemplateExampleDto, GetExampleRequirementsRequestDto,
    SupportLanguageAndDbDto
)

# 类型提示
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.core.ai.chat.base import IChatAIService

    from .services.data_design_service import DataDesignService
    from .services.data_design_ai_service import DataDesignAIService
    from .services.coding.code_template_generator_service import CodeTemplateGeneratorService
    # Repositories for type hinting in _get_data_design_service
    from .repositories.design_task_repository import DesignTaskRepository
    from .repositories.table_design_repository import TableDesignRepository
    from .repositories.field_design_repository import FieldDesignRepository
    from .repositories.index_design_repository import IndexDesignRepository
    from .repositories.index_field_repository import IndexFieldRepository
    from .repositories.table_relation_repository import TableRelationRepository
    from .repositories.design_chat_repository import DesignChatRepository
    from .repositories.code_template_repository import CodeTemplateRepository
    from .repositories.code_template_dtl_repository import CodeTemplateDtlRepository
    from .repositories.design_task_state_repository import DesignTaskStateRepository


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/datadesign", # Assuming /api is prepended by main app router
    tags=["DataDesign - AI数据设计"],
)

# --- 内部依赖项工厂：获取 DataDesignService 实例 ---
def _get_data_design_service(
    db: AsyncSession = Depends(get_db),
    http_client: httpx.AsyncClient = Depends(get_http_client_from_state),
    prompt_template_service: 'PromptTemplateService' = Depends(get_prompt_template_service)
) -> 'DataDesignService':
    """内部依赖项：创建并返回 DataDesignService 及其所有内部依赖。"""
    # 在函数内部导入，避免顶层循环依赖
    from .services.data_design_service import DataDesignService
    from .services.data_design_ai_service import DataDesignAIService
    from .services.coding.code_template_generator_service import CodeTemplateGeneratorService
    from .repositories.design_task_repository import DesignTaskRepository
    from .repositories.table_design_repository import TableDesignRepository
    from .repositories.field_design_repository import FieldDesignRepository
    from .repositories.index_design_repository import IndexDesignRepository
    from .repositories.index_field_repository import IndexFieldRepository
    from .repositories.table_relation_repository import TableRelationRepository
    from .repositories.design_chat_repository import DesignChatRepository
    from .repositories.code_template_repository import CodeTemplateRepository
    from .repositories.code_template_dtl_repository import CodeTemplateDtlRepository
    from .repositories.design_task_state_repository import DesignTaskStateRepository

    # 1. 创建 Repositories
    task_state_repo = DesignTaskStateRepository(db=db)
    task_repo = DesignTaskRepository(db=db)
    table_repo = TableDesignRepository(db=db)
    field_repo = FieldDesignRepository(db=db)
    index_repo = IndexDesignRepository(db=db)
    index_field_repo = IndexFieldRepository(db=db)
    relation_repo = TableRelationRepository(db=db)
    chat_repo = DesignChatRepository(db=db, task_state_repository=task_state_repo)
    code_template_repo = CodeTemplateRepository(db=db)
    code_template_dtl_repo = CodeTemplateDtlRepository(db=db)

    # 2. 创建 AI Service (specific for datadesign)
    datadesign_ai_provider = settings.DATADESIGN_CHAT_AI_PROVIDER_TYPE
    if not datadesign_ai_provider:
        logger.error("DATADESIGN_CHAT_AI_PROVIDER_TYPE 未在配置中设置!")
        # This ideally should be caught at startup or raise a clear server error
        raise HTTPException(status_code=500, detail="服务器AI配置错误")
    
    # Get the specific AI service instance for data design
    specific_ai_service_instance = get_chat_ai_service(datadesign_ai_provider, http_client)

    # 3. 创建内部服务
    code_gen_service = CodeTemplateGeneratorService(logger=logger, ai_service=specific_ai_service_instance)
    
    design_ai_service_instance = DataDesignAIService(
        logger=logger,
        design_task_repository=task_repo,
        design_chat_repository=chat_repo,
        ai_service=specific_ai_service_instance,
        prompt_template_service=prompt_template_service
    )

    # 4. 创建主服务 DataDesignService
    data_design_service_instance = DataDesignService(
        logger=logger,
        design_task_repo=task_repo,
        table_design_repo=table_repo,
        field_design_repo=field_repo,
        index_design_repo=index_repo,
        index_field_repo=index_field_repo,
        table_relation_repo=relation_repo,
        design_chat_repo=chat_repo,
        code_template_repo=code_template_repo,
        code_template_dtl_repo=code_template_dtl_repo,
        design_ai_service=design_ai_service_instance,
        code_template_generator_service=code_gen_service
    )
    return data_design_service_instance


# --- SSE Helper ---
async def send_sse_event(event_id: str, event_type: str, data: Any) -> str:
    """
    Helper to format an SSE event.
    Data will be JSON serialized if it's not already a string.
    """
    if not isinstance(data, str):
        try:
            # ensure_ascii=False is important for non-Latin characters
            data_str = json.dumps(data, ensure_ascii=False)
        except TypeError as e:
            logger.error(f"SSE data serialization error for event type {event_type}: {e}. Data: {data}")
            data_str = json.dumps({"error": "Serialization failed", "details": str(e)}, ensure_ascii=False)
    else:
        data_str = data
    
    return f"id: {event_id}\nevent: {event_type}\ndata: {data_str}\n\n"


# --- API Endpoints ---

# region 设计任务管理
@router.post("/tasks/create", response_model=ApiResponse[int], summary="创建设计任务")
async def create_design_task(
    request_data: CreateDesignTaskRequestDto,
    current_user_id: int = Depends(get_current_active_user_id),
    service: 'DataDesignService' = Depends(_get_data_design_service)
):
    try:
        task_id = await service.create_design_task_async(current_user_id, request_data)
        return ApiResponse[int].success(data=task_id, message="任务创建成功")
    except BusinessException as e:
        # Log a warning for business exceptions as they are expected failures
        logger.warning(f"创建设计任务业务异常 (user: {current_user_id}): {e.message}")
        return ApiResponse.fail(message=e.message, code=e.code or status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"创建设计任务发生意外错误 (user: {current_user_id}): {str(e)}", exc_info=True)
        return ApiResponse.fail(message="创建任务时发生内部服务器错误")


@router.post("/tasks/update", response_model=ApiResponse, summary="更新设计任务")
async def update_design_task(
    request_data: UpdateDesignTaskRequestDto,
    current_user_id: int = Depends(get_current_active_user_id),
    service: 'DataDesignService' = Depends(_get_data_design_service)
):
    try:
        success = await service.update_design_task_async(current_user_id, request_data)
        if success:
            return ApiResponse.success(message="任务更新成功")
        # This case might not be reachable if service throws NotFoundException
        logger.warning(f"更新设计任务未执行任何更改 (task_id: {request_data.id}, user: {current_user_id})")
        return ApiResponse.fail(message="任务更新失败 (可能未找到或无变化)")
    except NotFoundException as e:
        logger.warning(f"更新设计任务未找到 (task_id: {request_data.id}, user: {current_user_id}): {e.message}")
        return ApiResponse.fail(message=e.message, code=status.HTTP_404_NOT_FOUND)
    except BusinessException as e:
        logger.warning(f"更新设计任务业务异常 (task_id: {request_data.id}, user: {current_user_id}): {e.message}")
        return ApiResponse.fail(message=e.message, code=e.code or status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"更新设计任务发生意外错误 (task_id: {request_data.id}, user: {current_user_id}): {str(e)}", exc_info=True)
        return ApiResponse.fail(message="更新任务时发生内部服务器错误")


@router.post("/tasks/delete", response_model=ApiResponse, summary="删除设计任务")
async def delete_design_task(
    request_data: BaseIdRequestDto,
    current_user_id: int = Depends(get_current_active_user_id),
    service: 'DataDesignService' = Depends(_get_data_design_service)
):
    try:
        success = await service.delete_design_task_async(current_user_id, request_data.id)
        if success:
            return ApiResponse.success(message="任务删除成功")
        # This case might not be reachable if service throws NotFoundException
        logger.warning(f"删除设计任务未执行任何更改 (task_id: {request_data.id}, user: {current_user_id})")
        return ApiResponse.fail(message="任务删除失败 (可能未找到)")
    except NotFoundException as e:
        logger.warning(f"删除设计任务未找到 (task_id: {request_data.id}, user: {current_user_id}): {e.message}")
        return ApiResponse.fail(message=e.message, code=status.HTTP_404_NOT_FOUND)
    except BusinessException as e: # Should not typically occur for delete if not found is handled
        logger.warning(f"删除设计任务业务异常 (task_id: {request_data.id}, user: {current_user_id}): {e.message}")
        return ApiResponse.fail(message=e.message, code=e.code or status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"删除设计任务发生意外错误 (task_id: {request_data.id}, user: {current_user_id}): {str(e)}", exc_info=True)
        return ApiResponse.fail(message="删除任务时发生内部服务器错误")


@router.post("/tasks/dtl", response_model=ApiResponse[DesignTaskDetailDto], summary="获取设计任务详情")
async def get_design_task_detail(
    request_data: BaseIdRequestDto,
    current_user_id: int = Depends(get_current_active_user_id),
    service: 'DataDesignService' = Depends(_get_data_design_service)
):
    try:
        task_detail = await service.get_design_task_async(current_user_id, request_data.id)
        return ApiResponse[DesignTaskDetailDto].success(data=task_detail)
    except NotFoundException as e:
        logger.warning(f"获取设计任务详情未找到 (task_id: {request_data.id}, user: {current_user_id}): {e.message}")
        return ApiResponse.fail(message=e.message, code=status.HTTP_404_NOT_FOUND)
    except BusinessException as e: # Should not typically occur if NotFoundException is used for access errors
        logger.warning(f"获取设计任务详情业务异常 (task_id: {request_data.id}, user: {current_user_id}): {e.message}")
        return ApiResponse.fail(message=e.message, code=e.code or status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"获取设计任务详情发生意外错误 (task_id: {request_data.id}, user: {current_user_id}): {str(e)}", exc_info=True)
        return ApiResponse.fail(message="获取任务详情时发生内部服务器错误")


@router.post("/tasks/list", response_model=ApiResponse[DesignTaskPagedResultDto], summary="获取设计任务列表")
async def get_design_tasks(
    request_data: DesignTaskListRequestDto,
    current_user_id: int = Depends(get_current_active_user_id),
    service: 'DataDesignService' = Depends(_get_data_design_service)
):
    try:
        tasks_page = await service.get_design_tasks_async(current_user_id, request_data)
        return ApiResponse[DesignTaskPagedResultDto].success(data=tasks_page)
    except Exception as e: # Catchall for list, less specific errors expected
        logger.error(f"获取设计任务列表发生意外错误 (user: {current_user_id}): {str(e)}", exc_info=True)
        return ApiResponse.fail(message="获取任务列表时发生内部服务器错误")
# endregion

# region 表设计管理
@router.post("/tables/dtl", response_model=ApiResponse[TableDesignDetailDto], summary="获取表设计详情")
async def get_table_design_detail(
    request_data: BaseIdRequestDto,
    current_user_id: int = Depends(get_current_active_user_id),
    service: 'DataDesignService' = Depends(_get_data_design_service)
):
    try:
        table_detail = await service.get_table_design_async(current_user_id, request_data.id)
        return ApiResponse[TableDesignDetailDto].success(data=table_detail)
    except NotFoundException as e:
        logger.warning(f"获取表设计详情未找到 (table_id: {request_data.id}, user: {current_user_id}): {e.message}")
        return ApiResponse.fail(message=e.message, code=status.HTTP_404_NOT_FOUND)
    except BusinessException as e: # For permission errors within the service
        logger.warning(f"获取表设计详情业务异常 (table_id: {request_data.id}, user: {current_user_id}): {e.message}")
        return ApiResponse.fail(message=e.message, code=e.code or status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"获取表设计详情发生意外错误 (table_id: {request_data.id}, user: {current_user_id}): {str(e)}", exc_info=True)
        return ApiResponse.fail(message="获取表设计详情时发生内部服务器错误")


@router.post("/tables/list", response_model=ApiResponse[List[TableDesignListItemDto]], summary="获取任务的表设计列表")
async def get_table_designs(
    request_data: BaseIdRequestDto, # task_id is in BaseIdRequestDto.id
    current_user_id: int = Depends(get_current_active_user_id),
    service: 'DataDesignService' = Depends(_get_data_design_service)
):
    try:
        tables_list = await service.get_table_designs_async(current_user_id, request_data.id)
        return ApiResponse[List[TableDesignListItemDto]].success(data=tables_list)
    except BusinessException as e: # For task not found or permission errors
        logger.warning(f"获取表设计列表业务异常 (task_id: {request_data.id}, user: {current_user_id}): {e.message}")
        return ApiResponse.fail(message=e.message, code=e.code or status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"获取表设计列表发生意外错误 (task_id: {request_data.id}, user: {current_user_id}): {str(e)}", exc_info=True)
        return ApiResponse.fail(message="获取表设计列表时发生内部服务器错误")
# endregion

# region 设计聊天 (SSE)
# Helper for SSE streaming logic with asyncio.Queue
async def sse_streamer(
    event_id_prefix: str,
    initial_message: Dict[str, Any],
    service_call_coro: asyncio.Task, # The coroutine of the service method call
    queue: asyncio.Queue,
    logger_instance: logging.Logger # Pass logger explicitly
):
    event_id = f"{event_id_prefix}_{uuid.uuid4().hex}"
    try:
        yield await send_sse_event(event_id, "start", initial_message)
        
        while True:
            # Wait for either an item in the queue or the service_task to complete
            # Important: queue.get() is a coroutine and needs to be awaited.
            # We wrap it in a task to use with asyncio.wait
            get_item_task = asyncio.create_task(queue.get())
            done, pending = await asyncio.wait(
                {service_call_coro, get_item_task},
                return_when=asyncio.FIRST_COMPLETED
            )
            
            processed_service_task = False
            chunk_yielded = False

            for future in done:
                if future == service_call_coro:
                    processed_service_task = True
                    # Service task completed, check for errors
                    if service_call_coro.exception():
                        # Log and re-raise to be caught by the outer try-except
                        logger_instance.error(f"SSE service_call_coro (event {event_id}) exception: {service_call_coro.exception()}", exc_info=service_call_coro.exception())
                        raise service_call_coro.exception()
                elif future == get_item_task:
                    # Item from queue
                    item_from_queue = get_item_task.result() # Get result of queue.get()
                    yield item_from_queue # This is already formatted SSE string
                    chunk_yielded = True
                    queue.task_done() # Signal that the item from queue is processed
                else: # Should not happen
                    logger_instance.error(f"SSE streamer (event {event_id}): Unexpected future completed.")
            
            if processed_service_task and queue.empty():
                # Service task is done and queue is empty, so we are done
                break
            
            # If only the queue.get() completed, loop again to wait for more chunks or service completion.
            # If service_call_coro completed but queue might still have items, process them in next iterations.
            
    except asyncio.CancelledError:
        logger_instance.info(f"SSE streamer (event {event_id}) cancelled.")
        yield await send_sse_event(event_id, "canceled", "请求已取消")
        if not service_call_coro.done():
            service_call_coro.cancel() # Cancel the service task if streamer is cancelled
            try:
                await service_call_coro # Await to allow cleanup
            except asyncio.CancelledError:
                logger_instance.info(f"SSE service_call_coro (event {event_id}) successfully cancelled.")
            except Exception as e_cancel_service:
                 logger_instance.error(f"SSE service_call_coro (event {event_id}) error during cancellation: {e_cancel_service}")
    except Exception as e_stream:
        logger_instance.error(f"Error in SSE streamer (event {event_id}): {e_stream}", exc_info=True)
        yield await send_sse_event(event_id, "error", str(e_stream))
    finally:
        # Ensure service_call_coro is cleaned up if not done (e.g. client disconnects)
        if not service_call_coro.done():
            service_call_coro.cancel()
            # Optionally await it with a timeout if there's cleanup logic in the service
            # try: await asyncio.wait_for(service_call_coro, timeout=1.0)
            # except (asyncio.CancelledError, asyncio.TimeoutError): pass
        yield await send_sse_event(event_id, "end", "")


@router.post("/chat/upload", summary="上传文档并进行流式聊天 (SSE)")
async def chat_upload_document(
    current_user_id: int = Depends(get_current_active_user_id),
    service: 'DataDesignService' = Depends(_get_data_design_service),
    task_id: int = Form(...),
    file: UploadFile = Form(...)
    # logger is available via self.logger in service, or can be injected here too
):
    try:
        # Stage 1: Upload and process document content (non-streaming part)
        document_content = await service.upload_document_async(current_user_id, task_id, file)
        
        # Stage 2: Prepare for streaming chat based on document content
        # Message for AI will include context about the uploaded document
        ai_message = f"已上传文档 '{file.filename}'。请基于以下内容进行分析和设计：\n\n{document_content}"
        chat_request_dto = DesignChatRequestDto(task_id=task_id, message=ai_message)
        
        # Setup for SSE streaming
        queue = asyncio.Queue()
        async def sse_on_chunk_callback(chunk_data: str):
            """Callback for the service to put formatted SSE data into the queue."""
            # The chunk_data from service.streaming_chat_async is "role|content"
            # We need to format it into full SSE event string here.
            event_id = "upload_stream" # Could be made more unique if needed per chunk
            parts = chunk_data.split('|', 1)
            data_to_send_sse: Any = chunk_data # Default if no pipe
            if len(parts) == 2:
                role, content = parts
                data_to_send_sse = {"role": role, "content": content}
            
            formatted_sse_event = await send_sse_event(event_id, "chunk", data_to_send_sse)
            await queue.put(formatted_sse_event)

        # Start the service's streaming chat logic in a background task
        service_call_task = asyncio.create_task(
            service.streaming_chat_async(current_user_id, chat_request_dto, sse_on_chunk_callback)
        )
        
        # Return a StreamingResponse that reads from the queue
        return StreamingResponse(
            sse_streamer(
                "chat_upload", 
                {"message": "开始分析文档并生成回复"}, 
                service_call_task, 
                queue,
                logger # Pass the logger instance
            ), 
            media_type="text/event-stream"
        )

    except BusinessException as e:
        logger.warning(f"文档上传或聊天业务异常 (task_id: {task_id}, user: {current_user_id}): {e.message}")
        # For form data, FastAPI typically returns 422 if validation fails before endpoint.
        # If BusinessException happens in service, it's likely 400 or specific code.
        raise HTTPException(status_code=e.code or status.HTTP_400_BAD_REQUEST, detail=e.message)
    except Exception as e_outer:
        logger.error(f"文档上传或聊天发生意外错误 (task_id: {task_id}, user: {current_user_id}): {str(e_outer)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="文档上传或聊天处理失败")


@router.post("/chat/sendtext", summary="发送文本进行流式聊天 (SSE)")
async def chat_send_text(
    request_data: DesignChatRequestDto,
    current_user_id: int = Depends(get_current_active_user_id),
    service: 'DataDesignService' = Depends(_get_data_design_service)
):
    # RateLimit check would be here if using a FastAPI rate limiter dependency
    queue = asyncio.Queue()
    async def sse_on_chunk_callback(chunk_data: str):
        event_id = "text_stream" 
        parts = chunk_data.split('|', 1)
        data_to_send_sse: Any = chunk_data
        if len(parts) == 2:
            role, content = parts
            data_to_send_sse = {"role": role, "content": content}
        
        formatted_sse_event = await send_sse_event(event_id, "chunk", data_to_send_sse)
        await queue.put(formatted_sse_event)

    service_call_task = asyncio.create_task(
        service.streaming_chat_async(current_user_id, request_data, sse_on_chunk_callback)
    )
    
    return StreamingResponse(
        sse_streamer(
            "chat_sendtext", 
            {"message": "开始生成回复"}, 
            service_call_task, 
            queue,
            logger
        ), 
        media_type="text/event-stream"
    )


@router.post("/chat/history", response_model=ApiResponse[List[DesignChatMessageDto]], summary="获取聊天历史")
async def get_chat_history(
    request_data: BaseIdRequestDto, # task_id is in BaseIdRequestDto.id
    current_user_id: int = Depends(get_current_active_user_id),
    service: 'DataDesignService' = Depends(_get_data_design_service)
):
    try:
        history = await service.get_chat_history_async(current_user_id, request_data.id)
        return ApiResponse[List[DesignChatMessageDto]].success(data=history)
    except BusinessException as e: # Handles task not found or permission error
        logger.warning(f"获取聊天历史业务异常 (task_id: {request_data.id}, user: {current_user_id}): {e.message}")
        return ApiResponse.fail(message=e.message, code=e.code or status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"获取聊天历史发生意外错误 (task_id: {request_data.id}, user: {current_user_id}): {str(e)}", exc_info=True)
        return ApiResponse.fail(message="获取聊天历史时发生内部服务器错误")
# endregion

# region 代码生成
@router.post("/code/ddl", response_model=ApiResponse[GenerateDDLResultDto], summary="生成DDL脚本")
async def generate_ddl(
    request_data: GenerateDDLRequestDto,
    current_user_id: int = Depends(get_current_active_user_id),
    service: 'DataDesignService' = Depends(_get_data_design_service)
):
    try:
        result = await service.generate_ddl_async(current_user_id, request_data)
        return ApiResponse[GenerateDDLResultDto].success(data=result)
    except NotFoundException as e:
        logger.warning(f"生成DDL脚本资源未找到 (task_id: {request_data.task_id}, user: {current_user_id}): {e.message}")
        return ApiResponse.fail(message=e.message, code=status.HTTP_404_NOT_FOUND)
    except BusinessException as e:
        logger.warning(f"生成DDL脚本业务异常 (task_id: {request_data.task_id}, user: {current_user_id}): {e.message}")
        return ApiResponse.fail(message=e.message, code=e.code or status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"生成DDL脚本发生意外错误 (task_id: {request_data.task_id}, user: {current_user_id}): {str(e)}", exc_info=True)
        return ApiResponse.fail(message="生成DDL时发生内部服务器错误")


@router.post("/code/generate", response_model=ApiResponse[GenerateCodeResultDto], summary="根据模板生成代码")
async def generate_code(
    request_data: GenerateCodeRequestDto,
    current_user_id: int = Depends(get_current_active_user_id),
    service: 'DataDesignService' = Depends(_get_data_design_service)
):
    try:
        result = await service.generate_code_async(current_user_id, request_data)
        return ApiResponse[GenerateCodeResultDto].success(data=result)
    except NotFoundException as e:
        logger.warning(f"生成代码资源未找到 (table_id: {request_data.table_id}, user: {current_user_id}): {e.message}")
        return ApiResponse.fail(message=e.message, code=status.HTTP_404_NOT_FOUND)
    except BusinessException as e:
        logger.warning(f"生成代码业务异常 (table_id: {request_data.table_id}, user: {current_user_id}): {e.message}")
        return ApiResponse.fail(message=e.message, code=e.code or status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"生成代码发生意外错误 (table_id: {request_data.table_id}, user: {current_user_id}): {str(e)}", exc_info=True)
        return ApiResponse.fail(message="生成代码时发生内部服务器错误")


@router.post("/code/supportlangs", response_model=ApiResponse[SupportLanguageAndDbDto], summary="获取支持的数据库和编程语言")
async def get_support_language_and_db(
    service: 'DataDesignService' = Depends(_get_data_design_service)
):
    # This endpoint does not require authentication in C# version, so no current_user_id
    try:
        data = await service.get_support_language_and_db_async()
        return ApiResponse[SupportLanguageAndDbDto].success(data=data)
    except Exception as e:
        logger.error(f"获取支持的语言和数据库列表发生意外错误: {str(e)}", exc_info=True)
        return ApiResponse.fail(message="获取支持列表时发生内部服务器错误")


@router.post("/code/template/list", response_model=ApiResponse[List[CodeTemplateDto]], summary="获取代码模板列表")
async def get_code_templates(
    current_user_id: int = Depends(get_current_active_user_id),
    service: 'DataDesignService' = Depends(_get_data_design_service)
):
    try:
        templates = await service.get_code_templates_async(current_user_id)
        return ApiResponse[List[CodeTemplateDto]].success(data=templates)
    except Exception as e:
        logger.error(f"获取代码模板列表发生意外错误 (user: {current_user_id}): {str(e)}", exc_info=True)
        return ApiResponse.fail(message="获取代码模板列表时发生内部服务器错误")


@router.post("/code/template/dtls", response_model=ApiResponse[List[CodeTemplateDetailDto]], summary="获取代码模板的明细列表")
async def get_code_template_details(
    request_data: BaseIdRequestDto, # template_id is in BaseIdRequestDto.id
    current_user_id: int = Depends(get_current_active_user_id),
    service: 'DataDesignService' = Depends(_get_data_design_service)
):
    try:
        details = await service.get_code_template_dtls_async(current_user_id, request_data.id)
        return ApiResponse[List[CodeTemplateDetailDto]].success(data=details)
    except NotFoundException as e:
        logger.warning(f"获取代码模板详情未找到 (template_id: {request_data.id}, user: {current_user_id}): {e.message}")
        return ApiResponse.fail(message=e.message, code=status.HTTP_404_NOT_FOUND)
    except BusinessException as e: # For permission issues
        logger.warning(f"获取代码模板详情业务异常 (template_id: {request_data.id}, user: {current_user_id}): {e.message}")
        return ApiResponse.fail(message=e.message, code=e.code or status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"获取代码模板详情发生意外错误 (template_id: {request_data.id}, user: {current_user_id}): {str(e)}", exc_info=True)
        return ApiResponse.fail(message="获取模板详情时发生内部服务器错误")


@router.post("/code/template/create", response_model=ApiResponse[int], summary="用户新建代码模板")
async def create_code_template(
    request_data: CreateCodeTemplateDto,
    current_user_id: int = Depends(get_current_active_user_id),
    service: 'DataDesignService' = Depends(_get_data_design_service)
):
    try:
        template_id = await service.create_code_template_async(current_user_id, request_data)
        return ApiResponse[int].success(data=template_id, message="代码模板创建成功")
    except Exception as e:
        logger.error(f"创建代码模板发生意外错误 (user: {current_user_id}): {str(e)}", exc_info=True)
        return ApiResponse.fail(message="创建代码模板时发生内部服务器错误")


@router.post("/code/template/delete", response_model=ApiResponse[bool], summary="删除用户代码模板")
async def delete_code_template(
    request_data: BaseIdRequestDto, # template_id is in BaseIdRequestDto.id
    current_user_id: int = Depends(get_current_active_user_id),
    service: 'DataDesignService' = Depends(_get_data_design_service)
):
    try:
        success = await service.delete_code_template_async(current_user_id, request_data.id)
        return ApiResponse[bool].success(data=success, message="代码模板删除成功" if success else "代码模板删除失败")
    except BusinessException as e:
        logger.warning(f"删除代码模板业务异常 (template_id: {request_data.id}, user: {current_user_id}): {e.message}")
        return ApiResponse[bool].fail(message=e.message, code=e.code or status.HTTP_400_BAD_REQUEST, data=False)
    except Exception as e:
        logger.error(f"删除代码模板发生意外错误 (template_id: {request_data.id}, user: {current_user_id}): {str(e)}", exc_info=True)
        return ApiResponse[bool].fail(message="删除代码模板时发生内部服务器错误", data=False)


@router.post("/code/template/generatedtl", summary="借助AI流式生成代码模板内容 (SSE)")
async def generate_code_template_detail_stream( # Renamed to avoid conflict if non-stream exists
    request_data: GenerateCodeTemplateRequestDto,
    current_user_id: int = Depends(get_current_active_user_id),
    service: 'DataDesignService' = Depends(_get_data_design_service)
):
    queue = asyncio.Queue()
    async def sse_on_chunk_callback(chunk_data: str): # chunk_data is raw AI output here
        event_id = "template_gen_stream"
        # For this one, the service `generate_templates_with_ai_async`'s callback directly provides AI model's chunk
        formatted_sse_event = await send_sse_event(event_id, "chunk", chunk_data)
        await queue.put(formatted_sse_event)

    service_call_task = asyncio.create_task(
        service.generate_templates_with_ai_async(
            current_user_id, 
            request_data.template_id, 
            request_data.requirements, 
            sse_on_chunk_callback
        )
    )
    
    return StreamingResponse(
        sse_streamer(
            "template_generatedtl", 
            {"message": "开始生成模板内容"}, 
            service_call_task, 
            queue,
            logger
        ), 
        media_type="text/event-stream"
    )


@router.post("/code/template/example", response_model=ApiResponse[TemplateExampleDto], summary="获取AI生成模板的示例需求")
async def get_example_requirements(
    request_data: GetExampleRequirementsRequestDto,
    service: 'DataDesignService' = Depends(_get_data_design_service)
):
    # This endpoint does not require authentication in C# version
    try:
        example = await service.get_example_requirements_async(request_data.language, request_data.database_type)
        return ApiResponse[TemplateExampleDto].success(data=example)
    except Exception as e:
        logger.error(f"获取模板示例需求发生意外错误 (lang: {request_data.language}, db: {request_data.database_type}): {str(e)}", exc_info=True)
        return ApiResponse.fail(message="获取示例需求时发生内部服务器错误")

