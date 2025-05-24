# app/modules/tools/prototype/router.py
import datetime
import logging
from typing import List, Optional, Dict, Any, Callable
import asyncio
from fastapi import (
    APIRouter, Depends, File, Form, UploadFile, Body, 
    Request, Response, HTTPException, BackgroundTasks, status
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.core.database.session import get_db
from app.api.dependencies import (
    get_current_active_user_id,
    get_chatai_service_from_state,
    get_storage_service_from_state,
    RateLimiter
)
from app.core.dtos import ApiResponse, BaseIdRequestDto, BasePageRequestDto, PagedResultDto
from app.core.exceptions import NotFoundException, BusinessException, ForbiddenException
from app.modules.base.prompts.services import PromptTemplateService


from app.modules.tools.prototype.constants import (
    PrototypeMessageType, PrototypePageStatus, PrototypeSessionStatus
)
from app.modules.tools.prototype.dtos import (
    CreateSessionRequestDto, GetSessionDetailRequestDto, UpdateSessionRequestDto,
    SessionListItemDto, SessionDetailDto, MessageListRequestDto, MessageDto,
    AIChatRequestDto, AIChatUploadReferenceDto, PageDetailDto
)
from app.modules.tools.prototype.repositories import (
    PrototypeSessionRepository, PrototypePageRepository, 
    PrototypePageHistoryRepository, PrototypeMessageRepository, 
    PrototypeResourceRepository
)
from app.modules.tools.prototype.services.session_service import PrototypeSessionService
from app.modules.tools.prototype.services.page_service import PrototypePageService
from app.modules.tools.prototype.services.message_service import PrototypeMessageService
from app.modules.tools.prototype.services.ai_chat_service import AIChatService
from app.modules.tools.prototype.services.preview_service import PrototypePreviewService


# 获取 Logger
logger = logging.getLogger(__name__)

# 创建 API Router
router = APIRouter(
    prefix="/prototype",  # API 前缀 (结合 main.py 中的 /api -> /api/prototype)
    tags=["AI原型页面"]  # Swagger UI 分组标签
)

# --- 内部依赖项工厂 ---
def _get_repositories(db: AsyncSession = Depends(get_db)):
    """获取仓储实例"""
    return {
        "session_repository": PrototypeSessionRepository(db),
        "page_repository": PrototypePageRepository(db),
        "page_history_repository": PrototypePageHistoryRepository(db),
        "message_repository": PrototypeMessageRepository(db),
        "resource_repository": PrototypeResourceRepository(db)
    }

def _get_session_service(
    db: AsyncSession = Depends(get_db),
    repositories=Depends(_get_repositories)
) -> PrototypeSessionService:
    """获取会话服务实例"""
    return PrototypeSessionService(
        db=db,
        session_repository=repositories["session_repository"],
        page_repository=repositories["page_repository"],
        message_repository=repositories["message_repository"],
        resource_repository=repositories["resource_repository"],
        logger=logger
    )

def _get_page_service(
    db: AsyncSession = Depends(get_db),
    repositories=Depends(_get_repositories)
) -> PrototypePageService:
    """获取页面服务实例"""
    return PrototypePageService(
        db=db,
        session_repository=repositories["session_repository"],
        page_repository=repositories["page_repository"],
        page_history_repository=repositories["page_history_repository"],
        logger=logger
    )

def _get_message_service(
    db: AsyncSession = Depends(get_db),
    repositories=Depends(_get_repositories)
) -> PrototypeMessageService:
    """获取消息服务实例"""
    return PrototypeMessageService(
        db=db,
        session_repository=repositories["session_repository"],
        message_repository=repositories["message_repository"],
        logger=logger
    )

def _get_preview_service(
    db: AsyncSession = Depends(get_db),
    repositories=Depends(_get_repositories)
) -> PrototypePreviewService:
    """获取预览服务实例"""
    return PrototypePreviewService(
        db=db,
        session_repository=repositories["session_repository"],
        page_repository=repositories["page_repository"],
        resource_repository=repositories["resource_repository"],
        logger=logger
    )

def _get_ai_chat_service(
    db: AsyncSession = Depends(get_db),
    ai_service = Depends(get_chatai_service_from_state),
    storage_service = Depends(get_storage_service_from_state),
    repositories = Depends(_get_repositories),
    prompt_template_service: PromptTemplateService = Depends()
) -> AIChatService:
    """获取AI对话服务实例"""
    return AIChatService(
        db=db,
        ai_service=ai_service,
        storage_service=storage_service,
        prompt_service=prompt_template_service,
        session_repository=repositories["session_repository"],
        page_repository=repositories["page_repository"],
        page_history_repository=repositories["page_history_repository"],
        message_repository=repositories["message_repository"],
        resource_repository=repositories["resource_repository"],
        logger=logger
    )


# --- 会话管理接口 ---
@router.post(
    "/session/create",
    response_model=ApiResponse[BaseIdRequestDto],
    summary="创建会话",
    description="创建新的原型设计会话"
)
async def create_session(
    request: CreateSessionRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    service: PrototypeSessionService = Depends(_get_session_service)
):
    """
    创建会话接口
    
    - **name**: 会话名称，若为空，后面将自动赋值
    - **description**: 会话描述
    
    *需要有效的登录令牌*
    """
    session_id = await service.create_session_async(user_id, request)
    return ApiResponse.success(
        data=BaseIdRequestDto(id=session_id),
        message="会话创建成功"
    )

@router.post(
    "/session/detail",
    response_model=ApiResponse[SessionDetailDto],
    summary="获取会话详情",
    description="获取指定会话的详细信息，包括页面列表（可选）"
)
async def get_session_detail(
    request: GetSessionDetailRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    service: PrototypeSessionService = Depends(_get_session_service)
):
    """
    获取会话详情接口
    
    - **id**: 会话ID
    - **includePages**: 是否包含页面详情
    
    *需要有效的登录令牌*
    """
    session = await service.get_session_async(user_id, request)
    return ApiResponse.success(data=session)

@router.post(
    "/session/list",
    response_model=ApiResponse[PagedResultDto[SessionListItemDto]],
    summary="获取会话列表",
    description="获取当前用户的会话列表"
)
async def get_session_list(
    request: BasePageRequestDto = Body(...),  # 修复：使用 BasePageRequestDto
    user_id: int = Depends(get_current_active_user_id),
    service: PrototypeSessionService = Depends(_get_session_service)
):
    """
    获取会话列表接口
    
    - **pageIndex**: 页码
    - **pageSize**: 每页大小
    
    *需要有效的登录令牌*
    """
    sessions = await service.get_user_sessions_async(user_id, request)
    return ApiResponse.success(data=sessions)

@router.post(
    "/session/update",
    response_model=ApiResponse,
    summary="更新会话信息",
    description="更新会话的名称和描述"
)
async def update_session(
    request: UpdateSessionRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    service: PrototypeSessionService = Depends(_get_session_service)
):
    """
    更新会话信息接口
    
    - **id**: 会话ID
    - **name**: 会话名称
    - **description**: 会话描述
    
    *需要有效的登录令牌*
    """
    result = await service.update_session_async(user_id, request)
    return ApiResponse.success(message="会话更新成功") if result else ApiResponse.fail(message="会话更新失败")


# --- 页面管理接口 ---
@router.post(
    "/page/detail",
    response_model=ApiResponse[PageDetailDto],
    summary="获取页面详情",
    description="获取指定页面的详细信息，包括内容和历史版本（可选）"
)
async def get_page_detail(
    request: BaseIdRequestDto = Body(...),
    include_history: bool = False,
    user_id: int = Depends(get_current_active_user_id),
    service: PrototypePageService = Depends(_get_page_service)
):
    """
    获取页面详情接口
    
    - **id**: 页面ID
    - **includeHistory**: 是否包含历史版本
    
    *需要有效的登录令牌*
    """
    page = await service.get_page_async(user_id, request.id, include_history)
    return ApiResponse.success(data=page)

# app/modules/tools/prototype/router.py (continued)
@router.post(
    "/page/list",
    response_model=ApiResponse[List[PageDetailDto]],
    summary="获取会话的所有页面",
    description="获取指定会话的所有页面列表"
)
async def get_session_pages(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    service: PrototypePageService = Depends(_get_page_service)
):
    """
    获取会话的所有页面接口
    
    - **id**: 会话ID
    
    *需要有效的登录令牌*
    """
    pages = await service.get_session_pages_async(user_id, request.id)
    return ApiResponse.success(data=pages)


# --- 消息管理接口 ---
@router.post(
    "/message/paged",
    response_model=ApiResponse[PagedResultDto[MessageDto]],
    summary="分页获取会话的消息",
    description="分页获取指定会话的所有消息"
)
async def get_session_messages_paged(
    request: MessageListRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    service: PrototypeMessageService = Depends(_get_message_service)
):
    """
    分页获取会话消息接口
    
    - **sessionId**: 会话ID
    - **pageIndex**: 页码
    - **pageSize**: 每页大小
    
    *需要有效的登录令牌*
    """
    messages = await service.get_session_messages_paged_async(user_id, request)
    return ApiResponse.success(data=messages)


# --- AI对话接口 ---
class SSEItem:
    """SSE事件项"""
    def __init__(self, event_id: str, session_id: int, event_type: str, data: str):
        """
        初始化SSE事件项
        
        Args:
            event_id: 事件ID
            session_id: 会话ID
            event_type: 事件类型
            data: 数据
        """
        self.event_id = event_id
        self.session_id = session_id
        self.event_type = event_type
        self.data = data
    
    def __str__(self) -> str:
        """
        转换为SSE格式字符串
        
        Returns:
            SSE格式字符串
        """
        return f"id: {self.event_id}\nevent: {self.event_type}\ndata: {self.data}\n\n"

async def get_chat_service_instance(db: AsyncSession, request: Request) -> AIChatService:
    """获取AIChatService实例，不作为FastAPI依赖项"""
    # 获取必要的依赖
    ai_service = getattr(request.app.state, 'ai_services', None)
    storage_service = getattr(request.app.state, 'storage_service', None)
    
    # 创建仓储实例
    session_repository = PrototypeSessionRepository(db)
    page_repository = PrototypePageRepository(db)
    page_history_repository = PrototypePageHistoryRepository(db)
    message_repository = PrototypeMessageRepository(db)
    resource_repository = PrototypeResourceRepository(db)
    
    # 获取提示词服务
    from app.modules.base.prompts.services import PromptTemplateService
    from app.modules.base.prompts.repositories import PromptTemplateRepository
    prompt_repo = PromptTemplateRepository(db)
    redis_service = getattr(request.app.state, 'redis_service', None)
    prompt_service = PromptTemplateService(db=db, repository=prompt_repo, redis_service=redis_service)
    
    # 创建并返回服务实例
    return AIChatService(
        db=db,
        ai_service=ai_service,
        storage_service=storage_service,
        prompt_service=prompt_service,
        session_repository=session_repository,
        page_repository=page_repository,
        page_history_repository=page_history_repository,
        message_repository=message_repository,
        resource_repository=resource_repository,
        logger=logger
    )


async def get_chat_service_instance(db: AsyncSession, request: Request) -> AIChatService:
    """获取AIChatService实例，不作为FastAPI依赖项"""
    # 获取必要的依赖
    ai_service = getattr(request.app.state, 'ai_services', None)
    storage_service = getattr(request.app.state, 'storage_service', None)
    
    # 创建仓储实例
    session_repository = PrototypeSessionRepository(db)
    page_repository = PrototypePageRepository(db)
    page_history_repository = PrototypePageHistoryRepository(db)
    message_repository = PrototypeMessageRepository(db)
    resource_repository = PrototypeResourceRepository(db)
    
    # 获取提示词服务
    from app.modules.base.prompts.services import PromptTemplateService
    from app.modules.base.prompts.repositories import PromptTemplateRepository
    prompt_repo = PromptTemplateRepository(db)
    redis_service = getattr(request.app.state, 'redis_service', None)
    prompt_service = PromptTemplateService(db=db, repository=prompt_repo, redis_service=redis_service)
    
    # 创建并返回服务实例
    return AIChatService(
        db=db,
        ai_service=ai_service,
        storage_service=storage_service,
        prompt_service=prompt_service,
        session_repository=session_repository,
        page_repository=page_repository,
        page_history_repository=page_history_repository,
        message_repository=message_repository,
        resource_repository=resource_repository,
        logger=logger
    )

# 修改AI对话接口

@router.post(
    "/ai/chatstream",
    summary="发送AI对话消息",
    description="发送消息到AI并获取流式回复",
    response_model=None,  # 禁用响应模型生成
)
async def send_ai_chat_streaming(
    req: Request,  # 将非默认参数移到前面
    request: AIChatRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    发送AI对话消息接口，使用Server-Sent Events流式返回
    
    - **sessionId**: 会话ID
    - **userMessage**: 用户消息
    - **attachments**: 附件ID列表
    
    *需要有效的登录令牌*
    """
    # 手动创建服务实例，绕过FastAPI的依赖解析
    ai_chat_service = await get_chat_service_instance(db, req)
    
    # 使用异步生成器创建SSE流
    async def event_generator():
        # 创建事件ID
        import uuid
        event_id = str(uuid.uuid4())
        
        try:
            # 发送开始事件
            yield f"id: {event_id}\nevent: start\ndata: {json.dumps({'message': '开始生成回复'})}\n\n"
            
            # 记录收集到的块
            chunks = []
            
            # 定义块接收回调
            def on_chunk_received(chunk: str):
                chunks.append(chunk)
                return f"id: {event_id}\nevent: chunk\ndata: {chunk}\n\n"
            
            # 调用流式聊天API并获取结果
            response = await ai_chat_service.send_ai_chat_async(
                user_id,
                request,
                on_chunk_received
            )
            
            # 对于每个收到的块，生成事件
            for chunk_event in chunks:
                yield chunk_event
            
            # 发送完成事件
            yield f"id: {event_id}\nevent: done\ndata: \n\n"
        except asyncio.CancelledError:
            # 用户取消请求
            yield f"id: {event_id}\nevent: canceled\ndata: 请求已取消\n\n"
        except Exception as ex:
            # 发生错误
            yield f"id: {event_id}\nevent: error\ndata: {str(ex)}\n\n"
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

@router.post(
    "/ai/chat/uploadimage",
    response_model=ApiResponse[AIChatUploadReferenceDto],
    summary="上传参考图片",
    description="上传用于AI对话的参考图片"
)
async def upload_reference_image(
      req: Request,  # 添加请求对象参数
    request: BaseIdRequestDto = Form(...),
    image: UploadFile = File(...),
  
    user_id: int = Depends(get_current_active_user_id),
    db: AsyncSession = Depends(get_db)  # 直接获取数据库会话
):
    """
    上传参考图片接口
    
    - **id**: 会话ID
    - **image**: 图片文件
    
    *需要有效的登录令牌*
    """
    # 手动创建服务实例
    ai_chat_service = await get_chat_service_instance(db, req)
    
    file_id, file_url = await ai_chat_service.upload_reference_image_async(user_id, request.id, image)
    return ApiResponse.success(
        data=AIChatUploadReferenceDto(id=file_id, url=file_url),
        message="参考图片上传成功"
    )


# --- 预览接口 ---
@router.get(
    "/preview/{session_id}/{path:path}",
    summary="预览HTML页面",
    description="预览指定路径的HTML页面内容",
)
async def preview_page(
    session_id: int,
    path: str = "index.html",
    preview_service: PrototypePreviewService = Depends(_get_preview_service)
):
    """
    预览HTML页面接口
    
    - **session_id**: 会话ID
    - **path**: 页面路径 (可选，默认为index.html)
    
    *该接口允许匿名访问，通过会话ID进行权限验证*
    """
    try:
        # 标准化路径
        if not path:
            path = "index.html"
        elif not path.endswith(".html") and not path.endswith("/"):
            path += ".html"
        
        # 获取页面HTML
        html = await preview_service.get_page_html_async(session_id, path)
        
        # 返回HTML内容
        return Response(
            content=html,
            media_type="text/html",
            status_code=200
        )
    except Exception as ex:
        # 构建错误HTML页面
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
      <p class="text-gray-600 mb-6">{str(ex)}</p>
      <a href="/api/prototype/preview/{session_id}/index.html" class="inline-block bg-blue-500 hover:bg-blue-600 text-white font-medium py-2 px-4 rounded transition-colors duration-300">
        返回首页
      </a>
    </div>
  </div>
</body>
</html>"""
        
        # 返回错误页面
        return Response(
            content=error_html,
            media_type="text/html",
            status_code=404
        )