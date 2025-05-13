# app/modules/dataanalysis/services/data_analysis_processing_service.py
import logging
from typing import List, Dict, Any
import datetime
import asyncio

from app.core.job.decorators import recurring_job
from app.modules.tools.dataanalysis.services.data_file_processor import DataFileProcessor

class DataAnalysisProcessingService:
    """数据分析异步处理任务"""
    
    def __init__(
        self,

        data_file_processor: DataFileProcessor
    ):
        """
        初始化数据分析处理服务
        
        Args:
            logger: 日志记录器
            data_file_processor: 数据文件处理器
        """
  
        self.data_file_processor = data_file_processor
    
    @recurring_job("*/10 * * * * *", "default", "处理数据分析中待解析文档")
    async def process_pending_data_files_async(self) -> None:
        """
        处理待处理的文档
        
        Returns:
            处理成功的文档ID列表
        """
        print("开始处理待处理的文档")
        
        try:
            # 限制每次处理的文档数量
            batch_size = 5
            pending_documents = await self.data_file_processor.get_pending_files_async(batch_size)
            print(f"找到 {len(pending_documents)} 个待处理文档")
            
            for document in pending_documents:
                print(f"开始处理文档 {document.id}")
                await self.data_file_processor.process_file_async(document.id, "MySql")
                
                print(f"已创建文档处理作业用于文档 {document.id}")
        
        except Exception as ex:
            print(f"处理待处理文档时发生错误: {str(ex)}")