"""
视频混剪服务实现
"""
import os
import re
import json
import logging
import datetime
import subprocess
from typing import List, Dict, Tuple, Optional, Any, Union
from fastapi import UploadFile, HTTPException

from app.core.utils.snowflake import generate_id
from app.core.exceptions import BusinessException, NotFoundException

from app.modules.tools.videomixer.entities import (
    MixProject, SourceVideo, SceneFrame, SelectedScene, SelectedSceneNarration,
    FinalVideo, ProcessLog, AIAnalysis, MixProjectStatus, ProcessLogStatus
)
from app.modules.tools.videomixer.repositories import (
    MixProjectRepository, SourceVideoRepository, SceneFrameRepository,
    SelectedSceneRepository, SelectedSceneNarrationRepository,
    FinalVideoRepository, ProcessLogRepository, AIAnalysisRepository
)
from app.modules.tools.videomixer.dtos import (
    VideoMetadata, SceneFrameInfo, AIAnalysisResult, AnalysisRequest
)
from .file_service import FileService, FileValidationService
from .video_analysis import VideoAnalysisService
from .ai_analysis import AIAnalysisService
from .audio_service import AudioService, AudioHelper

logger = logging.getLogger(__name__)


class VideoMixerService:
    """视频混剪服务实现类"""
    
    def __init__(
        self,
        project_repository: MixProjectRepository,
        source_video_repository: SourceVideoRepository,
        scene_frame_repository: SceneFrameRepository,
        selected_scene_repository: SelectedSceneRepository,
        selected_scene_narration_repository: SelectedSceneNarrationRepository,
        final_video_repository: FinalVideoRepository,
        process_log_repository: ProcessLogRepository,
        ai_analysis_repository: AIAnalysisRepository,
        file_service: FileService,
        file_validation_service: FileValidationService,
        video_analysis_service: VideoAnalysisService,
        ai_analysis_service: AIAnalysisService,
        audio_service: AudioService
    ):
        """
        初始化视频混剪服务
        
        Args:
            project_repository: 项目仓储
            source_video_repository: 源视频仓储
            scene_frame_repository: 场景帧仓储
            selected_scene_repository: 选中场景仓储
            selected_scene_narration_repository: 选中场景解说词仓储
            final_video_repository: 最终视频仓储
            process_log_repository: 处理日志仓储
            ai_analysis_repository: AI分析结果仓储
            file_service: 文件服务
            file_validation_service: 文件验证服务
            video_analysis_service: 视频分析服务
            ai_analysis_service: AI分析服务
            audio_service: 音频服务
        """
        self.project_repository = project_repository
        self.source_video_repository = source_video_repository
        self.scene_frame_repository = scene_frame_repository
        self.selected_scene_repository = selected_scene_repository
        self.selected_scene_narration_repository = selected_scene_narration_repository
        self.final_video_repository = final_video_repository
        self.process_log_repository = process_log_repository
        self.ai_analysis_repository = ai_analysis_repository
        
        self.file_service = file_service
        self.file_validation_service = file_validation_service
        self.video_analysis_service = video_analysis_service
        self.ai_analysis_service = ai_analysis_service
        self.audio_service = audio_service
        
        # 从配置中获取基础存储路径
        from app.core.config.settings import settings
        self.base_storage_path = settings.get_or_default("VideoMixer.StoragePath", "uploads/videomixer")
        
        # 确保基础存储目录存在
        if not os.path.exists(self.base_storage_path):
            os.makedirs(self.base_storage_path, exist_ok=True)
    
    async def create_project_async(
        self,
        user_id: int,
        name: str,
        description: str,
        target_duration: int,
        scene_keywords: str,
        min_relevance_threshold: float,
        narration_style: str,
        background_music_type: int
    ) -> int:
        """
        创建混剪项目
        
        Args:
            user_id: 用户ID
            name: 项目名称
            description: 项目描述
            target_duration: 目标视频时长(秒)
            scene_keywords: 场景关键词
            min_relevance_threshold: 最低相关度阈值
            narration_style: 解说词风格
            background_music_type: 背景音乐类型
            
        Returns:
            项目ID
        """
        try:
            logger.info(f"开始创建混剪项目: {name}, 用户ID: {user_id}")
            
            # 验证目标视频时长
            if target_duration < 10:
                target_duration = 10  # 最短10秒
            
            # 验证相关度阈值
            if min_relevance_threshold < 0 or min_relevance_threshold > 1:
                min_relevance_threshold = 0.6  # 默认0.6
            
            # 创建项目实体
            project = MixProject(
                user_id=user_id,
                name=name,
                description=description,
                target_duration=target_duration,
                scene_keywords=scene_keywords,
                min_relevance_threshold=min_relevance_threshold,
                narration_style=narration_style,
                background_music_type=background_music_type,
                status=MixProjectStatus.INIT  # 创建状态
            )
            
            # 保存项目
            project_id = await self.project_repository.add(project)
            
            # 添加处理日志
            await self.process_log_repository.add_async(
                project_id, 
                MixProjectStatus.INIT, 
                ProcessLogStatus.SUCCESS, 
                "项目创建成功"
            )
            
            logger.info(f"混剪项目创建成功: ID={project_id}")
            return project_id
        
        except Exception as e:
            logger.error(f"创建混剪项目失败: {str(e)}", exc_info=True)
            raise
    
    async def upload_source_video_async(self, project_id: int, video_file: UploadFile) -> int:
        """
        上传源视频
        
        Args:
            project_id: 项目ID
            video_file: 视频文件
            
        Returns:
            源视频ID
        """
        try:
            logger.info(f"开始上传源视频: 项目ID={project_id}, 文件名={video_file.filename}")
            
            # 获取项目信息
            project = await self.project_repository.get_by_id(project_id)
            if not project:
                raise NotFoundException(f"项目不存在: ID={project_id}")
            
            # 创建项目存储目录
            project_dir = os.path.join(self.base_storage_path, "source_videos")
            
            # 上传视频文件
            video_path = await self.file_service.upload_file_async(video_file, project_dir)
            
            # 创建源视频实体
            source_video = SourceVideo(
                project_id=project_id,
                file_name=video_file.filename,
                file_path=video_path,
                file_size=video_file.size,
                status=0  # 上传完成状态
            )
            
            # 保存源视频信息
            video_id = await self.source_video_repository.add(source_video)
            
            # 添加处理日志
            await self.process_log_repository.add_async(
                project_id, 
                MixProjectStatus.UPLOAD, 
                ProcessLogStatus.SUCCESS, 
                f"视频上传成功: {video_file.filename}"
            )
            
            # 更新项目状态
            await self.project_repository.update_status_async(project_id, MixProjectStatus.UPLOAD)
            
            logger.info(f"源视频上传成功: ID={video_id}")
            return video_id
        
        except Exception as e:
            logger.error(f"上传源视频失败: {str(e)}", exc_info=True)
            
            # 添加处理日志
            await self.process_log_repository.add_async(
                project_id, 
                MixProjectStatus.UPLOAD, 
                ProcessLogStatus.FAIL, 
                "视频上传失败", 
                str(e)
            )
            
            raise
    
    async def upload_background_music_async(self, project_id: int, music_file: UploadFile) -> bool:
        """
        上传背景音乐
        
        Args:
            project_id: 项目ID
            music_file: 音乐文件
            
        Returns:
            操作是否成功
        """
        try:
            logger.info(f"开始上传背景音乐: 项目ID={project_id}, 文件名={music_file.filename}")
            
            # 获取项目信息
            project = await self.project_repository.get_by_id(project_id)
            if not project:
                raise NotFoundException(f"项目不存在: ID={project_id}")
            
            # 创建音乐存储目录
            music_dir = os.path.join(self.base_storage_path, "background_music")
            
            # 上传音乐文件
            music_path = await self.file_service.upload_file_async(music_file, music_dir)
            
            # 更新项目的背景音乐信息
            project.background_music_type = 3  # 上传音乐文件
            project.background_music_path = music_path
            await self.project_repository.update(project)
            
            # 添加处理日志
            await self.process_log_repository.add_async(
                project_id, 
                MixProjectStatus.UPLOAD, 
                ProcessLogStatus.SUCCESS, 
                f"背景音乐上传成功: {music_file.filename}"
            )
            
            logger.info(f"背景音乐上传成功: {music_path}")
            return True
        
        except Exception as e:
            logger.error(f"上传背景音乐失败: {str(e)}", exc_info=True)
            
            # 添加处理日志
            await self.process_log_repository.add_async(
                project_id, 
                MixProjectStatus.UPLOAD, 
                ProcessLogStatus.FAIL, 
                "背景音乐上传失败", 
                str(e)
            )
            
            raise
    
    async def analyze_videos_async(self, project_id: int) -> bool:
        """
        分析视频并生成场景帧
        
        Args:
            project_id: 项目ID
            
        Returns:
            操作是否成功
        """
        try:
            logger.info(f"开始分析视频: 项目ID={project_id}")
            
            # 获取项目信息
            project = await self.project_repository.get_by_id(project_id)
            if not project:
                raise NotFoundException(f"项目不存在: ID={project_id}")
            
            # 获取项目的所有源视频
            source_videos = await self.source_video_repository.get_by_project_id_async(project_id)
            if not source_videos:
                raise BusinessException("项目没有源视频")
            
            # 添加处理日志
            process_log_id = await self.process_log_repository.add_async(
                project_id, 
                MixProjectStatus.ANALYSE_VIDEO, 
                ProcessLogStatus.INIT, 
                "开始分析视频"
            )
            
            # 更新项目状态
            await self.project_repository.update_status_async(project_id, MixProjectStatus.ANALYSE_VIDEO)
            
            # 先删除历史的帧数据
            await self.scene_frame_repository.delete_by_project_async(project_id)
            
            for video in source_videos:
                # 检查视频文件是否存在
                if not os.path.exists(video.file_path):
                    raise FileNotFoundError(f"视频文件不存在: {video.file_path}")
                
                # 分析视频元数据
                metadata = await self.video_analysis_service.analyse_video_async(video.file_path)
                
                # 更新视频元数据
                await self.source_video_repository.update_metadata_async(
                    video.id,
                    metadata.duration,
                    metadata.width,
                    metadata.height,
                    metadata.frame_rate,
                    metadata.bit_rate,
                    metadata.codec or ""
                )
                
                # 更新视频状态
                await self.source_video_repository.update_status_async(video.id, 1)  # 验证完成状态
                
                # 创建场景帧存储目录
                frames_dir = os.path.join(self.base_storage_path, str(project_id), "frames", str(video.id))
                
                # 定义场景阈值
                scene_threshold = 0.3
                
                # 检测视频场景
                scene_frames = await self.video_analysis_service.detect_scenes_async(
                    video.file_path,
                    frames_dir,
                    scene_threshold,
                    3  # 图片质量设置为3，平衡质量和大小
                )
                
                # 保存场景帧信息
                frame_entities = []
                for frame in scene_frames:
                    frame_entities.append(SceneFrame(
                        project_id=project_id,
                        source_video_id=video.id,
                        frame_number=frame.frame_number,
                        frame_time=frame.frame_time.total_seconds(),
                        end_time=frame.end_time.total_seconds(),
                        image_path=frame.image_path,
                        is_selected=0,  # 未选中
                        relevance_score=0  # 初始相关度得分为0
                    ))
                
                # 批量保存场景帧
                if frame_entities:
                    await self.scene_frame_repository.add_batch(frame_entities)
                
                # 更新视频状态
                await self.source_video_repository.update_status_async(video.id, 2)  # 场景检测完成状态
            
            # 更新项目状态
            await self.project_repository.update_status_async(project_id, MixProjectStatus.DETECT_SCENES)
            
            # 更新处理日志
            await self.process_log_repository.update_status_async(
                process_log_id,
                ProcessLogStatus.SUCCESS,
                f"视频分析完成，共检测到 {len(source_videos)} 个视频"
            )
            
            logger.info(f"视频分析完成: 项目ID={project_id}")
            return True
        
        except Exception as e:
            logger.error(f"分析视频失败: {str(e)}", exc_info=True)
            
            # 更新项目状态和错误信息
            await self.project_repository.update_status_async(project_id, MixProjectStatus.ERROR, str(e))
            
            # 添加处理日志
            await self.process_log_repository.add_async(
                project_id, 
                MixProjectStatus.ANALYSE_VIDEO, 
                ProcessLogStatus.FAIL, 
                "视频分析失败", 
                str(e)
            )
            
            raise
    
    async def ai_analyze_scenes_async(self, project_id: int) -> bool:
        """
        AI分析场景并生成脚本
        
        Args:
            project_id: 项目ID
            
        Returns:
            操作是否成功
        """
        try:
            logger.info(f"开始AI分析场景: 项目ID={project_id}")
            
            # 获取项目信息
            project = await self.project_repository.get_by_id(project_id)
            if not project:
                raise NotFoundException(f"项目不存在: ID={project_id}")
            
            # 添加处理日志
            process_log_id = await self.process_log_repository.add_async(
                project_id, 
                MixProjectStatus.AI_ANALYZE, 
                ProcessLogStatus.INIT, 
                "开始AI分析场景"
            )
            
            # 按项目先删除AI分析过的场景
            await self.selected_scene_repository.delete_by_project_async(project_id)
            
            # 更新项目状态
            await self.project_repository.update_status_async(project_id, MixProjectStatus.AI_ANALYZE)
            
            # 获取项目的所有场景帧
            scene_frames = await self.scene_frame_repository.get_by_project_id_async(project_id)
            if not scene_frames:
                raise BusinessException("项目没有检测到场景帧")
            
            # 获取所有源视频
            source_videos = await self.source_video_repository.get_by_project_id_async(project_id)
            video_dict = {v.id: v for v in source_videos}
            
            # 将场景帧转换为分析所需的格式
            frame_infos = []
            for frame in scene_frames:
                frame_info = SceneFrameInfo()
                frame_info.id = frame.id
                frame_info.frame_number = frame.frame_number
                frame_info.frame_time = datetime.timedelta(seconds=frame.frame_time)
                frame_info.end_time = datetime.timedelta(seconds=frame.end_time)
                frame_info.image_path = frame.image_path
                frame_info.source_video_id = frame.source_video_id
                
                # 如果没有CDN URL，则上传到CDN
                if not frame.image_url:
                    # 上传帧图片到CDN
                    cdn_path = f"video-mixer/frames/{frame.id}.jpg"
                    image_url = await self.file_service.upload_to_cdn_async(frame.image_path, cdn_path)
                    
                    # 更新帧图片CDN URL
                    await self.scene_frame_repository.update_image_url_async(frame.id, image_url)
                    frame_info.image_url = image_url
                else:
                    frame_info.image_url = frame.image_url
                
                frame_infos.append(frame_info)
            
            # 创建AI分析记录
            ai_analysis = AIAnalysis(
                project_id=project_id,
                prompt_content=f"场景关键词: {project.scene_keywords}, 目标时长: {project.target_duration}秒, 解说词风格: {project.narration_style}",
                status=0  # 进行中
            )
            analysis_id = await self.ai_analysis_repository.add(ai_analysis)
            
            # 调用AI服务分析场景
            analysis_request = AnalysisRequest()
            analysis_request.scene_keywords = project.scene_keywords
            analysis_request.target_duration = project.target_duration
            analysis_request.min_relevance_threshold = project.min_relevance_threshold
            analysis_request.narration_style = project.narration_style
            
            ai_result = await self.ai_analysis_service.analyze_scenes_async(project_id, analysis_request, frame_infos)
            
            # 更新AI分析结果
            ai_result.analysis_id = analysis_id
            await self.ai_analysis_repository.update_response_content_async(
                analysis_id,
                "AI分析完成",  # 实际应保存完整的AI响应内容
                ai_result.narration_script or ""
            )
            
            if not ai_result.selected_scenes:
                raise BusinessException(f"AI分析完成，没有可用场景，{project_id}")
            
            # 创建选中场景实体
            selected_scenes = []
            for scene in ai_result.selected_scenes:
                db_scene = next((s for s in scene_frames if s.id == scene.id), None)
                if not db_scene:
                    continue
                
                selected_scene = SelectedScene(
                    project_id=project_id,
                    source_video_id=scene.source_video_id,
                    sequence_order=scene.sequence_order,
                    start_time=db_scene.frame_time,
                    end_time=db_scene.end_time,
                    duration=(db_scene.end_time - db_scene.frame_time),
                    scene_description=scene.content,
                    status=0  # 选中状态
                )
                
                # 保存场景
                selected_scene_id = await self.selected_scene_repository.add(selected_scene)
                
                # 保存解说词
                if scene.narratives:
                    for narration in scene.narratives:
                        narration_entity = SelectedSceneNarration(
                            project_id=project_id,
                            selected_scene_id=selected_scene_id,
                            duration=0,  # 初始时长为0
                            narration=narration
                        )
                        await self.selected_scene_narration_repository.add(narration_entity)
            
            # 更新项目状态
            await self.project_repository.update_status_async(project_id, MixProjectStatus.AI_ANALYZE)
            
            # 更新处理日志
            await self.process_log_repository.update_status_async(
                process_log_id,
                ProcessLogStatus.SUCCESS,
                f"AI分析场景完成，选择了 {len(ai_result.selected_scenes)} 个场景"
            )
            
            logger.info(f"AI分析场景完成: 项目ID={project_id}")
            return True
        
        except Exception as e:
            logger.error(f"AI分析场景失败: {str(e)}", exc_info=True)
            
            # 更新项目状态和错误信息
            await self.project_repository.update_status_async(project_id, MixProjectStatus.ERROR, str(e))
            
            # 添加处理日志
            await self.process_log_repository.add_async(
                project_id, 
                MixProjectStatus.AI_ANALYZE, 
                ProcessLogStatus.FAIL, 
                "AI分析场景失败", 
                str(e)
            )
            
            raise
    
    async def generate_narration_audio_async(self, project_id: int) -> bool:
        """
        生成解说音频
        
        Args:
            project_id: 项目ID
            
        Returns:
            操作是否成功
        """
        try:
            logger.info(f"开始生成解说音频: 项目ID={project_id}")
            
            # 获取项目信息
            project = await self.project_repository.get_by_id(project_id)
            if not project:
                raise NotFoundException(f"项目不存在: ID={project_id}")
            
            # 添加处理日志
            process_log_id = await self.process_log_repository.add_async(
                project_id, 
                MixProjectStatus.AUDIO_GENERATE, 
                ProcessLogStatus.INIT, 
                "开始生成解说音频"
            )
            
            # 更新项目状态
            await self.project_repository.update_status_async(project_id, MixProjectStatus.AUDIO_GENERATE)
            
            # 获取项目的所有选中场景
            selected_scenes = await self.selected_scene_repository.get_by_project_id_async(project_id)
            if not selected_scenes:
                raise BusinessException("项目没有选中的场景")
            
            # 创建音频存储目录
            audio_dir = os.path.join(self.base_storage_path, str(project_id), "narration_audio")
            if not os.path.exists(audio_dir):
                os.makedirs(audio_dir, exist_ok=True)
            
            for scene in selected_scenes:
                if not scene.narrations:
                    logger.warning(f"场景 {scene.id} 没有解说词，跳过")
                    continue
                
                # 一个帧，可能有多个解说脚本
                i = 0
                for scene_narration in scene.narrations:
                    if not scene_narration.narration:
                        continue
                    
                    # 生成解说音频
                    success, audio_url, audio_duration = await self.audio_service.text_to_speech_async(
                        scene_narration.id, 
                        scene_narration.narration
                    )
                    
                    if not success:
                        logger.warning(f"场景 {scene.id} 解说词ID {scene_narration.id} 音频生成失败")
                        continue
                    
                    # 转换为MP3格式
                    directory_path = os.path.dirname(audio_url)
                    audio_name = f"narration_{scene.id}_{i}"
                    mp3_audio_path = os.path.join(directory_path, f"{audio_name}_converted.mp3")
                    
                    await AudioHelper.convert_to_mp3_async(audio_url, mp3_audio_path, 128000)
                    
                    # 更新场景的解说音频路径
                    await self.selected_scene_narration_repository.update_narration_audio_path_async(
                        scene_narration.id, 
                        mp3_audio_path, 
                        audio_duration.total_seconds()
                    )
                    
                    i += 1
            
            # 更新项目状态
            await self.project_repository.update_status_async(project_id, MixProjectStatus.AUDIO_GENERATE)
            
            # 更新处理日志
            await self.process_log_repository.update_status_async(
                process_log_id,
                ProcessLogStatus.SUCCESS,
                f"解说音频生成完成，处理了 {len(selected_scenes)} 个场景"
            )
            
            logger.info(f"解说音频生成完成: 项目ID={project_id}")
            return True
        
        except Exception as e:
            logger.error(f"生成解说音频失败: {str(e)}", exc_info=True)
            
            # 更新项目状态和错误信息
            await self.project_repository.update_status_async(project_id, MixProjectStatus.ERROR, str(e))
            
            # 添加处理日志
            await self.process_log_repository.add_async(
                project_id, 
                MixProjectStatus.AUDIO_GENERATE, 
                ProcessLogStatus.FAIL, 
                "生成解说音频失败", 
                str(e)
            )
            
            raise
    
    async def generate_final_video_async(self, project_id: int) -> int:
        """
        生成最终视频
        
        Args:
            project_id: 项目ID
            
        Returns:
            最终视频ID
        """
        try:
            logger.info(f"开始生成最终视频: 项目ID={project_id}")
            
            # 获取项目信息
            project = await self.project_repository.get_by_id(project_id)
            if not project:
                raise NotFoundException(f"项目不存在: ID={project_id}")
            
            # 添加处理日志
            process_log_id = await self.process_log_repository.add_async(
                project_id, 
                MixProjectStatus.FINAL_VIDEO, 
                ProcessLogStatus.INIT, 
                "开始生成最终视频"
            )
            
            # 更新项目状态
            await self.project_repository.update_status_async(project_id, MixProjectStatus.FINAL_VIDEO)
            
            # 获取项目的所有选中场景
            selected_scenes = await self.selected_scene_repository.get_by_project_id_async(project_id)
            if not selected_scenes:
                raise BusinessException("项目没有选中的场景")
            
            # 获取所有源视频
            source_videos = await self.source_video_repository.get_by_project_id_async(project_id)
            video_dict = {v.id: v for v in source_videos}
            
            # 创建场景视频存储目录
            scenes_dir = os.path.join(self.base_storage_path, str(project_id), "scene_videos")
            if not os.path.exists(scenes_dir):
                os.makedirs(scenes_dir, exist_ok=True)
            
            # 创建最终视频存储目录
            final_dir = os.path.join(self.base_storage_path, str(project_id), "final_video")
            if not os.path.exists(final_dir):
                os.makedirs(final_dir, exist_ok=True)
            
            # 生成背景音乐（如果需要）
            background_music_path = ""
            if project.background_music_type == 1:  # AI生成
                music_file_name = f"background_music_{project_id}.mp3"
                music_path = os.path.join(final_dir, music_file_name)
                
                music_success = await self.ai_analysis_service.generate_music_async(project.scene_keywords or "", music_path)
                if music_success:
                    background_music_path = music_path
                    project.background_music_path = music_path
                    await self.project_repository.update(project)
            
            elif project.background_music_type == 2:  # 系统随机内置
                # 从配置中获取预设音乐路径
                from app.core.config.settings import settings
                preset_music_path = settings.get_or_default("VideoMixer.PresetMusicPath", "Files/PresetMusic/")
                
                if os.path.exists(preset_music_path):
                    # 获取目录下的所有mp3文件
                    import glob
                    mp3_files = glob.glob(os.path.join(preset_music_path, "*.mp3"))
                    
                    if mp3_files:
                        # 随机选择一个音乐文件
                        import random
                        selected_music = random.choice(mp3_files)
                        
                        music_file_name = f"background_music_{project_id}.mp3"
                        music_path = os.path.join(final_dir, music_file_name)
                        
                        # 复制预设音乐文件
                        import shutil
                        shutil.copy2(selected_music, music_path)
                        
                        background_music_path = music_path
                        project.background_music_path = music_path
                        await self.project_repository.update(project)
            
            elif project.background_music_type == 3:  # 上传的音乐文件
                if project.background_music_path and os.path.exists(project.background_music_path):
                    background_music_path = project.background_music_path
            
            # 处理每个选中的场景
            scene_video_paths = []
            for scene in selected_scenes:
                # 检查源视频是否存在
                if scene.source_video_id not in video_dict:
                    logger.warning(f"场景 {scene.id} 的源视频 {scene.source_video_id} 不存在，跳过")
                    continue
                
                source_video = video_dict[scene.source_video_id]
                
                # 生成场景视频文件路径
                scene_file_name = f"scene_{scene.id}.mp4"
                video_segment_path = os.path.join(scenes_dir, scene_file_name)
                
                # 提取场景视频片段
                await self._extract_and_compose_scene_async(video_segment_path, scene, source_video, scenes_dir)
                
                # 更新场景的视频路径
                await self.selected_scene_repository.update_scene_video_path_async(scene.id, video_segment_path)
                
                # 添加到场景视频列表
                scene_video_paths.append(video_segment_path)
            
            if not scene_video_paths:
                raise BusinessException("没有成功生成的场景视频")
            
            # 生成最终视频文件路径
            final_video_file_name = f"final_{project_id}.mp4"
            final_video_path = os.path.join(final_dir, final_video_file_name)
            
            # 合并场景视频
            await self._merge_scenes_async(selected_scenes, scene_video_paths, background_music_path, final_video_path)
            
            # 上传最终视频到CDN
            cdn_path = f"video-mixer/{project_id}/final/{final_video_file_name}"
            video_url = await self.file_service.upload_to_cdn_async(final_video_path, cdn_path)
            
            # 获取视频元数据
            video_metadata = await self.video_analysis_service.analyse_video_async(final_video_path)
            
            # 创建最终视频实体
            final_video = FinalVideo(
                project_id=project_id,
                title=project.name,
                description=project.description,
                file_path=final_video_path,
                video_url=video_url,
                duration=video_metadata.duration,
                width=video_metadata.width,
                height=video_metadata.height,
                file_size=os.path.getsize(final_video_path),
                background_music_path=background_music_path
            )
            
            # 保存最终视频信息
            final_video_id = await self.final_video_repository.add(final_video)
            
            # 更新项目的最终视频URL
            project.final_video_url = video_url
            await self.project_repository.update(project)
            
            # 更新项目状态
            await self.project_repository.update_status_async(project_id, MixProjectStatus.FINAL_VIDEO)
            
            # 更新处理日志
            await self.process_log_repository.update_status_async(
                process_log_id,
                ProcessLogStatus.SUCCESS,
                f"最终视频生成完成: {video_url}"
            )
            
            logger.info(f"最终视频生成完成: 项目ID={project_id}, 视频ID={final_video_id}, URL={video_url}")
            return final_video_id
        
        except Exception as e:
            logger.error(f"生成最终视频失败: {str(e)}", exc_info=True)
            
            # 更新项目状态和错误信息
            await self.project_repository.update_status_async(project_id, MixProjectStatus.ERROR, str(e))
            
            # 添加处理日志
            await self.process_log_repository.add_async(
                project_id, 
                MixProjectStatus.FINAL_VIDEO, 
                ProcessLogStatus.FAIL, 
                "生成最终视频失败", 
                str(e)
            )
            
            raise
    
    async def get_project_async(self, project_id: int) -> MixProject:
        """
        获取项目信息
        
        Args:
            project_id: 项目ID
            
        Returns:
            项目信息
        """
        project = await self.project_repository.get_by_id(project_id)
        if not project:
            raise NotFoundException(f"项目不存在: ID={project_id}")
        
        return project
    
    async def get_user_projects_async(self, user_id: int, page_index: int = 1, page_size: int = 20) -> Tuple[List[MixProject], int]:
        """
        获取用户项目列表
        
        Args:
            user_id: 用户ID
            page_index: 页码，从1开始
            page_size: 每页数量
            
        Returns:
            项目列表和总记录数
        """
        return await self.project_repository.get_by_user_id_async(user_id, page_index, page_size)
    
    async def get_final_video_async(self, project_id: int) -> Optional[FinalVideo]:
        """
        获取最终视频信息
        
        Args:
            project_id: 项目ID
            
        Returns:
            最终视频信息
        """
        return await self.final_video_repository.get_by_project_id_async(project_id)
    
    async def get_source_videos_by_project_id_async(self, project_id: int) -> List[SourceVideo]:
        """
        获取项目的源视频列表
        
        Args:
            project_id: 项目ID
            
        Returns:
            源视频列表
        """
        return await self.source_video_repository.get_by_project_id_async(project_id)
    
    async def get_selected_scenes_by_project_id_async(self, project_id: int) -> List[SelectedScene]:
        """
        获取项目的选中场景列表
        
        Args:
            project_id: 项目ID
            
        Returns:
            选中场景列表
        """
        return await self.selected_scene_repository.get_by_project_id_async(project_id)
    
    async def get_process_logs_by_project_id_async(self, project_id: int) -> List[ProcessLog]:
        """
        获取项目的处理日志列表
        
        Args:
            project_id: 项目ID
            
        Returns:
            处理日志列表
        """
        return await self.process_log_repository.get_by_project_id_async(project_id)
    
    async def get_pending_videos_async(self, batch_size: int = 5) -> List[MixProject]:
        """
        获取需要执行的视频
        
        Args:
            batch_size: 批量大小
            
        Returns:
            待处理项目列表
        """
        return await self.project_repository.get_pending_videos_async(batch_size)
    
    async def update_running_async(self, id: int, is_running: int) -> bool:
        """
        更新项目是否执行中，用于锁定，避免调度重复执行
        
        Args:
            id: 项目ID
            is_running: 是否执行锁定
            
        Returns:
            操作结果
        """
        return await self.project_repository.update_running_async(id, is_running)
    
    async def update_generate_lock_async(self, id: int, is_generate_lock: int) -> bool:
        """
        更新项目开始生成，开始生成就锁定了，不能再编辑或者点击
        
        Args:
            id: 项目ID
            is_generate_lock: 是否执行锁定
            
        Returns:
            操作结果
        """
        return await self.project_repository.update_generate_lock_async(id, is_generate_lock)
    
    async def _extract_and_compose_scene_async(
        self, 
        output_path: str, 
        scene: SelectedScene, 
        source_video: SourceVideo, 
        scenes_dir: str
    ) -> str:
        """
        提取并合成场景视频
        
        Args:
            output_path: 输出路径
            scene: 场景信息
            source_video: 源视频信息
            scenes_dir: 场景目录
            
        Returns:
            视频路径
        """
        try:
            # 1. 从原视频提取片段
            cmd = [
                "ffmpeg",
                "-i", source_video.file_path,
                "-ss", str(scene.start_time),
                "-t", str(scene.duration),
                "-c:v", "libx264",
                "-preset", "slow",
                "-crf", "23",
                "-copyts",
                "-avoid_negative_ts", "make_zero",
                "-y",  # 覆盖已存在的文件
                output_path
            ]
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.warning(f"场景 {scene.id} 视频片段提取失败: {stderr}")
                raise RuntimeError(f"场景视频片段提取失败: {stderr}")
            
            # 2. 如果有解说词，添加解说音频和字幕
            if scene.narrations:
                # 生成输出文件路径
                final_output_path = os.path.join(scenes_dir, f"scene_full_{scene.id}.mp4")
                
                # 构建命令参数
                cmd_args = ["ffmpeg", "-i", output_path]
                
                # 添加音频输入
                for i, narration in enumerate(scene.narrations):
                    if narration.narration_audio_path and os.path.exists(narration.narration_audio_path):
                        cmd_args.extend(["-i", narration.narration_audio_path])
                
                # 构建音频混合滤镜
                if len(scene.narrations) > 0:
                    audio_filter = self._build_audio_complex_filters(scene)
                    
                    # 生成简单字幕文件
                    subtitle_path = os.path.join(scenes_dir, f"subtitle_{scene.id}.srt")
                    await self._create_subtitle_file(scene, subtitle_path)
                    
                    # 完成命令构建
                    cmd_args.extend([
                        "-filter_complex", audio_filter,
                        "-vf", f"subtitles={subtitle_path}",
                        "-map", "0:v", "-map", "[aout]",
                        "-c:v", "libx264",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-shortest",
                        "-y",
                        final_output_path
                    ])
                    
                    # 执行命令
                    process = subprocess.Popen(
                        cmd_args, 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE,
                        universal_newlines=True
                    )
                    
                    stdout, stderr = process.communicate()
                    
                    if process.returncode != 0:
                        logger.warning(f"场景 {scene.id} 视频合成失败: {stderr}")
                        # 如果合成失败，使用原始提取的片段
                        return output_path
                    
                    return final_output_path
            
            return output_path
        
        except Exception as e:
            logger.error(f"提取场景视频失败: {str(e)}", exc_info=True)
            raise
    
    def _build_audio_complex_filters(self, scene: SelectedScene) -> str:
        """
        构建音频复杂滤镜
        
        Args:
            scene: 场景信息
            
        Returns:
            滤镜字符串
        """
        if not scene.narrations:
            return ""
        
        audio_filter = []
        current_time = 0.0
        
        # 为每个解说词设置延迟
        for i, narration in enumerate(scene.narrations):
            if narration.narration_audio_path:
                audio_filter.append(f"[{i+1}:a]adelay={int(current_time * 1000)}|{int(current_time * 1000)}[a{i}]")
                current_time += narration.duration
        
        # 合并所有解说音频
        if audio_filter:
            audio_inputs = "".join(f"[a{i}]" for i in range(len(scene.narrations)))
            audio_filter.append(f"{audio_inputs}amix=inputs={len(scene.narrations)}:duration=longest[aout]")
        
        return ";".join(audio_filter)
    
    async def _create_subtitle_file(self, scene: SelectedScene, output_path: str) -> None:
        """
        创建字幕文件
        
        Args:
            scene: 场景信息
            output_path: 输出路径
        """
        if not scene.narrations:
            return
        
        with open(output_path, "w", encoding="utf-8") as f:
            current_time = 0.0
            
            for i, narration in enumerate(scene.narrations):
                if narration.narration and narration.duration > 0:
                    start_time = self._format_srt_time(current_time)
                    end_time = self._format_srt_time(current_time + narration.duration)
                    
                    f.write(f"{i+1}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{narration.narration}\n\n")
                    
                    current_time += narration.duration
    
    def _format_srt_time(self, seconds: float) -> str:
        """
        格式化SRT时间
        
        Args:
            seconds: 秒数
            
        Returns:
            格式化的时间字符串
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        milliseconds = int((seconds - int(seconds)) * 1000)
        
        return f"{hours:02}:{minutes:02}:{int(seconds):02},{milliseconds:03}"
    
    async def _merge_scenes_async(
        self, 
        scenes: List[SelectedScene], 
        scene_videos: List[str],
        background_music_path: str, 
        output_path: str
    ) -> str:
        """
        合并场景视频
        
        Args:
            scenes: 场景列表
            scene_videos: 场景视频路径列表
            background_music_path: 背景音乐路径
            output_path: 输出路径
            
        Returns:
            输出视频路径
        """
        try:
            # 创建场景列表文件
            temp_dir = os.path.dirname(output_path)
            list_path = os.path.join(temp_dir, "scenes.txt")
            
            with open(list_path, "w", encoding="utf-8") as f:
                for video_path in scene_videos:
                    f.write(f"file '{video_path}'\n")
            
            # 计算总时长
            total_duration = 0
            for scene in scenes:
                total_duration += scene.duration
            
            # 处理背景音乐
            bgm_args = []
            audio_filter = ""
            
            if background_music_path and os.path.exists(background_music_path):
                # 处理背景音乐的循环和淡入淡出
                bgm_processed_path = os.path.join(temp_dir, "bgm_processed.mp3")
                
                # 创建循环版本的背景音乐
                await AudioHelper.create_looped_version_async(
                    background_music_path, 
                    datetime.timedelta(seconds=total_duration),
                    bgm_processed_path
                )
                
                # 应用淡入淡出效果
                bgm_final_path = os.path.join(temp_dir, "bgm_final.mp3")
                await AudioHelper.apply_fade_effects_async(
                    bgm_processed_path,
                    bgm_final_path,
                    datetime.timedelta(seconds=3),
                    datetime.timedelta(seconds=3)
                )
                
                # 添加背景音乐参数
                bgm_args = ["-i", bgm_final_path]
                audio_filter = "-filter_complex \"[0:a][1:a]amix=inputs=2:duration=first:weights=1 0.3[aout]\" -map 0:v -map \"[aout]\""
            
            # 构建合并命令
            cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", list_path
            ]
            
            # 添加背景音乐输入
            cmd.extend(bgm_args)
            
            # 添加输出选项
            cmd.extend([
                "-c:v", "libx264",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                "-y",
                output_path
            ])
            
            # 如果有音频滤镜，添加到命令中
            if audio_filter:
                # 由于音频滤镜包含引号，需要特殊处理
                cmd_str = " ".join(cmd)
                index = cmd_str.find("-y")
                cmd_str = cmd_str[:index] + audio_filter + " " + cmd_str[index:]
                
                # 使用shell模式执行命令
                process = subprocess.Popen(
                    cmd_str,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
            else:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"场景合并失败: {stderr}")
                raise RuntimeError(f"场景合并失败: {stderr}")
            
            return output_path
        
        except Exception as e:
            logger.error(f"合并场景视频失败: {str(e)}", exc_info=True)
            raise