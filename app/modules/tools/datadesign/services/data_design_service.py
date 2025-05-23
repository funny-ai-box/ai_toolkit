import logging
import datetime
from pathlib import Path
import pystache # For Mustache templating
import math
from typing import List, Callable, Optional, Dict, Any
from fastapi import UploadFile
import shutil # For file operations, if needed for UploadFile, though usually not

from app.core.exceptions import BusinessException, NotFoundException
from app.core.utils.snowflake import generate_id
from app.modules.tools.datadesign.dtos import (
    CreateDesignTaskRequestDto, UpdateDesignTaskRequestDto, DesignTaskDetailDto,
    DesignTaskListItemDto, DesignTaskListRequestDto, DesignTaskPagedResultDto,
    TableDesignDetailDto, FieldDesignDetailDto, IndexDesignDetailDto, IndexFieldDto, TableRelationDto,
    TableDesignListItemDto,
    DesignChatRequestDto, DesignChatMessageDto, DesignDialogResultDto,
    GenerateDDLRequestDto, GenerateDDLResultDto,
    GenerateCodeRequestDto, GenerateCodeResultDto, CodeFileDto,
    CodeTemplateDto, CodeTemplateDetailDto, CreateCodeTemplateDto,
    GenerateCodeTemplateRequestDto, TemplateExampleDto, GetExampleRequirementsRequestDto,
    DatabaseDesignJsonDto, SupportLanguageAndDbDto, SupportCodeLanguageDto,
    BaseIdRequestDto, PagedResultDto
)
from app.modules.tools.datadesign.entities import (
    DesignTask, TableDesign, FieldDesign, IndexDesign, IndexField, TableRelation,
    CodeTemplate, CodeTemplateDtl, DesignChat
)
from app.modules.tools.datadesign.enums import LanguageType, DatabaseType, AssistantRoleType
from app.core.ai.dtos import ChatRoleType

from app.modules.tools.datadesign.repositories.design_task_repository import DesignTaskRepository
from app.modules.tools.datadesign.repositories.table_design_repository import TableDesignRepository
from app.modules.tools.datadesign.repositories.field_design_repository import FieldDesignRepository
from app.modules.tools.datadesign.repositories.index_design_repository import IndexDesignRepository
from app.modules.tools.datadesign.repositories.index_field_repository import IndexFieldRepository
from app.modules.tools.datadesign.repositories.table_relation_repository import TableRelationRepository
from app.modules.tools.datadesign.repositories.design_chat_repository import DesignChatRepository
from app.modules.tools.datadesign.repositories.code_template_repository import CodeTemplateRepository
from app.modules.tools.datadesign.repositories.code_template_dtl_repository import CodeTemplateDtlRepository

from app.modules.tools.datadesign.services.data_design_ai_service import DataDesignAIService
from app.modules.tools.datadesign.services.coding.code_template_generator_service import CodeTemplateGeneratorService
from app.modules.tools.datadesign.services.coding import template_database_ddl_helper, template_code_helper


