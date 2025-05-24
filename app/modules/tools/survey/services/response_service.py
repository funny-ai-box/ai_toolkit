import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.snowflake import generate_id
from app.core.exceptions import BusinessException, NotFoundException
from app.core.dtos import PagedResultDto

from app.modules.tools.survey.models import SurveyTask, SurveyField, SurveyResponse, SurveyResponseDetail
from app.modules.tools.survey.repositories import (
    SurveyTaskRepository, SurveyFieldRepository, 
    SurveyResponseRepository, SurveyResponseDetailRepository
)
from app.modules.tools.survey.enums import SurveyTaskStatus
from app.modules.tools.survey.dtos import (
    SubmitSurveyResponseRequestDto, SurveyResponseListItemDto,
    SurveyResponseDetailDto, ResponseFieldValueDto
)


class SurveyResponseService:
    """问卷回答服务实现"""

    def __init__(
        self,
        db: AsyncSession,
        task_repository: SurveyTaskRepository,
        field_repository: SurveyFieldRepository,
        response_repository: SurveyResponseRepository,
        response_detail_repository: SurveyResponseDetailRepository
    ):
        self.db = db
        self.task_repository = task_repository
        self.field_repository = field_repository
        self.response_repository = response_repository
        self.response_detail_repository = response_detail_repository

    async def submit_response_async(
        self,
        respondent_id: Optional[int],
        respondent_ip: str,
        request: SubmitSurveyResponseRequestDto
    ) -> int:
        """提交问卷回答"""
        
        # 验证问卷状态
        task = await self.task_repository.get_by_id_async(request.task_id)
        if not task:
            raise NotFoundException("问卷不存在")
        
        if task.status != SurveyTaskStatus.PUBLISHED:
            raise BusinessException("问卷未发布或已关闭")
        
        # 获取问卷字段
        fields = await self.field_repository.get_by_task_id_async(request.task_id)
        field_dict = {f.id: f for f in fields}
        
        # 验证必填字段
        required_field_ids = {f.id for f in fields if f.is_required}
        submitted_field_ids = {fv.field_id for fv in request.field_values if fv.value}
        
        missing_required = required_field_ids - submitted_field_ids
        if missing_required:
            missing_names = [field_dict[fid].name for fid in missing_required if fid in field_dict]
            raise BusinessException(f"以下必填字段未填写: {', '.join(missing_names)}")
        
        # 创建回答记录
        response = SurveyResponse(
            task_id=request.task_id,
            respondent_id=respondent_id,
            respondent_ip=respondent_ip,
            submit_date=datetime.datetime.now()
        )
        
        await self.response_repository.add_async(response)
        
        # 创建回答详情
        details = []
        for field_value in request.field_values:
            if field_value.field_id not in field_dict:
                continue  # 忽略无效字段
            
            field = field_dict[field_value.field_id]
            detail = SurveyResponseDetail(
                response_id=response.id,
                task_id=request.task_id,
                field_id=field_value.field_id,
                field_key=field.field_key,
                value=field_value.value
            )
            details.append(detail)
        
        if details:
            await self.response_detail_repository.add_batch_async(details)
        
        await self.db.commit()
        return response.id

    async def get_responses_async(
        self,
        user_id: int,
        task_id: int,
        page_index: int = 1,
        page_size: int = 20
    ) -> PagedResultDto[SurveyResponseListItemDto]:
        """获取问卷回答列表"""
        
        # 验证任务权限
        task = await self.task_repository.get_by_id_async(task_id)
        if not task or task.user_id != user_id:
            raise NotFoundException("问卷任务不存在")
        
        responses, total_count = await self.response_repository.get_by_task_id_async(
            task_id, page_index, page_size
        )
        
        response_dtos = []
        for response in responses:
            response_dto = SurveyResponseListItemDto(
                id=response.id,
                task_id=response.task_id,
                respondent_id=response.respondent_id,
                respondent_ip=response.respondent_ip,
                submit_date=response.submit_date
            )
            response_dtos.append(response_dto)
        
        return PagedResultDto(
            items=response_dtos,
            total_count=total_count,
            page_index=page_index,
            page_size=page_size
        )

    async def get_response_detail_async(self, user_id: int, response_id: int) -> SurveyResponseDetailDto:
        """获取问卷回答详情"""
        
        response = await self.response_repository.get_by_id_async(response_id)
        if not response:
            raise NotFoundException("回答记录不存在")
        
        # 验证任务权限
        task = await self.task_repository.get_by_id_async(response.task_id)
        if not task or task.user_id != user_id:
            raise NotFoundException("无权限访问")
        
        # 获取回答详情
        details = await self.response_detail_repository.get_by_response_id_async(response_id)
        
        # 获取字段信息
        fields = await self.field_repository.get_by_task_id_async(response.task_id)
        field_dict = {f.id: f for f in fields}
        
        # 构建字段值列表
        field_values = []
        for detail in details:
            field = field_dict.get(detail.field_id)
            field_value = ResponseFieldValueDto(
                field_id=detail.field_id,
                field_key=detail.field_key,
                field_name=field.name if field else None,
                field_type=field.type if field else None,
                value=detail.value
            )
            field_values.append(field_value)
        
        return SurveyResponseDetailDto(
            id=response.id,
            task_id=response.task_id,
            respondent_id=response.respondent_id,
            respondent_ip=response.respondent_ip,
            submit_date=response.submit_date,
            field_values=field_values
        )

    async def delete_response_async(self, user_id: int, response_id: int) -> bool:
        """删除问卷回答"""
        
        response = await self.response_repository.get_by_id_async(response_id)
        if not response:
            raise NotFoundException("回答记录不存在")
        
        # 验证任务权限
        task = await self.task_repository.get_by_id_async(response.task_id)
        if not task or task.user_id != user_id:
            raise NotFoundException("无权限访问")
        
        # 删除回答详情
        await self.response_detail_repository.delete_by_response_id_async(response_id)
        
        # 删除回答记录
        await self.response_repository.delete_by_id_async(response_id)
        
        await self.db.commit()
        return True