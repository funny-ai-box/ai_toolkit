import json
import statistics
from typing import List, Dict, Any, Optional
from collections import Counter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.modules.tools.survey.models import SurveyTask, SurveyField
from app.modules.tools.survey.repositories import (
    SurveyTaskRepository, SurveyFieldRepository,
    SurveyResponseRepository, SurveyResponseDetailRepository
)
from app.modules.tools.survey.enums import SurveyFieldType
from app.modules.tools.survey.dtos import (
    SurveyReportDto, FieldStatisticsDto, OptionStatisticsDto, 
    NumericStatisticsDto, OptionDto
)


class SurveyReportService:
    """问卷报表服务实现"""

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

    async def get_report_async(self, user_id: int, task_id: int) -> SurveyReportDto:
        """获取问卷报表"""
        
        # 验证任务权限
        task = await self.task_repository.get_by_id_async(task_id)
        if not task or task.user_id != user_id:
            raise NotFoundException("问卷任务不存在")
        
        # 获取回答总数
        total_responses = await self.response_repository.get_response_count_async(task_id)
        
        # 获取字段列表
        fields = await self.field_repository.get_by_task_id_async(task_id)
        
        # 生成字段统计
        field_statistics = []
        for field in fields:
            stat = await self._generate_field_statistics(field, total_responses)
            field_statistics.append(stat)
        
        return SurveyReportDto(
            task_id=task_id,
            task_name=task.name,
            total_responses=total_responses,
            field_statistics=field_statistics
        )

    async def _generate_field_statistics(
        self, 
        field: SurveyField, 
        total_responses: int
    ) -> FieldStatisticsDto:
        """生成字段统计"""
        
        # 获取字段的所有回答值
        values = await self.response_detail_repository.get_field_values_async(
            field.task_id, field.id
        )
        
        # 过滤空值
        non_empty_values = [v for v in values if v and v.strip()]
        
        if field.type in [SurveyFieldType.RADIO, SurveyFieldType.SELECT]:
            # 单选类型统计
            option_stats = self._calculate_option_statistics(field, non_empty_values, total_responses)
            return FieldStatisticsDto(
                field_id=field.id,
                field_key=field.field_key,
                field_name=field.name,
                field_type=field.type,
                stat_type="option",
                option_stats=option_stats
            )
        
        elif field.type == SurveyFieldType.CHECKBOX:
            # 多选类型统计
            option_stats = self._calculate_checkbox_statistics(field, non_empty_values, total_responses)
            return FieldStatisticsDto(
                field_id=field.id,
                field_key=field.field_key,
                field_name=field.name,
                field_type=field.type,
                stat_type="option",
                option_stats=option_stats
            )
        
        elif field.type in [SurveyFieldType.NUMBER, SurveyFieldType.RATING, SurveyFieldType.SLIDER]:
            # 数值类型统计
            numeric_stats = self._calculate_numeric_statistics(non_empty_values)
            return FieldStatisticsDto(
                field_id=field.id,
                field_key=field.field_key,
                field_name=field.name,
                field_type=field.type,
                stat_type="numeric",
                numeric_stats=numeric_stats
            )
        
        else:
            # 文本类型统计
            return FieldStatisticsDto(
                field_id=field.id,
                field_key=field.field_key,
                field_name=field.name,
                field_type=field.type,
                stat_type="text",
                text_responses=non_empty_values[:50]  # 限制显示前50条
            )

    def _calculate_option_statistics(
        self, 
        field: SurveyField, 
        values: List[str], 
        total_responses: int
    ) -> List[OptionStatisticsDto]:
        """计算选项统计"""
        
        # 获取字段配置中的选项
        options = self._get_field_options(field)
        
        # 统计每个选项的选择次数
        value_counts = Counter(values)
        
        option_stats = []
        for option in options:
            count = value_counts.get(option.value, 0)
            percentage = (count / total_responses * 100) if total_responses > 0 else 0
            
            stat = OptionStatisticsDto(
                value=option.value,
                label=option.label,
                count=count,
                percentage=round(percentage, 2)
            )
            option_stats.append(stat)
        
        # 添加其他选项（不在预定义选项中的）
        predefined_values = {opt.value for opt in options}
        other_values = set(values) - predefined_values
        
        for value in other_values:
            count = value_counts[value]
            percentage = (count / total_responses * 100) if total_responses > 0 else 0
            
            stat = OptionStatisticsDto(
                value=value,
                label=value,
                count=count,
                percentage=round(percentage, 2)
            )
            option_stats.append(stat)
        
        return sorted(option_stats, key=lambda x: x.count, reverse=True)

    def _calculate_checkbox_statistics(
        self, 
        field: SurveyField, 
        values: List[str], 
        total_responses: int
    ) -> List[OptionStatisticsDto]:
        """计算多选框统计"""
        
        # 获取字段配置中的选项
        options = self._get_field_options(field)
        
        # 解析多选值（假设用逗号分隔）
        all_selected_values = []
        for value in values:
            if value:
                selected = [v.strip() for v in value.split(',')]
                all_selected_values.extend(selected)
        
        # 统计每个选项的选择次数
        value_counts = Counter(all_selected_values)
        
        option_stats = []
        for option in options:
            count = value_counts.get(option.value, 0)
            percentage = (count / total_responses * 100) if total_responses > 0 else 0
            
            stat = OptionStatisticsDto(
                value=option.value,
                label=option.label,
                count=count,
                percentage=round(percentage, 2)
            )
            option_stats.append(stat)
        
        return sorted(option_stats, key=lambda x: x.count, reverse=True)

    def _calculate_numeric_statistics(self, values: List[str]) -> NumericStatisticsDto:
        """计算数值统计"""
        
        # 转换为数值
        numeric_values = []
        for value in values:
            try:
                numeric_values.append(float(value))
            except (ValueError, TypeError):
                continue
        
        if not numeric_values:
            return NumericStatisticsDto(
                average=0,
                min=0,
                max=0,
                median=0,
                distribution={}
            )
        
        # 计算统计值
        avg = statistics.mean(numeric_values)
        min_val = min(numeric_values)
        max_val = max(numeric_values)
        median_val = statistics.median(numeric_values)
        
        # 计算分布（按整数分组）
        distribution = Counter(int(v) for v in numeric_values)
        
        return NumericStatisticsDto(
            average=round(avg, 2),
            min=min_val,
            max=max_val,
            median=median_val,
            distribution=dict(distribution)
        )

    def _get_field_options(self, field: SurveyField) -> List[OptionDto]:
        """获取字段选项"""
        
        if not field.config:
            return []
        
        try:
            config = json.loads(field.config)
            options_data = config.get('options', [])
            
            options = []
            for opt_data in options_data:
                if isinstance(opt_data, dict):
                    option = OptionDto(
                        value=opt_data.get('value'),
                        label=opt_data.get('label')
                    )
                    options.append(option)
            
            return options
        except (json.JSONDecodeError, TypeError):
            return []