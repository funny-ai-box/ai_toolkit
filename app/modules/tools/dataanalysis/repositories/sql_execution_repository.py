# app/modules/dataanalysis/repositories/sql_execution_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text
from typing import List, Optional, Tuple, Dict, Any
import datetime
import time
import json

from app.core.exceptions import BusinessException
from app.core.utils.snowflake import generate_id
from app.modules.tools.dataanalysis.models import SqlExecution

class DataConvertUtil:
    """数据转换工具类"""
    
    @staticmethod
    def is_dangerous_sql(sql: str) -> bool:
        """
        检查SQL是否包含危险操作
        
        Args:
            sql: SQL语句
        
        Returns:
            是否危险
        """
        # 转换为大写进行检查
        sql = sql.upper()
        
        # 检查是否包含非查询操作
        dangerous_keywords = [
            "DELETE ", "UPDATE ", "INSERT ", "DROP ", 
            "ALTER ", "TRUNCATE ", "CREATE "
        ]
        
        return any(keyword in sql for keyword in dangerous_keywords)
    
    @staticmethod
    def convert_result_to_json(results: List[Dict[str, Any]]) -> str:
        """
        将查询结果转换为JSON字符串
        
        Args:
            results: 查询结果列表
        
        Returns:
            JSON字符串
        """
        # 处理特殊类型
        def json_serial(obj):
            if isinstance(obj, (datetime.datetime, datetime.date)):
                return obj.isoformat()
            return str(obj)
        
        return json.dumps(results, default=json_serial)

class SqlExecutionRepository:
    """SQL执行记录仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化SQL执行记录仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def add_async(self, sql_execution: SqlExecution) -> SqlExecution:
        """
        添加SQL执行记录
        
        Args:
            sql_execution: SQL执行记录实体
        
        Returns:
            添加后的实体
        """
        # 使用雪花ID
        sql_execution.id = generate_id()
        
        # 设置创建和修改时间
        now = datetime.datetime.now()
        sql_execution.create_date = now
        sql_execution.last_modify_date = now
        
        # 插入数据
        self.db.add(sql_execution)
        await self.db.flush()
        
        return sql_execution
    
    async def update_async(self, sql_execution: SqlExecution) -> SqlExecution:
        """
        更新SQL执行记录
        
        Args:
            sql_execution: SQL执行记录实体
        
        Returns:
            更新后的实体
        """
        # 更新最后修改时间
        sql_execution.last_modify_date = datetime.datetime.now()
        
        # 更新数据
        self.db.add(sql_execution)
        await self.db.flush()
        
        return sql_execution
    
    async def get_by_id_async(self, id: int) -> Optional[SqlExecution]:
        """
        获取SQL执行记录
        
        Args:
            id: SQL执行记录ID
        
        Returns:
            SQL执行记录实体
        """
        result = await self.db.execute(
            select(SqlExecution).filter(SqlExecution.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_conversation_sql_executions_async(self, conversation_id: int) -> List[SqlExecution]:
        """
        获取对话的所有SQL执行记录
        
        Args:
            conversation_id: 对话ID
        
        Returns:
            SQL执行记录实体列表
        """
        result = await self.db.execute(
            select(SqlExecution)
            .filter(SqlExecution.conversation_id == conversation_id)
            .order_by(SqlExecution.create_date)
        )
        return list(result.scalars().all())
    
    async def execute_sql_query_async(self, sql: str, storage_type: str) -> Tuple[str, int, int]:
        """
        执行SQL查询
        
        Args:
            sql: SQL语句
            storage_type: 存储类型（mysql/doris）
        
        Returns:
            查询结果（JSON字符串）、行数、执行时间
        """
        try:
            # 验证SQL语句
            if not sql:
                raise BusinessException("SQL语句不能为空")
            
            # 对SQL语句进行安全检查，防止危险操作
            if DataConvertUtil.is_dangerous_sql(sql):
                raise BusinessException("不允许执行危险SQL操作（如DELETE、UPDATE、INSERT等）")
            
            # 记录执行时间
            start_time = time.time()
            
            # 执行SQL查询
            result = await self.db.execute(text(sql))
            
            # 获取结果集
            rows = result.fetchall()
            
            # 计算执行时间（毫秒）
            execution_time = int((time.time() - start_time) * 1000)
            
            # 获取列名
            columns = result.keys()
            
            # 转换为字典列表
            data = []
            for row in rows:
                data.append({col: row[idx] for idx, col in enumerate(columns)})
            
            # 获取行数
            row_count = len(data)
            
            # 转换为JSON字符串
            json_result = DataConvertUtil.convert_result_to_json(data)
            
            return json_result, row_count, execution_time
        
        except Exception as ex:
            # 记录错误日志
            raise BusinessException(f"执行SQL查询失败: {str(ex)}")
