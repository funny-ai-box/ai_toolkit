"""
面试问题服务实现

提供面试问题业务逻辑实现，包括问题的查询、更新以及基于AI生成面试问题等功能。
"""
import logging
from typing import List, Optional, Dict, Any
import datetime

from app.core.exceptions import BusinessException, NotFoundException, ValidationException, ForbiddenException
from app.core.dtos import ApiResponse, PagedResultDto

from app.modules.tools.interview.models import InterviewQuestion, JobPosition
from app.modules.tools.interview.enums import QuestionDifficulty, JobPositionQuestionStatusType
from app.modules.tools.interview.dtos import (
    QuestionDetailDto,
    QuestionsListRequestDto,
    QuestionListItemDto,
    QuestionsUpdateRequestDto,
    AIQuestionResponseDto,
    InterviewScenarioContentItemDto
)
from app.modules.tools.interview.repositories.scenario_repository import InterviewScenarioRepository
from app.modules.tools.interview.repositories.job_position_repository import JobPositionRepository
from app.modules.tools.interview.repositories.question_repository import InterviewQuestionRepository
from app.modules.tools.interview.services.ai_question_service import AIQuestionService


class InterviewQuestionService:
    """面试问题服务"""
    
    def __init__(
        self,
        logger: logging.Logger,
        scenario_repository: InterviewScenarioRepository,
        position_repository: JobPositionRepository,
        question_repository: InterviewQuestionRepository,
        ai_service: AIQuestionService
    ):
        """
        初始化面试问题服务
        
        Args:
            logger: 日志记录器
            scenario_repository: 场景仓储
            position_repository: 职位仓储
            question_repository: 问题仓储
            ai_service: AI生成问题服务
        """
        self.logger = logger
        self.scenario_repository = scenario_repository
        self.position_repository = position_repository
        self.question_repository = question_repository
        self.ai_service = ai_service
    
    async def get_question_async(self, user_id: int, question_id: int) -> QuestionDetailDto:
        """
        获取问题详情
        
        Args:
            user_id: 用户ID
            question_id: 问题ID
            
        Returns:
            问题详情
        """
        try:
            # 获取问题
            question = await self.question_repository.get_by_id_async(question_id)
            if not question:
                raise NotFoundException("面试问题不存在")
            
            # 验证权限
            scenario = await self.scenario_repository.get_by_id_async(question.scenario_id)
            if not scenario or scenario.user_id != user_id:
                raise ForbiddenException("无权访问此面试问题")
            
            # 获取职位信息
            position = await self.position_repository.get_by_id_async(question.job_position_id)
            if not position:
                raise NotFoundException("面试职位不存在")
            
            # 返回详情
            return QuestionDetailDto(
                id=question.id,
                scenario_id=question.scenario_id,
                job_position_id=question.job_position_id,
                job_position_name=position.name,
                content=question.content or "",
                standard_answer=question.standard_answer or "",
                question_type=question.question_type,
                difficulty=question.difficulty,
                sort_order=question.sort_order
            )
        except (NotFoundException, ForbiddenException):
            raise
        except Exception as e:
            print(f"获取面试问题详情时发生错误: {str(e)}", exc_info=True)
            raise BusinessException("获取面试问题详情失败")
    
    async def get_questions_async(self, user_id: int, request: QuestionsListRequestDto) -> PagedResultDto[QuestionListItemDto]:
        """
        获取场景的问题列表
        
        Args:
            user_id: 用户ID
            request: 列表请求
            
        Returns:
            问题列表和总数
        """
        try:
            # 验证权限
            scenario = await self.scenario_repository.get_by_id_async(request.scenario_id)
            if not scenario or scenario.user_id != user_id:
                raise ForbiddenException("无权访问此面试场景")
            
            # 获取问题列表
            questions, total_count = await self.question_repository.get_questions_async(
                request.scenario_id,
                request.job_position_id,
                request.difficulty,
                request.page_index,
                request.page_size
            )
            
            # 获取职位信息
            position_map = {}
            position_ids = set(q.job_position_id for q in questions)
            for position_id in position_ids:
                position = await self.position_repository.get_by_id_async(position_id)
                if position:
                    position_map[position_id] = position.name
            
            # 转换为DTO
            items = [
                QuestionListItemDto(
                    id=q.id,
                    job_position_id=q.job_position_id,
                    job_position_name=position_map.get(q.job_position_id, "未知职位"),
                    content=q.content or "",
                    short_answer=self._truncate_answer(q.standard_answer or "", 100),
                    question_type=q.question_type,
                    difficulty=q.difficulty,
                    sort_order=q.sort_order
                )
                for q in questions
            ]
            
            # 返回分页结果
            return PagedResultDto[QuestionListItemDto](
                items=items,
                total_count=total_count,
                page_index=request.page_index,
                page_size=request.page_size,
                total_pages=(total_count + request.page_size - 1) // request.page_size
            )
        except ForbiddenException:
            raise
        except Exception as e:
            print(f"获取面试问题列表时发生错误: {str(e)}", exc_info=True)
            raise BusinessException("获取面试问题列表失败")
    
    async def generate_questions_async(self, scenario_id: int, content_dtls: List[InterviewScenarioContentItemDto]) -> None:
        """
        生成面试问题（AI分析）
        
        Args:
            scenario_id: 场景ID
            content_dtls: 文档内容明细
            
        Returns:
            None
        """
        try:
            # 获取场景信息
            scenario = await self.scenario_repository.get_by_id_async(scenario_id)
            if not scenario:
                raise NotFoundException("面试场景不存在")
            
            # 获取职位列表
            positions = await self.position_repository.get_by_scenario_id_async(scenario_id)
            if not positions:
                raise ValidationException("面试场景没有关联的职位")
            
            # 合并所有内容
            document_content = ""
            for content in content_dtls:
                if content.source_content:
                    document_content += content.source_content
                    document_content += "\n"
            
            if not document_content:
                raise NotFoundException("面试场景还未上传文档内容")
            
            # 为每个职位生成问题
            for position in positions:
                # AI生成面试问题
                status, msg, ai_questions = await self.ai_service.generate_questions_for_position(
                    scenario, position, document_content
                )
                
                if status and ai_questions:
                    # 删除旧问题
                    await self.question_repository.delete_by_scenario_job_id_async(scenario_id, position.id)
                    
                    # 批量保存问题
                    questions = []
                    for question_dto in ai_questions:
                        question = InterviewQuestion(
                            scenario_id=scenario_id,
                            job_position_id=position.id,
                            content=question_dto.content,
                            standard_answer=question_dto.answer,
                            question_type=question_dto.type,
                            sort_order=question_dto.sort_order,
                            difficulty=question_dto.difficulty
                        )
                        questions.append(question)
                    
                    await self.question_repository.batch_add_async(questions)
                    
                    # 更新职位的问题生成状态
                    await self.position_repository.update_status_async(
                        position.id, 
                        JobPositionQuestionStatusType.COMPLETED
                    )
                else:
                    # 更新职位的问题生成状态
                    await self.position_repository.update_status_async(
                        position.id,
                        JobPositionQuestionStatusType.FAILED,
                        msg
                    )
        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            print(f"生成面试问题时发生错误: {str(e)}", exc_info=True)
            raise BusinessException(f"生成面试问题时发生错误: {str(e)}")
    
    async def update_question_async(self, user_id: int, request: QuestionsUpdateRequestDto) -> bool:
        """
        更新问题
        
        Args:
            user_id: 用户ID
            request: 请求DTO
            
        Returns:
            操作结果
        """
        try:
            # 获取问题
            question = await self.question_repository.get_by_id_async(request.question_id)
            if not question:
                raise NotFoundException("面试问题不存在")
            
            # 验证权限
            scenario = await self.scenario_repository.get_by_id_async(question.scenario_id)
            if not scenario or scenario.user_id != user_id:
                raise ForbiddenException("无权修改此面试问题")
            
            # 更新问题
            question.content = request.content
            question.standard_answer = request.answer
            
            return await self.question_repository.update_async(question)
        except (NotFoundException, ForbiddenException):
            raise
        except Exception as e:
            print(f"更新面试问题时发生错误: {str(e)}", exc_info=True)
            raise BusinessException("更新面试问题失败")
    
    def _truncate_answer(self, answer: str, max_length: int) -> str:
        """
        截断答案文本
        
        Args:
            answer: 完整答案
            max_length: 最大长度
            
        Returns:
            截断后的答案
        """
        if not answer:
            return ""
        
        if len(answer) <= max_length:
            return answer
        
        return answer[:max_length] + "..."