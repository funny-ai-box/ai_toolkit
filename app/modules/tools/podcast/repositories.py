"""
播客模块数据库仓储层 - 继续
"""
import datetime
import logging
from typing import List, Optional, Tuple, Dict, Any, Union
from sqlalchemy import select, func, update, delete, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from app.core.utils.snowflake import generate_id
from app.core.exceptions import BusinessException
from app.modules.tools.podcast.models import (
    PodcastTask, PodcastTaskContent, PodcastTaskScript, 
    PodcastScriptHistory, PodcastScriptHistoryItem, PodcastVoiceDefinition
)
from app.modules.tools.podcast.constants import (
    PodcastTaskStatus, PodcastRoleType, AudioStatusType, 
    PodcastTaskContentType, VoiceGenderType, VoicePlatformType
)

logger = logging.getLogger(__name__)

# 继续添加未完成的仓储类方法
class PodcastTaskScriptRepository:
    """播客脚本仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化播客脚本仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def get_by_id_async(self, id: int) -> Optional[PodcastTaskScript]:
        """
        获取播客脚本项
        
        Args:
            id: 脚本项ID
        
        Returns:
            脚本项实体
        """
        query = select(PodcastTaskScript).where(PodcastTaskScript.id == id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_podcast_id_async(self, podcast_id: int) -> List[PodcastTaskScript]:
        """
        获取播客的所有脚本项
        
        Args:
            podcast_id: 播客ID
        
        Returns:
            脚本项实体列表
        """
        query = select(PodcastTaskScript)\
            .where(PodcastTaskScript.podcast_id == podcast_id)\
            .order_by(PodcastTaskScript.sequence_number)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_by_podcast_ids_async(self, podcast_ids: List[int]) -> List[PodcastTaskScript]:
        """
        获取多个播客的所有脚本项
        
        Args:
            podcast_ids: 播客ID列表
        
        Returns:
            脚本项实体列表
        """
        if not podcast_ids:
            return []
        
        query = select(PodcastTaskScript)\
            .where(PodcastTaskScript.podcast_id.in_(podcast_ids))\
            .order_by(PodcastTaskScript.sequence_number)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def add_range_async(self, script_items: List[PodcastTaskScript]) -> bool:
        """
        批量新增脚本项
        
        Args:
            script_items: 脚本项列表
        
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        
        for item in script_items:
            item.id = generate_id()
            item.create_date = now
            item.last_modify_date = now
        
        self.db.add_all(script_items)
        await self.db.flush()
        await self.db.commit()
        return True
    
    async def add_async(self, script_item: PodcastTaskScript) -> bool:
        """
        新增脚本项
        
        Args:
            script_item: 脚本项实体
        
        Returns:
            操作结果
        """
        script_item.id = generate_id()
        now = datetime.datetime.now()
        script_item.create_date = now
        script_item.last_modify_date = now
        
        self.db.add(script_item)
        await self.db.flush()
        await self.db.commit()
        return True
    
    async def update_async(self, script_item: PodcastTaskScript) -> bool:
        """
        更新脚本项
        
        Args:
            script_item: 脚本项实体
        
        Returns:
            操作结果
        """
        script_item.last_modify_date = datetime.datetime.now()
        await self.db.merge(script_item)
        await self.db.flush()
        await self.db.commit()
        return True
    
    async def delete_by_podcast_id_async(self, podcast_id: int) -> bool:
        """
        删除播客的所有脚本项
        
        Args:
            podcast_id: 播客ID
        
        Returns:
            操作结果
        """
        query = delete(PodcastTaskScript).where(PodcastTaskScript.podcast_id == podcast_id)
        result = await self.db.execute(query)
        await self.db.commit()
        return result.rowcount > 0
    
    async def get_pending_audio_scripts_async(self, limit: int = 20) -> List[PodcastTaskScript]:
        """
        获取待生成语音的脚本项
        
        Args:
            limit: 限制数量
        
        Returns:
            待生成语音的脚本项列表
        """
        query = select(PodcastTaskScript)\
            .where(PodcastTaskScript.audio_status == AudioStatusType.PENDING)\
            .order_by(PodcastTaskScript.create_date)\
            .limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_audio_status_async(
        self, id: int, status: AudioStatusType, audio_path: str = "", audio_duration: float = 0
    ) -> bool:
        """
        更新脚本项语音状态
        
        Args:
            id: 脚本项ID
            status: 状态
            audio_path: 语音文件路径
            audio_duration: 语音文件时长(秒)
        
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        
        if audio_path:
            # 有音频文件路径时更新所有内容
            query = update(PodcastTaskScript)\
                .where(PodcastTaskScript.id == id)\
                .values(
                    audio_status=status,
                    audio_path=audio_path,
                    audio_duration=audio_duration,
                    last_modify_date=now
                )
        else:
            # 没有音频文件路径时只更新状态
            query = update(PodcastTaskScript)\
                .where(PodcastTaskScript.id == id)\
                .values(
                    audio_status=status,
                    last_modify_date=now
                )
        
        result = await self.db.execute(query)
        await self.db.flush()
        await self.db.commit()
        return result.rowcount > 0


class PodcastScriptHistoryRepository:
    """播客历史脚本仓储"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化播客历史脚本仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def get_by_podcast_id_async(self, podcast_id: int) -> List[PodcastScriptHistory]:
        """
        获取播客的所有脚本历史项
        
        Args:
            podcast_id: 播客ID
        
        Returns:
            脚本项实体列表
        """
        query = select(PodcastScriptHistory)\
            .where(PodcastScriptHistory.podcast_id == podcast_id)\
            .order_by(PodcastScriptHistory.id)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_script_history_item_async(self, history_id: int) -> List[PodcastScriptHistoryItem]:
        """
        获取播客历史脚本的明细
        
        Args:
            history_id: 历史Id
        
        Returns:
            脚本项实体列表
        """
        query = select(PodcastScriptHistoryItem)\
            .where(PodcastScriptHistoryItem.history_id == history_id)\
            .order_by(PodcastScriptHistoryItem.sequence_number)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def add_async(self, podcast_id: int) -> int:
        """
        新增历史操作记录
        
        Args:
            podcast_id: 播客ID
        
        Returns:
            新添加的历史记录ID
        """
        now = datetime.datetime.now()
        new_history = PodcastScriptHistory(
            id=generate_id(),
            podcast_id=podcast_id,
            name=f"{now.strftime('%Y-%m-%d %H:%M:%S')} 创建播客",
            status=PodcastTaskStatus.PROCESSING,
            error_message=None,
            create_date=now,
            last_modify_date=now
        )
        
        self.db.add(new_history)
        await self.db.flush()
        await self.db.commit()
        return new_history.id
    
    async def update_status_async(
        self, history_id: int, status: PodcastTaskStatus, error_message: Optional[str] = None
    ) -> bool:
        """
        更新播客历史记录状态
        
        Args:
            history_id: 历史Id
            status: 状态
            error_message: 错误消息
        
        Returns:
            操作结果
        """
        query = update(PodcastScriptHistory)\
            .where(PodcastScriptHistory.id == history_id)\
            .values(
                status=status,
                error_message=error_message,
                last_modify_date=datetime.datetime.now()
            )
        result = await self.db.execute(query)
        await self.db.flush()
        await self.db.commit()
        return result.rowcount > 0
    
    async def move_script_to_history_async(self, podcast_id: int) -> bool:
        """
        迁移，会将播客的现有脚本结转过来
        
        Args:
            podcast_id: 播客ID
        
        Returns:
            操作结果
        """
        # 获取播客的现有脚本
        script_query = select(PodcastTaskScript)\
            .where(PodcastTaskScript.podcast_id == podcast_id)
        script_result = await self.db.execute(script_query)
        script_items = list(script_result.scalars().all())
        
        if script_items:
            # 创建历史项
            history_items = []
            for script_item in script_items:
                history_item = PodcastScriptHistoryItem(
                    id=script_item.id,
                    podcast_id=script_item.podcast_id,
                    history_id=script_item.history_id,
                    sequence_number=script_item.sequence_number,
                    role_type=script_item.role_type,
                    role_name=script_item.role_name,
                    voice_id=script_item.voice_id,
                    content=script_item.content,
                    ssml_content=script_item.ssml_content,
                    audio_path=script_item.audio_path,
                    audio_duration=script_item.audio_duration,
                    audio_status=script_item.audio_status,
                    create_date=script_item.create_date,
                    last_modify_date=script_item.last_modify_date
                )
                history_items.append(history_item)
            
            # 将播客的现有脚本结转过来
            if history_items:
                self.db.add_all(history_items)
                await self.db.flush()
            
            # 清除旧的脚本项
            delete_query = delete(PodcastTaskScript)\
                .where(PodcastTaskScript.podcast_id == podcast_id)
            await self.db.execute(delete_query)
            await self.db.flush()
            await self.db.commit()
        
        return True


