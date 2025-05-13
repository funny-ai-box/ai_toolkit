from fastapi import FastAPI
from app.modules.tools.survey.router import router

def register_survey_module(app: FastAPI):
    """
    注册问卷调查模块
    
    Args:
        app: FastAPI应用实例
    """
    # 注册路由
    app.include_router(router)
