"""
播客业务服务 - 播客模块核心业务逻辑
"""
import logging
import datetime
from typing import List, Dict, Any, Optional, Tuple, Union

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dtos import PagedResultDto, DocumentAppType, BaseIdResponseDto
from app.core.utils.snowflake import generate_id
from app.core.exceptions import BusinessException, NotFoundException
from app.core.job.services import JobPersistenceService

from app.modules.base.knowledge.services.document_service import DocumentService

from app.modules.tools.podcast.constants import (
    PodcastTaskStatus, PodcastRoleType, AudioStatusType, 
    PodcastTaskContentType, VoiceGenderType
)
from app.modules.tools.podcast.models import (
    PodcastTask, PodcastTaskContent, PodcastTaskScript
)
from app.modules.tools.podcast.repositories import (
    PodcastTaskRepository, PodcastTaskContentRepository, 
    PodcastTaskScriptRepository, PodcastScriptHistoryRepository
)
from app.modules.tools.podcast.dtos import (
    CreatePodcastRequestDto, PodcastDetailDto, PodcastListRequestDto, 
    PodcastListItemDto, PodcastContentItemDto, PodcastScriptItemDto,
    TtsVoiceDefinition, PodcastScriptRawItemDto
)
from app.modules.tools.podcast.services.ai_script_service import AIScriptService
from app.modules.tools.podcast.services.ai_speech_service import AISpeechService


logger = logging.getLogger(__name__)


