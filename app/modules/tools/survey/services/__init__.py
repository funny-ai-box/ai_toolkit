from app.modules.tools.survey.services.ai_design_service import AIDesignService
from app.modules.tools.survey.enums import SurveyTaskStatus, SurveyFieldType, FieldOperationType, ChatRoleType


class SurveyTaskService:
    """问卷任务服务"""
    
    def __init__(self, *args, **kwargs):
        from app.modules.tools.survey.services import SurveyTaskService as ServiceImpl
        self._impl = ServiceImpl(*args, **kwargs)
    
    async def create_task_async(self, user_id, request):
        return await self._impl.create_task_async(user_id, request)
    
    async def update_task_async(self, user_id, request):
        return await self._impl.update_task_async(user_id, request)
    
    async def delete_task_async(self, user_id, task_id):
        return await self._impl.delete_task_async(user_id, task_id)
    
    async def get_task_async(self, user_id, task_id):
        return await self._impl.get_task_async(user_id, task_id)
    
    async def get_task_by_share_code_async(self, share_code):
        return await self._impl.get_task_by_share_code_async(share_code)
    
    async def get_user_tasks_async(self, user_id, page_index=1, page_size=20):
        return await self._impl.get_user_tasks_async(user_id, page_index, page_size)
    
    async def publish_task_async(self, user_id, task_id):
        return await self._impl.publish_task_async(user_id, task_id)
    
    async def close_task_async(self, user_id, task_id):
        return await self._impl.close_task_async(user_id, task_id)


class SurveyDesignService:
    """问卷设计服务"""
    
    def __init__(self, *args, **kwargs):
        from app.modules.tools.survey.services import SurveyDesignService as ServiceImpl
        self._impl = ServiceImpl(*args, **kwargs)
    
    async def streaming_ai_design_fields_async(self, user_id, request, on_chunk_received, cancellation_token=None):
        return await self._impl.streaming_ai_design_fields_async(
            user_id, request, on_chunk_received, cancellation_token
        )
    
    async def get_design_history_async(self, user_id, task_id, page_index=1, page_size=20):
        return await self._impl.get_design_history_async(user_id, task_id, page_index, page_size)
    
    async def save_design_async(self, user_id, task_id, tabs):
        return await self._impl.save_design_async(user_id, task_id, tabs)


class SurveyResponseService:
    """问卷回答服务"""
    
    def __init__(self, *args, **kwargs):
        from app.modules.tools.survey.services import SurveyResponseService as ServiceImpl
        self._impl = ServiceImpl(*args, **kwargs)
    
    async def submit_response_async(self, respondent_id, respondent_ip, request):
        return await self._impl.submit_response_async(respondent_id, respondent_ip, request)
    
    async def get_responses_async(self, user_id, task_id, page_index=1, page_size=20):
        return await self._impl.get_responses_async(user_id, task_id, page_index, page_size)
    
    async def get_response_detail_async(self, user_id, response_id):
        return await self._impl.get_response_detail_async(user_id, response_id)
    
    async def delete_response_async(self, user_id, response_id):
        return await self._impl.delete_response_async(user_id, response_id)


class SurveyReportService:
    """问卷报表服务"""
    
    def __init__(self, *args, **kwargs):
        from app.modules.tools.survey.services import SurveyReportService as ServiceImpl
        self._impl = ServiceImpl(*args, **kwargs)
    
    async def get_report_async(self, user_id, task_id):
        return await self._impl.get_report_async(user_id, task_id)