# app/modules/tools/podcast/services/podcast_service.py
import logging
import datetime
from typing import List, Optional, Tuple, Dict, Any

from app.core.config.settings import Settings
from app.core.exceptions import BusinessException, NotFoundException
from app.core.dtos import PagedResultDto, DocumentAppType
from app.modules.base.knowledge.services.document_service import DocumentService
from app.modules.base.knowledge.dtos import  DocumentStatus # From knowledge DTOs

from app.modules.tools.podcast.models import (
    PodcastTask, PodcastTaskStatus, PodcastTaskContent, PodcastTaskContentType,
    PodcastTaskScript, AudioStatusType, PodcastRoleType
)
from app.modules.tools.podcast.dtos import (
    CreatePodcastRequestDto, PodcastDetailDto, PodcastContentItemDto, PodcastScriptItemDto,
    PodcastListItemDto, PodcastListRequestDto, TtsVoiceDefinitionDto, PodcastScriptRawItemDto
)
from app.modules.tools.podcast.repositories import (
    PodcastTaskRepository, PodcastTaskScriptRepository,
    PodcastTaskContentRepository, PodcastScriptHistoryRepository
)
from .ai_script_service import AIScriptService # Relative import
from .ai_speech_service import AISpeechService # Relative import

logger = logging.getLogger(__name__)

