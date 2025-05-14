# app/modules/tools/podcast/repositories/podcast_task_script_repository.py
import datetime
from typing import List, Optional, Union

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tools.podcast.models import PodcastTaskScript, AudioStatusType
from app.core.utils.snowflake import generate_id

class PodcastTaskScriptRepository:
    """播客脚本项仓储"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id_async(self, script_id: int) -> Optional[PodcastTaskScript]:
        """获取播客脚本项"""
        stmt = select(PodcastTaskScript).where(PodcastTaskScript.id == script_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_podcast_id_async(self, podcast_id: int) -> List[PodcastTaskScript]:
        """获取播客的所有脚本项"""
        stmt = select(PodcastTaskScript).where(PodcastTaskScript.podcast_id == podcast_id).order_by(PodcastTaskScript.sequence_number)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_podcast_ids_async(self, podcast_ids: List[int]) -> List[PodcastTaskScript]:
        """获取多个播客的所有脚本项"""
        if not podcast_ids:
            return []
        stmt = select(PodcastTaskScript).where(PodcastTaskScript.podcast_id.in_(podcast_ids)).order_by(PodcastTaskScript.sequence_number)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add_range_async(self, script_items: List[PodcastTaskScript]) -> bool:
        """批量新增脚本项"""
        if not script_items:
            return True 
        now = datetime.datetime.now()
        for item in script_items:
            item.id = generate_id()
            item.create_date = now
            item.last_modify_date = now
        self.db.add_all(script_items)
        await self.db.flush()
        return True

    async def add_async(self, script_item: PodcastTaskScript) -> bool:
        """新增脚本项"""
        script_item.id = generate_id()
        now = datetime.datetime.now()
        script_item.create_date = now
        script_item.last_modify_date = now
        self.db.add(script_item)
        await self.db.flush()
        return True

    async def update_async(self, script_item: PodcastTaskScript) -> bool:
        """更新脚本项"""
        script_item.last_modify_date = datetime.datetime.now()
        # self.db.add(script_item) # For SQLAlchemy to track changes if detached
        await self.db.flush()
        return True

    async def delete_by_podcast_id_async(self, podcast_id: int) -> bool:
        """删除播客的所有脚本项"""
        stmt = delete(PodcastTaskScript).where(PodcastTaskScript.podcast_id == podcast_id)
        result = await self.db.execute(stmt)
        # No check for result.rowcount > 0 needed if we just want to ensure deletion attempt
        return True 

    async def get_pending_audio_scripts_async(self, limit: int = 20) -> List[PodcastTaskScript]:
        """获取待生成语音的脚本项"""
        stmt = (
            select(PodcastTaskScript)
            .where(PodcastTaskScript.audio_status == AudioStatusType.PENDING)
            .order_by(PodcastTaskScript.create_date.asc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_audio_status_async(self, script_id: int, status: AudioStatusType, audio_path: Optional[str], audio_duration: datetime.timedelta) -> bool:
        """更新脚本项语音状态"""
        values_to_update = {
            "audio_status": status,
            "last_modify_date": datetime.datetime.now()
        }
        if audio_path is not None: # C# checks !string.IsNullOrEmpty(audioPath)
            values_to_update["audio_path"] = audio_path
            values_to_update["audio_duration"] = audio_duration
        
        stmt = update(PodcastTaskScript).where(PodcastTaskScript.id == script_id).values(**values_to_update)
        result = await self.db.execute(stmt)
        return result.rowcount > 0
