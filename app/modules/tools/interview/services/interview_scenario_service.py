"""
面试场景服务实现

提供面试场景业务逻辑实现，包括场景的创建、查询、更新和删除等功能。
"""
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime


from app.core.exceptions import BusinessException, NotFoundException, ValidationException, ForbiddenException
from app.core.dtos import ApiResponse, PagedResultDto

from app.modules.base.knowledge.dtos import DocumentStatus
from app.modules.base.knowledge.services.document_service import DocumentService

from app.modules.tools.interview.models import (
    InterviewScenario, 
    JobPosition, 
    InterviewScenarioContent,
    InterviewQuestion
)
from app.modules.tools.interview.enums import (
    InterviewScenarioStatus,
    InterviewContentType,
    QuestionDifficulty,
    JobPositionQuestionStatusType
)
from app.modules.tools.interview.dtos import (
    CreateScenarioRequestDto,
    ScenarioCreationResultDto,
    JobPositionDto,
    ScenarioListRequestDto,
    ScenarioListItemDto,
    ScenarioDetailDto,
    JobPositionResponseDto,
    ScenarioContentItemDto,
    ImportInterviewTextRequestDto,
    InterviewScenarioContentItemDto
)
from app.modules.tools.interview.repositories.scenario_repository import InterviewScenarioRepository
from app.modules.tools.interview.repositories.job_position_repository import JobPositionRepository
from app.modules.tools.interview.repositories.question_repository import InterviewQuestionRepository
from app.modules.tools.interview.repositories.scenario_content_repository import InterviewScenarioContentRepository
from app.modules.tools.interview.services.interview_question_service import InterviewQuestionService


