"""
原型设计模块的路由定义
"""
import logging
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    UploadFile,
    Body,
    Request,
    Response,
    status,
    BackgroundTasks
)
from fastapi.responses import StreamingResponse,HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.config.settings import settings
from app.api.dependencies import (
    get_current_active_user_id,
    get_chatai_service_from_state,
    get_storage_service_from_state,
    get_redis_service_from_state,
    RateLimiter
)
from app.core.dtos import ApiResponse, BaseIdRequestDto, PagedResultDto
from app.core.exceptions import NotFoundException, BusinessException, ForbiddenException
from app.core.ai.chat.base import IChatAIService
from app.core.storage.base import IStorageService
from app.core.redis.service import RedisService
from app.modules.base.prompts.services import PromptTemplateService

from app.modules.tools.prototype.dtos import (
    CreateSessionRequestDto,
    UpdateSessionRequestDto,
    GetSessionDetailRequestDto,
    SessionDetailDto,
    SessionListItemDto,
    PageDetailDto,
    MessageListRequestDto,
    MessageDto,
    AIChatRequestDto,
    AIChatUploadReferenceDto
)
from app.modules.tools.prototype.config import get_prototype_config
from app.modules.tools.prototype.repositories import (
    PrototypeSessionRepository,
    PrototypePageRepository,
    PrototypePageHistoryRepository,
    PrototypeMessageRepository,
    PrototypeResourceRepository
)
from app.modules.tools.prototype.services.ai_chat_service import AIChatService
from app.modules.tools.prototype.services.message_service import PrototypeMessageService
from app.modules.tools.prototype.services.page_service import PrototypePageService
from app.modules.tools.prototype.services.preview_service import PrototypeHtmlPreviewService
from app.modules.tools.prototype.services.session_service import PrototypeSessionService


# 创建日志记录器
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(
    prefix="/prototype",
    tags=["Prototype Design"],
    responses={404: {"description": "Not found"}}
)

# 内部依赖项工厂：获取服务实例
def _get_services(
    db: AsyncSession = Depends(get_db),
    ai_service: IChatAIService = Depends(get_chatai_service_from_state),
    storage_service: IStorageService = Depends(get_storage_service_from_state),
    redis_service: RedisService = Depends(get_redis_service_from_state),
    prompt_template_service: PromptTemplateService = Depends()
):
    """
    内部依赖项：创建并返回服务实例
    
    Args:
        db: 数据库会话
        ai_service: AI服务
        storage_service: 存储服务
        redis_service: Redis服务
        prompt_template_service: 提示词模板服务
        
    Returns:
        服务实例元组
    """
    # 获取配置
    config = get_prototype_config()
    
    # 创建仓储
    session_repo = PrototypeSessionRepository(db)
    page_repo = PrototypePageRepository(db)
    page_history_repo = PrototypePageHistoryRepository(db)
    message_repo = PrototypeMessageRepository(db)
    resource_repo = PrototypeResourceRepository(db)
    
    # 创建服务
    session_service = PrototypeSessionService(
        db=db,
        session_repository=session_repo,
        page_repository=page_repo,
        message_repository=message_repo,
        resource_repository=resource_repo,
        logger=logger
    )
    
    page_service = PrototypePageService(
        db=db,
        session_repository=session_repo,
        page_repository=page_repo,
        page_history_repository=page_history_repo,
        logger=logger
    )
    
    message_service = PrototypeMessageService(
        db=db,
        session_repository=session_repo,
        message_repository=message_repo,
        logger=logger
    )
    
    ai_chat_service = AIChatService(
        db=db,
        ai_service=ai_service,
        storage_service=storage_service,
        prompt_template_service=prompt_template_service,
        session_repository=session_repo,
        page_repository=page_repo,
        page_history_repository=page_history_repo,
        message_repository=message_repo,
        resource_repository=resource_repo,
        chat_ai_provider_type=config.chat_ai_provider_type,
        logger=logger
    )
    
    preview_service = PrototypeHtmlPreviewService(
        db=db,
        session_repository=session_repo,
        page_repository=page_repo,
        resource_repository=resource_repo,
        logger=logger
    )
    
    return session_service, page_service, message_service, ai_chat_service, preview_service

