"""
面试处理后台服务

提供处理面试后台任务的服务，如生成面试问题、评估面试结果等。
"""
import logging
from typing import List, Optional
from datetime import datetime

from app.core.job.decorators import RecurringJob
from app.core.config.settings import Settings
from app.modules.tools.interview.repositories.scenario_repository import InterviewScenarioRepository
from app.modules.tools.interview.repositories.session_repository import InterviewSessionRepository
from app.modules.tools.interview.services.interview_scenario_service import InterviewScenarioService
from app.modules.tools.interview.services.interview_session_service import InterviewSessionService


class InterviewProcessingService:
    """面试处理后台服务"""
    
    def __init__(
        self,
        settings: Settings,
        logger: logging.Logger,
        scenario_repository: InterviewScenarioRepository,
        session_repository: InterviewSessionRepository,
        scenario_service: InterviewScenarioService,
        session_service: InterviewSessionService
    ):
        """
        初始化面试处理后台服务
        
        Args:
            settings: 应用配置
            logger: 日志记录器
            scenario_repository: 场景仓储
            session_repository: 会话仓储
            scenario_service: 场景服务
            session_service: 会话服务
        """
        self.settings = settings
        self.logger = logger
        self.scenario_repository = scenario_repository
        self.session_repository = session_repository
        self.scenario_service = scenario_service
        self.session_service = session_service
    
    @RecurringJob("*/10 * * * * *", "default", "处理生成面试的问题")
    async def process_generate_question_async(self):
        """
        处理生成面试的问题
        
        Returns:
            操作结果
        """
        try:
            self.logger.info("开始处理生成面试问题...")
            
            # 获取待处理的面试
            pendings = await self.scenario_repository.get_pending_scenarios_async(5)  # 一次最多处理5个
            if not pendings:
                self.logger.info("没有待处理的面试")
                return
            
            self.logger.info(f"找到{len(pendings)}个待处理的面试")
            
            # 逐个处理面试
            for scenario in pendings:
                try:
                    self.logger.info(f"开始处理面试生成问题：{scenario.id} - {scenario.name}")
                    await self.scenario_service.process_generate_questions_async(scenario.id)
                    self.logger.info(f"面试生成问题处理完成：{scenario.id} - {scenario.name}")
                except Exception as e:
                    self.logger.error(f"处理面试生成问题失败：{scenario.id} - {scenario.name}", exc_info=True)
        except Exception as e:
            self.logger.error("生成面试问题时发生异常", exc_info=True)
    
    @RecurringJob("*/10 * * * * *", "default", "处理评估面试结果")
    async def process_evaluate_session_async(self):
        """
        处理评估面试结果
        
        Returns:
            操作结果
        """
        try:
            self.logger.info("开始处理评估面试结果...")
            
            # 获取待处理的面试
            pendings = await self.session_repository.get_pending_evaluate_sessions_async(5)  # 一次最多处理5个
            if not pendings:
                self.logger.info("没有待处理的面试评估")
                return
            
            self.logger.info(f"找到{len(pendings)}个待处理的面试评估")
            
            # 逐个处理面试
            for session in pendings:
                try:
                    self.logger.info(f"开始处理评估面试结果：{session.id}")
                    await self.session_service.process_evaluate_session_async(session.id)
                    self.logger.info(f"处理评估面试结果完成：{session.id}")
                except Exception as e:
                    self.logger.error(f"处理评估面试结果失败：{session.id}", exc_info=True)
        except Exception as e:
            self.logger.error("处理评估面试结果异常", exc_info=True)