class DataDesignService:
    """数据设计服务实现"""

    def __init__(
        self,
        logger: logging.Logger,
        design_task_repo: DesignTaskRepository,
        table_design_repo: TableDesignRepository,
        field_design_repo: FieldDesignRepository,
        index_design_repo: IndexDesignRepository,
        index_field_repo: IndexFieldRepository,
        table_relation_repo: TableRelationRepository,
        design_chat_repo: DesignChatRepository,
        code_template_repo: CodeTemplateRepository,
        code_template_dtl_repo: CodeTemplateDtlRepository,
        design_ai_service: DataDesignAIService,
        code_template_generator_service: CodeTemplateGeneratorService
    ):
        self._logger = logger
        self.design_task_repo = design_task_repo
        self.table_design_repo = table_design_repo
        self.field_design_repo = field_design_repo
        self.index_design_repo = index_design_repo
        self.index_field_repo = index_field_repo
        self.table_relation_repo = table_relation_repo
        self.design_chat_repo = design_chat_repo
        self.code_template_repo = code_template_repo
        self.code_template_dtl_repo = code_template_dtl_repo
        self.design_ai_service = design_ai_service
        self.code_template_generator_service = code_template_generator_service
        self.renderer = pystache.Renderer()


    # region 设计任务管理
    async def create_design_task_async(self, user_id: int, request: CreateDesignTaskRequestDto) -> int:
        """创建设计任务"""
        try:
            task = DesignTask(
                user_id=user_id,
                task_name=request.taskName,
                description=request.description or ""
            )
            # ID and timestamps are set by repository
            new_id = await self.design_task_repo.add_async(task)
            return new_id
        except Exception as ex:
            self._logger.error(f"创建设计任务失败: {ex}", exc_info=True)
            raise BusinessException("创建设计任务失败", ex)

    async def update_design_task_async(self, user_id: int, request: UpdateDesignTaskRequestDto) -> bool:
        """更新设计任务"""
        try:
            task = await self.design_task_repo.get_by_id_async(request.id)
            if not task or task.user_id != user_id:
                raise NotFoundException("设计任务不存在或无权限")

            task.task_name = request.task_name
            task.description = request.description or ""
            # last_modify_date updated by repository
            return await self.design_task_repo.update_async(task)
        except NotFoundException:
            raise
        except Exception as ex:
            self._logger.error(f"更新设计任务失败 (id: {request.id}): {ex}", exc_info=True)
            raise BusinessException("更新设计任务失败", ex)

    async def delete_design_task_async(self, user_id: int, task_id: int) -> bool:
        """删除设计任务及其所有关联数据"""
        try:
            task = await self.design_task_repo.get_by_id_async(task_id)
            if not task or task.user_id != user_id:
                raise NotFoundException("设计任务不存在或无权限")

            # Order of deletion matters due to foreign key constraints (if any are hard enforced)
            # Python repositories will handle these individually.
            # Consider a transaction if these need to be atomic.
            await self.design_chat_repo.delete_by_task_id_async(task_id) # Also deletes task state
            await self.index_field_repo.delete_by_task_id_async(task_id)
            await self.index_design_repo.delete_by_task_id_async(task_id)
            await self.field_design_repo.delete_by_task_id_async(task_id)
            await self.table_relation_repo.delete_by_task_id_async(task_id)
            await self.table_design_repo.delete_by_task_id_async(task_id)
            
            return await self.design_task_repo.delete_async(task_id)
        except NotFoundException:
            raise
        except Exception as ex:
            self._logger.error(f"删除设计任务失败 (id: {task_id}): {ex}", exc_info=True)
            raise BusinessException("删除设计任务失败", ex)

    async def get_design_task_async(self, user_id: int, task_id: int) -> DesignTaskDetailDto:
        """获取设计任务详情"""
        try:
            task = await self.design_task_repo.get_by_id_async(task_id)
            if not task or task.user_id != user_id:
                raise NotFoundException("设计任务不存在或无权限")
            return DesignTaskDetailDto.model_validate(task)
        except NotFoundException:
            raise
        except Exception as ex:
            self._logger.error(f"获取设计任务详情失败 (id: {task_id}): {ex}", exc_info=True)
            raise BusinessException("获取设计任务详情失败", ex)

    async def get_design_tasks_async(self, user_id: int, request: DesignTaskListRequestDto) -> DesignTaskPagedResultDto:
        """获取用户的设计任务列表 (分页)"""
        try:
            tasks_entities, total_count = await self.design_task_repo.get_paginated_by_user_id_async(
                user_id, request.page_index, request.page_size
            )
            
            task_dtos: List[DesignTaskListItemDto] = []
            for task_entity in tasks_entities:
                tables = await self.table_design_repo.get_by_task_id_async(task_entity.id)
                task_dtos.append(
                    DesignTaskListItemDto(
                        id=task_entity.id,
                        task_name=task_entity.task_name,
                        description=task_entity.description,
                        table_count=len(tables),
                        create_date=task_entity.create_date,
                        last_modify_date=task_entity.last_modify_date
                    )
                )
            
            return DesignTaskPagedResultDto(
                items=task_dtos,
                total_count=total_count,
                page_index=request.page_index,
                page_size=request.page_size,
                total_pages=math.ceil(total_count / request.page_size) if request.page_size > 0 and total_count > 0 else 0
            )
        except Exception as ex:
            self._logger.error(f"获取设计任务列表失败 (user_id: {user_id}): {ex}", exc_info=True)
            raise BusinessException("获取设计任务列表失败", ex)
    # endregion

    # region 表设计管理
    async def get_table_design_async(self, user_id: int, table_id: int) -> TableDesignDetailDto:
        """获取表设计详情"""
        try:
            table = await self.table_design_repo.get_by_id_async(table_id)
            if not table:
                raise NotFoundException("表设计不存在")

            task = await self.design_task_repo.get_by_id_async(table.task_id)
            if not task or task.user_id != user_id:
                raise BusinessException("无权限访问此表设计")

            fields_entities = await self.field_design_repo.get_by_table_id_async(table_id)
            field_dtos = [FieldDesignDetailDto.model_validate(f) for f in sorted(fields_entities, key=lambda x: x.sort_order)]

            indexes_entities = await self.index_design_repo.get_by_table_id_async(table_id)
            index_dtos: List[IndexDesignDetailDto] = []
            for index_entity in indexes_entities:
                index_fields_entities = await self.index_field_repo.get_by_index_id_async(index_entity.id)
                index_field_dtos: List[IndexFieldDto] = []
                for if_entity in sorted(index_fields_entities, key=lambda x: x.sort_order):
                    field = next((f for f in fields_entities if f.id == if_entity.field_id), None)
                    if field:
                        index_field_dtos.append(IndexFieldDto(
                            id=if_entity.id,
                            field_id=if_entity.field_id,
                            field_name=field.field_name,
                            sort_direction=if_entity.sort_direction,
                            sort_order=if_entity.sort_order
                        ))
                index_dtos.append(IndexDesignDetailDto(
                    id=index_entity.id,
                    index_name=index_entity.index_name,
                    index_type=index_entity.index_type,
                    description=index_entity.description,
                    fields=index_field_dtos
                ))
            
            all_relations = await self.table_relation_repo.get_by_table_id_async(table_id)
            parent_relation_dtos: List[TableRelationDto] = []
            child_relation_dtos: List[TableRelationDto] = []

            all_table_ids_in_relations = {rel.parent_table_id for rel in all_relations} | \
                                         {rel.child_table_id for rel in all_relations}
            
            # Fetch names for all related tables in one go if possible, or map them
            # This simplified version fetches one by one, optimize if performance critical
            table_names_cache: Dict[int, Optional[str]] = {table.id: table.table_name}

            for rel_entity in all_relations:
                parent_name = table_names_cache.get(rel_entity.parent_table_id)
                if parent_name is None and rel_entity.parent_table_id not in table_names_cache:
                    pt = await self.table_design_repo.get_by_id_async(rel_entity.parent_table_id)
                    parent_name = pt.table_name if pt else "Unknown"
                    table_names_cache[rel_entity.parent_table_id] = parent_name
                
                child_name = table_names_cache.get(rel_entity.child_table_id)
                if child_name is None and rel_entity.child_table_id not in table_names_cache:
                    ct = await self.table_design_repo.get_by_id_async(rel_entity.child_table_id)
                    child_name = ct.table_name if ct else "Unknown"
                    table_names_cache[rel_entity.child_table_id] = child_name

                rel_dto = TableRelationDto(
                    id=rel_entity.id,
                    parent_table_id=rel_entity.parent_table_id,
                    parent_table_name=parent_name,
                    child_table_id=rel_entity.child_table_id,
                    child_table_name=child_name,
                    relation_type=rel_entity.relation_type,
                    description=rel_entity.description
                )
                if rel_entity.parent_table_id == table_id:
                    child_relation_dtos.append(rel_dto)
                elif rel_entity.child_table_id == table_id:
                    parent_relation_dtos.append(rel_dto)

            return TableDesignDetailDto(
                id=table.id, task_id=table.task_id, table_name=table.table_name,
                comment=table.comment, business_description=table.business_description,
                business_group=table.business_group, fields=field_dtos,
                parent_relations=parent_relation_dtos, child_relations=child_relation_dtos,
                indexes=index_dtos
            )
        except NotFoundException:
            raise
        except BusinessException:
            raise
        except Exception as ex:
            self._logger.error(f"获取表设计详情失败 (id: {table_id}): {ex}", exc_info=True)
            raise BusinessException("获取表设计详情失败", ex)

    async def get_table_designs_async(self, user_id: int, task_id: int) -> List[TableDesignListItemDto]:
        """获取任务的表设计列表"""
        try:
            task = await self.design_task_repo.get_by_id_async(task_id)
            if not task or task.user_id != user_id:
                raise BusinessException("设计任务不存在或无权限")

            tables_entities = await self.table_design_repo.get_by_task_id_async(task_id)
            relations_entities = await self.table_relation_repo.get_by_task_id_async(task_id)
            
            table_dtos: List[TableDesignListItemDto] = []
            # Cache table names for relations
            table_name_map = {t.id: t.table_name for t in tables_entities}

            for table_entity in tables_entities:
                child_relations_for_table: List[TableRelationDto] = []
                for rel_entity in relations_entities:
                    if rel_entity.parent_table_id == table_entity.id:
                        child_relations_for_table.append(TableRelationDto(
                            id=rel_entity.id,
                            parent_table_id=rel_entity.parent_table_id,
                            parent_table_name=table_name_map.get(rel_entity.parent_table_id),
                            child_table_id=rel_entity.child_table_id,
                            child_table_name=table_name_map.get(rel_entity.child_table_id),
                            relation_type=rel_entity.relation_type,
                            description=rel_entity.description
                        ))
                
                table_dtos.append(TableDesignListItemDto(
                    id=table_entity.id,
                    table_name=table_entity.table_name,
                    comment=table_entity.comment,
                    business_group=table_entity.business_group,
                    field_count=table_entity.field_count,
                    child_relations=child_relations_for_table
                ))
            
            return sorted(table_dtos, key=lambda t: (t.business_group or "", t.table_name or ""))
        except BusinessException:
            raise
        except Exception as ex:
            self._logger.error(f"获取表设计列表失败 (task_id: {task_id}): {ex}", exc_info=True)
            raise BusinessException("获取表设计列表失败", ex)
    # endregion

    # region 设计聊天
    async def upload_document_async(self, user_id: int, task_id: int, file: UploadFile) -> str:
        """上传文档并解析内容"""
        try:
            task = await self.design_task_repo.get_by_id_async(task_id)
            if not task or task.user_id != user_id:
                raise BusinessException("设计任务不存在或无权限")

            allowed_extensions = {".txt", ".pdf", ".doc", ".docx"}
            file_extension = "".join(Path(file.filename).suffixes).lower() if file.filename else "" # Handles .tar.gz etc.
            # For simplicity, check primary extension
            primary_extension = Path(file.filename).suffix.lower() if file.filename else ""


            if primary_extension not in allowed_extensions:
                raise BusinessException(f"不支持的文件格式。请上传以下格式的文件：{', '.join(allowed_extensions)}")

            # File size check (example: 50MB)
            # FastAPI UploadFile.file is a SpooledTemporaryFile, size check is complex before read.
            # Rely on RequestSizeLimit middleware or check after reading if small enough.
            # For now, we'll proceed and let system handle large files if not caught by server limits.
            
            content_bytes = await file.read()
            if len(content_bytes) > 50 * 1024 * 1024: # 50MB
                 raise BusinessException("文件大小不能超过50MB")

            content = ""
            if primary_extension == ".txt":
                try:
                    content = content_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    content = content_bytes.decode('latin-1') # Fallback
            elif primary_extension in [".pdf", ".doc", ".docx"]:
                # Placeholder for actual parsing logic
                # In a real app, use libraries like PyPDF2, python-docx
                self._logger.warning(f"解析 {primary_extension} 文件 ({file.filename}) 是占位符实现。")
                content = f"'{file.filename}' ({primary_extension}) 内容解析占位符..."
            
            chat_message_content = f"上传文档：{file.filename}\n\n{content}"
            chat_message = DesignChat(
                task_id=task_id,
                role=ChatRoleType.USER,
                content=chat_message_content,
                assistant_role=None # Not an assistant message
            )
            await self.design_chat_repo.add_async(chat_message)
            return content

        except BusinessException:
            raise
        except Exception as ex:
            self._logger.error(f"上传文档失败: {ex}", exc_info=True)
            raise BusinessException("上传文档失败", ex)

    async def streaming_chat_async(
        self,
        user_id: int,
        request: DesignChatRequestDto,
        on_chunk_received: Callable[[str], None]
    ) -> DesignDialogResultDto:
        """流式聊天"""
        try:
            dialog_result = await self.design_ai_service.process_async(
                user_id, request, on_chunk_received
            )
            if dialog_result.database_design_dto:
                await self._save_database_design_async(request.task_id, dialog_result.database_design_dto)
            return dialog_result
        except BusinessException:
            raise
        except Exception as ex:
            self._logger.error(f"流式聊天失败 (task_id: {request.task_id}): {ex}", exc_info=True)
            raise BusinessException("流式聊天失败", ex)

    async def _save_database_design_async(self, task_id: int, design_dto: DatabaseDesignJsonDto) -> bool:
        """保存数据库设计 (从AI的JSON输出)"""
        if not design_dto or not design_dto.tables:
            self._logger.warning(f"任务 {task_id}: 接收到空的数据库设计，不保存。")
            return False
        
        self._logger.info(f"任务 {task_id}: 开始保存数据库设计。")
        try:
            # Delete old design data for this task
            await self.index_field_repo.delete_by_task_id_async(task_id)
            await self.index_design_repo.delete_by_task_id_async(task_id)
            await self.field_design_repo.delete_by_task_id_async(task_id)
            await self.table_relation_repo.delete_by_task_id_async(task_id)
            await self.table_design_repo.delete_by_task_id_async(task_id)

            table_entities: List[TableDesign] = []
            field_entities: List[FieldDesign] = []
            index_entities: List[IndexDesign] = []
            index_field_entities: List[IndexField] = []
            relation_entities: List[TableRelation] = []
            
            table_name_to_id_map: Dict[str, int] = {}

            # Create Tables
            for table_order, table_dto in enumerate(design_dto.tables):
                if not table_dto.table_name:
                    self._logger.warning(f"任务 {task_id}: 跳过无表名的表设计。")
                    continue
                
                table_entity = TableDesign(
                    id=generate_id(), task_id=task_id, table_name=table_dto.table_name,
                    comment=table_dto.comment, business_description=table_dto.business_description,
                    field_count=len(table_dto.fields) if table_dto.fields else 0,
                    business_group=table_dto.business_group, sort_order=table_order + 1
                )
                table_entities.append(table_entity)
                table_name_to_id_map[table_dto.table_name] = table_entity.id

                # Create Fields
                if table_dto.fields:
                    for field_order, field_dto in enumerate(table_dto.fields):
                        if not field_dto.field_name:
                            self._logger.warning(f"任务 {task_id}, 表 {table_dto.table_name}: 跳过无字段名的字段。")
                            continue
                        field_entity = FieldDesign(
                            id=generate_id(), task_id=task_id, table_id=table_entity.id,
                            field_name=field_dto.field_name, comment=field_dto.comment,
                            data_type=field_dto.data_type, length=field_dto.length,
                            precision=field_dto.precision, scale=field_dto.scale,
                            default_value=field_dto.default_value,
                            is_primary_key=field_dto.is_primary_key,
                            is_nullable=field_dto.is_nullable,
                            is_auto_increment=field_dto.is_auto_increment,
                            sort_order=field_order + 1
                        )
                        field_entities.append(field_entity)
                
                # Create Indexes
                if table_dto.indexes:
                    for index_dto in table_dto.indexes:
                        if not index_dto.index_name:
                            self._logger.warning(f"任务 {task_id}, 表 {table_dto.table_name}: 跳过无索引名的索引。")
                            continue
                        index_entity = IndexDesign(
                            id=generate_id(), task_id=task_id, table_id=table_entity.id,
                            index_name=index_dto.index_name, index_type=index_dto.index_type,
                            description=index_dto.description
                        )
                        index_entities.append(index_entity)

                        if index_dto.fields:
                            for if_order, if_dto in enumerate(index_dto.fields):
                                if not if_dto.field_name:
                                    self._logger.warning(f"任务 {task_id}, 表 {table_dto.table_name}, 索引 {index_dto.index_name}: 跳过无字段名的索引字段。")
                                    continue
                                # Find field_id (from already collected field_entities for this table)
                                matching_field = next((f for f in field_entities if f.table_id == table_entity.id and f.field_name == if_dto.field_name), None)
                                if matching_field:
                                    index_field_entity = IndexField(
                                        id=generate_id(), index_id=index_entity.id, field_id=matching_field.id,
                                        sort_direction=if_dto.sort_direction or "ASC",
                                        sort_order=if_order + 1
                                    )
                                    index_field_entities.append(index_field_entity)
                                else:
                                    self._logger.warning(f"任务 {task_id}, 表 {table_dto.table_name}, 索引 {index_dto.index_name}: 找不到索引字段 '{if_dto.field_name}'。")
            
            # Create Relations
            if design_dto.relations:
                for rel_dto in design_dto.relations:
                    if not rel_dto.parent_table_name or not rel_dto.child_table_name:
                        self._logger.warning(f"任务 {task_id}: 跳过父表或子表名为空的关系。")
                        continue
                    if rel_dto.parent_table_name in table_name_to_id_map and \
                       rel_dto.child_table_name in table_name_to_id_map:
                        relation_entity = TableRelation(
                            id=generate_id(), task_id=task_id,
                            parent_table_id=table_name_to_id_map[rel_dto.parent_table_name],
                            child_table_id=table_name_to_id_map[rel_dto.child_table_name],
                            relation_type=rel_dto.relation_type, description=rel_dto.description
                        )
                        relation_entities.append(relation_entity)
                    else:
                        self._logger.warning(f"任务 {task_id}: 关系中表名 '{rel_dto.parent_table_name}' 或 '{rel_dto.child_table_name}' 未在表设计中找到。")

            # Batch save (assuming repositories handle setting create_date/last_modify_date)
            if table_entities: await self.table_design_repo.add_batch_async(table_entities)
            if field_entities: await self.field_design_repo.add_batch_async(field_entities)
            if index_entities: await self.index_design_repo.add_batch_async(index_entities)
            if index_field_entities: await self.index_field_repo.add_batch_async(index_field_entities)
            if relation_entities: await self.table_relation_repo.add_batch_async(relation_entities)
            
            self._logger.info(f"任务 {task_id}: 数据库设计保存成功。")
            return True
        except Exception as ex:
            self._logger.error(f"保存数据库设计失败 (task_id: {task_id}): {ex}", exc_info=True)
            # Do not re-raise as BusinessException here, as it's an internal process error
            return False # Indicate failure

    async def get_chat_history_async(self, user_id: int, task_id: int) -> List[DesignChatMessageDto]:
        """获取聊天历史"""
        try:
            task = await self.design_task_repo.get_by_id_async(task_id)
            if not task or task.user_id != user_id:
                raise BusinessException("设计任务不存在或无权限")

            history_entities = await self.design_chat_repo.get_by_task_id_async(task_id) # Already ordered by date desc
            # Re-sort by date asc for display
            return [DesignChatMessageDto.model_validate(h) for h in sorted(history_entities, key=lambda x: x.create_date)]
        except BusinessException:
            raise
        except Exception as ex:
            self._logger.error(f"获取聊天历史失败 (task_id: {task_id}): {ex}", exc_info=True)
            raise BusinessException("获取聊天历史失败", ex)
    # endregion

    # region 代码生成
    async def get_support_language_and_db_async(self) -> SupportLanguageAndDbDto:
        """返回支持的数据库和程序语言"""
        databases = [
            SupportCodeLanguageDto(value=db_type.value, code=db_type.name) for db_type in DatabaseType
        ]
        languages = [
            SupportCodeLanguageDto(value=lang_type.value, code=lang_type.name) for lang_type in LanguageType
        ]
        return SupportLanguageAndDbDto(databases=databases, languages=languages)

    async def generate_ddl_async(self, user_id: int, request: GenerateDDLRequestDto) -> GenerateDDLResultDto:
        """生成DDL脚本"""
        try:
            task = await self.design_task_repo.get_by_id_async(request.task_id)
            if not task or task.user_id != user_id:
                raise BusinessException("设计任务不存在或无权限")

            target_tables: List[TableDesign]
            if request.table_id and request.table_id > 0:
                table = await self.table_design_repo.get_by_id_async(request.table_id)
                if not table or table.task_id != request.task_id:
                    raise NotFoundException("表设计不存在或不属于该任务")
                target_tables = [table]
            else:
                target_tables = await self.table_design_repo.get_by_task_id_async(request.task_id)

            if not target_tables:
                raise BusinessException("没有可生成的表设计")

            tables_data: List[Dict[str, Any]] = []
            for table_entity in target_tables:
                fields_entities = await self.field_design_repo.get_by_table_id_async(table_entity.id)
                indexes_entities = await self.index_design_repo.get_by_table_id_async(table_entity.id)
                
                fields_data: List[Dict[str, Any]] = []
                for i, field_entity in enumerate(fields_entities):
                    db_data_type = template_database_ddl_helper.get_data_type_for_database(
                        field_entity.data_type, request.database_type,
                        field_entity.length, field_entity.precision, field_entity.scale
                    )
                    default_val = field_entity.default_value
                    # Handle string defaults for SQL dialects
                    if isinstance(default_val, str) and request.database_type in [DatabaseType.MYSQL, DatabaseType.SQLSERVER, DatabaseType.ORACLE]:
                         if not default_val.upper().startswith(("CURRENT_TIMESTAMP", "NOW()")) and not default_val.isdigit():
                            default_val = f"'{default_val}'"


                    fields_data.append({
                        "name": field_entity.field_name or "",
                        "tablename": table_entity.table_name or "", # For SQL Server comments
                        "comment": field_entity.comment or "",
                        "dataType": db_data_type,
                        "isPrimaryKey": field_entity.is_primary_key,
                        "isNullable": field_entity.is_nullable,
                        "isAutoIncrement": field_entity.is_auto_increment,
                        "defaultValue": default_val, # Handled by template with {{{}}}
                        "last": (i == len(fields_entities) - 1)
                    })
                
                indexes_data: List[Dict[str, Any]] = []
                for index_entity in indexes_entities:
                    index_fields_with_direction: List[str] = []
                    index_field_entities = await self.index_field_repo.get_by_index_id_async(index_entity.id)
                    for if_entity in sorted(index_field_entities, key=lambda x: x.sort_order):
                        field = next((f for f in fields_entities if f.id == if_entity.field_id), None)
                        if field:
                            field_name_formatted = f"`{field.field_name}`" if request.database_type == DatabaseType.MYSQL else f"[{field.field_name}]"
                            if request.database_type == DatabaseType.ORACLE:
                                field_name_formatted = field.field_name or ""

                            direction = f" {if_entity.sort_direction.upper()}" if if_entity.sort_direction and if_entity.sort_direction.upper() == "DESC" else ""
                            index_fields_with_direction.append(f"{field_name_formatted}{direction}")
                    
                    if index_fields_with_direction:
                         indexes_data.append({
                            "name": index_entity.index_name or "",
                            "tablename": table_entity.table_name or "",
                            "type": index_entity.index_type or "INDEX", # Default to INDEX
                            "fields": ", ".join(index_fields_with_direction)
                        })
                
                tables_data.append({
                    "name": table_entity.table_name or "",
                    "comment": table_entity.comment or "",
                    "fields": fields_data,
                    "indexes": indexes_data,
                    "primaryKey": next((f for f in fields_data if f["isPrimaryKey"]), None)
                })

            template_context = {
                "tables": tables_data,
                "now": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            ddl_template_str = template_database_ddl_helper.get_ddl_template(request.database_type)
            script = self.renderer.render(ddl_template_str, template_context)

            return GenerateDDLResultDto(
                task_id=request.task_id,
                table_id=request.table_id,
                database_type=request.database_type,
                script=script
            )
        except (BusinessException, NotFoundException):
            raise
        except Exception as ex:
            self._logger.error(f"生成DDL脚本失败: {ex}", exc_info=True)
            raise BusinessException("生成DDL脚本失败", ex)

    async def generate_code_async(self, user_id: int, request: GenerateCodeRequestDto) -> GenerateCodeResultDto:
        """生成代码"""
        try:
            table_entity = await self.table_design_repo.get_by_id_async(request.table_id)
            if not table_entity:
                raise NotFoundException("表设计不存在")

            task = await self.design_task_repo.get_by_id_async(table_entity.task_id)
            if not task or task.user_id != user_id:
                raise BusinessException("设计任务不存在或无权限")

            fields_entities = await self.field_design_repo.get_by_table_id_async(table_entity.id)
            if not fields_entities:
                raise BusinessException("表没有字段定义")
            
            # Get indexes for template context (some templates might use them)
            indexes_entities = await self.index_design_repo.get_by_table_id_async(table_entity.id)
            indexes_data: List[Dict[str, Any]] = []
            for index_entity in indexes_entities:
                index_fields_with_details: List[Dict[str, Any]] = []
                index_field_entities = await self.index_field_repo.get_by_index_id_async(index_entity.id)
                for if_entity in sorted(index_field_entities, key=lambda x: x.sort_order):
                    field = next((f for f in fields_entities if f.id == if_entity.field_id), None)
                    if field:
                        index_fields_with_details.append({
                            "fieldName": field.field_name or "",
                            "sortDirection": if_entity.sort_direction or "ASC"
                        })
                indexes_data.append({
                    "indexName": index_entity.index_name or "",
                    "indexType": index_entity.index_type or "NORMAL",
                    "fields": index_fields_with_details
                })


            code_template_entity = await self.code_template_repo.get_by_id_async(request.template_id)
            if not code_template_entity:
                raise NotFoundException("代码模板不存在")

            template_dtls_entities = await self.code_template_dtl_repo.get_by_template_async(request.template_id)
            if not template_dtls_entities:
                raise BusinessException(f"代码模板 {request.template_id} 没有定义模板明细")

            # Prepare template data
            table_name = table_entity.table_name or "UnknownTable"
            template_context = {
                "tableName": table_name,
                "pascalTableName": template_code_helper.to_pascal_case(table_name),
                "camelTableName": template_code_helper.to_camel_case(table_name),
                "snake_table_name": template_code_helper.to_snake_case(table_name), # Added snake_case
                "tableComment": table_entity.comment or "",
                "databaseType": code_template_entity.database_type.name, # Enum name
                "namespace": "YourApp.Modules.Generated", # Placeholder or configurable
                "package": "com.yourapp.modules.generated" # Java placeholder
            }

            fields_data: List[Dict[str, Any]] = []
            for f_entity in fields_entities:
                field_name = f_entity.field_name or "unknownField"
                fields_data.append({
                    "name": field_name,
                    "pascalName": template_code_helper.to_pascal_case(field_name),
                    "camelName": template_code_helper.to_camel_case(field_name),
                    "comment": f_entity.comment or "",
                    "dataType": f_entity.data_type or "", # Original DB data type
                    "codeDataType": template_code_helper.get_data_type_for_language(
                        f_entity.data_type or "", code_template_entity.language
                    ),
                    "length": f_entity.length,
                    "precision": f_entity.precision,
                    "scale": f_entity.scale,
                    "isPrimaryKey": f_entity.is_primary_key,
                    "isNullable": f_entity.is_nullable,
                    "isAutoIncrement": f_entity.is_auto_increment,
                    "defaultValue": f_entity.default_value or "",
                    # Helper for Python/Java boolean type hints in templates
                    "codeDataTypeBOOL": (template_code_helper.get_data_type_for_language(f_entity.data_type or "", code_template_entity.language) == "bool"),
                    "codeDataTypeINT": (template_code_helper.get_data_type_for_language(f_entity.data_type or "", code_template_entity.language) == "int"),
                    "codeDataTypeFLOAT": (template_code_helper.get_data_type_for_language(f_entity.data_type or "", code_template_entity.language) == "float"),
                    "codeDataTypeSTR": (template_code_helper.get_data_type_for_language(f_entity.data_type or "", code_template_entity.language) == "str"),
                    "codeDataTypeDATETIME": (template_code_helper.get_data_type_for_language(f_entity.data_type or "", code_template_entity.language) == "datetime.datetime"),

                })
            
            template_context["fields"] = fields_data
            template_context["primaryKey"] = next((f for f in fields_data if f["isPrimaryKey"]), None)
            template_context["indexes"] = indexes_data


            generated_files: List[CodeFileDto] = []
            for dtl_entity in template_dtls_entities:
                if not dtl_entity.template_content or not dtl_entity.file_name:
                    self._logger.warning(f"模板明细 {dtl_entity.id} 内容或文件名为空，跳过。")
                    continue
                try:
                    # Render filename first, as it might contain template variables
                    rendered_file_name = self.renderer.render(dtl_entity.file_name, template_context)
                    rendered_content = self.renderer.render(dtl_entity.template_content, template_context)
                    generated_files.append(CodeFileDto(
                        name=dtl_entity.template_dtl_name,
                        file_name=rendered_file_name,
                        content=rendered_content
                    ))
                except Exception as render_ex:
                    self._logger.error(f"渲染模板明细 {dtl_entity.template_dtl_name} (ID: {dtl_entity.id}) 失败: {render_ex}", exc_info=True)
                    # Optionally add a file with error message, or skip
                    generated_files.append(CodeFileDto(
                        name=dtl_entity.template_dtl_name,
                        file_name=f"ERROR_{dtl_entity.file_name or 'template'}.txt",
                        content=f"Error rendering template '{dtl_entity.template_dtl_name}': {str(render_ex)}\nContext: {template_context}"
                    ))


            return GenerateCodeResultDto(
                table_id=request.table_id,
                language=code_template_entity.language,
                database_type=code_template_entity.database_type,
                files=generated_files
            )
        except (BusinessException, NotFoundException):
            raise
        except Exception as ex:
            self._logger.error(f"生成代码失败: {ex}", exc_info=True)
            raise BusinessException("生成代码失败", ex)

    async def get_code_templates_async(self, user_id: int) -> List[CodeTemplateDto]:
        """获取代码模板列表 (系统预置和用户自定义)"""
        try:
            templates_entities = await self.code_template_repo.get_system_and_user_template_async(user_id)
            return [
                CodeTemplateDto(
                    id=t.id,
                    user_id=t.user_id,
                    template_name=t.template_name,
                    language=t.language,
                    database_type=t.database_type,
                    prompt_content=t.prompt_content,
                    is_system=(t.user_id == 0)
                ) for t in templates_entities
            ]
        except Exception as ex:
            self._logger.error(f"获取代码模板列表失败 (user_id: {user_id}): {ex}", exc_info=True)
            raise BusinessException("获取代码模板列表失败", ex)

    async def get_code_template_dtls_async(self, user_id: int, template_id: int) -> List[CodeTemplateDetailDto]:
        """获取指定代码模板的详情列表"""
        try:
            template = await self.code_template_repo.get_by_id_async(template_id)
            if not template or (template.user_id != 0 and template.user_id != user_id): # 0 is system
                raise NotFoundException("模板不存在或无权限")

            dtls_entities = await self.code_template_dtl_repo.get_by_template_async(template_id)
            return [CodeTemplateDetailDto.model_validate(d) for d in dtls_entities]
        except NotFoundException:
            raise
        except Exception as ex:
            self._logger.error(f"获取代码模板详情失败 (template_id: {template_id}): {ex}", exc_info=True)
            raise BusinessException("获取代码模板详情失败", ex)

    async def create_code_template_async(self, user_id: int, request: CreateCodeTemplateDto) -> int:
        """用户创建新的代码模板 (仅头部，无明细)"""
        try:
            template_entity = CodeTemplate(
                user_id=user_id,
                template_name=request.template_name,
                language=request.language,
                database_type=request.database_type,
                prompt_content=None # User will fill this later if generating via AI
            )
            new_id = await self.code_template_repo.add_async(template_entity)
            return new_id
        except Exception as ex:
            self._logger.error(f"创建代码模板失败 (user_id: {user_id}): {ex}", exc_info=True)
            raise BusinessException("创建代码模板失败", ex)

    async def delete_code_template_async(self, user_id: int, template_id: int) -> bool:
        """删除用户自定义的代码模板"""
        try:
            template = await self.code_template_repo.get_by_id_async(template_id)
            if not template or template.user_id != user_id or template.user_id == 0: # Cannot delete system
                raise BusinessException("模板不存在、无权限或试图删除系统模板")
            
            # Repository's delete_async should handle deleting dtls as well
            return await self.code_template_repo.delete_async(template_id)
        except BusinessException:
            raise
        except Exception as ex:
            self._logger.error(f"删除代码模板失败 (template_id: {template_id}): {ex}", exc_info=True)
            raise BusinessException("删除代码模板失败", ex)

    async def generate_templates_with_ai_async(
        self,
        user_id: int,
        template_id: int,
        user_requirements: str,
        on_chunk_received: Callable[[str], None]
    ) -> List[CodeTemplateDetailDto]:
        """使用AI为用户模板生成明细内容"""
        try:
            template = await self.code_template_repo.get_by_id_async(template_id)
            if not template or template.user_id != user_id or template.user_id == 0:
                raise BusinessException("模板不存在、无权限或试图修改系统模板")

            # Update prompt content for the user's template
            await self.code_template_repo.update_prompt_content_async(template_id, user_requirements)

            generated_dtls_entities = await self.code_template_generator_service.generate_templates_async(
                template_id, template.language, template.database_type, user_requirements, on_chunk_received
            )

            if generated_dtls_entities:
                # Delete old details and add new ones
                await self.code_template_dtl_repo.delete_by_template_async(template_id)
                await self.code_template_dtl_repo.batch_add_async(generated_dtls_entities)
            
            return await self.get_code_template_dtls_async(user_id, template_id)
        except BusinessException:
            raise
        except Exception as ex:
            self._logger.error(f"AI生成代码模板明细失败 (template_id: {template_id}): {ex}", exc_info=True)
            raise BusinessException(f"AI生成代码模板明细失败: {str(ex)}")


    async def get_example_requirements_async(self, language: LanguageType, database_type: DatabaseType) -> TemplateExampleDto:
        """获取用于AI生成模板的示例需求"""
        example_requirements = ""
        lang_name = language.name
        db_name = database_type.name

        if language == LanguageType.CSHARP:
            example_requirements = f"""请为我创建C# ({lang_name})语言和{db_name}数据库的代码模板，包括：
1. 实体类模板：使用最新版本的Sqlsugar（或Entity Framework Core）。
2. 仓储接口模板：定义基本的CRUD操作和分页查询。
3. 仓储实现模板：实现仓储接口，包含异常处理和数据库上下文注入。
4. DTO模板：包含基本DTO、创建请求DTO和更新请求DTO，使用System.ComponentModel.DataAnnotations进行验证。
5. 服务接口模板：定义业务逻辑操作。
6. 服务实现模板：实现业务逻辑，包含AutoMapper或手动映射逻辑、日志记录和依赖注入。

代码风格要求：
- 所有异步方法以Async结尾。
- 添加标准的XML文档注释。
- 遵循Microsoft的C#代码规范和命名约定。
- 使用依赖注入模式（例如构造函数注入）。
- 考虑线程安全和性能。"""
        elif language == LanguageType.JAVA:
            example_requirements = f"""请为我创建Java ({lang_name})语言和{db_name}数据库的代码模板，包括：
1. 实体类模板：使用JPA注解（如@Entity, @Table, @Id, @Column, @GeneratedValue），支持Lombok (@Data, @Getter, @Setter)。
2. 仓储接口模板：继承Spring Data JPA的JpaRepository和JpaSpecificationExecutor。
3. DTO模板：包含基本DTO、创建请求DTO和更新请求DTO。使用javax.validation（或jakarta.validation）注解进行验证。
4. 服务接口模板：定义业务逻辑操作。
5. 服务实现模板：使用Spring框架（@Service, @Autowired或构造函数注入, @Transactional），包含日志记录(SLF4J)和 DTO与实体的转换逻辑 (如使用BeanUtils, ModelMapper, or MapStruct)。

代码风格要求：
- 遵循Google Java代码规范或Oracle Java代码规范。
- 使用构造函数注入依赖。
- 添加标准的Javadoc注释。
- 确保与Spring Boot最新稳定版本兼容。
- 返回 PagedResultDTO 用于分页查询。"""
        elif language == LanguageType.PYTHON:
            example_requirements = f"""请为我创建Python ({lang_name})语言和{db_name}数据库的代码模板，包括：
1. 模型模板：使用SQLAlchemy ORM (Declarative Base)，包含类型注解。
2. 仓储模板：实现异步数据访问逻辑 (async/await)，接收AsyncSession。
3. Schema模板：使用Pydantic进行数据验证和序列化 (请求和响应模型)，支持ORM模式。
4. 服务模板：实现异步业务逻辑 (async/await)，包含依赖注入和日志记录。

代码风格要求：
- 遵循PEP 8代码规范。
- 使用Python 3.8+的类型注解。
- 所有数据库和外部I/O操作使用async/await。
- 添加详细的中文文档字符串 (docstrings)。
- 设计与FastAPI框架兼容的结构。
- DTO字段名在JSON中应为camelCase。"""
        else:
            example_requirements = f"请为我创建{lang_name}语言和{db_name}数据库的代码模板，包括实体、数据访问层和业务逻辑层。请遵循该语言的最佳实践和常用框架。"

        return TemplateExampleDto(
            language=language,
            database_type=database_type,
            example_requirements=example_requirements
        )
    # endregion

