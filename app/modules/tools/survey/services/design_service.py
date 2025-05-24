import json
import datetime
from typing import List, Optional, Callable
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.snowflake import generate_id
from app.core.exceptions import BusinessException, NotFoundException
from app.core.dtos import PagedResultDto

from app.modules.tools.survey.models import SurveyTask, SurveyTab, SurveyField, SurveyDesignHistory
from app.modules.tools.survey.repositories import (
    SurveyTaskRepository, SurveyTabRepository, SurveyFieldRepository, SurveyDesignHistoryRepository
)
from app.modules.tools.survey.services.ai_design_service import AIDesignService
from app.modules.tools.survey.enums import SurveyTaskStatus, FieldOperationType
from app.modules.tools.survey.dtos import (
    AIDesignRequestDto, AIDesignResponseDto, TabDesignDto, FieldDesignDto,
    DesignHistoryMessageDto
)


class SurveyDesignService:
    """问卷设计服务实现"""

    def __init__(
        self,
        db: AsyncSession,
        task_repository: SurveyTaskRepository,
        tab_repository: SurveyTabRepository,
        field_repository: SurveyFieldRepository,
        design_history_repository: SurveyDesignHistoryRepository,
        ai_design_service: AIDesignService
    ):
        self.db = db
        self.task_repository = task_repository
        self.tab_repository = tab_repository
        self.field_repository = field_repository
        self.design_history_repository = design_history_repository
        self.ai_design_service = ai_design_service

    async def streaming_ai_design_fields_async(
        self,
        user_id: int,
        request: AIDesignRequestDto,
        on_chunk_received: Callable[[str], None],
        cancellation_token = None
    ) -> AIDesignResponseDto:
        """流式AI设计问卷字段"""
        
        # 验证任务权限
        task = await self.task_repository.get_by_id_async(request.task_id)
        if not task or task.user_id != user_id:
            raise NotFoundException("问卷任务不存在")
        
        if task.status == SurveyTaskStatus.CLOSED:
            raise BusinessException("已关闭的问卷无法编辑")
        
        # 获取现有的tabs和fields
        tabs = await self.tab_repository.get_by_task_id_async(request.task_id)
        fields = await self.field_repository.get_by_task_id_async(request.task_id)
        
        # 调用AI设计服务
        response = await self.ai_design_service.ai_design_fields_async(
            user_id=user_id,
            task=task,
            user_message=request.message,
            on_chunk_received=on_chunk_received,
            tabs=tabs,
            fields=fields,
            cancellation_token=cancellation_token
        )
        
        await self.db.commit()
        return response

    async def get_design_history_async(
        self,
        user_id: int,
        task_id: int,
        page_index: int = 1,
        page_size: int = 20
    ) -> PagedResultDto[DesignHistoryMessageDto]:
        """获取问卷设计历史"""
        
        # 验证任务权限
        task = await self.task_repository.get_by_id_async(task_id)
        if not task or task.user_id != user_id:
            raise NotFoundException("问卷任务不存在")
        
        histories, total_count = await self.design_history_repository.get_by_task_id_paginated_async(
            task_id, page_index, page_size
        )
        
        history_dtos = []
        for history in histories:
            history_dto = DesignHistoryMessageDto(
                id=history.id,
                role=history.role,
                content=history.content,
                complete_json_config=history.complete_json_config,
                create_date=history.create_date
            )
            history_dtos.append(history_dto)
        
        return PagedResultDto(
            items=history_dtos,
            total_count=total_count,
            page_index=page_index,
            page_size=page_size
        )

    async def save_design_async(self, user_id: int, task_id: int, tabs: List[TabDesignDto]) -> bool:
        """保存问卷设计"""
        
        # 验证任务权限
        task = await self.task_repository.get_by_id_async(task_id)
        if not task or task.user_id != user_id:
            raise NotFoundException("问卷任务不存在")
        
        if task.status == SurveyTaskStatus.CLOSED:
            raise BusinessException("已关闭的问卷无法编辑")
        
        # 获取现有数据
        existing_tabs = await self.tab_repository.get_by_task_id_async(task_id)
        existing_fields = await self.field_repository.get_by_task_id_async(task_id)
        
        # 处理每个Tab
        for tab_dto in tabs:
            await self._process_tab_design(task_id, tab_dto, existing_tabs, existing_fields)
        
        # 处理删除操作
        await self._process_deletions(task_id, tabs, existing_tabs, existing_fields)
        
        await self.db.commit()
        return True

    async def _process_tab_design(
        self,
        task_id: int,
        tab_dto: TabDesignDto,
        existing_tabs: List[SurveyTab],
        existing_fields: List[SurveyField]
    ):
        """处理单个Tab的设计"""
        
        if tab_dto.operation == FieldOperationType.DELETE:
            # 删除Tab及其字段
            existing_tab = next((t for t in existing_tabs if t.name == tab_dto.name), None)
            if existing_tab:
                await self.field_repository.delete_by_tab_id_async(existing_tab.id)
                await self.tab_repository.delete_async(existing_tab.id)
            return
        
        # 创建或更新Tab
        existing_tab = next((t for t in existing_tabs if t.name == tab_dto.name), None)
        
        if existing_tab:
            # 更新现有Tab
            existing_tab.order_no = tab_dto.order_no
            await self.tab_repository.update_async(existing_tab)
            tab_id = existing_tab.id
        else:
            # 创建新Tab
            new_tab = SurveyTab(
                task_id=task_id,
                name=tab_dto.name,
                order_no=tab_dto.order_no
            )
            await self.tab_repository.add_async(new_tab)
            tab_id = new_tab.id
        
        # 处理字段
        if tab_dto.fields:
            for field_dto in tab_dto.fields:
                await self._process_field_design(task_id, tab_id, field_dto, existing_fields)

    async def _process_field_design(
        self,
        task_id: int,
        tab_id: int,
        field_dto: FieldDesignDto,
        existing_fields: List[SurveyField]
    ):
        """处理单个字段的设计"""
        
        if field_dto.operation == FieldOperationType.DELETE:
            # 删除字段
            existing_field = next((f for f in existing_fields if f.field_key == field_dto.field_key), None)
            if existing_field:
                await self.field_repository.delete_async(existing_field.id)
            return
        
        # 创建或更新字段
        existing_field = next((f for f in existing_fields if f.field_key == field_dto.field_key), None)
        
        # 准备配置JSON
        config_json = None
        if field_dto.config:
            config_json = json.dumps(field_dto.config.model_dump(exclude_none=True), ensure_ascii=False)
        
        if existing_field:
            # 更新现有字段
            existing_field.tab_id = tab_id
            existing_field.name = field_dto.name
            existing_field.type = field_dto.type
            existing_field.is_required = field_dto.is_required
            existing_field.config = config_json
            existing_field.placeholder = field_dto.placeholder
            existing_field.order_no = field_dto.order_no
            
            await self.field_repository.update_async(existing_field)
        else:
            # 创建新字段
            new_field = SurveyField(
                task_id=task_id,
                tab_id=tab_id,
                field_key=field_dto.field_key,
                name=field_dto.name,
                type=field_dto.type,
                is_required=field_dto.is_required,
                config=config_json,
                placeholder=field_dto.placeholder,
                order_no=field_dto.order_no
            )
            await self.field_repository.add_async(new_field)

    async def _process_deletions(
        self,
        task_id: int,
        new_tabs: List[TabDesignDto],
        existing_tabs: List[SurveyTab],
        existing_fields: List[SurveyField]
    ):
        """处理删除操作 - 删除不在新设计中的Tab和字段"""
        
        # 获取新设计中的Tab名称
        new_tab_names = {tab.name for tab in new_tabs if tab.operation != FieldOperationType.DELETE}
        
        # 删除不存在的Tab
        for existing_tab in existing_tabs:
            if existing_tab.name not in new_tab_names:
                await self.field_repository.delete_by_tab_id_async(existing_tab.id)
                await self.tab_repository.delete_async(existing_tab.id)
        
        # 删除不存在的字段
        for tab_dto in new_tabs:
            if tab_dto.operation == FieldOperationType.DELETE or not tab_dto.fields:
                continue
                
            new_field_keys = {field.field_key for field in tab_dto.fields 
                            if field.operation != FieldOperationType.DELETE}
            
            existing_tab = next((t for t in existing_tabs if t.name == tab_dto.name), None)
            if existing_tab:
                tab_fields = [f for f in existing_fields if f.tab_id == existing_tab.id]
                for field in tab_fields:
                    if field.field_key not in new_field_keys:
                        await self.field_repository.delete_async(field.id)