# 获取各个服务的依赖函数
def _get_session_service(services=Depends(_get_services)):
    return services[0]

def _get_page_service(services=Depends(_get_services)):
    return services[1]

def _get_message_service(services=Depends(_get_services)):
    return services[2]

def _get_ai_chat_service(services=Depends(_get_services)):
    return services[3]

def _get_preview_service(services=Depends(_get_services)):
    return services[4]


# 会话管理API
@router.post(
    "/session/create",
    response_model=ApiResponse[BaseIdRequestDto],
    summary="创建会话",
    description="创建新的原型设计会话"
)
async def create_session(
    request: CreateSessionRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    session_service: PrototypeSessionService = Depends(_get_session_service)
):
    """
    创建一个新的原型设计会话
    """
    session_id = await session_service.create_session_async(user_id, request)
    return ApiResponse.success(data=BaseIdRequestDto(id=session_id), message="会话创建成功")


@router.post(
    "/session/detail",
    response_model=ApiResponse[SessionDetailDto],
    summary="获取会话详情",
    description="获取原型设计会话详细信息"
)
async def get_session_detail(
    request: GetSessionDetailRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    session_service: PrototypeSessionService = Depends(_get_session_service)
):
    """
    获取会话详情
    """
    session = await session_service.get_session_async(user_id, request)
    return ApiResponse.success(data=session)


@router.post(
    "/session/list",
    response_model=ApiResponse[PagedResultDto[SessionListItemDto]],
    summary="获取会话列表",
    description="获取用户的所有原型设计会话"
)
async def get_session_list(
    request: BaseIdRequestDto = Body(...),  # 使用BasePageRequestDto，但忽略id字段
    user_id: int = Depends(get_current_active_user_id),
    session_service: PrototypeSessionService = Depends(_get_session_service)
):
    """
    获取用户的所有会话列表
    """
    sessions = await session_service.get_user_sessions_async(user_id, request)
    return ApiResponse.success(data=sessions)


@router.post(
    "/session/update",
    response_model=ApiResponse,
    summary="更新会话",
    description="更新原型设计会话信息"
)
async def update_session(
    request: UpdateSessionRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    session_service: PrototypeSessionService = Depends(_get_session_service)
):
    """
    更新会话信息
    """
    result = await session_service.update_session_async(user_id, request)
    return ApiResponse.success(message="会话更新成功") if result else ApiResponse.fail(message="会话更新失败")


# 页面管理API
@router.post(
    "/page/detail",
    response_model=ApiResponse[PageDetailDto],
    summary="获取页面详情",
    description="获取原型设计页面详细信息"
)
async def get_page_detail(
    request: BaseIdRequestDto = Body(...),
    include_history: bool = False,
    user_id: int = Depends(get_current_active_user_id),
    page_service: PrototypePageService = Depends(_get_page_service)
):
    """
    获取页面详情
    """
    page = await page_service.get_page_async(user_id, request.id, include_history)
    return ApiResponse.success(data=page)


@router.post(
    "/page/list",
    response_model=ApiResponse[List[PageDetailDto]],
    summary="获取页面列表",
    description="获取会话的所有页面"
)
async def get_session_pages(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    page_service: PrototypePageService = Depends(_get_page_service)
):
    """
    获取会话的所有页面
    """
    pages = await page_service.get_session_pages_async(user_id, request.id)
    return ApiResponse.success(data=pages)


# 消息管理API
@router.post(
    "/message/paged",
    response_model=ApiResponse[PagedResultDto[MessageDto]],
    summary="获取消息列表",
    description="分页获取会话的消息列表"
)
async def get_session_messages_paged(
    request: MessageListRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    message_service: PrototypeMessageService = Depends(_get_message_service)
):
    """
    分页获取会话的消息
    """
    messages = await message_service.get_session_messages_paged_async(user_id, request)
    return ApiResponse.success(data=messages)