class PodcastVoiceRepository:
    """播客语音角色仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化播客语音角色仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def get_by_id_async(self, id: int) -> Optional[PodcastVoiceDefinition]:
        """
        获取语音角色
        
        Args:
            id: 语音角色ID
        
        Returns:
            语音角色实体
        """
        query = select(PodcastVoiceDefinition).where(PodcastVoiceDefinition.id == id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_voice_symbol_async(self, voice_symbol: str) -> Optional[PodcastVoiceDefinition]:
        """
        根据语音ID获取语音角色
        
        Args:
            voice_symbol: 语音ID
        
        Returns:
            语音角色实体
        """
        query = select(PodcastVoiceDefinition)\
            .where(PodcastVoiceDefinition.voice_symbol == voice_symbol)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_all_active_voices_async(self, voice_type: str) -> List[PodcastVoiceDefinition]:
        """
        获取所有启用的语音角色
        
        Args:
            voice_type: 语音类型
        
        Returns:
            语音角色实体列表
        """
        query = select(PodcastVoiceDefinition)\
            .where(
                and_(
                    PodcastVoiceDefinition.voice_type == voice_type,
                    PodcastVoiceDefinition.is_active == True
                )
            )\
            .order_by(
                PodcastVoiceDefinition.locale,
                PodcastVoiceDefinition.gender,
                PodcastVoiceDefinition.name
            )
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_active_voices_by_locale_async(
        self, voice_type: str, locale: str
    ) -> List[PodcastVoiceDefinition]:
        """
        获取指定语言的所有启用的语音角色
        
        Args:
            voice_type: 语音类型
            locale: 语言/地区
        
        Returns:
            语音角色实体列表
        """
        query = select(PodcastVoiceDefinition)\
            .where(
                and_(
                    PodcastVoiceDefinition.voice_type == voice_type,
                    PodcastVoiceDefinition.locale == locale,
                    PodcastVoiceDefinition.is_active == True
                )
            )\
            .order_by(
                PodcastVoiceDefinition.gender,
                PodcastVoiceDefinition.name
            )
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def add_async(self, voice: PodcastVoiceDefinition) -> bool:
        """
        新增语音角色
        
        Args:
            voice: 语音角色实体
        
        Returns:
            操作结果
        """
        voice.id = generate_id()
        now = datetime.datetime.now()
        voice.create_date = now
        voice.last_modify_date = now
        
        self.db.add(voice)
        await self.db.flush()
        await self.db.commit()
        return True
    
    async def update_async(self, voice: PodcastVoiceDefinition) -> bool:
        """
        更新语音角色
        
        Args:
            voice: 语音角色实体
        
        Returns:
            操作结果
        """
        voice.last_modify_date = datetime.datetime.now()
        await self.db.merge(voice)
        await self.db.flush()
        await self.db.commit()
        return True
    
    async def delete_async(self, id: int) -> bool:
        """
        删除语音角色
        
        Args:
            id: 语音角色ID
        
        Returns:
            操作结果
        """
        query = delete(PodcastVoiceDefinition).where(PodcastVoiceDefinition.id == id)
        result = await self.db.execute(query)
        await self.db.commit()
        return result.rowcount > 0
    
    async def set_active_status_async(self, id: int, is_active: bool) -> bool:
        """
        启用/禁用语音角色
        
        Args:
            id: 语音角色ID
            is_active: 是否启用
        
        Returns:
            操作结果
        """
        query = update(PodcastVoiceDefinition)\
            .where(PodcastVoiceDefinition.id == id)\
            .values(
                is_active=is_active,
                last_modify_date=datetime.datetime.now()
            )
        result = await self.db.execute(query)
        await self.db.flush()
        await self.db.commit()
        return result.rowcount > 0