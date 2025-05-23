"""
视频混剪后台服务
"""
import logging
import asyncio
from typing import List, Optional

from app.modules.tools.videomixer.entities import MixProject, MixProjectStatus, ProcessLogStatus
from app.modules.tools.videomixer.services.video_mixer import VideoMixerService

logger = logging.getLogger(__name__)


class VideoProcessingService:
    """视频处理后台服务"""
    
    def __init__(self, video_mixer_service: VideoMixerService):
        """
        初始化视频处理服务
        
        Args:
            video_mixer_service: 视频混剪服务
        """
        self.video_mixer_service = video_mixer_service
    
    async def process_pending_videos_async(self):
        """处理待处理的视频项目"""
        logger.info("开始处理待处理的视频项目")
        
        try:
            # 限制每次处理的视频项目数量
            batch_size = 5
            pending_videos = await self.video_mixer_service.get_pending_videos_async(batch_size)
            logger.info(f"找到 {len(pending_videos)} 个待处理视频项目")
            
            for project in pending_videos:
                logger.info(f"处理视频项目 {project.id}")
                await self.process_single_video_async(project)
        
        except Exception as e:
            logger.error(f"处理待处理视频项目时发生错误: {str(e)}")
    
    async def process_single_video_async(self, project: MixProject):
        """
        处理单个视频项目
        
        Args:
            project: 视频项目
        """
        logger.info(f"开始处理视频项目 {project.id}")
        
        try:
            # 更新视频项目状态为执行中
            await self.video_mixer_service.update_running_async(project.id, 1)
            
            # 处理视频项目
            await self.process_single_video_loop_status_async(project.id)
        
        except Exception as e:
            logger.error(f"处理视频项目 {project.id} 时发生错误: {str(e)}")
            
            try:
                # 更新视频项目状态为解锁执行
                await self.video_mixer_service.update_running_async(project.id, 0)
            except Exception as update_ex:
                logger.error(f"解锁视频项目 {project.id} 状态时发生错误: {str(update_ex)}")
    
    async def process_single_video_loop_status_async(self, project_id: int):
        """
        处理单个视频项目状态循环
        
        Args:
            project_id: 项目ID
        """
        # 同一个项目，串行执行四次，四个步骤
        for i in range(4):
            # 每次重新获取项目状态
            project = await self.video_mixer_service.get_project_async(project_id)
            
            if project.status == MixProjectStatus.UPLOAD:  # 上传完成
                logger.info(f"项目 {project_id} 开始分析视频")
                await self.video_mixer_service.analyze_videos_async(project.id)
            
            elif project.status == MixProjectStatus.DETECT_SCENES:  # 分析和场景检测完成
                logger.info(f"项目 {project_id} 开始AI分析视频")
                await self.video_mixer_service.ai_analyze_scenes_async(project.id)
            
            elif project.status == MixProjectStatus.AI_ANALYZE:  # AI分析完成
                logger.info(f"项目 {project_id} 开始生成解说音频")
                await self.video_mixer_service.generate_narration_audio_async(project.id)
            
            elif project.status == MixProjectStatus.AUDIO_GENERATE:  # 音频完成
                logger.info(f"项目 {project_id} 开始生成最终视频")
                await self.video_mixer_service.generate_final_video_async(project.id)
            
            # 检查项目是否已完成或失败
            if project.status in [MixProjectStatus.FINAL_VIDEO, MixProjectStatus.ERROR]:
                # 解锁执行状态
                await self.video_mixer_service.update_running_async(project.id, 0)
                logger.info(f"项目 {project_id} 处理完成，状态: {project.status}")
                break
            
            # 等待一秒，避免过于频繁地检查状态
            await asyncio.sleep(1)
        
        # 最后确保解锁执行状态
        await self.video_mixer_service.update_running_async(project_id, 0)