class InterviewScenarioService:
    """面试场景服务"""
    
    def __init__(
        self,
        logger: logging.Logger,
        scenario_repository: InterviewScenarioRepository,
        position_repository: JobPositionRepository,
        question_repository: InterviewQuestionRepository,
        scenario_content_repository: InterviewScenarioContentRepository,
        document_service: DocumentService,
        question_service: InterviewQuestionService
    ):
        """
        初始化面试场景服务
        
        Args:
            logger: 日志记录器
            scenario_repository: 场景仓储
            position_repository: 职位仓储
            question_repository: 问题仓储
            scenario_content_repository: 场景内容仓储
            document_service: 文档服务
            question_service: 问题服务
        """
        self.logger = logger
        self.scenario_repository = scenario_repository
        self.position_repository = position_repository
        self.question_repository = question_repository
        self.scenario_content_repository = scenario_content_repository
        self.document_service = document_service
        self.question_service = question_service
    
    async def create_scenario_async(self, user_id: int, request: CreateScenarioRequestDto) -> ScenarioCreationResultDto:
        """
        创建面试场景
        
        Args:
            user_id: 用户ID
            request: 创建请求
            
        Returns:
            创建结果
        """
        try:
            if not request.job_positions:
                raise ValidationException("至少需要一个职位")
            print("****************")
            print(request.interviewer_gender.value)
            print("****************")
            # 创建面试场景
            scenario = InterviewScenario(
                user_id=user_id,
                name=request.name,
                description=request.description,
                interviewer_name=request.interviewer_name,
                interviewer_gender=request.interviewer_gender.value,
                status=InterviewScenarioStatus.INIT.value
            )
            
            scenario = await self.scenario_repository.add_async(scenario)
            
            # 创建职位
            positions = []
            for position_dto in request.job_positions:
                position = JobPosition(
                    scenario_id=scenario.id,
                    name=position_dto.name,
                    level=position_dto.level.value,
                    question_status=JobPositionQuestionStatusType.PENDING.value
                )
                positions.append(position)
            
            created_positions = await self.position_repository.batch_add_async(positions)
            
            # 返回创建结果
            position_dtos = [
                JobPositionDto(
                    id=p.id,
                    name=p.name,
                    level=p.level
                )
                for p in created_positions
            ]
            
            return ScenarioCreationResultDto(
                id=scenario.id,
                name=scenario.name,
                status=scenario.status,
                job_positions=position_dtos
            )
        except ValidationException:
            raise
        except Exception as e:
            print(f"创建面试场景时发生错误: {str(e)}")
            raise BusinessException("创建面试场景失败")
    
    async def add_scenario_content_async(
        self, 
        user_id: int, 
        scenario_id: int, 
        content_type: InterviewContentType,
        source_document_id: int, 
        source_content: str
    ) -> int:
        """
        给面试添加内容
        
        Args:
            user_id: 用户ID
            scenario_id: 场景Id
            content_type: 内容类型
            source_document_id: 文档Id
            source_content: 文本内容
            
        Returns:
            内容项ID
        """
        try:
            # 检查场景是否存在
            scenario = await self.scenario_repository.get_by_id_async(scenario_id)
            if not scenario or scenario.user_id != user_id:
                raise NotFoundException("面试场景不存在或无权访问")
            
            # 创建内容项
            content_item = InterviewScenarioContent(
                user_id=user_id,
                scenario_id=scenario_id,
                content_type=content_type,
                source_document_id=source_document_id,
                source_content=source_content
            )
            
            content_id = await self.scenario_content_repository.add_async(content_item)
            return content_id
        except NotFoundException:
            raise
        except Exception as e:
            print(f"创建内容失败: {str(e)}")
            raise BusinessException("创建内容失败")
    
    async def delete_scenario_content_async(self, user_id: int, content_id: int) -> bool:
        """
        删除场景的内容
        
        Args:
            user_id: 用户ID
            content_id: 内容Id
            
        Returns:
            操作结果
        """
        try:
            content = await self.scenario_content_repository.get_by_id_async(content_id)
            if not content:
                raise NotFoundException("内容不存在或您没有访问权限")
            
            scenario = await self.scenario_repository.get_by_id_async(content.scenario_id)
            if not scenario or scenario.user_id != user_id:
                raise NotFoundException("面试场景不存在或无权访问")
            
            return await self.scenario_content_repository.delete_async(content_id)
        except NotFoundException:
            raise
        except Exception as e:
            print(f"删除内容失败，ID: {content_id}")
            raise BusinessException(f"删除内容失败: {str(e)}")
    
    async def get_scenario_content_detail_async(self, user_id: int, content_id: int) -> InterviewScenarioContentItemDto:
        """
        获取场景内容的详情
        
        Args:
            user_id: 用户ID
            content_id: 内容ID
            
        Returns:
            内容详情
        """
        try:
            content = await self.scenario_content_repository.get_by_id_async(content_id)
            if not content:
                raise NotFoundException("内容不存在或您没有访问权限")
            
            scenario = await self.scenario_repository.get_by_id_async(content.scenario_id)
            if not scenario or scenario.user_id != user_id:
                raise NotFoundException("面试场景不存在或无权访问")
            
            # 构建响应DTO
            content_item = InterviewScenarioContentItemDto(
                id=content.id,
                content_type=content.content_type,
                source_document_id=content.source_document_id,
                source_content=content.source_content,
                source_document_title=None,
                source_document_original_name=None,
                source_document_source_url=None,
                source_document_status=DocumentStatus.COMPLETED.value,
                source_document_process_message=None,
                create_date=content.create_date
            )
            
            # 如果有文档ID，获取文档信息
            if content.source_document_id > 0:
                document = await self.document_service.get_document_async(user_id, content.source_document_id)
                if document:
                    content_item.source_content = document.content  # 文档的内容
                    content_item.source_document_title = document.title
                    content_item.source_document_source_url = document.source_url
                    content_item.source_document_process_message = document.process_message
                    content_item.source_document_original_name = document.original_name
                    content_item.source_document_status = document.status.value
            
            return content_item
        except NotFoundException:
            raise
        except Exception as e:
            print(f"获取内容的详情失败，ID: {content_id}")
            raise BusinessException("获取内容的详情失败")
    
    async def get_scenario_async(self, user_id: int, scenario_id: int) -> ScenarioDetailDto:
        """
        获取面试场景详情
        
        Args:
            user_id: 用户ID
            scenario_id: 场景ID
            
        Returns:
            场景详情
        """
        try:
            # 获取场景
            scenario = await self.scenario_repository.get_by_id_async(scenario_id)
            if not scenario or scenario.user_id != user_id:
                raise NotFoundException("面试场景不存在或无权访问")
            
            # 获取职位
            positions = await self.position_repository.get_by_scenario_id_async(scenario_id)
            position_dtos = [
                JobPositionResponseDto(
                    id=p.id,
                    name=p.name,
                    level=p.level,
                    question_status=p.question_status,
                    error_message=p.error_message
                )
                for p in positions
            ]
            
            # 获取内容项
            content_items = await self.scenario_content_repository.get_by_scenario_id_async(scenario_id)
            content_dtos = []
            
            # 处理内容项
            for content_item in content_items:
                content_dto = ScenarioContentItemDto(
                    id=content_item.id,
                    content_type=content_item.content_type,
                    source_document_id=content_item.source_document_id,
                    source_content=content_item.source_content,
                    source_document_title=None,
                    source_document_original_name=None,
                    source_document_source_url=None,
                    source_document_status=DocumentStatus.COMPLETED.value,
                    source_document_process_message=None,
                    create_date=content_item.create_date
                )
                
                # 如果有文档ID，获取文档信息
                if content_item.source_document_id > 0:
                    document = await self.document_service.get_document_async(user_id, content_item.source_document_id)
                    if document:
                        content_dto.source_document_title = document.title
                        content_dto.source_document_original_name = document.original_name
                        content_dto.source_document_source_url = document.source_url
                        content_dto.source_document_status = document.status.value
                        content_dto.source_document_process_message = document.process_message
                
                content_dtos.append(content_dto)
            
            # 构建场景详情DTO
            result = ScenarioDetailDto(
                id=scenario.id,
                name=scenario.name,
                description=scenario.description,
                interviewer_name=scenario.interviewer_name,
                interviewer_gender=scenario.interviewer_gender,
                status=scenario.status,
                job_positions=position_dtos,
                content_items=content_dtos,
                create_date=scenario.create_date,
                last_modify_date=scenario.last_modify_date
            )
            
            return result
        except NotFoundException:
            raise
        except Exception as e:
            print(f"获取面试场景详情时发生错误: {str(e)}")
            raise BusinessException("获取面试场景详情失败")
    
    async def get_user_scenarios_async(self, user_id: int, request: ScenarioListRequestDto) -> PagedResultDto[ScenarioListItemDto]:
        """
        获取用户的面试场景列表
        
        Args:
            user_id: 用户ID
            request: 列表请求
            
        Returns:
            场景列表和总数
        """
        try:
            # 获取场景列表
            scenarios, total_count = await self.scenario_repository.get_user_scenarios_async(
                user_id,
                request.name,
                request.status,
                request.page_index,
                request.page_size
            )
            
            # 获取场景对应的职位数量
            scenario_ids = [s.id for s in scenarios]
            position_counts = {}
            content_counts = {}
            
            if scenario_ids:
                # 获取内容数量
                content_items = await self.scenario_content_repository.get_by_scenario_ids_async(scenario_ids)
                
                for scenario_id in scenario_ids:
                    # 获取职位数量
                    positions = await self.position_repository.get_by_scenario_id_async(scenario_id)
                    position_counts[scenario_id] = len(positions)
                    
                    # 获取内容数量
                    scenario_content_items = [c for c in content_items if c.scenario_id == scenario_id]
                    content_counts[scenario_id] = len(scenario_content_items)
            
            # 转换为DTO
            items = [
                ScenarioListItemDto(
                    id=s.id,
                    name=s.name,
                    description=s.description,
                    interviewer_name=s.interviewer_name,
                    interviewer_gender=s.interviewer_gender,
                    job_position_count=position_counts.get(s.id, 0),
                    content_item_count=content_counts.get(s.id, 0),
                    status=s.status,
                    create_date=s.create_date
                )
                for s in scenarios
            ]
            
            # 返回分页结果
            return PagedResultDto[ScenarioListItemDto](
                items=items,
                total_count=total_count,
                page_index=request.page_index,
                page_size=request.page_size,
                total_pages=(total_count + request.page_size - 1) // request.page_size
            )
        except Exception as e:
            print(f"获取面试场景列表时发生错误: {str(e)}")
            raise BusinessException("获取面试场景列表失败")
    
    async def delete_scenario_async(self, user_id: int, scenario_id: int) -> bool:
        """
        删除面试场景
        
        Args:
            user_id: 用户ID
            scenario_id: 场景ID
            
        Returns:
            操作结果
        """
        try:
            # 获取场景
            scenario = await self.scenario_repository.get_by_id_async(scenario_id)
            if not scenario or scenario.user_id != user_id:
                raise NotFoundException("面试场景不存在或无权访问")
            
            # 删除职位
            await self.position_repository.delete_by_scenario_id_async(scenario_id)
            
            # 删除问题
            await self.question_repository.delete_by_scenario_id_async(scenario_id)
            
            # 删除内容项
            await self.scenario_content_repository.delete_by_scenario_id_async(scenario_id)
            
            # 删除场景
            result = await self.scenario_repository.delete_async(scenario_id)
            
            return result
        except NotFoundException:
            raise
        except Exception as e:
            print(f"删除面试场景时发生错误: {str(e)}")
            raise BusinessException("删除面试场景失败")
    
    async def start_analysis_question_async(self, user_id: int, scenario_id: int) -> bool:
        """
        开始分析问题和生成面试问题
        
        Args:
            user_id: 用户ID
            scenario_id: 场景Id
            
        Returns:
            操作结果
        """
        try:
            scenario = await self.scenario_repository.get_by_id_async(scenario_id)
            if not scenario or scenario.user_id != user_id:
                raise NotFoundException("面试场景不存在或无权访问")
            
            # 检查文档解析是否完成
            contents = await self.scenario_content_repository.get_by_scenario_id_async(scenario_id)
            if not contents:
                raise BusinessException("面试场景还未上传内容")
            
            doc_ids = [c.source_document_id for c in contents if c.source_document_id > 0]
            if doc_ids:
                doc_statuses = await self.document_service.get_document_status_async(user_id, doc_ids)
                if any(s.status != DocumentStatus.COMPLETED for s in doc_statuses):
                    raise BusinessException("文档内容未解析完成")
            
            # 检查状态
            if scenario.status not in [InterviewScenarioStatus.INIT, InterviewScenarioStatus.READY, InterviewScenarioStatus.FAILED]:
                raise BusinessException("面试场景分析正在处理中，请稍后再试")
            
            if scenario.generate_count > 5:
                raise BusinessException("该任务生成已超过5次，不可再生成")
            
            return await self.scenario_repository.start_analysis_question_async(scenario_id)
        except NotFoundException:
            raise
        except BusinessException:
            raise
        except Exception as e:
            print(f"开始分析问题和生成面试问题时发生错误: {str(e)}")
            print(f"面试问题生成失败，ID: {scenario_id}")
            raise BusinessException("面试问题生成失败")
    
    async def process_generate_questions_async(self, scenario_id: int) -> None:
        """
        调度任务异步处理面试场景的问题生成
        
        Args:
            scenario_id: 场景Id
            
        Returns:
            None
            
        Raises:
            NotFoundException: 面试场景不存在
        """
        # 获取场景信息
        scenario = await self.scenario_repository.get_by_id_async(scenario_id)
        if not scenario:
            raise NotFoundException("面试场景不存在")
        
        try:
            # 更新状态为处理中
            if not await self.scenario_repository.lock_processing_status_async(scenario_id):
                raise BusinessException("面试问题正在处理中，请稍后再试")
            
            # 获取上传的问题项
            content_dtls = []
            content_items = await self.scenario_content_repository.get_by_scenario_id_async(scenario_id)
            for content_item in content_items:
                # 获取内容的具体文档
                scenario_content = await self.get_scenario_content_detail_async(scenario.user_id, content_item.id)
                content_dtls.append(scenario_content)
            
            # 调用问题生成服务
            await self.question_service.generate_questions_async(scenario.id, content_dtls)
            
            # 更新场景状态
            await self.scenario_repository.update_status_async(scenario.id, InterviewScenarioStatus.READY)
        except Exception as e:
            err = f"生成面试问题时发生错误: {str(e)}"
            print(err)
            await self.scenario_repository.update_status_async(scenario.id, InterviewScenarioStatus.FAILED, err)