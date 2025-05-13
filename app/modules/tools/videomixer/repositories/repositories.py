"""
视频混剪仓储实现
"""
import datetime
from typing import List, Optional, Tuple, Dict, Any

from sqlalchemy import select, update, func, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.snowflake import generate_id
from app.modules.tools.videomixer.entities import (
    MixProject, SourceVideo, SceneFrame, SelectedScene, SelectedSceneNarration,
    FinalVideo, ProcessLog, AIAnalysis, MixProjectStatus, ProcessLogStatus
)
from .repository_base import BaseRepository


class MixProjectRepository(BaseRepository[MixProject]):
    """混剪项目仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化仓储
        
        Args:
            db: 数据库会话
        """
        super().__init__(db, MixProject)
    
    async def get_by_user_id_async(self, user_id: int, page_index: int = 1, page_size: int = 20) -> Tuple[List[MixProject], int]:
        """
        获取用户的混剪项目列表
        
        Args:
            user_id: 用户ID
            page_index: 页码，从1开始
            page_size: 每页数量
            
        Returns:
            项目列表和总记录数
        """
        # 确保页码和每页数量有效
        if page_index < 1:
            page_index = 1
        if page_size < 1:
            page_size = 20
            
        # 计算跳过的记录数
        skip = (page_index - 1) * page_size
        
        # 查询满足条件的记录总数
        count_query = select(func.count()).select_from(MixProject).where(MixProject.user_id == user_id)
        total_count = await self.db.scalar(count_query)
        
        # 查询分页数据
        query = (
            select(MixProject)
            .where(MixProject.user_id == user_id)
            .order_by(MixProject.id.desc())
            .offset(skip)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        items = result.scalars().all()
        
        return list(items), total_count or 0
    
    async def update_status_async(self, id: int, status: MixProjectStatus, error_message: Optional[str] = None) -> bool:
        """
        更新项目状态
        
        Args:
            id: 项目ID
            status: 新状态
            error_message: 错误信息（如有）
            
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        
        # 构建更新字典
        update_values = {
            "status": status,
            "last_modify_date": now
        }
        
        # 如果有错误信息，则更新错误信息
        if error_message is not None:
            update_values["error_message"] = error_message
        
        # 执行更新
        query = (
            update(MixProject)
            .where(MixProject.id == id)
            .values(**update_values)
        )
        
        await self.db.execute(query)
        return True
    
    async def update_running_async(self, id: int, is_running: int) -> bool:
        """
        更新项目是否执行中，用于锁定，避免调度重复执行
        
        Args:
            id: 项目ID
            is_running: 是否执行锁定
            
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        
        query = (
            update(MixProject)
            .where(MixProject.id == id)
            .values(
                is_running=is_running,
                last_modify_date=now
            )
        )
        
        await self.db.execute(query)
        return True
    
    async def update_generate_lock_async(self, id: int, is_generate_lock: int) -> bool:
        """
        更新项目开始生成，开始生成就锁定了，不能再编辑或者点击
        
        Args:
            id: 项目ID
            is_generate_lock: 是否执行锁定
            
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        
        query = (
            update(MixProject)
            .where(MixProject.id == id)
            .values(
                is_generate_lock=is_generate_lock,
                last_modify_date=now
            )
        )
        
        await self.db.execute(query)
        return True
    
    async def get_pending_videos_async(self, batch_size: int = 5) -> List[MixProject]:
        """
        获取需要执行的视频
        
        Args:
            batch_size: 批量大小
            
        Returns:
            待处理项目列表
        """
        query = (
            select(MixProject)
            .where(
                and_(
                    MixProject.status >= 0,
                    MixProject.status <= 5,
                    MixProject.is_generate_lock == 1,
                    MixProject.is_running == 0
                )
            )
            .order_by(MixProject.create_date)
            .limit(batch_size)
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())


class SourceVideoRepository(BaseRepository[SourceVideo]):
    """源视频仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化仓储
        
        Args:
            db: 数据库会话
        """
        super().__init__(db, SourceVideo)
    
    async def get_by_project_id_async(self, project_id: int) -> List[SourceVideo]:
        """
        获取项目的所有源视频
        
        Args:
            project_id: 项目ID
            
        Returns:
            源视频列表
        """
        query = select(SourceVideo).where(SourceVideo.project_id == project_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_status_async(self, id: int, status: int) -> bool:
        """
        更新源视频状态
        
        Args:
            id: 视频ID
            status: 新状态
            
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        
        query = (
            update(SourceVideo)
            .where(SourceVideo.id == id)
            .values(
                status=status,
                last_modify_date=now
            )
        )
        
        await self.db.execute(query)
        return True
    
    async def update_metadata_async(
        self, 
        id: int, 
        duration: float, 
        width: int, 
        height: int, 
        frame_rate: float, 
        bit_rate: int, 
        codec: str
    ) -> bool:
        """
        更新视频元数据
        
        Args:
            id: 视频ID
            duration: 时长
            width: 宽度
            height: 高度
            frame_rate: 帧率
            bit_rate: 比特率
            codec: 编码格式
            
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        
        query = (
            update(SourceVideo)
            .where(SourceVideo.id == id)
            .values(
                duration=duration,
                width=width,
                height=height,
                frame_rate=frame_rate,
                bit_rate=bit_rate,
                codec=codec,
                last_modify_date=now
            )
        )
        
        await self.db.execute(query)
        return True


class SceneFrameRepository(BaseRepository[SceneFrame]):
    """场景帧仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化仓储
        
        Args:
            db: 数据库会话
        """
        super().__init__(db, SceneFrame)
    
    async def get_by_source_video_id_async(self, source_video_id: int) -> List[SceneFrame]:
        """
        获取源视频的所有场景帧
        
        Args:
            source_video_id: 源视频ID
            
        Returns:
            场景帧列表
        """
        query = select(SceneFrame).where(SceneFrame.source_video_id == source_video_id).order_by(SceneFrame.frame_time)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_by_project_id_async(self, project_id: int) -> List[SceneFrame]:
        """
        获取项目的所有场景帧
        
        Args:
            project_id: 项目ID
            
        Returns:
            场景帧列表
        """
        query = (
            select(SceneFrame)
            .where(SceneFrame.project_id == project_id)
            .order_by(SceneFrame.source_video_id, SceneFrame.frame_time)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_image_url_async(self, id: int, image_url: str) -> bool:
        """
        更新场景帧CDN URL
        
        Args:
            id: 帧ID
            image_url: CDN URL
            
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        
        query = (
            update(SceneFrame)
            .where(SceneFrame.id == id)
            .values(
                image_url=image_url,
                last_modify_date=now
            )
        )
        
        await self.db.execute(query)
        return True
    
    async def update_selected_status_async(self, id: int, is_selected: int, relevance_score: float) -> bool:
        """
        更新场景帧AI选中状态
        
        Args:
            id: 帧ID
            is_selected: 是否被选中
            relevance_score: 相关度得分
            
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        
        query = (
            update(SceneFrame)
            .where(SceneFrame.id == id)
            .values(
                is_selected=is_selected,
                relevance_score=relevance_score,
                last_modify_date=now
            )
        )
        
        await self.db.execute(query)
        return True
    
    async def update_selected_status_batch_async(self, frame_ids: List[int], is_selected: int) -> bool:
        """
        批量更新场景帧AI选中状态
        
        Args:
            frame_ids: 帧ID列表
            is_selected: 是否被选中
            
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        
        query = (
            update(SceneFrame)
            .where(SceneFrame.id.in_(frame_ids))
            .values(
                is_selected=is_selected,
                last_modify_date=now
            )
        )
        
        await self.db.execute(query)
        return True
    
    async def delete_by_project_async(self, project_id: int) -> bool:
        """
        按照项目删除场景帧
        
        Args:
            project_id: 项目ID
            
        Returns:
            操作结果
        """
        query = delete(SceneFrame).where(SceneFrame.project_id == project_id)
        await self.db.execute(query)
        return True


class SelectedSceneRepository(BaseRepository[SelectedScene]):
    """选中场景仓储实现"""
    
    def __init__(self, db: AsyncSession, narration_repository: 'SelectedSceneNarrationRepository' = None):
        """
        初始化仓储
        
        Args:
            db: 数据库会话
            narration_repository: 解说词仓储
        """
        super().__init__(db, SelectedScene)
        self.narration_repository = narration_repository
    
    async def get_by_project_id_async(self, project_id: int) -> List[SelectedScene]:
        """
        获取项目的所有选中场景
        
        Args:
            project_id: 项目ID
            
        Returns:
            选中场景列表
        """
        query = select(SelectedScene).where(SelectedScene.project_id == project_id).order_by(SelectedScene.sequence_order)
        result = await self.db.execute(query)
        scenes = list(result.scalars().all())
        
        # 获取解说词
        if self.narration_repository and scenes:
            for scene in scenes:
                scene.narrations = await self.narration_repository.get_by_selected_scene_id_async(scene.id)
        
        return scenes
    
    async def update_status_async(self, id: int, status: int) -> bool:
        """
        更新选中场景状态
        
        Args:
            id: 场景ID
            status: 新状态
            
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        
        query = (
            update(SelectedScene)
            .where(SelectedScene.id == id)
            .values(
                status=status,
                last_modify_date=now
            )
        )
        
        await self.db.execute(query)
        return True
    
    async def update_scene_video_path_async(self, id: int, scene_video_path: str) -> bool:
        """
        更新场景视频路径
        
        Args:
            id: 场景ID
            scene_video_path: 场景视频路径
            
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        
        query = (
            update(SelectedScene)
            .where(SelectedScene.id == id)
            .values(
                scene_video_path=scene_video_path,
                status=2,  # 场景视频生成完成
                last_modify_date=now
            )
        )
        
        await self.db.execute(query)
        return True
    
    async def delete_by_project_async(self, project_id: int) -> bool:
        """
        按项目删除选中场景
        
        Args:
            project_id: 项目ID
            
        Returns:
            操作结果
        """
        # 获取所有场景
        scenes = await self.get_by_project_id_async(project_id)
        
        # 删除解说词
        if self.narration_repository and scenes:
            for scene in scenes:
                await self.narration_repository.delete_by_scene_id_async(scene.id)
        
        # 删除场景
        query = delete(SelectedScene).where(SelectedScene.project_id == project_id)
        await self.db.execute(query)
        
        return True


class SelectedSceneNarrationRepository(BaseRepository[SelectedSceneNarration]):
    """选中场景解说词仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化仓储
        
        Args:
            db: 数据库会话
        """
        super().__init__(db, SelectedSceneNarration)
    
    async def get_by_selected_scene_id_async(self, selected_scene_id: int) -> List[SelectedSceneNarration]:
        """
        获取场景的所有解说词
        
        Args:
            selected_scene_id: 场景ID
            
        Returns:
            解说词列表
        """
        query = select(SelectedSceneNarration).where(SelectedSceneNarration.selected_scene_id == selected_scene_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_narration_audio_path_async(self, id: int, narration_audio_path: str, duration: float) -> bool:
        """
        更新解说音频路径
        
        Args:
            id: 解说词ID
            narration_audio_path: 解说音频路径
            duration: 音频时长
            
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        
        query = (
            update(SelectedSceneNarration)
            .where(SelectedSceneNarration.id == id)
            .values(
                duration=duration,
                narration_audio_path=narration_audio_path,
                last_modify_date=now
            )
        )
        
        await self.db.execute(query)
        return True
    
    async def delete_by_scene_id_async(self, scene_id: int) -> bool:
        """
        按场景删除解说词
        
        Args:
            scene_id: 场景ID
            
        Returns:
            操作结果
        """
        query = delete(SelectedSceneNarration).where(SelectedSceneNarration.selected_scene_id == scene_id)
        await self.db.execute(query)
        return True


class FinalVideoRepository(BaseRepository[FinalVideo]):
    """最终视频仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化仓储
        
        Args:
            db: 数据库会话
        """
        super().__init__(db, FinalVideo)
    
    async def get_by_project_id_async(self, project_id: int) -> Optional[FinalVideo]:
        """
        根据项目ID获取最终视频
        
        Args:
            project_id: 项目ID
            
        Returns:
            最终视频实体
        """
        query = select(FinalVideo).where(FinalVideo.project_id == project_id)
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def update_video_url_async(self, id: int, video_url: str) -> bool:
        """
        更新CDN URL
        
        Args:
            id: 视频ID
            video_url: CDN URL
            
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        
        query = (
            update(FinalVideo)
            .where(FinalVideo.id == id)
            .values(
                video_url=video_url,
                last_modify_date=now
            )
        )
        
        await self.db.execute(query)
        return True


class ProcessLogRepository(BaseRepository[ProcessLog]):
    """处理日志仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化仓储
        
        Args:
            db: 数据库会话
        """
        super().__init__(db, ProcessLog)
    
    async def add_async(
        self, 
        project_id: int,
        process_step: MixProjectStatus, 
        process_status: ProcessLogStatus, 
        msg: str, 
        err_msg: str = ""
    ) -> int:
        """
        添加处理日志
        
        Args:
            project_id: 项目ID
            process_step: 处理步骤
            process_status: 处理状态
            msg: 处理信息
            err_msg: 错误详情
            
        Returns:
            日志ID
        """
        log_obj = ProcessLog(
            id=generate_id(),
            project_id=project_id,
            process_step=process_step,  # 处理步骤
            status=process_status,  # 处理状态
            message=msg,
            error_details=err_msg,
            create_date=datetime.datetime.now(),
            last_modify_date=datetime.datetime.now()
        )
        
        self.db.add(log_obj)
        await self.db.flush()
        return log_obj.id
    
    async def get_by_project_id_async(self, project_id: int) -> List[ProcessLog]:
        """
        获取项目的所有处理日志
        
        Args:
            project_id: 项目ID
            
        Returns:
            处理日志列表
        """
        query = select(ProcessLog).where(ProcessLog.project_id == project_id).order_by(ProcessLog.create_date)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_by_project_id_and_step_async(self, project_id: int, process_step: int) -> List[ProcessLog]:
        """
        获取项目的特定步骤处理日志
        
        Args:
            project_id: 项目ID
            process_step: 处理步骤
            
        Returns:
            处理日志列表
        """
        query = (
            select(ProcessLog)
            .where(and_(ProcessLog.project_id == project_id, ProcessLog.process_step == process_step))
            .order_by(ProcessLog.create_date.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_status_async(
        self, 
        id: int, 
        status: ProcessLogStatus, 
        message: Optional[str] = None, 
        error_details: Optional[str] = None
    ) -> bool:
        """
        更新处理日志状态
        
        Args:
            id: 日志ID
            status: 新状态
            message: 处理信息
            error_details: 错误详情
            
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        
        # 构建更新字典
        update_values = {
            "status": status,
            "last_modify_date": now
        }
        
        # 如果有消息，则更新消息
        if message is not None:
            update_values["message"] = message
            
        # 如果有错误详情，则更新错误详情
        if error_details is not None:
            update_values["error_details"] = error_details
        
        # 执行更新
        query = (
            update(ProcessLog)
            .where(ProcessLog.id == id)
            .values(**update_values)
        )
        
        await self.db.execute(query)
        return True


class AIAnalysisRepository(BaseRepository[AIAnalysis]):
    """AI分析结果仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化仓储
        
        Args:
            db: 数据库会话
        """
        super().__init__(db, AIAnalysis)
    
    async def get_by_project_id_async(self, project_id: int) -> Optional[AIAnalysis]:
        """
        根据项目ID获取AI分析结果
        
        Args:
            project_id: 项目ID
            
        Returns:
            AI分析结果实体
        """
        query = (
            select(AIAnalysis)
            .where(AIAnalysis.project_id == project_id)
            .order_by(AIAnalysis.create_date.desc())
        )
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def update_status_async(self, id: int, status: int) -> bool:
        """
        更新AI分析状态
        
        Args:
            id: 分析结果ID
            status: 新状态
            
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        
        query = (
            update(AIAnalysis)
            .where(AIAnalysis.id == id)
            .values(
                status=status,
                last_modify_date=now
            )
        )
        
        await self.db.execute(query)
        return True
    
    async def update_response_content_async(self, id: int, response_content: str, narration_script: str) -> bool:
        """
        更新AI分析响应内容
        
        Args:
            id: 分析结果ID
            response_content: 响应内容
            narration_script: 叙事脚本
            
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        
        query = (
            update(AIAnalysis)
            .where(AIAnalysis.id == id)
            .values(
                response_content=response_content,
                narration_script=narration_script,
                status=1,  # 成功
                last_modify_date=now
            )
        )
        
        await self.db.execute(query)
        return True