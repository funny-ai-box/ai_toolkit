"""
面试会话服务实现

提供面试会话业务逻辑实现，包括会话的创建、开始、结束、评估以及保存交互记录等功能。
"""
import logging
import base64
import io
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime


from app.core.exceptions import BusinessException, NotFoundException, ValidationException, ForbiddenException
from app.core.dtos import ApiResponse, PagedResultDto
from app.core.storage.base import IStorageService, StorageProviderType

from app.modules.tools.interview.models import (
    InterviewSession,
    InterviewInteraction,
    InterviewScenario,
    JobPosition
)
from app.modules.tools.interview.enums import (
    InterviewSessionStatus,
    InterviewSessionEvaluateStatusType
)
from app.modules.tools.interview.dtos import (
    CreateInterviewSessionRequestDto,
    InterviewSessionInfoDto,
    StartSessionRequestDto,
    EndSessionRequestDto,
    InterviewSessionListRequestDto,
    InterviewSessionListItemDto,
    InterviewSessionDetailDto,
    SaveInteractionRequestDto,
    EvaluateSessionRequestDto,
    EvaluationResultDto,
    AnswerEvaluationDto,
    RealTimeConnectionInfoDto,
    QuestionListItemDto,
    InteractionDto
)
from app.modules.tools.interview.repositories.session_repository import InterviewSessionRepository
from app.modules.tools.interview.repositories.interaction_repository import InterviewInteractionRepository
from app.modules.tools.interview.repositories.scenario_repository import InterviewScenarioRepository
from app.modules.tools.interview.repositories.job_position_repository import JobPositionRepository
from app.modules.tools.interview.repositories.question_repository import InterviewQuestionRepository
from app.modules.tools.interview.services.ai_realtime_service import AIRealTimeService
from app.modules.tools.interview.services.ai_evaluate_answer_service import AIEvaluateAnswerService


