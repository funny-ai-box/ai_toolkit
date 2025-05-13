
# app/modules/dataanalysis/config.py
from pydantic import Field
from pydantic_settings import BaseSettings
import os

class DataAnalysisFileStorageSettings(BaseSettings):
    """数据分析文件存储配置"""
    base_path: str = Field(default="uploads", env="DTA_FILE_STORAGE_BASE_PATH")
    visualization_path: str = Field(default="uploads/generate", env="DTA_FILE_STORAGE_VISUALIZATION_PATH")
    generate_html: bool = Field(default=True, env="DTA_FILE_STORAGE_GENERATE_HTML")
    supported_file_extensions: list[str] = Field(default=[".csv", ".xlsx", ".xls"], env="DTA_FILE_STORAGE_SUPPORTED_FILE_EXTENSIONS")
    storage_provider: str = Field(default="Local", env="DTA_FILE_STORAGE_STORAGE_PROVIDER")

class DataAnalysisTempTableSettings(BaseSettings):
    """数据分析临时表配置"""
    default_expiry_days: int = Field(default=30, env="DTA_TEMP_TABLE_DEFAULT_EXPIRY_DAYS")
    prefix: str = Field(default="dta_temp_", env="DTA_TEMP_TABLE_PREFIX")

class DataAnalysisSettings(BaseSettings):
    """数据分析配置"""
    file_storage: DataAnalysisFileStorageSettings = Field(default_factory=DataAnalysisFileStorageSettings)
    temporary_table: DataAnalysisTempTableSettings = Field(default_factory=DataAnalysisTempTableSettings)
    chat_ai_provider_type: str = Field(default="OpenAI", env="DTA_CHAT_AI_PROVIDER_TYPE")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"
