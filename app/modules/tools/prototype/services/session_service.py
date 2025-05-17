# app/modules/tools/prototype/services/session_service.py
import datetime
from typing import List, Optional
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dtos import PagedResultDto
from app.core.exceptions import NotFoundException, BusinessException
from app.modules.tools.prototype.constants import PrototypeSessionStatus, PrototypePageStatus, PrototypeMessageType
from app.modules.tools.prototype.dtos import (
    CreateSessionRequestDto, GetSessionDetailRequestDto, UpdateSessionRequestDto,
    SessionListItemDto, SessionDetailDto, PageDetailDto, BasePageRequestDto
)
from app.modules.tools.prototype.models import PrototypeSession, PrototypeMessage
from app.modules.tools.prototype.repositories import (
    PrototypeSessionRepository, PrototypePageRepository, 
    PrototypeMessageRepository, PrototypeResourceRepository
)


class PrototypeSessionService:
    """原型会话服务实现"""
    
    def __init__(
        self,
        db: AsyncSession,
        session_repository: PrototypeSessionRepository,
        page_repository: PrototypePageRepository,
        message_repository: PrototypeMessageRepository,
        resource_repository: PrototypeResourceRepository,
        logger: Optional[logging.Logger] = None
    ):
        """
        初始化
        
        Args:
            db: 数据库会话
            session_repository: 会话仓储
            page_repository: 页面仓储
            message_repository: 消息仓储
            resource_repository: 资源仓储
            logger: 日志记录器
        """
        self.db = db
        self.session_repository = session_repository
        self.page_repository = page_repository
        self.message_repository = message_repository
        self.resource_repository = resource_repository
        self.logger = logger or logging.getLogger(__name__)
    
    async def create_session_async(self, user_id: int, request: CreateSessionRequestDto) -> int:
        """
        创建会话
        
        Args:
            user_id: 用户ID
            request: 创建请求
            
        Returns:
            会话ID
        """
        try:
            # 创建会话
            session = PrototypeSession(
                user_id=user_id,
                name=request.name if request.name else "新的会话",
                description=request.description,
                status=PrototypeSessionStatus.REQUIREMENT_GATHERING,
            )
            
            # 保存会话
            session_id = await self.session_repository.add_async(session)
            if session_id == 0:
                raise BusinessException("创建会话失败")
            
            # 添加系统欢迎消息
            welcome_message = PrototypeMessage(
                session_id=session_id,
                user_id=user_id,
                message_type=PrototypeMessageType.SYSTEM,
                content="欢迎使用AI原型设计工具。请描述您需要设计的应用原型，包括功能、页面结构、风格、配色等。"
            )
            await self.message_repository.add_async(welcome_message)
            
            return session_id
        
        except Exception as ex:
            if isinstance(ex, BusinessException):
                raise
            
            print(f"创建会话失败: {str(ex)}")
            raise BusinessException(f"创建会话失败: {str(ex)}")
    
    async def get_session_async(self, user_id: int, request: GetSessionDetailRequestDto) -> SessionDetailDto:
        """
        获取会话详情
        
        Args:
            user_id: 用户ID
            request: 会话ID请求
            
        Returns:
            会话详情
        """
        try:
            session = await self.session_repository.get_by_id_async(request.id)
            if session is None or session.user_id != user_id:
                raise NotFoundException("会话不存在或无权访问")
            
            # 转换为DTO
            result = SessionDetailDto(
                id=session.id,
                name=session.name,
                description=session.description,
                status=session.status,
                status_description=self._get_session_status_description(session.status),
                requirements=session.requirements,
                page_structure=session.page_structure,
                is_generating_code=session.is_generating_code,
                create_date=session.create_date,
                last_modify_date=session.last_modify_date
            )
            
            # 如果需要包含页面详情，则获取页面列表
            if request.include_pages:
                pages = await self.page_repository.get_by_session_id_async(request.id)
                result.pages = [
                    PageDetailDto(
                        id=p.id,
                        session_id=p.session_id,
                        name=p.name,
                        path=p.path,
                        description=p.description,
                        content=p.content,
                        status=p.status,
                        status_description=self._get_page_status_description(p.status),
                        error_message=p.error_message,
                        order=p.order,
                        version=p.version,
                        history=None,  # 不包含历史版本
                        create_date=p.create_date,
                        last_modify_date=p.last_modify_date
                    )
                    for p in pages
                ]
            
            return result
        
        except Exception as ex:
            if isinstance(ex, NotFoundException):
                raise
            
            print(f"获取会话详情失败，ID: {request.id}: {str(ex)}")
            raise BusinessException(f"获取会话详情失败: {str(ex)}")
    
    async def get_user_sessions_async(
        self, user_id: int, request: BasePageRequestDto
    ) -> PagedResultDto[SessionListItemDto]:
        """
        获取用户会话列表
        
        Args:
            user_id: 用户ID
            request: 分页请求
            
        Returns:
            会话列表
        """
        try:
            sessions, total_count = await self.session_repository.get_paginated_async(
                user_id, request.page_index, request.page_size
            )
            
            # 获取每个会话的页面数量
            session_ids = [s.id for s in sessions]
            page_count_dict = {}
            
            if session_ids:
                for session_id in session_ids:
                    pages = await self.page_repository.get_by_session_id_async(session_id)
                    page_count_dict[session_id] = len(pages)
            
            # 转换为DTO列表
            items = [
                SessionListItemDto(
                    id=s.id,
                    name=s.name,
                    status=s.status,
                    status_description=self._get_session_status_description(s.status),
                    page_count=page_count_dict.get(s.id, 0),
                    create_date=s.create_date,
                    last_modify_date=s.last_modify_date
                )
                for s in sessions
            ]
            
            # 构建分页结果
            # app/modules/tools/prototype/services/session_service.py (continued)
            # 构建分页结果
            result = PagedResultDto[SessionListItemDto](
                items=items,
                total_count=total_count,
                page_index=request.page_index,
                page_size=request.page_size,
                total_pages=(total_count + request.page_size - 1) // request.page_size
            )
            
            return result
            
        except Exception as ex:
            print(f"获取用户会话列表失败: {str(ex)}")
            raise BusinessException(f"获取会话列表失败: {str(ex)}")
    
    async def update_session_async(self, user_id: int, request: UpdateSessionRequestDto) -> bool:
        """
        更新会话信息
        
        Args:
            user_id: 用户ID
            request: 更新请求
            
        Returns:
            操作结果
        """
        try:
            session = await self.session_repository.get_by_id_async(request.id)
            if session is None or session.user_id != user_id:
                raise NotFoundException("会话不存在或无权访问")
            
            # 更新会话信息
            session.name = request.name
            session.description = request.description
            
            return await self.session_repository.update_async(session)
            
        except Exception as ex:
            if isinstance(ex, NotFoundException):
                raise
            
            print(f"更新会话信息失败，ID: {request.id}: {str(ex)}")
            raise BusinessException(f"更新会话信息失败: {str(ex)}")
    
    async def delete_session_async(self, user_id: int, session_id: int) -> bool:
        """
        删除会话
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            
        Returns:
            操作结果
        """
        try:
            session = await self.session_repository.get_by_id_async(session_id)
            if session is None or session.user_id != user_id:
                raise NotFoundException("会话不存在或无权访问")
            
            # 先删除会话相关的所有数据
            await self.page_repository.delete_by_session_id_async(session_id)
            # 资源删除（可能需要删除文件系统中的文件）
            await self.resource_repository.delete_by_session_id_async(session_id)
            # 最后删除会话
            return await self.session_repository.delete_async(session_id)
            
        except Exception as ex:
            if isinstance(ex, NotFoundException):
                raise
            
            print(f"删除会话失败，ID: {session_id}: {str(ex)}")
            raise BusinessException(f"删除会话失败: {str(ex)}")
    
    def _get_session_status_description(self, status: PrototypeSessionStatus) -> str:
        """
        获取会话状态描述
        
        Args:
            status: 状态
            
        Returns:
            状态描述
        """
        status_descriptions = {
            PrototypeSessionStatus.NONE: "未知",
            PrototypeSessionStatus.REQUIREMENT_GATHERING: "需求收集中",
            PrototypeSessionStatus.REQUIREMENT_ANALYZING: "需求分析中",
            PrototypeSessionStatus.STRUCTURE_CONFIRMATION: "结构确认中",
            PrototypeSessionStatus.PAGE_GENERATION: "页面生成中",
            PrototypeSessionStatus.COMPLETED: "已完成",
            PrototypeSessionStatus.ABANDONED: "已放弃"
        }
        return status_descriptions.get(status, "未知状态")
    
    def _get_page_status_description(self, status: PrototypePageStatus) -> str:
        """
        获取页面状态描述
        
        Args:
            status: 状态
            
        Returns:
            状态描述
        """
        status_descriptions = {
            PrototypePageStatus.PENDING: "待生成",
            PrototypePageStatus.GENERATING: "生成中",
            PrototypePageStatus.GENERATED: "已生成",
            PrototypePageStatus.FAILED: "生成失败",
            PrototypePageStatus.MODIFIED: "已修改"
        }
        return status_descriptions.get(status, "未知状态")