# app/modules/tools/podcast/repositories/podcast_task_content_repository.py
import datetime
from typing import List, Optional

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tools.podcast.models import PodcastTaskContent
from app.core.utils.snowflake import generate_id

class PodcastTaskContentRepository:
    """播客内容项仓储"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id_async(self, content_id: int) -> Optional[PodcastTaskContent]:
        """获取播客内容项"""
        stmt = select(PodcastTaskContent).where(PodcastTaskContent.id == content_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_podcast_id_async(self, podcast_id: int) -> List[PodcastTaskContent]:
        """获取播客的所有内容项"""
        stmt = select(PodcastTaskContent).where(PodcastTaskContent.podcast_id == podcast_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_podcast_ids_async(self, podcast_ids: List[int]) -> List[PodcastTaskContent]:
        """获取多个播客的所有内容项"""
        if not podcast_ids:
            return []
        stmt = select(PodcastTaskContent).where(PodcastTaskContent.podcast_id.in_(podcast_ids))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add_async(self, content_item: PodcastTaskContent) -> int:
        """新增内容项，返回内容项ID"""
        content_item.id = generate_id()
        now = datetime.datetime.now()
        content_item.create_date = now
        content_item.last_modify_date = now
        self.db.add(content_item)
        await self.db.flush()
        return content_item.id

    async def update_async(self, content_item: PodcastTaskContent) -> bool:
        """更新内容项"""
        # Ensure ID is set for update to work correctly if instance is not yet persisted or re-fetched
        if not content_item.id:
             raise ValueError("Cannot update PodcastTaskContent without an ID.")

        # Create a dictionary of values to update, excluding primary key and None values if desired.
        # For a full update of provided fields, direct usage of merge or targeted update is fine.
        values_to_update = {
            "user_id": content_item.user_id,
            "podcast_id": content_item.podcast_id,
            "content_type": content_item.content_type,
            "source_document_id": content_item.source_document_id,
            "source_content": content_item.source_content,
            "last_modify_date": datetime.datetime.now()
        }
        stmt = update(PodcastTaskContent).where(PodcastTaskContent.id == content_item.id).values(**values_to_update)
        result = await self.db.execute(stmt)
        return result.rowcount > 0


    async def delete_async(self, content_id: int) -> bool:
        """删除内容项"""
        stmt = delete(PodcastTaskContent).where(PodcastTaskContent.id == content_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_by_podcast_id_async(self, podcast_id: int) -> bool:
        """删除播客的所有内容项"""
        stmt = delete(PodcastTaskContent).where(PodcastTaskContent.podcast_id == podcast_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0