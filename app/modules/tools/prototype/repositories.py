"""
原型设计模块的数据库仓储实现
"""
import datetime
from typing import List, Tuple, Optional

from sqlalchemy import select, update, delete, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.snowflake import generate_id
from app.modules.tools.prototype.models import (
    PrototypeSession, 
    PrototypePage, 
    PrototypePageHistory, 
    PrototypeMessage, 
    PrototypeResource
)
from app.modules.tools.prototype.enums import PrototypePageStatus, PrototypeSessionStatus


# 会话仓储
class PrototypeSessionRepository:
    """原型会话仓储"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化会话仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, id: int) -> Optional[PrototypeSession]:
        """
        根据ID获取会话
        
        Args:
            id: 会话ID
            
        Returns:
            会话实体
        """
        query = select(PrototypeSession).where(PrototypeSession.id == id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_user_id_async(self, user_id: int) -> List[PrototypeSession]:
        """
        获取用户的所有会话
        
        Args:
            user_id: 用户ID
            
        Returns:
            会话实体列表
        """
        query = select(PrototypeSession).where(
            PrototypeSession.user_id == user_id
        ).order_by(desc(PrototypeSession.last_modify_date))
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_paginated_async(self, user_id: int, page_index: int = 1, page_size: int = 20) -> Tuple[List[PrototypeSession], int]:
        """
        分页获取用户的会话
        
        Args:
            user_id: 用户ID
            page_index: 页码
            page_size: 每页大小
            
        Returns:
            (会话列表, 总数)
        """
        # 确保页码和每页数量有效
        if page_index < 1:
            page_index = 1
        if page_size < 1:
            page_size = 20

        # 计算跳过的记录数
        skip = (page_index - 1) * page_size

        # 查询满足条件的记录总数
        count_query = select(func.count()).select_from(PrototypeSession).where(
            PrototypeSession.user_id == user_id
        )
        total_count = await self.db.execute(count_query)
        total_count = total_count.scalar() or 0

        # 查询分页数据
        query = select(PrototypeSession).where(
            PrototypeSession.user_id == user_id
        ).order_by(desc(PrototypeSession.last_modify_date)).offset(skip).limit(page_size)
        
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total_count

    async def add_async(self, session: PrototypeSession) -> int:
        """
        新增会话
        
        Args:
            session: 会话实体
            
        Returns:
            会话ID
        """
        session.id = generate_id()
        now = datetime.datetime.now()
        session.create_date = now
        session.last_modify_date = now
        
        self.db.add(session)
        await self.db.flush()
        return session.id

    async def update_session_name_from_first_message_async(self, id: int, message: str) -> bool:
        """
        根据首次聊天内容更新会话名称
        
        Args:
            id: 会话ID
            message: 首次聊天内容
            
        Returns:
            更新结果
        """
        # 截取用户消息的前20个字符作为会话名称
        # 如果消息很短，则使用全部内容
        if len(message) <= 20:
            new_session_name = message
        else:
            # 尝试找到一个合适的截断点，比如句号或问号
            end_pos = -1
            for i in range(min(len(message), 30)):
                if message[i] in ['.', '?', '!', '。', '？', '！']:
                    end_pos = i
                    break

            # 如果找不到合适的截断点，就截取前20个字符
            if end_pos == -1 or end_pos > 20:
                new_session_name = message[:20] + "..."
            else:
                new_session_name = message[:end_pos + 1]

        stmt = update(PrototypeSession).where(
            PrototypeSession.id == id
        ).values(
            name=new_session_name, 
            last_modify_date=datetime.datetime.now()
        )
        
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def lock_generating_code_async(self, id: int, locked: bool) -> bool:
        """
        锁定生成代码的状态，这时候用户不能发送消息
        
        Args:
            id: 会话ID
            locked: 是否锁定
            
        Returns:
            锁定结果
        """
        stmt = update(PrototypeSession).where(
            PrototypeSession.id == id
        ).values(
            is_generating_code=locked, 
            last_modify_date=datetime.datetime.now()
        )
        
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def update_async(self, session: PrototypeSession) -> bool:
        """
        更新会话
        
        Args:
            session: 会话实体
            
        Returns:
            更新结果
        """
        session.last_modify_date = datetime.datetime.now()
        await self.db.merge(session)
        return True

    async def delete_async(self, id: int) -> bool:
        """
        删除会话
        
        Args:
            id: 会话ID
            
        Returns:
            删除结果
        """
        stmt = delete(PrototypeSession).where(PrototypeSession.id == id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def update_status_async(self, id: int, status: PrototypeSessionStatus) -> bool:
        """
        更新会话状态
        
        Args:
            id: 会话ID
            status: 状态
            
        Returns:
            更新结果
        """
        stmt = update(PrototypeSession).where(
            PrototypeSession.id == id
        ).values(
            status=status, 
            last_modify_date=datetime.datetime.now()
        )
        
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def update_page_structure_async(self, id: int, page_structure: str) -> bool:
        """
        更新会话页面结构
        
        Args:
            id: 会话ID
            page_structure: 页面结构JSON
            
        Returns:
            更新结果
        """
        stmt = update(PrototypeSession).where(
            PrototypeSession.id == id
        ).values(
            page_structure=page_structure, 
            last_modify_date=datetime.datetime.now()
        )
        
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def update_requirements_async(self, id: int, requirements: str) -> bool:
        """
        更新会话需求
        
        Args:
            id: 会话ID
            requirements: 需求JSON
            
        Returns:
            更新结果
        """
        stmt = update(PrototypeSession).where(
            PrototypeSession.id == id
        ).values(
            requirements=requirements, 
            last_modify_date=datetime.datetime.now()
        )
        
        result = await self.db.execute(stmt)
        return result.rowcount > 0


# 页面仓储
class PrototypePageRepository:
    """原型页面仓储"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化页面仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, id: int) -> Optional[PrototypePage]:
        """
        获取页面
        
        Args:
            id: 页面ID
            
        Returns:
            页面实体
        """
        query = select(PrototypePage).where(PrototypePage.id == id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_session_id_async(self, session_id: int) -> List[PrototypePage]:
        """
        获取会话的所有页面
        
        Args:
            session_id: 会话ID
            
        Returns:
            页面实体列表
        """
        query = select(PrototypePage).where(
            PrototypePage.session_id == session_id
        ).order_by(PrototypePage.order)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_path_async(self, session_id: int, path: str) -> Optional[PrototypePage]:
        """
        获取特定会话和路径的页面
        
        Args:
            session_id: 会话ID
            path: 页面路径
            
        Returns:
            页面实体
        """
        query = select(PrototypePage).where(
            and_(
                PrototypePage.session_id == session_id,
                PrototypePage.path == path
            )
        )
        
        result = await self.db.execute(query)
        return result.scalars().first()

    async def add_async(self, page: PrototypePage) -> int:
        """
        新增页面
        
        Args:
            page: 页面实体
            
        Returns:
            页面ID
        """
        page.id = generate_id()
        now = datetime.datetime.now()
        page.create_date = now
        page.last_modify_date = now
        
        self.db.add(page)
        await self.db.flush()
        return page.id

    async def add_range_async(self, pages: List[PrototypePage]) -> bool:
        """
        批量新增页面
        
        Args:
            pages: 页面实体列表
            
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        for page in pages:
            page.id = generate_id()
            page.create_date = now
            page.last_modify_date = now
            self.db.add(page)
            
        await self.db.flush()
        return True

    async def update_async(self, page: PrototypePage) -> bool:
        """
        更新页面
        
        Args:
            page: 页面实体
            
        Returns:
            操作结果
        """
        page.last_modify_date = datetime.datetime.now()
        await self.db.merge(page)
        return True

    async def update_content_async(self, id: int, content: str) -> bool:
        """
        更新页面内容
        
        Args:
            id: 页面ID
            content: 页面内容
            
        Returns:
            操作结果
        """
        stmt = update(PrototypePage).where(
            PrototypePage.id == id
        ).values(
            content=content,
            version=PrototypePage.version + 1,
            last_modify_date=datetime.datetime.now()
        )
        
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def update_status_async(self, id: int, status: PrototypePageStatus, error_message: Optional[str] = None) -> bool:
        """
        更新页面状态
        
        Args:
            id: 页面ID
            status: 页面状态
            error_message: 错误消息（如果有）
            
        Returns:
            操作结果
        """
        stmt = update(PrototypePage).where(
            PrototypePage.id == id
        ).values(
            status=status,
            error_message=error_message,
            last_modify_date=datetime.datetime.now()
        )
        
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_async(self, id: int) -> bool:
        """
        删除页面
        
        Args:
            id: 页面ID
            
        Returns:
            操作结果
        """
        stmt = delete(PrototypePage).where(PrototypePage.id == id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_by_session_id_async(self, session_id: int) -> bool:
        """
        删除会话的所有页面
        
        Args:
            session_id: 会话ID
            
        Returns:
            操作结果
        """
        stmt = delete(PrototypePage).where(PrototypePage.session_id == session_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def update_partial_content_async(self, page_id: int, partial_html: str) -> bool:
        """
        更新页面部分内容
        
        Args:
            page_id: 页面ID
            partial_html: 部分HTML内容
            
        Returns:
            操作结果
        """
        stmt = update(PrototypePage).where(
            PrototypePage.id == page_id
        ).values(
            partial_content=partial_html,
            last_modify_date=datetime.datetime.now()
        )
        
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def mark_page_as_complete_async(self, page_id: int) -> bool:
        """
        标记页面为完成状态
        
        Args:
            page_id: 页面ID
            
        Returns:
            操作结果
        """
        stmt = update(PrototypePage).where(
            PrototypePage.id == page_id
        ).values(
            is_complete=True,
            last_modify_date=datetime.datetime.now()
        )
        
        result = await self.db.execute(stmt)
        return result.rowcount > 0


# 页面历史仓储
class PrototypePageHistoryRepository:
    """原型页面历史版本仓储"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化页面历史仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, id: int) -> Optional[PrototypePageHistory]:
        """
        获取页面历史版本
        
        Args:
            id: 历史记录ID
            
        Returns:
            历史版本实体
        """
        query = select(PrototypePageHistory).where(PrototypePageHistory.id == id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_page_id_async(self, page_id: int) -> List[PrototypePageHistory]:
        """
        获取页面的所有历史版本
        
        Args:
            page_id: 页面ID
            
        Returns:
            历史版本实体列表
        """
        query = select(PrototypePageHistory).where(
            PrototypePageHistory.page_id == page_id
        ).order_by(desc(PrototypePageHistory.version))
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_version_async(self, page_id: int, version: int) -> Optional[PrototypePageHistory]:
        """
        获取页面的特定版本
        
        Args:
            page_id: 页面ID
            version: 版本号
            
        Returns:
            历史版本实体
        """
        query = select(PrototypePageHistory).where(
            and_(
                PrototypePageHistory.page_id == page_id,
                PrototypePageHistory.version == version
            )
        )
        
        result = await self.db.execute(query)
        return result.scalars().first()

    async def add_async(self, history: PrototypePageHistory) -> int:
        """
        新增页面历史版本
        
        Args:
            history: 历史版本实体
            
        Returns:
            历史记录ID
        """
        history.id = generate_id()
        history.create_date = datetime.datetime.now()
        
        self.db.add(history)
        await self.db.flush()
        return history.id

    async def delete_by_page_id_async(self, page_id: int) -> bool:
        """
        删除页面的所有历史版本
        
        Args:
            page_id: 页面ID
            
        Returns:
            操作结果
        """
        stmt = delete(PrototypePageHistory).where(PrototypePageHistory.page_id == page_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0


# 消息仓储
class PrototypeMessageRepository:
    """原型消息仓储"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化消息仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, id: int) -> Optional[PrototypeMessage]:
        """
        获取消息
        
        Args:
            id: 消息ID
            
        Returns:
            消息实体
        """
        query = select(PrototypeMessage).where(PrototypeMessage.id == id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_session_id_async(self, session_id: int) -> List[PrototypeMessage]:
        """
        获取会话的所有消息
        
        Args:
            session_id: 会话ID
            
        Returns:
            消息实体列表
        """
        query = select(PrototypeMessage).where(
            PrototypeMessage.session_id == session_id
        ).order_by(PrototypeMessage.create_date)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_paginated_async(self, session_id: int, page_index: int = 1, page_size: int = 20) -> Tuple[List[PrototypeMessage], int]:
        """
        分页获取会话的消息
        
        Args:
            session_id: 会话ID
            page_index: 页码
            page_size: 每页大小
            
        Returns:
            消息列表和总数
        """
        # 确保页码和每页数量有效
        if page_index < 1:
            page_index = 1
        if page_size < 1:
            page_size = 20

        # 计算跳过的记录数
        skip = (page_index - 1) * page_size

        # 查询满足条件的记录总数
        count_query = select(func.count()).select_from(PrototypeMessage).where(
            PrototypeMessage.session_id == session_id
        )
        total_count = await self.db.execute(count_query)
        total_count = total_count.scalar() or 0

        # 查询分页数据，降序返回数据
        query = select(PrototypeMessage).where(
            PrototypeMessage.session_id == session_id
        ).order_by(desc(PrototypeMessage.id)).offset(skip).limit(page_size)
        
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        # 按id升序排序
        items.sort(key=lambda x: x.id)
        
        return items, total_count

    async def add_async(self, message: PrototypeMessage) -> int:
        """
        新增消息
        
        Args:
            message: 消息实体
            
        Returns:
            消息ID
        """
        message.id = generate_id()
        message.create_date = datetime.datetime.now()
        
        self.db.add(message)
        await self.db.flush()
        return message.id

    async def add_range_async(self, messages: List[PrototypeMessage]) -> bool:
        """
        批量新增消息
        
        Args:
            messages: 消息实体列表
            
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        for message in messages:
            message.id = generate_id()
            message.create_date = now
            self.db.add(message)
            
        await self.db.flush()
        return True

    async def delete_async(self, id: int) -> bool:
        """
        删除消息
        
        Args:
            id: 消息ID
            
        Returns:
            操作结果
        """
        stmt = delete(PrototypeMessage).where(PrototypeMessage.id == id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0


# 资源仓储
class PrototypeResourceRepository:
    """原型资源仓储"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化资源仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, id: int) -> Optional[PrototypeResource]:
        """
        获取资源
        
        Args:
            id: 资源ID
            
        Returns:
            资源实体
        """
        query = select(PrototypeResource).where(PrototypeResource.id == id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_ids_async(self, ids: List[int]) -> List[PrototypeResource]:
        """
        获取资源
        
        Args:
            ids: 资源ID列表
            
        Returns:
            资源实体列表
        """
        if not ids:
            return []
            
        query = select(PrototypeResource).where(PrototypeResource.id.in_(ids))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_session_id_async(self, session_id: int) -> List[PrototypeResource]:
        """
        获取会话的所有资源
        
        Args:
            session_id: 会话ID
            
        Returns:
            资源实体列表
        """
        query = select(PrototypeResource).where(
            PrototypeResource.session_id == session_id
        ).order_by(PrototypeResource.resource_type)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_type_async(self, session_id: int, resource_type: str) -> List[PrototypeResource]:
        """
        获取会话的特定类型资源
        
        Args:
            session_id: 会话ID
            resource_type: 资源类型
            
        Returns:
            资源实体列表
        """
        query = select(PrototypeResource).where(
            and_(
                PrototypeResource.session_id == session_id,
                PrototypeResource.resource_type == resource_type
            )
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def add_async(self, resource: PrototypeResource) -> int:
        """
        新增资源
        
        Args:
            resource: 资源实体
            
        Returns:
            资源ID
        """
        resource.id = generate_id()
        resource.create_date = datetime.datetime.now()
        
        self.db.add(resource)
        await self.db.flush()
        return resource.id

    async def add_range_async(self, resources: List[PrototypeResource]) -> bool:
        """
        批量新增资源
        
        Args:
            resources: 资源实体列表
            
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        for resource in resources:
            resource.id = generate_id()
            resource.create_date = now
            self.db.add(resource)
            
        await self.db.flush()
        return True

    async def update_async(self, resource: PrototypeResource) -> bool:
        """
        更新资源
        
        Args:
            resource: 资源实体
            
        Returns:
            操作结果
        """
        await self.db.merge(resource)
        return True

    async def delete_async(self, id: int) -> bool:
        """
        删除资源
        
        Args:
            id: 资源ID
            
        Returns:
            操作结果
        """
        stmt = delete(PrototypeResource).where(PrototypeResource.id == id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_by_session_id_async(self, session_id: int) -> bool:
        """
        删除会话的所有资源
        
        Args:
            session_id: 会话ID
            
        Returns:
            操作结果
        """
        stmt = delete(PrototypeResource).where(PrototypeResource.session_id == session_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0