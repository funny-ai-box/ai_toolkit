import os
import logging
from typing import Tuple, List, Optional
from fastapi import UploadFile
import datetime

from app.core.exceptions import BusinessException
from app.core.storage.base import IStorageService

from app.core.dtos import ApiResponse, PagedResultDto
from app.modules.tools.dataanalysis.dtos import (
    FileUploadResultDto,
    FileDetailItemDto,
    FileListItemDto,
    FileColumnDto
)
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

class FileUploadService:
    """文件上传服务实现"""
    
    def __init__(
        self,
        upload_file_repository: UploadFileRepository,
        data_table_repository: DataTableRepository,
        table_column_repository: TableColumnRepository,
        import_log_repository: ImportLogRepository,
        file_parser_service: FileParserService,
        storage_service: IStorageService,

        supported_file_extensions: List[str] = None
    ):
        """
        初始化文件上传服务
        
        Args:
            upload_file_repository: 文件上传仓储
            data_table_repository: 数据表仓储
            table_column_repository: 表列信息仓储
            import_log_repository: 导入日志仓储
            file_parser_service: 文件解析服务
            storage_service: 存储服务
  
            supported_file_extensions: 支持的文件扩展名列表
        """
        self.upload_file_repository = upload_file_repository
        self.data_table_repository = data_table_repository
        self.table_column_repository = table_column_repository
        self.import_log_repository = import_log_repository
        self.file_parser_service = file_parser_service
        self.storage_service = storage_service
 
        self.supported_file_extensions = supported_file_extensions or ['.csv', '.xlsx', '.xls']
    
    async def upload_and_process_file_async(self, file: UploadFile, user_id: int) -> FileUploadResultDto:
        """
        上传并处理数据文件
        
        Args:
            file: 上传的文件
            user_id: 用户ID
        
        Returns:
            上传结果
        """
        # 验证文件
        is_valid, error_message = self._validate_file(file)
        if not is_valid:
            raise BusinessException(error_message)
        
        # 获取文件扩展名
        file_extension = os.path.splitext(file.filename)[1].lower()
        
        # 上传文件到存储
        file_key = f"data_files/{user_id}/{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
        content_type = file.content_type
        
        file_content = await file.read()
        await self.storage_service.upload_async(file_content, file_key, content_type)
        
        # 保存上传记录
        upload_file = UploadFile(
            user_id=user_id,
            original_file_name=file.filename,
            file_path=file_key,
            file_size=file.size,
            file_type=file_extension.lstrip('.'),
            status=0  # 初始状态
        )
        
        upload_file = await self.upload_file_repository.add_async(upload_file)
        
        # 返回上传结果（异步处理将由调度任务完成）
        return FileUploadResultDto(
            id=upload_file.id,
            original_file_name=upload_file.original_file_name,
            file_type=upload_file.file_type,
            file_size=upload_file.file_size,
            status="上传完成，等待解析文件数据...",
            upload_time=upload_file.create_date
        )
    
    async def get_file_details_async(self, file_id: int) -> FileDetailItemDto:
        """
        获取文件上传详情
        
        Args:
            file_id: 文件ID
        
        Returns:
            文件详情
        """
        file = await self.upload_file_repository.get_by_id_async(file_id)
        if not file:
            raise BusinessException("文件不存在")
        
        data_table = await self.data_table_repository.get_by_upload_file_id_async(file_id)
        
        # 如果表解析成功，则加载列名
        table_columns = []
        if data_table:
            db_table_cols = await self.table_column_repository.get_table_columns_async(data_table.id)
            for col in db_table_cols:
                table_columns.append(FileColumnDto(
                    id=col.id,
                    column_name=col.english_name,
                    original_name=col.original_name,
                    column_index=col.column_index,
                    data_type=col.data_type,
                    description=col.description,
                ))
        
        return FileDetailItemDto(
            id=file.id,
            original_file_name=file.original_file_name,
            file_type=file.file_type,
            file_size=file.file_size,
            status=file.status,
            upload_time=file.create_date,
            table_id=data_table.id if data_table else None,
            table_name=data_table.table_name if data_table else None,
            display_name=data_table.display_name if data_table else None,
            row_count=data_table.row_count if data_table else None,
            columns=table_columns,
        )
    
    async def get_user_files_async(self, user_id: int, page_index: int = 1, page_size: int = 20) -> PagedResultDto[FileListItemDto]:
        """
        获取用户上传的文件列表
        
        Args:
            user_id: 用户ID
            page_index: 页码
            page_size: 每页大小
        
        Returns:
            文件列表
        """
        # 确保页码和每页数量有效
        if page_index < 1:
            page_index = 1
        if page_size < 1:
            page_size = 20
        
        # 获取用户的文件列表
        files = await self.upload_file_repository.get_user_files_async(user_id)
        
        # 计算总记录数
        total_count = len(files)
        
        # 应用分页
        paged_files = files[(page_index - 1) * page_size:page_index * page_size]
        
        # 构建结果列表
        result = []
        
        for file in paged_files:
            data_table = await self.data_table_repository.get_by_upload_file_id_async(file.id)
            
            result.append(FileListItemDto(
                id=file.id,
                original_file_name=file.original_file_name,
                file_type=file.file_type,
                file_size=file.file_size,
                status=file.status,
                upload_time=file.create_date,
                table_id=data_table.id if data_table else None,
                table_name=data_table.table_name if data_table else None,
                display_name=data_table.display_name if data_table else None,
                row_count=data_table.row_count if data_table else None,
            ))
        
        # 构建分页结果
        return PagedResultDto[FileListItemDto](
            items=result,
            total_count=total_count,
            page_index=page_index,
            page_size=page_size,
            total_pages=(total_count + page_size - 1) // page_size  # 向上取整
        )
    
    def _validate_file(self, file: UploadFile) -> Tuple[bool, str]:
        """
        验证文件
        
        Args:
            file: 上传的文件
        
        Returns:
            (是否有效, 错误信息)
        """
        # 检查文件是否为空
        if file.size == 0:
            return False, "文件不能为空"
        
        # 检查文件类型
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in self.supported_file_extensions:
            return False, f"不支持的文件类型，仅支持 {', '.join(self.supported_file_extensions)}"
        
        # 检查文件大小（限制为5MB）
        max_size = 5 * 1024 * 1024  # 5MB
        if file.size > max_size:
            return False, f"文件大小超过限制（最大5MB）"
        
        return True, ""
