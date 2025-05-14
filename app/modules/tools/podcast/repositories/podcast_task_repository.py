import datetime
from typing import List, Tuple, Optional

from sqlalchemy import select, update, delete, func, BigInteger
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tools.podcast.models import PodcastTask, PodcastTaskStatus
from app.core.utils.snowflake import generate_id

class PodcastTaskRepository:
      """播客任务仓储实现"""

      def __init__(self, db: AsyncSession):
            self.db = db

      async def get_by_id_async(self, podcast_id: int) -> Optional[PodcastTask]:
            """获取播客任务"""
            stmt = select(PodcastTask).where(PodcastTask.id == podcast_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()

      async def get_by_user_id_async(self, user_id: int) -> List[PodcastTask]:
            """获取用户的所有播客任务"""
            stmt = select(PodcastTask).where(PodcastTask.user_id == user_id).order_by(PodcastTask.create_date.desc())
            result = await self.db.execute(stmt)
            return list(result.scalars().all())

      async def get_paginated_async(self, user_id: int, page_index: int = 1, page_size: int = 20) -> Tuple[List[PodcastTask], int]:
            """分页获取用户的播客"""
            if page_index < 1:
                  page_index = 1
            if page_size < 1:
                  page_size = 20
            
            offset = (page_index - 1) * page_size

            count_stmt = select(func.count()).select_from(PodcastTask).where(PodcastTask.user_id == user_id)
            total_count_result = await self.db.execute(count_stmt)
            total_count = total_count_result.scalar_one()

            items_stmt = (
                  select(PodcastTask)
                  .where(PodcastTask.user_id == user_id)
                  .order_by(PodcastTask.create_date.desc())
                  .offset(offset)
                  .limit(page_size)
            )
            items_result = await self.db.execute(items_stmt)
            items = list(items_result.scalars().all())
            
            return items, total_count

      async def add_async(self, podcast_task: PodcastTask) -> bool:
            """新增播客任务"""
            podcast_task.id = generate_id() 
            now = datetime.datetime.now()
            podcast_task.create_date = now
            podcast_task.last_modify_date = now
            # Default values are set in model, but can be confirmed here if needed
            podcast_task.status = PodcastTaskStatus.INIT # Ensure initial status is set as per C# logic
            podcast_task.generate_count = 0
            podcast_task.generate_id = 0
            podcast_task.progress_step = 0

            self.db.add(podcast_task)
            await self.db.flush() # To get ID if needed immediately, or commit later
            return True # Assuming success if no exception

      async def update_async(self, podcast_task: PodcastTask) -> bool:
            """更新播客任务"""
            podcast_task.last_modify_date = datetime.datetime.now()
            # self.db.add(podcast_task) # if it's already tracked, just flush/commit
            await self.db.flush() 
            return True

      async def delete_async(self, podcast_id: int) -> bool:
            """删除播客任务"""
            stmt = delete(PodcastTask).where(PodcastTask.id == podcast_id)
            result = await self.db.execute(stmt)
            return result.rowcount > 0

      async def start_podcast_generate_async(self, podcast_id: int, history_id: int) -> bool:
            """开始播客脚本和音频的生成"""
            stmt = (
                  update(PodcastTask)
                  .where(PodcastTask.id == podcast_id)
                  .values(
                        status=PodcastTaskStatus.PENDING,
                        error_message=None,
                        generate_id=history_id,
                        generate_count=PodcastTask.generate_count + 1,
                        progress_step=0,
                        last_modify_date=datetime.datetime.now()
                  )
            )
            result = await self.db.execute(stmt)
            return result.rowcount > 0

      async def get_pending_podcasts_async(self, limit: int = 10) -> List[PodcastTask]:
            """获取待处理的播客列表"""
            stmt = (
                  select(PodcastTask)
                  .where(PodcastTask.status == PodcastTaskStatus.PENDING)
                  .order_by(PodcastTask.create_date.asc()) # C# has .OrderBy(x => x.CreateDate)
                  .limit(limit)
            )
            result = await self.db.execute(stmt)
            return list(result.scalars().all())

      async def lock_processing_status_async(self, podcast_id: int) -> bool:
            """执行播客任务生成前的锁定更新"""
            stmt = (
                  update(PodcastTask)
                  .where(PodcastTask.id == podcast_id)
                  .where(PodcastTask.status == PodcastTaskStatus.PENDING) # Optimistic lock
                  .values(
                        status=PodcastTaskStatus.PROCESSING,
                        last_modify_date=datetime.datetime.now()
                  )
            )
            result = await self.db.execute(stmt)
            return result.rowcount > 0

      async def update_status_async(self, podcast_id: int, status: PodcastTaskStatus, error_message: Optional[str] = None) -> bool:
            """更新播客状态"""
            stmt = (
                  update(PodcastTask)
                  .where(PodcastTask.id == podcast_id)
                  .values(
                        status=status,
                        error_message=error_message,
                        last_modify_date=datetime.datetime.now()
                  )
            )
            result = await self.db.execute(stmt)
            return result.rowcount > 0

      async def update_progress_step_async(self, podcast_id: int, progress_step: int) -> bool:
            """更新播客生成的进度"""
            stmt = (
                  update(PodcastTask)
                  .where(PodcastTask.id == podcast_id)
                  .values(
                        progress_step=progress_step,
                        last_modify_date=datetime.datetime.now()
                  )
            )
            result = await self.db.execute(stmt)
            return result.rowcount > 0