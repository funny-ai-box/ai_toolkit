from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json
import time
from typing import Tuple

class TempDataTableRepository:
    """临时数据表仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化数据表仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def get_datas_by_id_async(self, table_id: int) -> Tuple[str, int, int]:
        """
        获取数据表记录
        
        Args:
            table_id: 数据表ID
        
        Returns:
            数据结果 (JSON字符串, 行数, 执行时间)
        """
        from ..repositories.data_table_repository import DataTableRepository
        
        # 通过依赖注入获取 DataTableRepository
        data_table_repo = DataTableRepository(self.db)
        
        # 获取表定义
        table_define = await data_table_repo.get_by_id_async(table_id)
        return await self.get_datas_by_table_name_async(table_define.table_name)
    
    async def get_datas_by_table_name_async(self, table_name: str) -> Tuple[str, int, int]:
        """
        获取数据表记录
        
        Args:
            table_name: 数据表
        
        Returns:
            数据结果 (JSON字符串, 行数, 执行时间)
        """
        # 记录执行时间
        start_time = time.time()
        
        # 限制最多5000条数据
        sql = f"SELECT * FROM {table_name} LIMIT 5000"
        
        # 执行SQL查询
        result = await self.db.execute(text(sql))
        
        # 获取结果集
        rows = result.fetchall()
        
        # 获取列名
        columns = result.keys()
        
        # 转换为字典列表
        data = []
        for row in rows:
            data.append({col: row[idx] for idx, col in enumerate(columns)})
        
        # 转换为JSON字符串
        json_result = json.dumps(data, default=str)
        
        # 获取行数
        row_count = len(data)
        
        # 计算执行时间（毫秒）
        execution_time = int((time.time() - start_time) * 1000)
        
        return json_result, row_count, execution_time