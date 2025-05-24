import datetime
import uuid
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.snowflake import generate_id
from app.core.exceptions import BusinessException, NotFoundException
from app.core.dtos import PagedResultDto

from app.modules.tools.survey.models import SurveyTask, SurveyTab, SurveyField
from app.modules.tools.survey.repositories import (
    SurveyTaskRepository, SurveyTabRepository, SurveyFieldRepository, SurveyResponseRepository
)
from app.modules.tools.survey.enums import SurveyTaskStatus
from app.modules.tools.survey.dtos import (
    CreateSurveyTaskRequestDto, UpdateSurveyTaskRequestDto, SurveyTaskListItemDto,
    SurveyTaskDetailDto, SurveyTabDto, SurveyFieldDto, FieldConfigDto
)


class SurveyTaskService:
    """问卷任务服务实现"""

    def __init__(
        self,
        db: AsyncSession,
        task_repository: SurveyTaskRepository,
        tab_repository: SurveyTabRepository,
        field_repository: SurveyFieldRepository,
        response_repository: SurveyResponseRepository
    ):
        self.db = db
        self.task_repository = task_repository
        self.tab_repository = tab_repository
        self.field_repository = field_repository
        self.response_repository = response_repository

    async def create_task_async(self, user_id: int, request: CreateSurveyTaskRequestDto) -> int:
        """创建问卷任务"""
        task = SurveyTask(
            user_id=user_id,
            name=request.name,
            description=request.description,
            status=int(SurveyTaskStatus.DRAFT)
        )
        
        await self.task_repository.add_async(task)
        await self.db.commit()
        return task.id

    async def update_task_async(self, user_id: int, request: UpdateSurveyTaskRequestDto) -> bool:
        """更新问卷任务"""
        task = await self.task_repository.get_by_id_async(request.id)
        if not task or task.user_id != user_id:
            raise NotFoundException("问卷任务不存在")
        
        task.name = request.name
        task.description = request.description
        
        await self.task_repository.update_async(task)
        await self.db.commit()
        return True

    async def delete_task_async(self, user_id: int, task_id: int) -> bool:
        """删除问卷任务"""
        task = await self.task_repository.get_by_id_async(task_id)
        if not task or task.user_id != user_id:
            raise NotFoundException("问卷任务不存在")
        
        # 删除相关数据
        await self.field_repository.delete_by_task_id_async(task_id)
        await self.tab_repository.delete_by_task_id_async(task_id)
        await self.task_repository.delete_async(task_id)
        
        await self.db.commit()
        return True

    async def get_task_async(self, user_id: int, task_id: int) -> SurveyTaskDetailDto:
        """获取问卷任务详情"""
        task = await self.task_repository.get_by_id_async(task_id)
        if not task or task.user_id != user_id:
            raise NotFoundException("问卷任务不存在")
        
        # 获取tabs和fields
        tabs = await self.tab_repository.get_by_task_id_async(task_id)
        fields = await self.field_repository.get_by_task_id_async(task_id)
        
        # 构建DTO
        tab_dtos = []
        for tab in tabs:
            tab_fields = [f for f in fields if f.tab_id == tab.id]
            field_dtos = []
            
            for field in sorted(tab_fields, key=lambda x: x.order_no):
                config = None
                if field.config:
                    import json
                    try:
                        config_dict = json.loads(field.config)
                        config = FieldConfigDto(**config_dict)
                    except:
                        config = FieldConfigDto()
                
                field_dto = SurveyFieldDto(
                    id=field.id,
                    task_id=field.task_id,
                    tab_id=field.tab_id,
                    field_key=field.field_key,
                    name=field.name,
                    type=field.type,
                    is_required=field.is_required,
                    config=config,
                    placeholder=field.placeholder,
                    order_no=field.order_no
                )
                field_dtos.append(field_dto)
            
            tab_dto = SurveyTabDto(
                id=tab.id,
                task_id=tab.task_id,
                name=tab.name,
                order_no=tab.order_no,
                fields=field_dtos
            )
            tab_dtos.append(tab_dto)
        
        return SurveyTaskDetailDto(
            id=task.id,
            name=task.name,
            description=task.description,
            status=task.status,
            status_name=self._get_status_name(task.status),
            share_code=task.share_code,
            tabs=sorted(tab_dtos, key=lambda x: x.order_no),
            create_date=task.create_date,
            last_modify_date=task.last_modify_date
        )

    async def get_task_by_share_code_async(self, share_code: str) -> SurveyTaskDetailDto:
        """通过共享码获取问卷任务"""
        task = await self.task_repository.get_by_share_code_async(share_code)
        if not task:
            raise NotFoundException("问卷不存在或已失效")
        
        if task.status != SurveyTaskStatus.PUBLISHED:
            raise BusinessException("问卷未发布")
        
        # 获取tabs和fields（无需用户权限检查）
        tabs = await self.tab_repository.get_by_task_id_async(task.id)
        fields = await self.field_repository.get_by_task_id_async(task.id)
        
        # 构建DTO（复用上面的逻辑）
        tab_dtos = []
        for tab in tabs:
            tab_fields = [f for f in fields if f.tab_id == tab.id]
            field_dtos = []
            
            for field in sorted(tab_fields, key=lambda x: x.order_no):
                config = None
                if field.config:
                    import json
                    try:
                        config_dict = json.loads(field.config)
                        config = FieldConfigDto(**config_dict)
                    except:
                        config = FieldConfigDto()
                
                field_dto = SurveyFieldDto(
                    id=field.id,
                    task_id=field.task_id,
                    tab_id=field.tab_id,
                    field_key=field.field_key,
                    name=field.name,
                    type=field.type,
                    is_required=field.is_required,
                    config=config,
                    placeholder=field.placeholder,
                    order_no=field.order_no
                )
                field_dtos.append(field_dto)
            
            tab_dto = SurveyTabDto(
                id=tab.id,
                task_id=tab.task_id,
                name=tab.name,
                order_no=tab.order_no,
                fields=field_dtos
            )
            tab_dtos.append(tab_dto)
        
        return SurveyTaskDetailDto(
            id=task.id,
            name=task.name,
            description=task.description,
            status=task.status,
            status_name=self._get_status_name(task.status),
            share_code=task.share_code,
            tabs=sorted(tab_dtos, key=lambda x: x.order_no),
            create_date=task.create_date,
            last_modify_date=task.last_modify_date
        )

    async def get_user_tasks_async(self, user_id: int, page_index: int = 1, page_size: int = 20) -> PagedResultDto[SurveyTaskListItemDto]:
        """获取用户的问卷任务列表"""
        tasks, total_count = await self.task_repository.get_by_user_id_async(user_id, page_index, page_size)
        
        task_dtos = []
        for task in tasks:
            # 获取回答数量
            response_count = await self.response_repository.get_response_count_async(task.id)
            
            task_dto = SurveyTaskListItemDto(
                id=task.id,
                name=task.name,
                description=task.description,
                status=task.status,
                status_name=self._get_status_name(task.status),
                share_code=task.share_code,
                response_count=response_count,
                create_date=task.create_date,
                last_modify_date=task.last_modify_date
            )
            task_dtos.append(task_dto)
        
        return PagedResultDto(
            items=task_dtos,
            total_count=total_count,
            page_index=page_index,
            page_size=page_size
        )

    async def publish_task_async(self, user_id: int, task_id: int) -> str:
        """发布问卷任务"""
        task = await self.task_repository.get_by_id_async(task_id)
        if not task or task.user_id != user_id:
            raise NotFoundException("问卷任务不存在")
        
        if task.status != SurveyTaskStatus.DRAFT:
            raise BusinessException("只能发布草稿状态的问卷")
        
        # 检查是否有字段
        fields = await self.field_repository.get_by_task_id_async(task_id)
        if not fields:
            raise BusinessException("问卷至少需要包含一个字段")
        
        # 生成共享码
        if not task.share_code:
            task.share_code = str(uuid.uuid4()).replace('-', '')[:16]
        
        # 更新状态
        await self.task_repository.update_status_async(task_id, SurveyTaskStatus.PUBLISHED)
        await self.db.commit()
        
        # 返回分享URL（这里可以根据实际需求构建完整URL）
        return f"/survey/share?code={task.share_code}"

    async def close_task_async(self, user_id: int, task_id: int) -> bool:
        """关闭问卷任务"""
        task = await self.task_repository.get_by_id_async(task_id)
        if not task or task.user_id != user_id:
            raise NotFoundException("问卷任务不存在")
        
        if task.status != SurveyTaskStatus.PUBLISHED:
            raise BusinessException("只能关闭已发布的问卷")
        
        await self.task_repository.update_status_async(task_id, SurveyTaskStatus.CLOSED)
        await self.db.commit()
        return True

    def _get_status_name(self, status: int) -> str:
        """获取状态名称"""
        status_names = {
            SurveyTaskStatus.DRAFT: "草稿",
            SurveyTaskStatus.PUBLISHED: "已发布", 
            SurveyTaskStatus.CLOSED: "已关闭"
        }
        return status_names.get(status, "未知")