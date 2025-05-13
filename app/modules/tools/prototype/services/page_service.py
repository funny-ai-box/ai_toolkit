"""
原型页面服务，处理页面的查询和管理
"""
import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ForbiddenException, BusinessException
from app.modules.tools.prototype.dtos import PageDetailDto, PageHistoryDto
from app.modules.tools.prototype.enums import PrototypePageStatus
from app.modules.tools.prototype.repositories import (
    PrototypeSessionRepository, PrototypePageRepository, PrototypePageHistoryRepository
)


class PrototypePageService:
    """原型页面服务实现"""
    
    def __init__(
        self,
        db: AsyncSession,
        session_repository: PrototypeSessionRepository,
        page_repository: PrototypePageRepository,
        page_history_repository: PrototypePageHistoryRepository,
        logger: logging.Logger
    ):
        """
        初始化页面服务
        
        Args:
            db: 数据库会话
            session_repository: 会话仓储
            page_repository: 页面仓储
            page_history_repository: 页面历史仓储
            logger: 日志记录器
        """
        self.db = db
        self.session_repository = session_repository
        self.page_repository = page_repository
        self.page_history_repository = page_history_repository
        self.logger = logger
    
    async def get_page_async(self, user_id: int, page_id: int, include_history: bool = False) -> PageDetailDto:
        """
        获取页面详情
        
        Args:
            user_id: 用户ID
            page_id: 页面ID
            include_history: 是否包含历史版本
            
        Returns:
            页面详情
        """
        try:
            page = await self.page_repository.get_by_id_async(page_id)
            if page is None:
                raise NotFoundException("页面不存在")
            
            # 检查用户权限
            session = await self.session_repository.get_by_id_async(page.session_id)
            if session is None or session.user_id != user_id:
                raise ForbiddenException("无权访问该页面")
            
            # 转换为DTO
            result = PageDetailDto(
                id=page.id,
                sessionId=page.session_id,
                name=page.name,
                path=page.path,
                description=page.description,
                content=page.content,
                status=page.status,
                statusDescription=self._get_page_status_description(page.status),
                errorMessage=page.error_message,
                order=page.order,
                version=page.version,
                createDate=page.create_date,
                lastModifyDate=page.last_modify_date
            )
            
            # 如果需要包含历史版本，则获取历史版本列表
            if include_history:
                history = await self.page_history_repository.get_by_page_id_async(page_id)
                result.history = [
                    PageHistoryDto(
                        id=h.id,
                        pageId=h.page_id,
                        version=h.version,
                        changeDescription=h.change_description,
                        createDate=h.create_date
                    )
                    for h in history
                ]
            
            return result
        except Exception as ex:
            if not isinstance(ex, (NotFoundException, ForbiddenException)):
                self.logger.error(f"获取页面详情失败，ID: {page_id}", exc_info=ex)
                raise BusinessException(f"获取页面详情失败: {str(ex)}")
            raise
    
    async def get_session_pages_async(self, user_id: int, session_id: int) -> List[PageDetailDto]:
        """
        获取会话的所有页面
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            
        Returns:
            页面列表
        """
        try:
            # 检查用户权限
            session = await self.session_repository.get_by_id_async(session_id)
            if session is None or session.user_id != user_id:
                raise ForbiddenException("无权访问该会话")
            
            pages = await self.page_repository.get_by_session_id_async(session_id)
            return [
                PageDetailDto(
                    id=p.id,
                    sessionId=p.session_id,
                    name=p.name,
                    path=p.path,
                    description=p.description,
                    content=None,  # 不返回页面内容
                    status=p.status,
                    statusDescription=self._get_page_status_description(p.status),
                    errorMessage=p.error_message,
                    order=p.order,
                    version=p.version,
                    createDate=p.create_date,
                    lastModifyDate=p.last_modify_date
                )
                for p in pages
            ]
        except Exception as ex:
            if not isinstance(ex, ForbiddenException):
                self.logger.error(f"获取会话页面列表失败，会话ID: {session_id}", exc_info=ex)
                raise BusinessException(f"获取会话页面列表失败: {str(ex)}")
            raise
    
    def _get_page_status_description(self, status: PrototypePageStatus) -> str:
        """
        获取页面状态描述
        
        Args:
            status: 状态
            
        Returns:
            状态描述
        """
        if status == PrototypePageStatus.PENDING:
            return "待生成"
        elif status == PrototypePageStatus.GENERATING:
            return "生成中"
        elif status == PrototypePageStatus.GENERATED:
            return "已生成"
        elif status == PrototypePageStatus.FAILED:
            return "生成失败"
        elif status == PrototypePageStatus.MODIFIED:
            return "已修改"
        else:
            return "未知状态"