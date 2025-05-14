# app/modules/tools/podcast/repositories/podcast_voice_repository.py
import datetime
from typing import List, Optional

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tools.podcast.models import PodcastVoiceDefinition
from app.core.ai.speech.base import VoicePlatformType # Core enum
from app.core.utils.snowflake import generate_id

class PodcastVoiceRepository:
    """播客语音角色仓储"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id_async(self, voice_id: int) -> Optional[PodcastVoiceDefinition]:
        """获取语音角色"""
        stmt = select(PodcastVoiceDefinition).where(PodcastVoiceDefinition.id == voice_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_voice_symbol_async(self, voice_symbol: str) -> Optional[PodcastVoiceDefinition]:
        """根据语音符号获取语音角色"""
        stmt = select(PodcastVoiceDefinition).where(PodcastVoiceDefinition.voice_symbol == voice_symbol)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_active_voices_async(self, voice_type: VoicePlatformType) -> List[PodcastVoiceDefinition]:
        """获取所有启用的语音角色"""
        stmt = (
            select(PodcastVoiceDefinition)
            .where(PodcastVoiceDefinition.voice_type == voice_type)
            .where(PodcastVoiceDefinition.is_active == True)
            .order_by(PodcastVoiceDefinition.locale, PodcastVoiceDefinition.gender, PodcastVoiceDefinition.name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_active_voices_by_locale_async(self, voice_type: VoicePlatformType, locale: str) -> List[PodcastVoiceDefinition]:
        """获取指定语言的所有启用的语音角色"""
        stmt = (
            select(PodcastVoiceDefinition)
            .where(PodcastVoiceDefinition.voice_type == voice_type)
            .where(PodcastVoiceDefinition.is_active == True)
            .where(PodcastVoiceDefinition.locale == locale)
            .order_by(PodcastVoiceDefinition.gender, PodcastVoiceDefinition.name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add_async(self, voice_definition: PodcastVoiceDefinition) -> bool:
        """新增语音角色"""
        voice_definition.id = generate_id()
        now = datetime.datetime.now()
        voice_definition.create_date = now
        voice_definition.last_modify_date = now
        self.db.add(voice_definition)
        await self.db.flush()
        return True

    async def update_async(self, voice_definition: PodcastVoiceDefinition) -> bool:
        """更新语音角色"""
        voice_definition.last_modify_date = datetime.datetime.now()
        # self.db.add(voice_definition) # If detached
        await self.db.flush()
        return True

    async def delete_async(self, voice_id: int) -> bool:
        """删除语音角色"""
        stmt = delete(PodcastVoiceDefinition).where(PodcastVoiceDefinition.id == voice_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def set_active_status_async(self, voice_id: int, is_active: bool) -> bool:
        """启用/禁用语音角色"""
        stmt = (
            update(PodcastVoiceDefinition)
            .where(PodcastVoiceDefinition.id == voice_id)
            .values(
                is_active=is_active,
                last_modify_date=datetime.datetime.now()
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0