class PodcastService:
    """播客服务实现"""

    def __init__(
        self,
        settings: Settings,
        podcast_task_repo: PodcastTaskRepository,
        podcast_script_repo: PodcastTaskScriptRepository,
        podcast_content_repo: PodcastTaskContentRepository,
        podcast_history_repo: PodcastScriptHistoryRepository,
        ai_script_service: AIScriptService,
        ai_speech_service: AISpeechService,
        document_service: DocumentService # From base.knowledge
    ):
        self.settings = settings
        self.podcast_task_repo = podcast_task_repo
        self.podcast_script_repo = podcast_script_repo
        self.podcast_content_repo = podcast_content_repo
        self.podcast_history_repo = podcast_history_repo
        self.ai_script_service = ai_script_service
        self.ai_speech_service = ai_speech_service
        self.document_service = document_service

    def _get_status_description(self, status: PodcastTaskStatus) -> str:
        return {
            PodcastTaskStatus.INIT: "初始化",
            PodcastTaskStatus.PENDING: "待处理",
            PodcastTaskStatus.PROCESSING: "处理中", # C# was "开始处理"
            PodcastTaskStatus.COMPLETED: "已完成",
            PodcastTaskStatus.FAILED: "处理失败",
        }.get(status, "未知状态")

    def _map_script_to_dto(self, script: PodcastTaskScript, voice_definitions: List[TtsVoiceDefinitionDto]) -> PodcastScriptItemDto:
        voice_def = next((v for v in voice_definitions if v.id == script.voice_id), None)
        role_type_desc = "主持人" if script.role_type == PodcastRoleType.HOST else "嘉宾"
        audio_status_desc = {
            AudioStatusType.PENDING: "待生成",
            AudioStatusType.PROCESSING: "生成中",
            AudioStatusType.COMPLETED: "已生成", # C# was "已生成"
            AudioStatusType.FAILED: "生成失败",
        }.get(script.audio_status, "未知状态")

        return PodcastScriptItemDto(
            id=script.id,
            sequence_number=script.sequence_number,
            role_type=script.role_type,
            role_type_description=role_type_desc,
            role_name=script.role_name,
            voice_symbol=voice_def.voice_symbol if voice_def else None,
            voice_name=voice_def.name if voice_def else None,
            voice_description=voice_def.description if voice_def else None,
            content=script.content, # NoSSML content
            audio_duration=script.audio_duration,
            audio_url=script.audio_path, # Assuming audio_path is the URL
            audio_status=script.audio_status,
            audio_status_description=audio_status_desc
        )

    async def create_podcast_async(self, user_id: int, request: CreatePodcastRequestDto) -> int:
        """创建播客，返回播客ID"""
        try:
            podcast = PodcastTask(
                user_id=user_id,
                title=request.title,
                description=request.description,
                scene=request.scene,
                atmosphere=request.atmosphere,
                guest_count=request.guest_count,
                # status, generate_id, generate_count, progress_step will use model defaults or be set by add_async
            )
            await self.podcast_task_repo.add_async(podcast)
            return podcast.id
        except Exception as e:
            logger.error(f"创建播客失败: {e}", exc_info=True)
            if isinstance(e, (BusinessException, NotFoundException)):
                 raise
            raise BusinessException(f"创建播客失败: {str(e)}")

    async def add_podcast_content_async(
        self, user_id: int, podcast_id: int, content_type: PodcastTaskContentType,
        source_document_id: Optional[int], source_content: Optional[str]
    ) -> int:
        """给播客添加内容，返回内容项ID"""
        # Validate podcast ownership and existence (optional here, or trust caller/controller)
        podcast = await self.podcast_task_repo.get_by_id_async(podcast_id)
        if not podcast or podcast.user_id != user_id:
            raise NotFoundException("播客不存在或无权访问")
        if podcast.status not in [PodcastTaskStatus.INIT, PodcastTaskStatus.COMPLETED, PodcastTaskStatus.FAILED]:
             raise BusinessException(f"播客当前状态 ({self._get_status_description(podcast.status)}) 不允许添加内容")

        try:
            content_item = PodcastTaskContent(
                user_id=user_id,
                podcast_id=podcast_id,
                content_type=content_type,
                source_document_id=source_document_id if source_document_id and source_document_id > 0 else None,
                source_content=source_content
            )
            content_id = await self.podcast_content_repo.add_async(content_item)
            return content_id
        except Exception as e:
            logger.error(f"创建播客内容失败: {e}", exc_info=True)
            if isinstance(e, (BusinessException, NotFoundException)):
                 raise
            raise BusinessException(f"创建播客内容失败: {str(e)}")

    async def delete_podcast_content_async(self, user_id: int, content_id: int) -> bool:
        """删除播客的内容项"""
        try:
            content = await self.podcast_content_repo.get_by_id_async(content_id)
            if not content:
                raise NotFoundException("播客内容不存在")
            
            podcast = await self.podcast_task_repo.get_by_id_async(content.podcast_id)
            if not podcast or podcast.user_id != user_id:
                raise NotFoundException("播客不存在或您没有访问权限")
             
            if podcast.status not in [PodcastTaskStatus.INIT, PodcastTaskStatus.COMPLETED, PodcastTaskStatus.FAILED]:
                raise BusinessException(f"播客当前状态 ({self._get_status_description(podcast.status)}) 不允许删除内容")

            return await self.podcast_content_repo.delete_async(content_id)
        except Exception as e:
            logger.error(f"删除播客内容失败, ID: {content_id}, Error: {e}", exc_info=True)
            if isinstance(e, (BusinessException, NotFoundException)):
                 raise
            raise BusinessException(f"删除播客内容失败: {str(e)}")

    async def get_podcast_content_detail_async(self, user_id: int, content_id: int) -> PodcastContentItemDto:
         """获取播客内容的详情"""
         try:
             content_item_model = await self.podcast_content_repo.get_by_id_async(content_id)
             if not content_item_model:
                 raise NotFoundException("播客内容不存在")

             podcast = await self.podcast_task_repo.get_by_id_async(content_item_model.podcast_id)
             if not podcast or podcast.user_id != user_id:
                 raise NotFoundException("播客不存在或您没有访问权限")

             # Base DTO from model
             content_dto = PodcastContentItemDto.model_validate(content_item_model)
             
             # If it's a document-based content, fetch document details
             if content_item_model.source_document_id and content_item_model.source_document_id > 0:
                 try:
                     # document_service.get_document_async returns a more detailed DTO
                     doc_detail_dto = await self.document_service.get_document_async(user_id, content_item_model.source_document_id)
                     if doc_detail_dto:
                         content_dto.source_content = doc_detail_dto.content # Full content from document
                         content_dto.source_document_title = doc_detail_dto.title
                         content_dto.source_document_original_name = doc_detail_dto.original_name
                         content_dto.source_document_source_url = doc_detail_dto.source_url
                         content_dto.source_document_status = doc_detail_dto.status
                         content_dto.source_document_process_message = doc_detail_dto.process_message
                     else: # Document not found by document_service, clear related fields
                         content_dto.source_document_id = None # Mark as if document doesn't exist or error
                 except NotFoundException:
                      logger.warning(f"Document {content_item_model.source_document_id} for podcast content {content_id} not found via DocumentService.")
                      content_dto.source_document_id = None # Or handle as error
                 except Exception as doc_e:
                     logger.error(f"Error fetching document {content_item_model.source_document_id} details: {doc_e}")
                     # Decide if this is critical or just partial data
             elif content_item_model.content_type == PodcastTaskContentType.TEXT:
                 # Source content is already in content_item_model.source_content
                 pass # content_dto.source_content is already set by model_validate
             elif content_item_model.content_type == PodcastTaskContentType.URL:
                 # content_item_model.source_content would be the URL itself.
                 # If actual web content is needed, it should have been fetched and stored in a document,
                 # then source_document_id would be populated.
                 # If source_content here *is* the scraped text from URL, it's fine.
                 # C# implies document service handles URL import into a document.
                 pass


             return content_dto
         except Exception as e:
             logger.error(f"获取播客内容详情失败, ID: {content_id}, Error: {e}", exc_info=True)
             if isinstance(e, (BusinessException, NotFoundException)):
                 raise
             raise BusinessException(f"获取播客内容详情失败: {str(e)}")


    async def _get_podcast_full_async(self, podcast_task_model: PodcastTask) -> PodcastDetailDto:
        """Helper to get full PodcastDetailDto including resolved contents and scripts."""
        # Get all voice definitions once
        all_voice_defs = await self.ai_speech_service.get_supported_voices_async()

        # Get script items
        script_models = await self.podcast_script_repo.get_by_podcast_id_async(podcast_task_model.id)
        script_dtos = [self._map_script_to_dto(s, all_voice_defs) for s in script_models]

        # Get content items
        content_models = await self.podcast_content_repo.get_by_podcast_id_async(podcast_task_model.id)
        content_dtos: List[PodcastContentItemDto] = []
        
        doc_ids_to_fetch = []
        temp_content_map: Dict[int, PodcastContentItemDto] = {} # doc_id -> content_dto

        for cm in content_models:
            cdto = PodcastContentItemDto.model_validate(cm)
            # For TEXT or URL (if content is pre-fetched), source_content is already from model
            # If URL content needs fetching or File content, it should be via document_service
            if cm.source_document_id and cm.source_document_id > 0:
                doc_ids_to_fetch.append(cm.source_document_id)
                temp_content_map[cm.source_document_id] = cdto # Store temporarily
            content_dtos.append(cdto)

        if doc_ids_to_fetch:
            try:
                # Assuming get_documents_async returns a list of DTOs (e.g., DocumentDetailResponseDto)
                document_details_list = await self.document_service.get_documents_async(
                    podcast_task_model.user_id, list(set(doc_ids_to_fetch))
                )
                for doc_detail in document_details_list:
                    if doc_detail.id in temp_content_map:
                        target_cdto = temp_content_map[doc_detail.id]
                        target_cdto.source_content = doc_detail.content # Full content
                        target_cdto.source_document_title = doc_detail.title
                        target_cdto.source_document_original_name = doc_detail.original_name
                        target_cdto.source_document_source_url = doc_detail.source_url
                        target_cdto.source_document_status = doc_detail.status
                        target_cdto.source_document_process_message = doc_detail.process_message
            except Exception as e:
                logger.error(f"Error fetching document details for podcast {podcast_task_model.id}: {e}", exc_info=True)
                # Content DTOs might have incomplete document info
        
        return PodcastDetailDto(
            id=podcast_task_model.id,
            title=podcast_task_model.title,
            description=podcast_task_model.description,
            scene=podcast_task_model.scene,
            atmosphere=podcast_task_model.atmosphere,
            guest_count=podcast_task_model.guest_count,
            generate_count=podcast_task_model.generate_count,
            progress_step=podcast_task_model.progress_step,
            status=podcast_task_model.status,
            status_description=self._get_status_description(podcast_task_model.status),
            error_message=podcast_task_model.error_message,
            create_date=podcast_task_model.create_date,
            script_items=script_dtos,
            content_items=content_dtos
        )

    async def get_podcast_async(self, user_id: int, podcast_id: int) -> PodcastDetailDto:
        """获取播客详情"""
        try:
            podcast_model = await self.podcast_task_repo.get_by_id_async(podcast_id)
            if not podcast_model or podcast_model.user_id != user_id:
                raise NotFoundException("播客不存在或您没有访问权限")
            return await self._get_podcast_full_async(podcast_model)
        except Exception as e:
            logger.error(f"获取播客详情失败, ID: {podcast_id}, Error: {e}", exc_info=True)
            if isinstance(e, (BusinessException, NotFoundException)):
                 raise
            raise BusinessException(f"获取播客详情失败: {str(e)}")

    async def get_user_podcasts_async(self, user_id: int, request: PodcastListRequestDto) -> PagedResultDto[PodcastListItemDto]:
        """获取用户的播客列表"""
        try:
            podcast_models, total_count = await self.podcast_task_repo.get_paginated_async(
                user_id, request.page_index, request.page_size
            )
            
            items_dtos: List[PodcastListItemDto] = []
            if podcast_models:
                podcast_ids = [p.id for p in podcast_models]
                
                # Get script counts
                script_items_for_podcasts = await self.podcast_script_repo.get_by_podcast_ids_async(podcast_ids)
                script_counts: Dict[int, int] = {pid: 0 for pid in podcast_ids}
                for script in script_items_for_podcasts:
                    script_counts[script.podcast_id] = script_counts.get(script.podcast_id, 0) + 1
                    
                # Get content counts
                content_items_for_podcasts = await self.podcast_content_repo.get_by_podcast_ids_async(podcast_ids)
                content_counts: Dict[int, int] = {pid: 0 for pid in podcast_ids}
                for content in content_items_for_podcasts:
                    content_counts[content.podcast_id] = content_counts.get(content.podcast_id, 0) + 1

                for p_model in podcast_models:
                    items_dtos.append(
                        PodcastListItemDto(
                            id=p_model.id,
                            title=p_model.title,
                            description=p_model.description,
                            scene=p_model.scene,
                            atmosphere=p_model.atmosphere,
                            guest_count=p_model.guest_count,
                            progress_step=p_model.progress_step,
                            generate_count=p_model.generate_count,
                            status=p_model.status,
                            status_description=self._get_status_description(p_model.status),
                            content_item_count=content_counts.get(p_model.id, 0),
                            script_item_count=script_counts.get(p_model.id, 0),
                            create_date=p_model.create_date
                        )
                    )
            
            return PagedResultDto(
                items=items_dtos,
                total_count=total_count,
                page_index=request.page_index,
                page_size=request.page_size,
                # total_pages is calculated in PagedResultDto or can be done here
            )
        except Exception as e:
            logger.error(f"获取用户播客列表失败: {e}", exc_info=True)
            raise BusinessException(f"获取播客列表失败: {str(e)}")

    async def delete_podcast_async(self, user_id: int, podcast_id: int) -> bool:
        """删除播客"""
        try:
            podcast = await self.podcast_task_repo.get_by_id_async(podcast_id)
            if not podcast or podcast.user_id != user_id:
                raise NotFoundException("播客不存在或您没有访问权限")
            
            # Check status - C# does not check status for deletion, but it might be a good idea
            # if podcast.status == PodcastTaskStatus.PROCESSING:
            #     raise BusinessException("播客正在处理中，无法删除")

            # Cascade delete related items
            await self.podcast_script_repo.delete_by_podcast_id_async(podcast_id)
            await self.podcast_content_repo.delete_by_podcast_id_async(podcast_id)
            # Consider deleting history items too, or keep them for audit
            # C# code doesn't explicitly delete history items here
            
            return await self.podcast_task_repo.delete_async(podcast_id)
        except Exception as e:
            logger.error(f"删除播客失败, ID: {podcast_id}, Error: {e}", exc_info=True)
            if isinstance(e, (BusinessException, NotFoundException)):
                 raise
            raise BusinessException(f"删除播客失败: {str(e)}")

    async def start_podcast_generate_async(self, user_id: int, podcast_id: int) -> bool:
        """开始播客脚本和音频的生成"""
        try:
            podcast = await self.podcast_task_repo.get_by_id_async(podcast_id)
            if not podcast or podcast.user_id != user_id:
                raise BusinessException("播客不存在或您没有访问权限") # C# uses BusinessException here

            content_items = await self.podcast_content_repo.get_by_podcast_id_async(podcast_id)
            if not content_items:
                raise BusinessException("播客任务还未上传任何内容")
            
            doc_ids_to_check = [
                item.source_document_id for item in content_items 
                if item.source_document_id and item.source_document_id > 0
             ]
            if doc_ids_to_check:
                # This returns List[DocumentStatusDto]
                doc_statuses = await self.document_service.get_document_status_async(user_id, doc_ids_to_check)
                if any(ds.status != DocumentStatus.COMPLETED for ds in doc_statuses):
                    incomplete_docs = [ds.id for ds in doc_statuses if ds.status != DocumentStatus.COMPLETED]
                    logger.warning(f"播客 {podcast_id} 包含未完成的文档: {incomplete_docs}")
                    raise BusinessException("部分源文档内容未解析完成，请稍后再试")
            
            if podcast.status not in [PodcastTaskStatus.INIT, PodcastTaskStatus.COMPLETED, PodcastTaskStatus.FAILED]:
                raise BusinessException("播客正在处理中或已在队列中，请稍后再试")
            
            if podcast.generate_count >= 5: # Max 5 generations
                raise BusinessException("该任务生成已超过5次，不可再生成")

            # Create a new history entry for this generation attempt
            history_id = await self.podcast_history_repo.add_async(podcast_id)
            
            # Update podcast task to PENDING and link to this history_id
            return await self.podcast_task_repo.start_podcast_generate_async(podcast_id, history_id)
        except Exception as e:
            logger.error(f"播客生成任务提交失败, ID: {podcast_id}, Error: {e}", exc_info=True)
            if isinstance(e, (BusinessException, NotFoundException)):
                 raise
            raise BusinessException(f"播客生成任务提交失败: {str(e)}")

    async def _generate_script_internal_async(self, history_id: int, podcast_detail: PodcastDetailDto, voices: List[TtsVoiceDefinitionDto]) -> bool:
        """Internal: AI generates script and saves to DB."""
        try:
            logger.info(f"开始为播客 {podcast_detail.id} (History ID: {history_id}) 生成脚本...")
            raw_script_items: List[PodcastScriptRawItemDto] = await self.ai_script_service.generate_script_async(podcast_detail, voices)
            await self.podcast_task_repo.update_progress_step_async(podcast_detail.id, 20)

            # Important: Move current scripts (if any) to history *before* adding new ones.
            # The C# logic moves scripts from PodcastTaskScript to PodcastScriptHistoryItem
            # PodcastScriptHistoryRepository.MoveScriptToHistoryAsync does this.
            await self.podcast_history_repo.move_script_to_history_async(podcast_detail.id)

            new_task_scripts: List[PodcastTaskScript] = []
            for i, raw_item in enumerate(raw_script_items):
                role_type_str = (raw_item.role_type or "guest").lower()
                role_type = PodcastRoleType.HOST if role_type_str == "host" else PodcastRoleType.GUEST
                
                voice_def = next((v for v in voices if v.voice_symbol == raw_item.voice_symbol), None)
                if not voice_def:
                    raise BusinessException(f"AI生成的脚本中包含无效的语音角色: {raw_item.voice_symbol}")
                
                new_task_scripts.append(
                    PodcastTaskScript(
                        podcast_id=podcast_detail.id,
                        history_id=history_id, # Link to current generation attempt
                        sequence_number=i + 1,
                        role_type=role_type,
                        role_name=raw_item.role_name,
                        voice_id=voice_def.id, # Store ID of the voice definition
                        content=raw_item.no_ssml_content,
                        ssml_content=raw_item.content, # Potentially SSML content
                        audio_status=AudioStatusType.PENDING 
                    )
                )
            
            if new_task_scripts:
                await self.podcast_script_repo.add_range_async(new_task_scripts)
            
            await self.podcast_task_repo.update_progress_step_async(podcast_detail.id, 30)
            logger.info(f"播客 {podcast_detail.id} (History ID: {history_id}) 脚本生成成功。")
            return True
        except Exception as e:
            logger.error(f"生成播客脚本内部失败, Podcast ID: {podcast_detail.id}, History ID: {history_id}, Error: {e}", exc_info=True)
            # This error will be caught by process_podcast_generate
            raise BusinessException(f"生成播客脚本失败: {str(e)}")


    async def _generate_audio_internal_async(self, podcast_task: PodcastTask, voices: List[TtsVoiceDefinitionDto]) -> bool:
        """Internal: Generates audio for script items."""
        script_items = await self.podcast_script_repo.get_by_podcast_id_async(podcast_task.id)
        if not script_items:
            # This might happen if script generation failed but wasn't caught before, or if no scripts were generated.
            logger.warning(f"播客 {podcast_task.id} 脚本为空，无法生成语音。")
            # Depending on desired behavior, this could be an error or just complete this step.
            # Let's assume if no scripts, this step is "done" but no audio generated.
            return True # Or False if this state is an error for audio generation phase.

        total_scripts = len(script_items)
        scripts_processed_count = 0
        initial_progress = 30 # Progress after script generation

        for item in script_items:
            try:
                logger.info(f"开始为脚本项 {item.id} (播客 {podcast_task.id}) 生成语音...")
                await self.podcast_script_repo.update_audio_status_async(item.id, AudioStatusType.PROCESSING, None, datetime.timedelta(0))
                
                voice_def = next((v for v in voices if v.id == item.voice_id), None)
                if not voice_def or not voice_def.voice_symbol:
                    logger.error(f"脚本项 {item.id} 语音角色定义无效或缺少符号。")
                    await self.podcast_script_repo.update_audio_status_async(item.id, AudioStatusType.FAILED, "无效语音角色", datetime.timedelta(0))
                    continue # Skip to next item or raise error for the whole batch
                
                # Use ai_speech_service's combined TTS and upload method
                success, audio_url, audio_duration = await self.ai_speech_service.text_to_speech_and_upload_async(
                    task_id=podcast_task.id, # For pathing/identification
                    ssml_text=item.ssml_content or item.content or "", # Prefer SSML, fallback to content
                    plain_text=item.content or "", # Plain text
                    voice_symbol=voice_def.voice_symbol
                )

                if success and audio_url:
                    await self.podcast_script_repo.update_audio_status_async(item.id, AudioStatusType.COMPLETED, audio_url, audio_duration)
                    logger.info(f"脚本项 {item.id} 语音生成成功: {audio_url}")
                else:
                    logger.error(f"脚本项 {item.id} 语音生成失败。")
                    await self.podcast_script_repo.update_audio_status_async(item.id, AudioStatusType.FAILED, "语音生成接口调用失败", datetime.timedelta(0))
                    # Decide: continue with others or fail the whole podcast generation? C# implies it throws.
                    raise BusinessException(f"脚本项 {item.id} 语音生成失败")

                scripts_processed_count += 1
                current_step_progress = int((scripts_processed_count / total_scripts) * 60) # Audio part is 60% of progress (30-90)
                await self.podcast_task_repo.update_progress_step_async(podcast_task.id, initial_progress + current_step_progress)

            except Exception as e_audio:
                logger.error(f"生成语音失败，脚本项ID: {item.id}, Error: {e_audio}", exc_info=True)
                await self.podcast_script_repo.update_audio_status_async(item.id, AudioStatusType.FAILED, str(e_audio), datetime.timedelta(0))
                # This error will be caught by process_podcast_generate
                raise BusinessException(f"脚本项 {item.id} 的语音生成过程中断: {str(e_audio)}")
        
        logger.info(f"播客 {podcast_task.id} 所有脚本项语音处理完成。")
        return True

    async def process_podcast_generate(self, podcast_id: int) -> bool:
        """
        异步处理播客脚本和音频的生成。
        This is the main worker logic for a single podcast generation task.
        """
        podcast_task = await self.podcast_task_repo.get_by_id_async(podcast_id)
        if not podcast_task:
            logger.error(f"ProcessPodcastGenerate: 播客 {podcast_id} 未找到。")
            return False # Or raise NotFoundException
        
        # This check is important. C# logic has this.
        if podcast_task.status != PodcastTaskStatus.PENDING:
            logger.warning(f"播客 {podcast_id} 状态为 {podcast_task.status}, 非 PENDING，跳过处理。")
            # Potentially another worker picked it up, or it's not meant to be processed.
            return False # Not an error, but not processed by this call.

        # Try to lock the task for processing
        locked = await self.podcast_task_repo.lock_processing_status_async(podcast_id)
        if not locked:
            logger.info(f"无法锁定播客 {podcast_id} 进行处理 (可能已被另一进程锁定或状态已改变)。")
            return False 

        current_history_id = podcast_task.generate_id # This was set by start_podcast_generate_async
        if not current_history_id or current_history_id == 0:
            errmsg = f"播客 {podcast_id} 缺少有效的 GenerateId (HistoryId) 无法处理。"
            logger.error(errmsg)
            await self.podcast_task_repo.update_status_async(podcast_id, PodcastTaskStatus.FAILED, errmsg)
            # Also update history entry if one was add_async-ed but generate_id wasn't set on task
            return False

        try:
            logger.info(f"开始处理播客生成任务: {podcast_id}, History ID: {current_history_id}")
            
            # Fetch full details needed for generation (includes content text)
            podcast_detail_dto = await self._get_podcast_full_async(podcast_task)
            
            # Fetch all supported voices once
            supported_voices = await self.ai_speech_service.get_supported_voices_async()
            if not supported_voices:
                raise BusinessException("系统中未配置可用的语音角色。")

            await self.podcast_task_repo.update_progress_step_async(podcast_id, 5)

            # Step 1: Generate Script
            logger.info(f"播客 {podcast_id}: 开始脚本生成...")
            await self._generate_script_internal_async(current_history_id, podcast_detail_dto, supported_voices)
            logger.info(f"播客 {podcast_id}: 脚本生成完成。")
            # Progress is updated inside _generate_script_internal_async (to 30)

            # Step 2: Generate Audio
            logger.info(f"播客 {podcast_id}: 开始语音合成...")
            await self._generate_audio_internal_async(podcast_task, supported_voices)
            logger.info(f"播客 {podcast_id}: 语音合成完成。")
            # Progress is updated inside _generate_audio_internal_async (up to 90)
            
            await self.podcast_task_repo.update_status_async(podcast_id, PodcastTaskStatus.COMPLETED)
            await self.podcast_history_repo.update_status_async(current_history_id, PodcastTaskStatus.COMPLETED)
            await self.podcast_task_repo.update_progress_step_async(podcast_id, 100)
            
            logger.info(f"播客 {podcast_id} (History ID: {current_history_id}) 处理成功完成。")
            return True

        except Exception as e:
            logger.error(f"生成播客内容失败, ID: {podcast_id}, History ID: {current_history_id}, Error: {e}", exc_info=True)
            error_message = str(e) if isinstance(e, BusinessException) else f"内部处理错误: {str(e)}"
            
            await self.podcast_task_repo.update_status_async(podcast_id, PodcastTaskStatus.FAILED, error_message)
            if current_history_id: # Ensure history_id is valid before updating
                await self.podcast_history_repo.update_status_async(current_history_id, PodcastTaskStatus.FAILED, error_message)
            await self.podcast_task_repo.update_progress_step_async(podcast_id, 100) # Mark progress as done even on failure
            return False

    async def get_supported_voices_async(self) -> List[TtsVoiceDefinitionDto]:
        """获取所有支持的语音角色"""
        return await self.ai_speech_service.get_supported_voices_async()

    async def get_voices_by_locale_async(self, locale: str) -> List[TtsVoiceDefinitionDto]:
        """获取指定语言的语音角色"""
        return await self.ai_speech_service.get_voices_by_locale_async(locale)