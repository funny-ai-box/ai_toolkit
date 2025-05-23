import logging
from typing import List, Optional, Union, Any
from fastapi import APIRouter, Depends, Body, Query, status, Response, Request
from fastapi.responses import StreamingResponse
import asyncio
import json

from app.core.database.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_active_user_id,
    get_chatai_service_from_state,
    get_redis_service_from_state,
    RateLimiter
)

from app.core.dtos import ApiResponse, BaseIdRequestDto, PagedResultDto
from app.core.exceptions import BusinessException, NotFoundException, ValidationException

from app.modules.base.prompts.services import PromptTemplateService
from app.modules.base.prompts.repositories import PromptTemplateRepository

from app.modules.tools.survey.dtos import (
    CreateSurveyTaskRequestDto, UpdateSurveyTaskRequestDto, SurveyTaskListItemDto,
    SurveyTaskDetailDto, AIDesignRequestDto, AIDesignHistoryRequestDto,
    DesignHistoryMessageDto, SubmitSurveyResponseRequestDto, ResponseListRequestDto,
    SurveyResponseListItemDto, SurveyResponseDetailDto, SurveyReportDto
)
from app.modules.tools.survey.repositories import (
    SurveyTaskRepository, SurveyTabRepository, SurveyFieldRepository,
    SurveyResponseRepository, SurveyResponseDetailRepository, SurveyDesignHistoryRepository
)
from app.modules.tools.survey.services.ai_design_service import AIDesignService
from app.modules.tools.survey.services import (
    SurveyTaskService, SurveyDesignService, SurveyResponseService, SurveyReportService
)

# 创建logger
logger = logging.getLogger(__name__)

# 创建API路由
router = APIRouter(
    prefix="/survey",
    tags=["Survey"],
    responses={404: {"description": "Not found"}}
)

# 内部依赖项工厂：获取服务实例
def _get_services(db: AsyncSession = Depends(get_db)):
    """获取问卷服务"""
    
    # 创建仓储
    task_repository = SurveyTaskRepository(db)
    tab_repository = SurveyTabRepository(db)
    field_repository = SurveyFieldRepository(db)
    design_history_repository = SurveyDesignHistoryRepository(db)
    response_repository = SurveyResponseRepository(db)
    response_detail_repository = SurveyResponseDetailRepository(db)
    
    # 创建服务
    task_service = SurveyTaskService(
        db=db,
        task_repository=task_repository,
        tab_repository=tab_repository,
        field_repository=field_repository,
        response_repository=response_repository
    )
    
    design_service = None
    response_service = SurveyResponseService(
        db=db,
        task_repository=task_repository,
        field_repository=field_repository,
        response_repository=response_repository,
        response_detail_repository=response_detail_repository
    )
    
    report_service = SurveyReportService(
        db=db,
        task_repository=task_repository,
        field_repository=field_repository,
        response_repository=response_repository,
        response_detail_repository=response_detail_repository
    )
    
    return task_service, design_service, response_service, report_service

# 内部依赖项工厂：获取AI设计服务
def _get_design_service(
    db: AsyncSession = Depends(get_db),
    ai_service = Depends(get_chatai_service_from_state),
    redis_service = Depends(get_redis_service_from_state)
):
    """获取AI设计服务"""
    
    # 创建仓储
    task_repository = SurveyTaskRepository(db)
    tab_repository = SurveyTabRepository(db)
    field_repository = SurveyFieldRepository(db)
    design_history_repository = SurveyDesignHistoryRepository(db)
    
    # 创建提示词模板服务
    prompt_repo = PromptTemplateRepository(db=db)
    prompt_service = PromptTemplateService(db=db, repository=prompt_repo, redis_service=redis_service)
    
    # 创建AI设计服务
    ai_design_service = AIDesignService(
        ai_service=ai_service,
        prompt_template_service=prompt_service,
        design_history_repository=design_history_repository
    )
    
    # 创建设计服务
    design_service = SurveyDesignService(
        db=db,
        task_repository=task_repository,
        tab_repository=tab_repository,
        field_repository=field_repository,
        design_history_repository=design_history_repository,
        ai_design_service=ai_design_service
    )
    
    return design_service


#
# 问卷任务管理API
#