# AI对话API
@router.post(
    "/ai/chatstream",
    summary="发送AI对话消息(流式)",
    description="发送消息给AI并获取流式回复"
)
async def send_ai_chat_streaming(
    request: AIChatRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    ai_chat_service: AIChatService = Depends(_get_ai_chat_service)
):
    """
    发送AI对话消息并获取流式回复
    """
    async def event_generator():
        # 创建事件id
        event_id = settings.id_generator.next_id()
        
        try:
            # 发送开始事件
            yield f"id: {event_id}\nevent: start\ndata: {{'message': '开始生成回复'}}\n\n"
            
            # 调用流式聊天API
            async def on_chunk_received(chunk):
                # 发送数据块
                nonlocal event_id
                yield f"id: {event_id}\nevent: chunk\ndata: {chunk}\n\n"
            
            await ai_chat_service.send_ai_chat_async(
                user_id=user_id,
                request=request,
                on_chunk_received=on_chunk_received
            )
            
            # 发送完成事件
            yield f"id: {event_id}\nevent: done\ndata: \n\n"
        except Exception as ex:
            # 发生错误
            if isinstance(ex, (ForbiddenException, BusinessException)):
                error_message = str(ex)
            else:
                logger.error("处理AI对话时出错", exc_info=ex)
                error_message = "发送AI对话消息失败"
            
            yield f"id: {event_id}\nevent: error\ndata: {error_message}\n\n"
        finally:
            # 发送结束事件
            yield f"id: {event_id}\nevent: end\ndata: \n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@router.post(
    "/ai/chat/uploadimage",
    response_model=ApiResponse[AIChatUploadReferenceDto],
    summary="上传参考图片",
    description="上传参考图片用于AI对话"
)
async def upload_reference_image(
    session_id: int = Form(..., alias="id"),
    image: UploadFile = File(...),
    user_id: int = Depends(get_current_active_user_id),
    ai_chat_service: AIChatService = Depends(_get_ai_chat_service)
):
    """
    上传参考图片
    """
    image_id, image_url = await ai_chat_service.upload_reference_image_async(user_id, session_id, image)
    return ApiResponse.success(
        data=AIChatUploadReferenceDto(id=image_id, url=image_url),
        message="参考图片上传成功"
    )


# 预览API
@router.get(
    "/preview/{session_id}/{path:path}",
    summary="预览HTML页面",
    description="预览生成的HTML页面",
    response_class=HTMLResponse
)
async def preview_page(
    session_id: int,
    path: str = "",
    preview_service: PrototypeHtmlPreviewService = Depends(_get_preview_service)
):
    """
    预览HTML页面
    """
    try:
        # 标准化路径
        if not path:
            path = "index.html"
        elif not path.endswith(".html") and not path.endswith("/"):
            path += ".html"
        
        # 获取页面HTML
        html = await preview_service.get_page_html_async(session_id, path)
        
        return HTMLResponse(
            content=html,
            media_type="text/html",
            status_code=200
        )
    except Exception as ex:
        # 返回错误页面
        if isinstance(ex, (NotFoundException, ForbiddenException, BusinessException)):
            error_message = str(ex)
        else:
            logger.error("预览页面时出错", exc_info=ex)
            error_message = "页面加载失败"
        
        error_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>页面加载错误</title>
  <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
</head>
<body class="bg-gray-100 flex items-center justify-center min-h-screen p-4">
  <div class="bg-white shadow-lg rounded-lg p-8 max-w-lg w-full">
    <div class="text-center">
      <svg class="w-16 h-16 text-red-500 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
      </svg>
      <h2 class="text-2xl font-bold text-gray-800 mb-2">页面加载错误</h2>
      <p class="text-gray-600 mb-6">{error_message}</p>
      <a href="/api/prototype/preview/{session_id}/index.html" class="inline-block bg-blue-500 hover:bg-blue-600 text-white font-medium py-2 px-4 rounded transition-colors duration-300">
        返回首页
      </a>
    </div>
  </div>
</body>
</html>"""
        
        return HTMLResponse(
            content=error_html,
            media_type="text/html",
            status_code=404
        )