class PodcastService:
    """播客服务实现"""
    
    def __init__(
        self,
        db: AsyncSession,
        podcast_repository: PodcastTaskRepository,
        podcast_content_repository: PodcastTaskContentRepository,
        podcast_script_repository: PodcastTaskScriptRepository,
        script_history_repository: PodcastScriptHistoryRepository,
        document_service: DocumentService,
        ai_script_service: AIScriptService,
        ai_speech_service: AISpeechService,
        job_persistence_service: JobPersistenceService
    ):
        """
        初始化播客服务
        
        Args:
            db: 数据库会话
            podcast_repository: 播客仓储
            podcast_content_repository: 播客内容仓储
            podcast_script_repository: 播客脚本仓储
            script_history_repository: 播客脚本历史仓储
            document_service: 文档服务
            ai_script_service: AI脚本服务
            ai_speech_service: AI语音服务
            job_persistence_service: 任务持久化服务
        """
        self.db = db
        self.podcast_repository = podcast_repository
        self.podcast_content_repository = podcast_content_repository
        self.podcast_script_repository = podcast_script_repository
        self.script_history_repository = script_history_repository
        self.document_service = document_service
        self.ai_script_service = ai_script_service
        self.ai_speech_service = ai_speech_service
        self.job_persistence_service = job_persistence_service
    
    async def create_podcast_async(
        self, user_id: int, request: CreatePodcastRequestDto
    ) -> int:
        """
        创建播客
        
        Args:
            user_id: 用户ID
            request: 创建请求
        
        Returns:
            播客ID
        """
        try:
            # 创建播客记录
            podcast = PodcastTask(
                user_id=user_id,
                title=request.title,
                description=request.description,
                scene=request.scene,
                atmosphere=request.atmosphere,
                guest_count=request.guest_count,
                status=PodcastTaskStatus.INIT,
                generate_count=0,
                generate_id=0,
                progress_step=0
            )
            
            # 保存播客
            await self.podcast_repository.add_async(podcast)
            
            return podcast.id
        except Exception as e:
            if not isinstance(e, (BusinessException, NotFoundException)):
                logger.exception(f"创建播客失败: {e}")
                raise BusinessException(f"创建播客失败: {str(e)}")
            raise
    
    async def add_podcast_content_async(
        self, user_id: int, podcast_id: int, content_type: PodcastTaskContentType,
        source_document_id: int, source_content: str
    ) -> int:
        """
        给播客添加内容
        
        Args:
            user_id: 用户ID
            podcast_id: 播客ID
            content_type: 内容类型
            source_document_id: 文档ID
            source_content: 文本内容
        
        Returns:
            添加的内容项ID
        """
        try:
            # 创建播客内容项
            content_item = PodcastTaskContent(
                user_id=user_id,
                podcast_id=podcast_id,
                content_type=content_type,
                source_document_id=source_document_id,
                source_content=source_content
            )
            
            # 保存内容项
            return await self.podcast_content_repository.add_async(content_item)
        except Exception as e:
            if not isinstance(e, (BusinessException, NotFoundException)):
                logger.exception(f"创建播客内容失败: {e}")
                raise BusinessException(f"创建播客内容失败: {str(e)}")
            raise
    
    async def delete_podcast_content_async(self, user_id: int, content_id: int) -> bool:
        """
        删除播客的内容
        
        Args:
            user_id: 用户ID
            content_id: 内容ID
        
        Returns:
            操作结果
        """
        try:
            # 获取内容项
            content = await self.podcast_content_repository.get_by_id_async(content_id)
            if not content:
                raise NotFoundException("播客内容不存在或您没有访问权限")
            
            # 获取播客，验证所有权
            podcast = await self.podcast_repository.get_by_id_async(content.podcast_id)
            if not podcast or podcast.user_id != user_id:
                raise NotFoundException("播客不存在或您没有访问权限")
            
            # 删除内容项
            return await self.podcast_content_repository.delete_async(content_id)
        except Exception as e:
            if not isinstance(e, NotFoundException):
                logger.exception(f"删除播客内容失败，ID: {content_id}")
                raise BusinessException(f"删除播客内容失败: {str(e)}")
            raise
    
    async def get_podcast_content_detail_async(
        self, user_id: int, content_id: int
    ) -> PodcastContentItemDto:
        """
        获取播客内容的详情
        
        Args:
            user_id: 用户ID
            content_id: 内容ID
        
        Returns:
            内容详情
        """
        try:
            # 获取内容项
            content = await self.podcast_content_repository.get_by_id_async(content_id)
            if not content:
                raise NotFoundException("播客内容不存在或您没有访问权限")
            
            # 获取播客，验证所有权
            podcast = await self.podcast_repository.get_by_id_async(content.podcast_id)
            if not podcast or podcast.user_id != user_id:
                raise NotFoundException("播客不存在或您没有访问权限")
            
            # 创建响应对象
            result = PodcastContentItemDto(
                id=content.id,
                contentType=content.content_type,
                createDate=content.create_date,
                sourceContent=content.source_content,
                sourceDocumentId=content.source_document_id,
                sourceDocumentStatus=2,  # 默认为已完成状态
                sourceDocumentOriginalName=None,
                sourceDocumentProcessMessage=None,
                sourceDocumentSourceUrl=None,
                sourceDocumentTitle=None
            )
            
            # 处理有文档的id列表
            if content.source_document_id > 0:
                try:
                    document = await self.document_service.get_document_async(
                        user_id, content.source_document_id
                    )
                    if document:
                        result.sourceContent = document.content
                        result.sourceDocumentTitle = document.title
                        result.sourceDocumentSourceUrl = document.source_url
                        result.sourceDocumentProcessMessage = document.process_message
                        result.sourceDocumentOriginalName = document.original_name
                except Exception as doc_e:
                    logger.warning(f"获取文档失败: {doc_e}")
            
            return result
        except Exception as e:
            if not isinstance(e, NotFoundException):
                logger.exception(f"获取播客内容的详情失败，ID: {content_id}")
                raise BusinessException(f"获取播客内容的详情失败: {str(e)}")
            raise
    
    async def get_podcast_async(self, user_id: int, podcast_id: int) -> PodcastDetailDto:
        """
        获取播客详情
        
        Args:
            user_id: 用户ID
            podcast_id: 播客ID
        
        Returns:
            播客详情
        """
        try:
            # 获取播客
            podcast = await self.podcast_repository.get_by_id_async(podcast_id)
            if not podcast or podcast.user_id != user_id:
                raise NotFoundException("播客不存在或您没有访问权限")
            
            # 获取脚本项
            script_items = await self.podcast_script_repository.get_by_podcast_id_async(podcast.id)
            
            # 获取语音角色定义
            voices = await self.ai_speech_service.get_supported_voices_async()
            
            # 构建响应
            result = PodcastDetailDto(
                id=podcast.id,
                title=podcast.title,
                description=podcast.description,
                scene=podcast.scene,
                atmosphere=podcast.atmosphere,
                guestCount=podcast.guest_count,
                progressStep=podcast.progress_step,
                generateCount=podcast.generate_count,
                status=podcast.status,
                statusDescription=self._get_status_description(podcast.status),
                errorMessage=podcast.error_message,
                createDate=podcast.create_date,
                scriptItems=[self._map_to_script_item_dto(item, voices) for item in script_items],
                contentItems=[]
            )
            
            # 获取内容项
            content_items = await self.podcast_content_repository.get_by_podcast_id_async(podcast.id)
            content_dtos = []
            
            for content_item in content_items:
                content_dto = PodcastContentItemDto(
                    id=content_item.id,
                    contentType=content_item.content_type,
                    createDate=content_item.create_date,
                    sourceContent=content_item.source_content,
                    sourceDocumentId=content_item.source_document_id,
                    sourceDocumentStatus=2,  # 默认为已完成状态
                    sourceDocumentOriginalName=None,
                    sourceDocumentProcessMessage=None,
                    sourceDocumentSourceUrl=None,
                    sourceDocumentTitle=None
                )
                content_dtos.append(content_dto)
            
            # 处理文档信息
            document_ids = [c.source_document_id for c in content_items if c.source_document_id > 0]
            if document_ids:
                try:
                    documents = await self.document_service.get_documents_async(user_id, document_ids)
                    
                    # 更新文档信息
                    for doc in documents:
                        for content in content_dtos:
                            if content.sourceDocumentId == doc.id:
                                content.sourceContent = doc.content
                                content.sourceDocumentTitle = doc.title
                                content.sourceDocumentSourceUrl = doc.source_url
                                content.sourceDocumentProcessMessage = doc.process_message
                                content.sourceDocumentOriginalName = doc.original_name
                except Exception as doc_e:
                    logger.warning(f"获取文档失败: {doc_e}")
            
            result.contentItems = content_dtos
            
            return result
        except Exception as e:
            if not isinstance(e, NotFoundException):
                logger.exception(f"获取播客详情失败，ID: {podcast_id}")
                raise BusinessException(f"获取播客详情失败: {str(e)}")
            raise
    
    async def get_user_podcasts_async(
        self, user_id: int, request: PodcastListRequestDto
    ) -> PagedResultDto[PodcastListItemDto]:
        """
        获取用户的播客列表
        
        Args:
            user_id: 用户ID
            request: 请求参数
        
        Returns:
            播客列表
        """
        try:
            # 获取播客数据
            podcasts, total_count = await self.podcast_repository.get_paginated_async(
                user_id, request.page_index, request.page_size
            )
            
            # 获取内容项和脚本项数量
            podcast_ids = [p.id for p in podcasts]
            script_count_dict = {}
            content_count_dict = {}
            
            if podcast_ids:
                # 获取脚本数量
                script_items = await self.podcast_script_repository.get_by_podcast_ids_async(podcast_ids)
                # 获取内容数量
                content_items = await self.podcast_content_repository.get_by_podcast_ids_async(podcast_ids)
                
                # 统计每个播客的数量
                for podcast_id in podcast_ids:
                    script_count_dict[podcast_id] = len([s for s in script_items if s.podcast_id == podcast_id])
                    content_count_dict[podcast_id] = len([c for c in content_items if c.podcast_id == podcast_id])
            
            # 转换为DTO
            items = []
            for podcast in podcasts:
                podcast_dto = PodcastListItemDto(
                    id=podcast.id,
                    title=podcast.title,
                    description=podcast.description,
                    scene=podcast.scene,
                    atmosphere=podcast.atmosphere,
                    guestCount=podcast.guest_count,
                    progressStep=podcast.progress_step,
                    generateCount=podcast.generate_count,
                    status=podcast.status,
                    statusDescription=self._get_status_description(podcast.status),
                    contentItemCount=content_count_dict.get(podcast.id, 0),
                    scriptItemCount=script_count_dict.get(podcast.id, 0),
                    createDate=podcast.create_date
                )
                items.append(podcast_dto)
            
            # 构建分页结果
            result = PagedResultDto[PodcastListItemDto](
                items=items,
                totalCount=total_count,
                pageIndex=request.page_index,
                pageSize=request.page_size,
                totalPages=(total_count + request.page_size - 1) // request.page_size
            )
            
            return result
        except Exception as e:
            logger.exception(f"获取用户播客列表失败: {e}")
            raise BusinessException(f"获取播客列表失败: {str(e)}")
    
    async def delete_podcast_async(self, user_id: int, podcast_id: int) -> bool:
        """
        删除播客
        
        Args:
            user_id: 用户ID
            podcast_id: 播客ID
        
        Returns:
            操作结果
        """
        try:
            # 获取播客
            podcast = await self.podcast_repository.get_by_id_async(podcast_id)
            if not podcast or podcast.user_id != user_id:
                raise NotFoundException("播客不存在或您没有访问权限")
            
            # 删除脚本项
            await self.podcast_script_repository.delete_by_podcast_id_async(podcast_id)
            
            # 删除内容项
            await self.podcast_content_repository.delete_by_podcast_id_async(podcast_id)
            
            # 删除播客
            return await self.podcast_repository.delete_async(podcast_id)
        except Exception as e:
            if not isinstance(e, NotFoundException):
                logger.exception(f"删除播客失败，ID: {podcast_id}")
                raise BusinessException(f"删除播客失败: {str(e)}")
            raise
    
    async def start_podcast_generate_async(self, user_id: int, podcast_id: int) -> bool:
        """
        开始播客脚本和音频的生成
        
        Args:
            user_id: 用户ID
            podcast_id: 播客ID
        
        Returns:
            操作结果
        """
        try:
            # 获取播客
            podcast = await self.podcast_repository.get_by_id_async(podcast_id)
            if not podcast or podcast.user_id != user_id:
                raise BusinessException("播客不存在或您没有访问权限")
            
            # 检查内容是否存在
            contents = await self.podcast_content_repository.get_by_podcast_id_async(podcast_id)
            if not contents:
                raise BusinessException("播客任务还未上传内容")
            
            # 检查文档解析是否完成
            doc_ids = [c.source_document_id for c in contents if c.source_document_id > 0]
            if doc_ids:
                doc_statuses = await self.document_service.get_document_status_async(user_id, doc_ids)
                if any(status.status != 2 for status in doc_statuses):
                    raise BusinessException("文档内容未解析完成")
            
            # 检查播客状态
            valid_statuses = [PodcastTaskStatus.INIT, PodcastTaskStatus.COMPLETED, PodcastTaskStatus.FAILED]
            if podcast.status not in valid_statuses:
                raise BusinessException("播客正在处理中，请稍后再试")
            
            # 检查生成次数限制
            if podcast.generate_count >= 5:
                raise BusinessException("该任务生成已超过5次，不可再生成")
            
            # 写入历史记录
            history_id = await self.script_history_repository.add_async(podcast_id)
            
            # 开始播客生成
            result = await self.podcast_repository.start_podcast_generate_async(podcast_id, history_id)
            
            # 创建持久化任务记录
            await self.job_persistence_service.create_job(
                task_type="podcast.generate",
                params_id=podcast_id,
                params_data=None
            )
            
            return result
        except Exception as e:
            if isinstance(e, BusinessException):
                raise
            logger.exception(f"播客生成失败，ID: {podcast_id}")
            raise BusinessException(f"播客生成失败: {str(e)}")
    
    async def process_podcast_generate(self, podcast_id: int) -> bool:
        """
        处理播客脚本和音频的生成
        
        Args:
            podcast_id: 播客ID
        
        Returns:
            操作结果
        """
        # 获取播客
        podcast = await self.podcast_repository.get_by_id_async(podcast_id)
        
        # 检查播客状态
        if podcast.status != PodcastTaskStatus.PENDING:
            raise BusinessException("播客不是待处理状态")
        
        try:
            # 锁定处理状态
            if not await self.podcast_repository.lock_processing_status_async(podcast_id):
                raise BusinessException("播客正在处理中，请稍后再试")
            
            # 获取播客详情
            podcast_detail = await self.get_podcast_async(podcast.user_id, podcast_id)
            
            # 获取支持的语音类型
            voices = await self.ai_speech_service.get_supported_voices_async()
            
            # 更新进度
            await self.podcast_repository.update_progress_step_async(podcast_id, 5)
            
            # 1. 生成播客脚本
            await self._generate_script_async(podcast.generate_id, podcast_detail, voices)
            
            # 2. 根据脚本生成音频
            await self._generate_audio_async(podcast, voices)
            
            # 更新状态为已完成
            await self.podcast_repository.update_status_async(podcast_id, PodcastTaskStatus.COMPLETED)
            await self.script_history_repository.update_status_async(podcast.generate_id, PodcastTaskStatus.COMPLETED)
            
            # 更新进度
            await self.podcast_repository.update_progress_step_async(podcast_id, 100)
            
            return True
        except Exception as e:
            # 更新状态为失败
            error_msg = str(e)
            await self.podcast_repository.update_status_async(podcast_id, PodcastTaskStatus.FAILED, error_msg)
            await self.script_history_repository.update_status_async(podcast.generate_id, PodcastTaskStatus.FAILED, error_msg)
            
            # 更新进度
            await self.podcast_repository.update_progress_step_async(podcast_id, 100)
            
            logger.exception(f"生成播客内容失败，ID: {podcast_id}")
            return False
    
    async def _generate_script_async(
        self, history_id: int, podcast: PodcastDetailDto, voices: List[TtsVoiceDefinition]
    ) -> bool:
        """
        生成播客脚本
        
        Args:
            history_id: 历史ID
            podcast: 播客对象
            voices: 音频角色
        
        Returns:
            操作结果
        """
        try:
            # AI生成播客脚本
            script_items = await self.ai_script_service.generate_script_async(podcast, voices)
            
            # 更新进度
            await self.podcast_repository.update_progress_step_async(podcast.id, 20)
            
            # 迁移旧的脚本项
            await self.script_history_repository.move_script_to_history_async(podcast.id)
            
            # 创建新的脚本项
            new_script_items = []
            for i, item in enumerate(script_items):
                # 确定角色类型
                role_type = PodcastRoleType.HOST if item.role_type.lower() == "host" else PodcastRoleType.GUEST
                
                # 验证语音角色的有效性
                voice_definition = next((v for v in voices if v.voice_symbol == item.voice_symbol), None)
                if not voice_definition:
                    raise BusinessException(f"语音角色不存在: {item.voice_symbol}")
                
                # 创建脚本项
                script_item = PodcastTaskScript(
                    podcast_id=podcast.id,
                    history_id=history_id,
                    sequence_number=i + 1,
                    role_type=role_type,
                    role_name=item.role_name,
                    voice_id=voice_definition.id,
                    content=item.no_ssml_content or "",
                    ssml_content=item.content or "",
                    audio_status=AudioStatusType.PENDING,
                    audio_duration=0
                )
                new_script_items.append(script_item)
            
            # 保存脚本项
            await self.podcast_script_repository.add_range_async(new_script_items)
            
            # 更新进度
            await self.podcast_repository.update_progress_step_async(podcast.id, 30)
            
            return True
        except Exception as e:
            logger.exception(f"生成播客脚本失败，ID: {podcast.id}")
            raise BusinessException(f"生成播客脚本失败: {str(e)}")
    
    async def _generate_audio_async(
        self, podcast: PodcastTask, voices: List[TtsVoiceDefinition]
    ) -> bool:
        """
        生成播客语音
        
        Args:
            podcast: 播客对象
            voices: 音频角色
        
        Returns:
            操作结果
        """
        # 获取脚本项
        script_items = await self.podcast_script_repository.get_by_podcast_id_async(podcast.id)
        if not script_items:
            raise BusinessException("播客脚本为空，无法生成语音")
        
        # 逐个生成语音
        i = 0
        total_scripts = len(script_items)
        for item in script_items:
            try:
                # 更新状态为处理中
                await self.podcast_script_repository.update_audio_status_async(
                    item.id, AudioStatusType.PROCESSING
                )
                
                # 获取语音定义
                voice_def = next((v for v in voices if v.id == item.voice_id), None)
                if not voice_def:
                    raise BusinessException(f"语音角色不存在，ID: {item.voice_id}")
                
                # 生成语音
                success, audio_url, audio_duration = await self.ai_speech_service.text_to_speech_async(
                    podcast.id,
                    item.ssml_content or "",  # 使用包含SSML标记的内容
                    item.content or "",       # 不带SSML标记的内容
                    voice_def.voice_symbol or ""
                )
                
                if not success:
                    raise BusinessException("语音生成失败")
                
                # 更新状态为已完成
                await self.podcast_script_repository.update_audio_status_async(
                    item.id,
                    AudioStatusType.COMPLETED,
                    audio_url,
                    float(audio_duration)
                )
                
                # 更新进度
                i += 1
                progress_step = 30 + (i * 70 // total_scripts)
                await self.podcast_repository.update_progress_step_async(podcast.id, progress_step)
            
            except Exception as e:
                # 更新状态为失败
                await self.podcast_script_repository.update_audio_status_async(
                    item.id, AudioStatusType.FAILED
                )
                logger.exception(f"生成语音失败，脚本项ID: {item.id}")
                raise BusinessException(f"生成语音失败，脚本项ID: {item.id}: {str(e)}")
        
        return True
    
    async def get_supported_voices_async(self) -> List[TtsVoiceDefinition]:
        """
        获取所有支持的语音角色
        
        Returns:
            语音角色列表
        """
        return await self.ai_speech_service.get_supported_voices_async()
    
    async def get_voices_by_locale_async(self, locale: str) -> List[TtsVoiceDefinition]:
        """
        获取指定语言的语音角色
        
        Args:
            locale: 语言/地区
        
        Returns:
            语音角色列表
        """
        return await self.ai_speech_service.get_voices_by_locale_async(locale)
    
    def _get_status_description(self, status: PodcastTaskStatus) -> str:
        """
        获取状态描述
        
        Args:
            status: 状态代码
        
        Returns:
            状态描述
        """
        status_descriptions = {
            PodcastTaskStatus.INIT: "初始化",
            PodcastTaskStatus.PENDING: "待处理",
            PodcastTaskStatus.PROCESSING: "开始处理",
            PodcastTaskStatus.COMPLETED: "已完成",
            PodcastTaskStatus.FAILED: "处理失败"
        }
        return status_descriptions.get(status, "未知状态")
    
    def _map_to_script_item_dto(
        self, script_item: PodcastTaskScript, voices: List[TtsVoiceDefinition]
    ) -> PodcastScriptItemDto:
        """
        将实体对象转换为DTO
        
        Args:
            script_item: 脚本项实体
            voices: 语音定义列表
        
        Returns:
            脚本项DTO
        """
        # 查找匹配的语音定义
        voice = next((v for v in voices if v.id == script_item.voice_id), None)
        
        # 语音状态描述
        audio_status_descriptions = {
            AudioStatusType.PENDING: "待生成",
            AudioStatusType.PROCESSING: "生成中",
            AudioStatusType.COMPLETED: "已生成",
            AudioStatusType.FAILED: "生成失败"
        }
        
        # 角色类型描述
        role_type_descriptions = {
            PodcastRoleType.HOST: "主持人",
            PodcastRoleType.GUEST: "嘉宾"
        }
        
        return PodcastScriptItemDto(
            id=script_item.id,
            sequenceNumber=script_item.sequence_number,
            roleType=script_item.role_type,
            roleTypeDescription=role_type_descriptions.get(script_item.role_type, "未知角色"),
            roleName=script_item.role_name,
            voiceSymbol=voice.voice_symbol if voice else None,
            voiceName=voice.name if voice else None,
            voiceDescription=voice.description if voice else None,
            content=script_item.content,
            audioDuration=script_item.audio_duration,
            audioUrl=script_item.audio_path,
            audioStatus=script_item.audio_status,
            audioStatusDescription=audio_status_descriptions.get(script_item.audio_status, "未知状态")
        )