class InterviewSessionService:
    """面试会话服务"""
    
    def __init__(
        self,
        logger: logging.Logger,
        session_repository: InterviewSessionRepository,
        interaction_repository: InterviewInteractionRepository,
        scenario_repository: InterviewScenarioRepository,
        position_repository: JobPositionRepository,
        question_repository: InterviewQuestionRepository,
        real_time_service: AIRealTimeService,
        evaluate_service: AIEvaluateAnswerService,
        storage_service: IStorageService
    ):
        """
        初始化面试会话服务
        
        Args:
            logger: 日志记录器
            session_repository: 会话仓储
            interaction_repository: 交互记录仓储
            scenario_repository: 场景仓储
            position_repository: 职位仓储
            question_repository: 问题仓储
            real_time_service: AI实时交互服务
            evaluate_service: AI评估服务
            storage_service: 存储服务
        """
        self.logger = logger
        self.session_repository = session_repository
        self.interaction_repository = interaction_repository
        self.scenario_repository = scenario_repository
        self.position_repository = position_repository
        self.question_repository = question_repository
        self.real_time_service = real_time_service
        self.evaluate_service = evaluate_service
        self.storage_service = storage_service
    
    async def create_session_async(self, user_id: int, request: CreateInterviewSessionRequestDto) -> InterviewSessionInfoDto:
        """
        创建面试会话
        
        Args:
            user_id: 用户ID
            request: 创建请求
            
        Returns:
            会话信息
        """
        try:
            # 验证场景和职位
            scenario = await self.scenario_repository.get_by_id_async(request.scenario_id)
            if not scenario:
                raise NotFoundException("面试场景不存在")
            
            # 验证场景状态
            if scenario.status != 3:  # InterviewScenarioStatus.READY
                raise ValidationException(f"面试场景状态不可用，当前状态: {scenario.status}")
            
            # 验证职位
            position = await self.position_repository.get_by_id_async(request.job_position_id)
            if not position or position.scenario_id != request.scenario_id:
                raise NotFoundException("面试职位不存在或不属于指定场景")
            
            # 创建会话
            session = InterviewSession(
                interviewee_id=user_id,
                scenario_id=request.scenario_id,
                job_position_id=request.job_position_id,
                status=InterviewSessionStatus.NOT_STARTED
            )
            
            session = await self.session_repository.add_async(session)
            
            # 返回会话信息
            return InterviewSessionInfoDto(
                id=session.id,
                scenario_id=session.scenario_id,
                scenario_name=scenario.name,
                interviewer_name=scenario.interviewer_name,
                job_position_id=session.job_position_id,
                job_position_name=position.name,
                status=session.status
            )
        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            print(f"创建面试会话时发生错误: {str(e)}")
            raise BusinessException("创建面试会话失败")
    
    async def start_session_async(self, user_id: int, request: StartSessionRequestDto) -> RealTimeConnectionInfoDto:
        """
        开始面试会话
        
        Args:
            user_id: 用户ID
            request: 开始请求
            
        Returns:
            会话连接信息
        """
        try:
            # 获取会话
            session = await self.session_repository.get_by_id_async(request.session_id)
            if not session or session.interviewee_id != user_id:
                raise NotFoundException("面试会话不存在或无权访问")
            
            # 验证会话状态
            if session.status != InterviewSessionStatus.NOT_STARTED:
                raise ValidationException(f"面试会话状态不正确，当前状态: {session.status}")
            
            # 获取场景和职位信息
            scenario = await self.scenario_repository.get_by_id_async(session.scenario_id)
            position = await self.position_repository.get_by_id_async(session.job_position_id)
            
            if not scenario or not position:
                raise NotFoundException("面试场景或职位不存在")
            
            # 获取问题列表
            questions = await self.question_repository.get_questions_by_position_async(session.scenario_id, session.job_position_id)
            
            # 创建OpenAI RealTime会话
            session_token = await self.real_time_service.create_realtime_session_async(session.id, request.noise_reduction)
            
            # 返回连接信息
            result = RealTimeConnectionInfoDto(
                session_token=session_token,
                session_info=InterviewSessionInfoDto(
                    id=session.id,
                    scenario_id=session.scenario_id,
                    scenario_name=scenario.name,
                    interviewer_name=scenario.interviewer_name,
                    job_position_id=session.job_position_id,
                    job_position_name=position.name,
                    status=session.status,
                    openai_session_token=session_token
                ),
                questions=[
                    QuestionListItemDto(
                        id=q.id,
                        job_position_id=q.job_position_id,
                        job_position_name=position.name,
                        content=q.content or "",
                        short_answer=self._truncate_text(q.standard_answer or "", 100),
                        question_type=q.question_type,
                        difficulty=q.difficulty,
                        sort_order=q.sort_order
                    )
                    for q in questions
                ]
            )
            
            return result
        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            print(f"开始面试会话时发生错误: {str(e)}")
            raise BusinessException("开始面试会话失败")
    
    async def end_session_async(self, user_id: int, request: EndSessionRequestDto) -> bool:
        """
        结束面试会话
        
        Args:
            user_id: 用户ID
            request: 结束请求
            
        Returns:
            操作结果
        """
        try:
            # 获取会话
            session = await self.session_repository.get_by_id_async(request.session_id)
            if not session or session.interviewee_id != user_id:
                raise NotFoundException("面试会话不存在或无权访问")
            
            # 验证会话状态
            if session.status != InterviewSessionStatus.IN_PROGRESS:
                raise ValidationException(f"面试会话状态不正确，当前状态: {session.status}")
            
            # 更新会话状态
            session.status = InterviewSessionStatus.COMPLETED
            session.end_time = datetime.now()
            
            # 保存更新
            return await self.session_repository.update_async(session)
        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            print(f"结束面试会话时发生错误: {str(e)}")
            raise BusinessException("结束面试会话失败")
    
    async def get_session_async(self, user_id: int, session_id: int) -> InterviewSessionDetailDto:
        """
        获取会话详情
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            
        Returns:
            会话详情
        """
        try:
            # 获取会话
            session = await self.session_repository.get_by_id_async(session_id)
            if not session or session.interviewee_id != user_id:
                raise NotFoundException("面试会话不存在或无权访问")
            
            # 获取场景和职位信息
            scenario = await self.scenario_repository.get_by_id_async(session.scenario_id)
            position = await self.position_repository.get_by_id_async(session.job_position_id)
            
            if not scenario or not position:
                raise NotFoundException("面试场景或职位不存在")
            
            # 获取交互记录
            interactions = await self.interaction_repository.get_by_session_id_async(session_id)
            
            # 计算持续时间（分钟）
            duration_minutes = None
            if session.start_time and session.end_time:
                duration = session.end_time - session.start_time
                duration_minutes = int((duration.total_seconds() + 59) // 60)  # 向上取整分钟
            
            # 构建会话详情
            result = InterviewSessionDetailDto(
                id=session.id,
                scenario_id=session.scenario_id,
                scenario_name=scenario.name,
                job_position_id=session.job_position_id,
                job_position_name=position.name,
                status=session.status,
                start_time=session.start_time,
                end_time=session.end_time,
                duration_minutes=duration_minutes,
                overall_score=session.overall_score,
                overall_evaluation=session.overall_evaluation,
                evaluate_status=session.evaluate_status,
                evaluate_count=session.evaluate_count,
                error_message=session.error_message,
                interactions=[
                    InteractionDto(
                        id=i.id,
                        question_id=i.question_id,
                        question=i.question,
                        answer=i.answer,
                        question_audio_url=i.question_audio_url,
                        answer_audio_url=i.answer_audio_url,
                        score=i.score,
                        evaluation=i.evaluation,
                        interaction_order=i.interaction_order,
                        create_date=i.create_date
                    )
                    for i in interactions
                ]
            )
            
            return result
        except NotFoundException:
            raise
        except Exception as e:
            print(f"获取面试会话详情时发生错误: {str(e)}")
            raise BusinessException("获取面试会话详情失败")
    
    async def get_user_sessions_async(self, user_id: int, request: InterviewSessionListRequestDto) -> PagedResultDto[InterviewSessionListItemDto]:
        """
        获取用户的会话列表
        
        Args:
            user_id: 用户ID
            request: 列表请求
            
        Returns:
            会话列表和总数
        """
        try:
            # 获取会话列表
            sessions, total_count = await self.session_repository.get_user_sessions_async(
                user_id,
                request.scenario_id,
                request.job_position_id,
                request.status,
                request.page_index,
                request.page_size
            )
            
            # 获取场景和职位信息
            scenario_map = {}
            position_map = {}
            
            # 收集所有需要查询的ID
            scenario_ids = set(s.scenario_id for s in sessions)
            position_ids = set(s.job_position_id for s in sessions)
            
            # 批量查询
            for scenario_id in scenario_ids:
                scenario = await self.scenario_repository.get_by_id_async(scenario_id)
                if scenario:
                    scenario_map[scenario_id] = scenario.name
            
            for position_id in position_ids:
                position = await self.position_repository.get_by_id_async(position_id)
                if position:
                    position_map[position_id] = position.name
            
            # 转换为DTO
            items = []
            for s in sessions:
                # 计算持续时间（分钟）
                duration_minutes = None
                if s.start_time and s.end_time:
                    duration = s.end_time - s.start_time
                    duration_minutes = int((duration.total_seconds() + 59) // 60)  # 向上取整分钟
                
                items.append(InterviewSessionListItemDto(
                    id=s.id,
                    scenario_name=scenario_map.get(s.scenario_id, "未知场景"),
                    job_position_name=position_map.get(s.job_position_id, "未知职位"),
                    status=s.status,
                    start_time=s.start_time,
                    end_time=s.end_time,
                    duration_minutes=duration_minutes,
                    overall_score=s.overall_score
                ))
            
            # 返回分页结果
            return PagedResultDto[InterviewSessionListItemDto](
                items=items,
                total_count=total_count,
                page_index=request.page_index,
                page_size=request.page_size,
                total_pages=(total_count + request.page_size - 1) // request.page_size
            )
        except Exception as e:
            print(f"获取用户会话列表时发生错误: {str(e)}")
            raise BusinessException("获取用户会话列表失败")
    
    async def save_interaction_async(self, request: SaveInteractionRequestDto) -> bool:
        """
        保存交互记录（面试过程中通过Function Call调用）
        
        Args:
            request: 保存交互记录请求
            
        Returns:
            操作结果
        """
        try:
            # 获取会话信息
            session = await self.session_repository.get_by_id_async(request.session_id)
            if not session:
                raise NotFoundException("面试会话不存在")
            
            # 检查会话状态
            if session.status != InterviewSessionStatus.IN_PROGRESS:
                session.status = InterviewSessionStatus.IN_PROGRESS
                await self.session_repository.update_async(session)
            
            # 处理音频数据
            question_audio_url = None
            answer_audio_url = None
            
            if request.question_audio_base64:
                question_audio_url = await self._save_audio_data(
                    request.question_audio_base64,
                    session.id,
                    request.interaction_order,
                    "question"
                )
            
            if request.answer_audio_base64:
                answer_audio_url = await self._save_audio_data(
                    request.answer_audio_base64,
                    session.id,
                    request.interaction_order,
                    "answer"
                )
            
            # 创建交互记录
            interaction = InterviewInteraction(
                session_id=request.session_id,
                question_id=request.question_id,
                question=request.question,
                answer=request.answer,
                question_audio_url=question_audio_url,
                answer_audio_url=answer_audio_url,
                interaction_order=request.interaction_order
            )
            
            await self.interaction_repository.add_async(interaction)
            return True
        except NotFoundException:
            raise
        except Exception as e:
            print(f"保存交互记录时发生错误: {str(e)}")
            raise BusinessException("保存交互记录失败")
    
    async def start_evaluate_session_async(self, user_id: int, request: EvaluateSessionRequestDto) -> bool:
        """
        开始评估面试
        
        Args:
            user_id: 用户ID
            request: 评估请求
            
        Returns:
            评估结果
        """
        try:
            # 获取会话
            session = await self.session_repository.get_by_id_async(request.session_id)
            if not session or session.interviewee_id != user_id:
                raise NotFoundException("面试会话不存在或无权访问")
            
            # 验证会话状态
            valid_statuses = [InterviewSessionStatus.COMPLETED, InterviewSessionStatus.EVALUATED]
            if session.status not in valid_statuses:
                raise ValidationException(f"面试会话状态不正确，当前状态: {session.status}，必须是已完成/已评估状态")
            
            # 获取场景和职位信息
            scenario = await self.scenario_repository.get_by_id_async(session.scenario_id)
            position = await self.position_repository.get_by_id_async(session.job_position_id)
            
            if not scenario or not position:
                raise NotFoundException("面试场景或职位不存在")
            
            # 获取所有交互记录
            interactions = await self.interaction_repository.get_by_session_id_async(request.session_id)
            if not interactions:
                raise ValidationException("面试会话没有交互记录，无法评估")
            
            # 检查状态
            if session.evaluate_status not in [
                InterviewSessionEvaluateStatusType.INIT,
                InterviewSessionEvaluateStatusType.COMPLETED,
                InterviewSessionEvaluateStatusType.FAILED
            ]:
                raise BusinessException("评估正在处理中，请稍后再试")
            
            if session.evaluate_count > 5:
                raise BusinessException("该评估已超过5次，不可再评估")
            
            return await self.session_repository.start_evaluate_session_async(request.session_id)
        except (NotFoundException, ValidationException, BusinessException):
            raise
        except Exception as e:
            print(f"评估面试时发生错误: {str(e)}")
            raise BusinessException("评估面试时发生错误")
    
    async def process_evaluate_session_async(self, session_id: int) -> EvaluationResultDto:
        """
        处理评估面试
        
        Args:
            session_id: 会话ID
            
        Returns:
            评估结果
        """
        try:
            # 获取会话
            session = await self.session_repository.get_by_id_async(session_id)
            if not session:
                raise NotFoundException("面试会话不存在或无权访问")
            
            # 更新状态为处理中
            if not await self.session_repository.lock_processing_status_async(session_id):
                raise BusinessException("面试评估正在处理中，请稍后再试")
            
            # 获取场景和职位信息
            scenario = await self.scenario_repository.get_by_id_async(session.scenario_id)
            position = await self.position_repository.get_by_id_async(session.job_position_id)
            if not scenario or not position:
                raise NotFoundException("面试场景或职位不存在")
            
            # 获取所有交互记录
            interactions = await self.interaction_repository.get_by_session_id_async(session_id)
            if not interactions:
                raise ValidationException("面试会话没有交互记录，无法评估")
            
            # 获取问题标准答案
            standard_answers = {}
            for interaction in interactions:
                if interaction.question_id:
                    if interaction.question_id not in standard_answers:
                        question = await self.question_repository.get_by_id_async(interaction.question_id)
                        if question:
                            standard_answers[interaction.question_id] = question.standard_answer
            
            # 为每个交互进行评估
            evaluations = []
            total_score = 0
            
            for interaction in interactions:
                # 获取标准答案
                standard_answer = ""
                if interaction.question_id and interaction.question_id in standard_answers:
                    standard_answer = standard_answers[interaction.question_id]
                
                # 评估回答
                success, score, evaluation = await self.evaluate_service.evaluate_answer(
                    interaction.question,
                    interaction.answer,
                    standard_answer,
                    position.level
                )
                
                # 更新交互记录
                interaction.score = score
                interaction.evaluation = evaluation
                interaction.evaluate_status = 1 if success else -1  # 1=评估完成，-1=评估失败
                await self.interaction_repository.update_async(interaction)
                
                # 添加到评估结果
                evaluations.append(AnswerEvaluationDto(
                    interaction_id=interaction.id,
                    question=interaction.question,
                    answer=interaction.answer,
                    score=score,
                    evaluation=evaluation or ""
                ))
                
                total_score += score
            
            # 计算总体评分和评价
            overall_score = total_score // len(interactions) if interactions else 0
            overall_evaluation = ""
            
            # 只有在存在成功评估的问题时才生成总体评价
            success_interactions = [i for i in interactions if i.evaluate_status == 1]
            if success_interactions:
                overall_evaluation = await self.evaluate_service.generate_overall_evaluation(interactions, position)
            else:
                overall_evaluation = "没有需要评估的面试题目"
            
            # 更新会话
            session.overall_score = overall_score
            session.overall_evaluation = overall_evaluation
            session.status = InterviewSessionStatus.EVALUATED
            session.evaluate_status = InterviewSessionEvaluateStatusType.COMPLETED
            await self.session_repository.update_async(session)
            
            # 返回评估结果
            return EvaluationResultDto(
                session_id=session.id,
                success=True,
                overall_score=overall_score,
                overall_evaluation=overall_evaluation,
                answer_evaluations=evaluations
            )
        except (NotFoundException, ValidationException, BusinessException):
            raise
        except Exception as e:
            err = f"评估面试时发生错误: {str(e)}"
            print(err)
            
            # 更新会话状态为评估失败
            await self.session_repository.update_evaluate_status_async(
                session_id,
                InterviewSessionEvaluateStatusType.FAILED,
                err
            )
            
            return EvaluationResultDto(
                session_id=session_id,
                success=False,
                overall_evaluation=f"评估失败: {str(e)}"
            )
    
    async def _save_audio_data(self, base64_audio: str, session_id: int, interaction_order: int, type_name: str) -> str:
        """
        保存音频数据
        
        Args:
            base64_audio: Base64编码的音频数据
            session_id: 会话ID
            interaction_order: 交互顺序
            type_name: 类型(question/answer)
            
        Returns:
            音频URL
        """
        try:
            # 解码Base64数据
            audio_bytes = base64.b64decode(base64_audio)
            
            # 生成文件名和路径
            file_name = f"session_{session_id}_{type_name}_{interaction_order}.raw"
            file_key = f"interview_audio/{file_name}"
            
            # 使用存储服务保存
            with io.BytesIO(audio_bytes) as mem_stream:
                url = await self.storage_service.upload_async(mem_stream, file_key, "audio/raw")
                return url
        except Exception as e:
            print(f"保存音频数据时发生错误: {str(e)}")
            return ""
    
    def _truncate_text(self, text: str, max_length: int) -> str:
        """
        截断文本
        
        Args:
            text: 文本
            max_length: 最大长度
            
        Returns:
            截断后的文本
        """
        if not text:
            return ""
        
        if len(text) <= max_length:
            return text
        
        return text[:max_length] + "..."