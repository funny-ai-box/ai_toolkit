"""
AI 实时交互服务实现

提供面试过程中的实时AI交互能力，包括OpenAI RealTime会话的创建和管理等功能。
"""
import json
import httpx
from typing import Dict, Any, List, Optional
import logging
import datetime

from app.core.config.settings import Settings
from app.core.exceptions import BusinessException

from app.modules.base.prompts.services import PromptTemplateService
from app.modules.tools.interview.models import InterviewScenario, JobPosition, InterviewQuestion
from app.modules.tools.interview.repositories.scenario_repository import InterviewScenarioRepository
from app.modules.tools.interview.repositories.job_position_repository import JobPositionRepository
from app.modules.tools.interview.repositories.question_repository import InterviewQuestionRepository
from app.modules.tools.interview.repositories.session_repository import InterviewSessionRepository
from app.modules.tools.interview.enums import InterviewerGender, InterviewSessionStatus
from app.modules.tools.interview.dtos import RealTimeSessionResponse


class AIRealTimeService:
    """AI 实时交互服务"""
    
    def __init__(
        self,
        settings: Settings,
        logger: logging.Logger,
        prompt_template_service: PromptTemplateService,
        scenario_repository: InterviewScenarioRepository,
        position_repository: JobPositionRepository,
        question_repository: InterviewQuestionRepository,
        session_repository: InterviewSessionRepository
    ):
        """
        初始化AI实时交互服务
        
        Args:
            settings: 应用配置
            logger: 日志记录器
            prompt_template_service: 提示词模板服务
            scenario_repository: 场景仓储
            position_repository: 职位仓储
            question_repository: 问题仓储
            session_repository: 会话仓储
        """
        self.settings = settings
        self.logger = logger
        self.prompt_template_service = prompt_template_service
        self.scenario_repository = scenario_repository
        self.position_repository = position_repository
        self.question_repository = question_repository
        self.session_repository = session_repository
        
        # 获取OpenAI配置
        self.openai_api_key = getattr(settings, "OPENAI_API_KEY", "")
        if not self.openai_api_key:
            raise ValueError("OpenAI API密钥未配置，请检查配置文件")
    
    async def create_realtime_session_async(self, session_id: int, noise_reduction: Optional[str] = None) -> str:
        """
        创建OpenAI RealTime会话
        
        Args:
            session_id: 面试会话ID
            noise_reduction: 音频降噪配置
            
        Returns:
            OpenAI会话令牌
        """
        try:
            # 获取会话信息
            session = await self.session_repository.get_by_id_async(session_id)
            if not session:
                raise BusinessException("面试会话不存在")
            
            # 获取场景信息
            scenario = await self.scenario_repository.get_by_id_async(session.scenario_id)
            if not scenario:
                raise BusinessException("面试场景不存在")
            
            # 获取职位信息
            position = await self.position_repository.get_by_id_async(session.job_position_id)
            if not position:
                raise BusinessException("面试职位不存在")
            
            # 准备面试指令
            instructions = await self._prepare_interview_instructions_async(scenario, position)
            
            # 创建OpenAI RealTime会话
            session_response = await self._create_openai_session_async(scenario.interviewer_gender, instructions, noise_reduction)
            
            # 更新会话记录
            session.openai_session_id = session_response.id
            session.status = InterviewSessionStatus.IN_PROGRESS
            session.start_time = datetime.datetime.now()
            await self.session_repository.update_async(session)
            
            return session_response.client_secret_value
        except BusinessException:
            raise
        except Exception as e:
            print(f"创建OpenAI RealTime会话时发生错误: {str(e)}")
            raise BusinessException(f"创建OpenAI RealTime会话失败: {str(e)}")
    
    async def _prepare_interview_instructions_async(self, scenario: InterviewScenario, position: JobPosition) -> str:
        """
        准备面试提示词
        
        Args:
            scenario: 场景
            position: 职位
            
        Returns:
            系统提示词
        """
        # 获取该职位下的面试问题
        questions = await self.question_repository.get_questions_by_position_async(scenario.id, position.id)
        
        # 获取系统提示词模板
        system_prompt = await self.prompt_template_service.get_content_by_key_async("INTERVIEW_INTERVIEW_INSTRUCTIONS_PROMPT")
        
        # 构建面试官提示词
        instructions = f"{system_prompt}\n\n"
        
        # 添加面试问题
        instructions += "#面试问题列表#：\n"
        for i, question in enumerate(questions, 1):
            instructions += f"   {i}. {question.content}\n"
            instructions += f"      [问题ID: {question.id}]\n"
        
        instructions += f"\n你现在名叫{scenario.interviewer_name}，正在面试{position.name}岗位的候选人。\n"
        
        return instructions
    
    async def _create_openai_session_async(
        self, 
        gender: InterviewerGender,
        instructions: str,
        noise_reduction: Optional[str] = None
    ) -> RealTimeSessionResponse:
        """
        创建openAI的实时语音Session
        
        Args:
            gender: 性别
            instructions: 指令
            noise_reduction: 音频降噪配置
            
        Returns:
            OpenAI会话响应
        """
        # 构建请求参数
        request_body = {
            "model": "gpt-4o-mini-realtime-preview",
            "modalities": ["audio", "text"],
            "instructions": instructions,
            "voice": self._get_voice_by_gender(gender),
            "input_audio_transcription": {"language": "zh", "model": "whisper-1"},
            "input_audio_noise_reduction": None if not noise_reduction else {"type": noise_reduction},
            "tools": [
                {
                    "type": "function",
                    "name": "saveInteraction",
                    "description": "保存面试过程中的问答交互记录",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sessionId": {
                                "type": "number",
                                "description": "面试会话ID"
                            },
                            "questionId": {
                                "type": "number",
                                "description": "问题ID（如果是预设问题）"
                            },
                            "question": {
                                "type": "string",
                                "description": "提问内容"
                            },
                            "answer": {
                                "type": "string",
                                "description": "回答内容"
                            },
                            "questionAudiobase64": {
                                "type": "string",
                                "description": "问题音频数据(Base64编码)"
                            },
                            "answerAudiobase64": {
                                "type": "string",
                                "description": "回答音频数据(Base64编码)"
                            },
                            "interactionOrder": {
                                "type": "number",
                                "description": "交互顺序"
                            }
                        },
                        "required": ["sessionId", "questionId", "question", "answer", "interactionOrder"]
                    }
                },
                {
                    "type": "function",
                    "name": "endInterview",
                    "description": "结束面试",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sessionId": {
                                "type": "number",
                                "description": "面试会话ID"
                            },
                            "reason": {
                                "type": "string",
                                "description": "结束原因"
                            }
                        },
                        "required": ["sessionId"]
                    }
                }
            ]
        }
        
        try:
            # 发送请求
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/realtime/sessions",
                    json=request_body,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.openai_api_key}"
                    }
                )
                
                if response.status_code != 200:
                    print(f"OpenAI RealTime API 错误: {response.text}")
                    raise BusinessException("创建OpenAI RealTime会话失败", response.status_code)
                
                result = response.json()
                
                # 转换为响应DTO
                client_secret = result.get("client_secret", {})
                session_response = RealTimeSessionResponse(
                    id=result.get("id", ""),
                    model=result.get("model", ""),
                    modalities=result.get("modalities", []),
                    instructions=result.get("instructions", ""),
                    voice=result.get("voice", ""),
                    client_secret_value=client_secret.get("value", ""),
                    client_secret_expires_at=client_secret.get("expires_at", 0)
                )
                
                return session_response
                
        except httpx.RequestError as e:
            print(f"请求OpenAI RealTime API失败: {str(e)}")
            raise BusinessException(f"请求OpenAI RealTime API失败: {str(e)}")
    
    def _get_voice_by_gender(self, gender: InterviewerGender) -> str:
        """
        根据性别获取OpenAI语音类型
        
        Args:
            gender: 性别
            
        Returns:
            语音类型
        """
        if gender == InterviewerGender.MALE:
            return "alloy"  # 男声选择
        elif gender == InterviewerGender.FEMALE:
            return "nova"   # 女声选择
        else:
            return "alloy"  # 默认声音