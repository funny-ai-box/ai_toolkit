import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, update, desc

from app.modules.tools.datadesign.entities import DesignChat, DesignTaskState
from app.modules.tools.datadesign.enums import AssistantRoleType
from app.core.ai.dtos import ChatRoleType
from app.core.utils.snowflake import generate_id
from app.modules.tools.datadesign.repositories.design_task_state_repository import DesignTaskStateRepository


class DesignChatRepository:
    """设计会话仓储实现"""

    def __init__(self, db: AsyncSession, task_state_repository: DesignTaskStateRepository):
        """
        构造函数

        Args:
            db (AsyncSession): 数据库会话
            task_state_repository (DesignTaskStateRepository): 任务状态仓储
        """
        self.db = db
        self.task_state_repository = task_state_repository

    async def get_by_id_async(self, id: int) -> Optional[DesignChat]:
        """
        获取设计会话

        Args:
            id (int): 会话ID

        Returns:
            Optional[DesignChat]: 设计会话实体
        """
        result = await self.db.execute(select(DesignChat).filter(DesignChat.id == id))
        return result.scalars().first()

    async def get_by_task_id_async(self, task_id: int) -> List[DesignChat]:
        """
        获取任务的所有设计会话

        Args:
            task_id (int): 任务ID

        Returns:
            List[DesignChat]: 设计会话实体列表，按创建时间降序排列
        """
        stmt = select(DesignChat).filter(DesignChat.task_id == task_id).order_by(desc(DesignChat.create_date))
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def _get_latest_chat_by_role_type_async(self, task_id: int, role_type: AssistantRoleType, latest_id_from_state: Optional[int]) -> Optional[DesignChat]:
        """辅助方法获取最新聊天记录"""
        if latest_id_from_state and latest_id_from_state > 0:
            chat = await self.get_by_id_async(latest_id_from_state)
            if chat:
                return chat
        
        stmt = select(DesignChat).filter(
            DesignChat.task_id == task_id,
            DesignChat.assistant_role == role_type
        ).order_by(desc(DesignChat.create_date))
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_latest_business_analysis_async(self, task_id: int) -> Optional[DesignChat]:
        """获取任务的最新业务分析"""
        task_state = await self.task_state_repository.get_by_task_id_async(task_id)
        latest_id = task_state.latest_business_analysis_id if task_state else None
        return await self._get_latest_chat_by_role_type_async(task_id, AssistantRoleType.BUSINESS_ANALYST, latest_id)

    async def get_latest_database_design_async(self, task_id: int) -> Optional[DesignChat]:
        """获取任务的最新数据库设计"""
        task_state = await self.task_state_repository.get_by_task_id_async(task_id)
        latest_id = task_state.latest_database_design_id if task_state else None
        return await self._get_latest_chat_by_role_type_async(task_id, AssistantRoleType.DATABASE_ARCHITECT, latest_id)

    async def get_latest_json_structure_async(self, task_id: int) -> Optional[DesignChat]:
        """获取任务的最新JSON结构"""
        task_state = await self.task_state_repository.get_by_task_id_async(task_id)
        latest_id = task_state.latest_json_structure_id if task_state else None
        return await self._get_latest_chat_by_role_type_async(task_id, AssistantRoleType.DATABASE_OPERATOR, latest_id)

    async def get_user_message_history_async(self, task_id: int) -> List[DesignChat]:
        """
        获取任务的用户消息历史

        Args:
            task_id (int): 任务ID

        Returns:
            List[DesignChat]: 设计会话实体列表 (用户消息，按创建时间升序)
        """
        stmt = select(DesignChat).filter(
            DesignChat.task_id == task_id,
            DesignChat.role == ChatRoleType.USER # Make sure ChatRoleType.USER is defined
        ).order_by(DesignChat.create_date)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def add_async(self, chat: DesignChat) -> DesignChat:
        """
        新增设计会话

        Args:
            chat (DesignChat): 设计会话实体

        Returns:
            DesignChat: 完成添加的设计会话实体
        """
        chat.id = generate_id()
        now = datetime.datetime.now()
        chat.create_date = now
        chat.last_modify_date = now
        self.db.add(chat)
        await self.db.flush() # Ensure ID is populated

        if chat.is_latest_analysis:
            if chat.assistant_role == AssistantRoleType.BUSINESS_ANALYST:
                await self.set_as_latest_business_analysis_async(chat.id, chat.task_id)
            elif chat.assistant_role == AssistantRoleType.DATABASE_ARCHITECT:
                await self.set_as_latest_database_design_async(chat.id, chat.task_id)
            elif chat.assistant_role == AssistantRoleType.DATABASE_OPERATOR:
                await self.set_as_latest_json_structure_async(chat.id, chat.task_id)
        
        await self.db.refresh(chat) # Refresh to get any DB-side changes
        return chat

    async def add_batch_async(self, chats: List[DesignChat]) -> bool:
        """
        批量新增设计会话

        Args:
            chats (List[DesignChat]): 设计会话实体列表

        Returns:
            bool: 操作结果
        """
        now = datetime.datetime.now()
        for chat in chats:
            chat.id = generate_id()
            chat.create_date = now
            chat.last_modify_date = now
        
        self.db.add_all(chats)
        await self.db.flush()

        for chat in chats: # Process after IDs are assigned
            if chat.is_latest_analysis:
                if chat.assistant_role == AssistantRoleType.BUSINESS_ANALYST:
                    await self.set_as_latest_business_analysis_async(chat.id, chat.task_id)
                elif chat.assistant_role == AssistantRoleType.DATABASE_ARCHITECT:
                    await self.set_as_latest_database_design_async(chat.id, chat.task_id)
                elif chat.assistant_role == AssistantRoleType.DATABASE_OPERATOR:
                    await self.set_as_latest_json_structure_async(chat.id, chat.task_id)
        return True

    async def update_async(self, chat: DesignChat) -> bool:
        """
        更新设计会话

        Args:
            chat (DesignChat): 设计会话实体

        Returns:
            bool: 操作结果
        """
        chat.last_modify_date = datetime.datetime.now()
        # self.db.add(chat) # For detached objects
        # await self.db.flush()
        stmt = (
            update(DesignChat)
            .where(DesignChat.id == chat.id)
            .values(
                role=chat.role,
                assistant_role=chat.assistant_role,
                content=chat.content,
                is_latest_analysis=chat.is_latest_analysis,
                last_modify_date=chat.last_modify_date
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0


    async def _set_as_latest_async(self, chat_id: int, task_id: int, role_type: AssistantRoleType) -> bool:
        """辅助方法设置最新分析/设计/结构"""
        # Update task state
        if role_type == AssistantRoleType.BUSINESS_ANALYST:
            await self.task_state_repository.update_latest_business_analysis_id_async(task_id, chat_id)
        elif role_type == AssistantRoleType.DATABASE_ARCHITECT:
            await self.task_state_repository.update_latest_database_design_id_async(task_id, chat_id)
        elif role_type == AssistantRoleType.DATABASE_OPERATOR:
            await self.task_state_repository.update_latest_json_structure_id_async(task_id, chat_id)

        # Set all others of this role for this task to IsLatestAnalysis = False
        stmt_reset = (
            update(DesignChat)
            .where(DesignChat.task_id == task_id, DesignChat.assistant_role == role_type, DesignChat.id != chat_id)
            .values(is_latest_analysis=False)
        )
        await self.db.execute(stmt_reset)

        # Set current chat as latest
        stmt_set_latest = (
            update(DesignChat)
            .where(DesignChat.id == chat_id)
            .values(is_latest_analysis=True)
        )
        result = await self.db.execute(stmt_set_latest)
        return result.rowcount > 0

    async def set_as_latest_business_analysis_async(self, chat_id: int, task_id: int) -> bool:
        return await self._set_as_latest_async(chat_id, task_id, AssistantRoleType.BUSINESS_ANALYST)

    async def set_as_latest_database_design_async(self, chat_id: int, task_id: int) -> bool:
        return await self._set_as_latest_async(chat_id, task_id, AssistantRoleType.DATABASE_ARCHITECT)

    async def set_as_latest_json_structure_async(self, chat_id: int, task_id: int) -> bool:
        return await self._set_as_latest_async(chat_id, task_id, AssistantRoleType.DATABASE_OPERATOR)

    async def delete_async(self, id: int) -> bool:
        """
        删除设计会话

        Args:
            id (int): 会话ID

        Returns:
            bool: 操作结果
        """
        stmt = delete(DesignChat).where(DesignChat.id == id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_by_task_id_async(self, task_id: int) -> bool:
        """
        删除任务的所有设计会话 (并删除关联的任务状态)

        Args:
            task_id (int): 任务ID

        Returns:
            bool: 操作结果
        """
        await self.task_state_repository.delete_by_task_id_async(task_id)
        
        stmt = delete(DesignChat).where(DesignChat.task_id == task_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0