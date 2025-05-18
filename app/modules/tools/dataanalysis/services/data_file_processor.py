# app/modules/dataanalysis/services/data_file_processor.py
import os
import logging
from typing import List, Dict, Any
import datetime
import pandas as pd

from app.core.exceptions import BusinessException

from app.core.job.services import JobPersistenceService
from app.core.utils.snowflake import generate_id
from app.modules.tools.dataanalysis.models import (
    UploadFile,
    DataTable,
    TableColumn,
    ImportLog
)
from app.modules.tools.dataanalysis.repositories.upload_file_repository import UploadFileRepository
from app.modules.tools.dataanalysis.repositories.data_table_repository import DataTableRepository
from app.modules.tools.dataanalysis.repositories.table_column_repository import TableColumnRepository
from app.modules.tools.dataanalysis.repositories.import_log_repository import ImportLogRepository
from app.modules.tools.dataanalysis.services.file_parser_service import FileParserService

class DataFileProcessor:
    """数据分析的文档处理服务"""
    
    def __init__(
        self,
        upload_file_repository: UploadFileRepository,
        data_table_repository: DataTableRepository,
        table_column_repository: TableColumnRepository,
        import_log_repository: ImportLogRepository,
        file_parser_service: FileParserService,
  
        base_storage_path: str = "uploads"
    ):
        """
        初始化数据文件处理器
        
        Args:
            upload_file_repository: 文件上传仓储
            data_table_repository: 数据表仓储
            table_column_repository: 表列信息仓储
            import_log_repository: 导入日志仓储
            file_parser_service: 文件解析服务

            base_storage_path: 基础存储路径
        """
        self.upload_file_repository = upload_file_repository
        self.data_table_repository = data_table_repository
        self.table_column_repository = table_column_repository
        self.import_log_repository = import_log_repository
        self.file_parser_service = file_parser_service

        self.base_storage_path = base_storage_path
    
    async def get_pending_files_async(self, limit: int = 10) -> List[UploadFile]:
        """
        获取待处理的文档
        
        Args:
            limit: 数量限制
        
        Returns:
            文档列表
        """
        try:
            return await self.upload_file_repository.get_pending_files_async(limit)
        except Exception as ex:
            print(f"获取待处理文档失败: 限制数量={limit}, 错误: {str(ex)}")
            raise
    
    async def process_file_async(self, file_id: int, storage_type: str) -> None:
        """
        处理上传的文件
        
        Args:
            file_id: 文件ID
            storage_type: 存储类型
        """
        # 获取文件记录
        upload_file = await self.upload_file_repository.get_by_id_async(file_id)
        if not upload_file:
            raise BusinessException("文件不存在")
        if upload_file.status != 0:
            raise BusinessException("文件已在处理或处理完毕")
        
        # 创建导入日志
        import_log = ImportLog(
            upload_file_id=file_id,
            table_id=0,  # 暂时为0，后面会更新
            total_rows=0,
            success_rows=0,
            failed_rows=0,
            status=0,  # 进行中
            start_time=datetime.datetime.now()
        )
        
        import_log = await self.import_log_repository.add_async(import_log)
        
        # 更新文件状态
        upload_file.status = 1  # 解析中
        await self.upload_file_repository.update_async(upload_file)
        
        # 生成表名（使用雪花Id）
      
        table_name = f"dta_temp_{generate_id()}"
        data_table = None
        
        try:
            # 构建完整的文件路径
            file_path = os.path.join(self.base_storage_path, upload_file.file_path)
            
            # 解析文件
            columns_list = []
            df = None
            
            if upload_file.file_type.lower() == "csv":
                columns_list, df = await self.file_parser_service.parse_csv_file_async(file_path)
            else:  # Excel
                columns_list, df = await self.file_parser_service.parse_excel_file_async(file_path)
            
            # 检查是否已存在表
            data_table = await self.data_table_repository.get_by_upload_file_id_async(file_id)
            if not data_table:
                # 创建数据表记录
                data_table = DataTable(
                    upload_file_id=file_id,
                    user_id=upload_file.user_id,
                    table_name=table_name,
                    display_name=os.path.splitext(upload_file.original_file_name)[0],
                    row_count=0,  # 暂时为0，后面会更新
                    storage_type=storage_type,
                    status=0,  # 创建中
                    expiry_date=datetime.datetime.now() + datetime.timedelta(days=30)  # 30天后过期
                )
                
                data_table = await self.data_table_repository.add_async(data_table)
            else:
                # 状态先还原
                data_table.row_count = 0
                data_table.status = 0
                await self.data_table_repository.update_async(data_table)
            
            # 更新导入日志的TableId
            import_log.table_id = data_table.id
            await self.import_log_repository.update_async(import_log)
            
            # 更新TableId并保存列信息
            for column in columns_list:
                column.table_id = data_table.id
            
            await self.table_column_repository.add_batch_async(columns_list)
            
            # 创建表结构
            await self.data_table_repository.create_table_structure_async(
                table_name, data_table.display_name, columns_list, storage_type
            )
            
            # 导入数据
            row_count = await self.data_table_repository.bulk_insert_data_async(table_name, df)
            
            # 更新表状态和行数
            data_table.row_count = row_count
            data_table.status = 1  # 可用
            await self.data_table_repository.update_async(data_table)
            
            # 更新文件状态
            upload_file.status = 2  # 解析成功
            await self.upload_file_repository.update_async(upload_file)
            
            # 更新导入日志
            import_log.total_rows = row_count
            import_log.success_rows = row_count
            import_log.status = 1  # 成功
            import_log.end_time = datetime.datetime.now()
            await self.import_log_repository.update_async(import_log)
            
        except Exception as ex:
            print(f"处理文件失败: {upload_file.original_file_name}, 错误: {str(ex)}")
            
            # 更新文件状态为解析失败
            upload_file.status = 3  # 解析失败
            await self.upload_file_repository.update_async(upload_file)
            
            # 列可能创建了，删除列
            if data_table:
                await self.table_column_repository.delete_by_table_id_async(data_table.id)
            
            # 删除临时表，可能创建了，也可能还未创建
            await self.data_table_repository.drop_temp_table_async(table_name)
            
            # 更新导入日志
            import_log.status = 2  # 失败
            import_log.error_message = str(ex)
            import_log.end_time = datetime.datetime.now()
            await self.import_log_repository.update_async(import_log)
            
            raise