@router.post("/tasks/create", response_model=ApiResponse[int])
async def create_task(
    request: CreateSurveyTaskRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    创建问卷任务
    
    Args:
        request: 创建请求
        user_id: 当前用户ID
        services: 服务实例
    
    Returns:
        任务ID
    """
    task_service, _, _, _ = services
    task_id = await task_service.create_task_async(user_id, request)
    return ApiResponse.success(data=task_id, message="问卷任务创建成功")


@router.post("/tasks/update", response_model=ApiResponse)
async def update_task(
    request: UpdateSurveyTaskRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    更新问卷任务基本信息
    
    Args:
        request: 更新请求
        user_id: 当前用户ID
        services: 服务实例
    
    Returns:
        操作结果
    """
    task_service, _, _, _ = services
    result = await task_service.update_task_async(user_id, request)
    return ApiResponse.success(message="问卷任务更新成功") if result else ApiResponse.fail(message="问卷任务更新失败")


@router.post("/tasks/delete", response_model=ApiResponse)
async def delete_task(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    删除问卷任务
    
    Args:
        request: 任务ID请求
        user_id: 当前用户ID
        services: 服务实例
    
    Returns:
        操作结果
    """
    task_service, _, _, _ = services
    result = await task_service.delete_task_async(user_id, request.id)
    return ApiResponse.success(message="问卷任务删除成功") if result else ApiResponse.fail(message="问卷任务删除失败")


@router.post("/tasks/list", response_model=ApiResponse[PagedResultDto[SurveyTaskListItemDto]])
async def get_task_list(
    user_id: int = Depends(get_current_active_user_id),
    page_index: int = Query(1, ge=1, alias="pageIndex"),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    services = Depends(_get_services)
):
    """
    获取问卷任务列表
    
    Args:
        user_id: 当前用户ID
        page_index: 页码
        page_size: 每页数量
        services: 服务实例
    
    Returns:
        任务列表
    """
    task_service, _, _, _ = services
    result = await task_service.get_user_tasks_async(user_id, page_index, page_size)
    return ApiResponse.success(data=result)


@router.post("/tasks/detail", response_model=ApiResponse[SurveyTaskDetailDto])
async def get_task_detail(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    获取问卷任务详情
    
    Args:
        request: 任务ID请求
        user_id: 当前用户ID
        services: 服务实例
    
    Returns:
        任务详情
    """
    task_service, _, _, _ = services
    task = await task_service.get_task_async(user_id, request.id)
    return ApiResponse.success(data=task)


@router.post("/tasks/publish", response_model=ApiResponse[str])
async def publish_task(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    发布问卷任务
    
    Args:
        request: 任务ID请求
        user_id: 当前用户ID
        services: 服务实例
    
    Returns:
        分享URL
    """
    task_service, _, _, _ = services
    share_url = await task_service.publish_task_async(user_id, request.id)
    return ApiResponse.success(data=share_url, message="问卷发布成功")


@router.post("/tasks/close", response_model=ApiResponse)
async def close_task(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    关闭问卷任务
    
    Args:
        request: 任务ID请求
        user_id: 当前用户ID
        services: 服务实例
    
    Returns:
        操作结果
    """
    task_service, _, _, _ = services
    result = await task_service.close_task_async(user_id, request.id)
    return ApiResponse.success(message="问卷任务关闭成功") if result else ApiResponse.fail(message="问卷任务关闭失败")


@router.get("/share", response_model=ApiResponse[SurveyTaskDetailDto])
async def get_task_by_share_code(
    share_code: str,
    services = Depends(_get_services)
):
    """
    通过共享码获取问卷任务
    
    Args:
        share_code: 共享码
        services: 服务实例
    
    Returns:
        任务详情
    """
    task_service, _, _, _ = services
    task = await task_service.get_task_by_share_code_async(share_code)
    return ApiResponse.success(data=task)


#
# 问卷设计API
#

@router.post("/design/ai/stream")
@router.post("/design/ai/stream", response_class=StreamingResponse, status_code=status.HTTP_200_OK)
async def ai_design_streaming(
    request: AIDesignRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    design_service: SurveyDesignService = Depends(_get_design_service),
    rate_limiter: None = Depends(RateLimiter(limit=10, period_seconds=60, limit_type="user"))
):
    """
    流式AI设计问卷
    
    Args:
        request: 设计请求
        user_id: 当前用户ID
        design_service: 设计服务实例
        rate_limiter: 限流器
    
    Returns:
        流式响应
    """
    async def event_generator():
        # 创建事件ID
        event_id = "survey_design_" + str(request.task_id)
        
        try:
            # 发送开始事件
            start_message = json.dumps({"message": "开始生成设计"})
            yield f"id: {event_id}\nevent: start\ndata: {start_message}\n\n"
            
            # 收集响应块
            chunks = []
            
            # 定义回调函数
            def on_chunk_received(chunk):
                # 记录响应块
                chunks.append(chunk)
                # 注意：SSE事件数据中不能有换行，需要进行处理
                escaped_chunk = chunk.replace("\n", "\\n").replace("\r", "\\r")
                return f"id: {event_id}\nevent: chunk\ndata: {escaped_chunk}\n\n"
            
            # # 调用流式设计API
            # response = await design_service.streaming_ai_design_fields_async(
            #     user_id=user_id,
            #     request=request,
            #     on_chunk_received=lambda chunk: yield(on_chunk_received(chunk)),
            #     cancellation_token=None
            # )
            
        except asyncio.CancelledError:
            # 用户取消请求
            yield f"id: {event_id}\nevent: canceled\ndata: 请求已取消\n\n"
        except Exception as ex:
            # 发送错误事件
            error_message = str(ex)
            logger.error(f"AI设计问卷失败: {error_message}")
            yield f"id: {event_id}\nevent: error\ndata: {error_message}\n\n"
        finally:
            # 发送结束事件
            yield f"id: {event_id}\nevent: end\ndata: \n\n"
    
    # 返回流式响应
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/design/history", response_model=ApiResponse[PagedResultDto[DesignHistoryMessageDto]])
async def get_design_history(
    request: AIDesignHistoryRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    design_service: SurveyDesignService = Depends(_get_design_service)
):
    """
    获取问卷设计历史
    
    Args:
        request: 设计历史请求
        user_id: 当前用户ID
        design_service: 设计服务实例
    
    Returns:
        设计历史
    """
    history = await design_service.get_design_history_async(
        user_id=user_id, 
        task_id=request.task_id, 
        page_index=request.page_index, 
        page_size=request.page_size
    )
    return ApiResponse.success(data=history)


#
# 问卷填写API
#

@router.post("/response/submit", response_model=ApiResponse[int])
async def submit_response(
    request: SubmitSurveyResponseRequestDto = Body(...),
    request_obj: Request = None,
    user_id: Optional[int] = Depends(get_current_active_user_id),
    services = Depends(_get_services),
    rate_limiter: None = Depends(RateLimiter(limit=20, period_seconds=60, limit_type="ip"))
):
    """
    提交问卷回答
    
    Args:
        request: 提交请求
        request_obj: 请求对象
        user_id: 当前用户ID（可选）
        services: 服务实例
        rate_limiter: 限流器（基于IP）
    
    Returns:
        提交结果
    """
    # 获取客户端IP
    ip = request_obj.client.host if request_obj else "Unknown"
    
    # 提交问卷回答
    _, _, response_service, _ = services
    response_id = await response_service.submit_response_async(user_id, ip, request)
    return ApiResponse.success(data=response_id, message="问卷提交成功")


@router.post("/response/list", response_model=ApiResponse[PagedResultDto[SurveyResponseListItemDto]])
async def get_response_list(
    request: ResponseListRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    获取问卷回答列表
    
    Args:
        request: 请求参数
        user_id: 当前用户ID
        services: 服务实例
    
    Returns:
        回答列表
    """
    _, _, response_service, _ = services
    result = await response_service.get_responses_async(
        user_id=user_id, 
        task_id=request.task_id,
        page_index=request.page_index,
        page_size=request.page_size
    )
    return ApiResponse.success(data=result)


@router.post("/response/detail", response_model=ApiResponse[SurveyResponseDetailDto])
async def get_response_detail(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    获取问卷回答详情
    
    Args:
        request: 回答ID请求
        user_id: 当前用户ID
        services: 服务实例
    
    Returns:
        回答详情
    """
    _, _, response_service, _ = services
    detail = await response_service.get_response_detail_async(user_id, request.id)
    return ApiResponse.success(data=detail)


@router.post("/response/delete", response_model=ApiResponse)
async def delete_response(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    删除问卷回答
    
    Args:
        request: 回答ID请求
        user_id: 当前用户ID
        services: 服务实例
    
    Returns:
        操作结果
    """
    _, _, response_service, _ = services
    result = await response_service.delete_response_async(user_id, request.id)
    return ApiResponse.success(message="问卷回答删除成功") if result else ApiResponse.fail(message="问卷回答删除失败")


#
# 问卷报表API
#

@router.post("/report/summary", response_model=ApiResponse[SurveyReportDto])
async def get_report(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    获取问卷报表
    
    Args:
        request: 任务ID请求
        user_id: 当前用户ID
        services: 服务实例
    
    Returns:
        问卷报表
    """
    _, _, _, report_service = services
    report = await report_service.get_report_async(user_id, request.id)
    return ApiResponse.success(data=report)