# app/modules/tools/podcast/repositories/podcast_script_history_repository.py
import datetime
from typing import List, Optional

from sqlalchemy import select, update, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tools.podcast.models import (
    PodcastScriptHistory, PodcastScriptHistoryItem, PodcastTaskStatus, PodcastTaskScript
)
from app.modules.tools.podcast.repositories.podcast_task_script_repository import PodcastTaskScriptRepository # Relative import
from app.core.utils.snowflake import generate_id

class PodcastScriptHistoryRepository:
    """播客历史脚本仓储"""

    def __init__(self, db: AsyncSession, script_repository: PodcastTaskScriptRepository):
        self.db = db
        self.script_repository = script_repository # Injected

    async def get_by_podcast_id_async(self, podcast_id: int) -> List[PodcastScriptHistory]:
        """获取播客的所有脚本历史项"""
        stmt = select(PodcastScriptHistory).where(PodcastScriptHistory.podcast_id == podcast_id).order_by(PodcastScriptHistory.id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_script_history_item_async(self, history_id: int) -> List[PodcastScriptHistoryItem]:
        """获取播客历史脚本的明细"""
        stmt = select(PodcastScriptHistoryItem).where(PodcastScriptHistoryItem.history_id == history_id).order_by(PodcastScriptHistoryItem.sequence_number)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add_async(self, podcast_id: int) -> int:
        """新增历史操作记录，返回历史记录ID"""
        history_id = generate_id()
        now = datetime.datetime.now()
        new_history = PodcastScriptHistory(
            id=history_id,
            podcast_id=podcast_id,
            name=f"{now.strftime('%Y-%m-%d %H:%M:%S')} 创建播客", # C# example
            status=PodcastTaskStatus.PROCESSING, # C# sets Processing initially
            error_message=None,
            create_date=now,
            last_modify_date=now
        )
        self.db.add(new_history)
        await self.db.flush()
        return new_history.id

    async def update_status_async(self, history_id: int, status: PodcastTaskStatus, error_message: Optional[str] = None) -> bool:
        """更新播客历史记录状态"""
        stmt = (
            update(PodcastScriptHistory)
            .where(PodcastScriptHistory.id == history_id)
            .values(
                status=status,
                error_message=error_message,
                last_modify_date=datetime.datetime.now()
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def move_script_to_history_async(self, podcast_id: int) -> bool:
        """迁移，会将播客的现有脚本 (PodcastTaskScript) 结转到 PodcastScriptHistoryItem"""
        # Note: C# GetByPodcastIdAsync is on _scriptRepository which is IPodcastTaskScriptRepository
        script_items: List[PodcastTaskScript] = await self.script_repository.get_by_podcast_id_async(podcast_id)
        
        if not script_items:
            return True # Nothing to move

        history_items_to_insert = []
        for script_item in script_items:
            history_items_to_insert.append(
                PodcastScriptHistoryItem(
                    id=script_item.id, # Using same ID as original script item
                    podcast_id=script_item.podcast_id,
                    voice_id=script_item.voice_id,
                    history_id=script_item.history_id, # This is the crucial link
                    content=script_item.content,
                    ssml_content=script_item.ssml_content,
                    role_name=script_item.role_name,
                    role_type=script_item.role_type,
                    audio_duration=script_item.audio_duration,
                    audio_path=script_item.audio_path,
                    audio_status=script_item.audio_status,
                    sequence_number=script_item.sequence_number,
                    create_date=script_item.create_date, # Preserve original creation time
                    last_modify_date=datetime.datetime.now() # Update modification time for this operation
                )
            )
        
        if history_items_to_insert:
            self.db.add_all(history_items_to_insert)
            await self.db.flush()

        # 清除旧的脚本项 from PodcastTaskScript table
        await self.script_repository.delete_by_podcast_id_async(podcast_id)
        return True