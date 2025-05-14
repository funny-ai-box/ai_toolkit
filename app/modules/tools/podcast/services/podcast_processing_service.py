# app/modules/tools/podcast/services/podcast_processing_service.py
import logging
from typing import List

from app.core.config.settings import Settings
from app.modules.tools.podcast.repositories import PodcastTaskRepository
from .podcast_service import PodcastService # Relative import

logger = logging.getLogger(__name__)

class PodcastProcessingService:
    """
    播客处理后台服务。
    This service contains logic that would be triggered by a recurring job.
    The C# [JobService] and [RecurringJob] attributes suggest this.
    In Python, a scheduler calls an API endpoint decorated with @job_endpoint,
    which then calls a method like `process_pending_podcasts_async`.
    """

    def __init__(
        self,
        settings: Settings,
        podcast_repo: PodcastTaskRepository,
        podcast_service: PodcastService # The main service for actual processing
    ):
        self.settings = settings
        self.podcast_repo = podcast_repo
        self.podcast_service = podcast_service # To call ProcessPodcastGenerate

    async def process_pending_podcasts_async(self) -> None:
        """
        处理所有状态为 PENDING 的播客任务。
        This method is intended to be called by a recurring job trigger.
        """
        try:
            logger.info("开始处理待处理的播客...")
            # Fetch a batch of pending podcasts
            pending_podcasts = await self.podcast_repo.get_pending_podcasts_async(limit=5) # C# example limit

            if not pending_podcasts:
                logger.info("没有待处理的播客。")
                return

            logger.info(f"找到 {len(pending_podcasts)} 个待处理的播客。")

            for podcast_task in pending_podcasts:
                logger.info(f"开始处理播客：{podcast_task.id} - {podcast_task.title or '无标题'}")
                try:
                    # The actual processing of a single podcast task
                    # This call is synchronous in the loop, as per C# logic.
                    # If ProcessPodcastGenerate is very long, consider making it a separate job itself.
                    await self.podcast_service.process_podcast_generate(podcast_task.id)
                    logger.info(f"播客处理调用完成（成功或失败）: {podcast_task.id} - {podcast_task.title or '无标题'}")
                except Exception as e_process:
                    # This catch is if process_podcast_generate itself throws before handling its own state.
                    # Normally, process_podcast_generate should handle its own errors and update task status.
                    logger.error(f"处理单个播客 {podcast_task.id} 时发生意外顶级错误: {e_process}", exc_info=True)
                    # Optionally update task status to FAILED here if not handled by process_podcast_generate
                    # await self.podcast_repo.update_status_async(podcast_task.id, PodcastTaskStatus.FAILED, f"顶级处理错误: {e_process}")
        
        except Exception as e_outer:
            logger.error(f"处理待处理的播客列表时发生全局异常: {e_outer}", exc_info=True)
            # This is an error in the processing loop itself, not a specific podcast task.
