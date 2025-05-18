# app/modules/dataanalysis/repositories/data_table_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from typing import List, Optional, Tuple
import datetime
import pandas as pd


from app.core.exceptions import BusinessException
from app.core.utils.snowflake import generate_id
from app.modules.tools.dataanalysis.models import DataTable, TableColumn

class DataTableRepository:
    """数据表仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化数据表仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def add_async(self, data_table: DataTable) -> DataTable:
        """
        添加数据表记录
        
        Args:
            data_table: 数据表实体
        
        Returns:
            添加后的实体
        """
        # 使用雪花ID
        data_table.id = generate_id()
        
        # 设置创建和修改时间
        now = datetime.datetime.now()
        data_table.create_date = now
        data_table.last_modify_date = now
        
        # 插入数据
        self.db.add(data_table)
        await self.db.flush()
        await self.db.commit()  # 添加commit确保数据持久化
        
        return data_table
    
    async def update_async(self, data_table: DataTable) -> DataTable:
        """
        更新数据表记录
        
        Args:
            data_table: 数据表实体
        
        Returns:
            更新后的实体
        """
        # 更新最后修改时间
        data_table.last_modify_date = datetime.datetime.now()
        
        # 更新数据
        self.db.add(data_table)
        await self.db.flush()
        await self.db.commit()  # 添加commit确保数据持久化
        
        return data_table
    
    async def get_by_id_async(self, id: int) -> Optional[DataTable]:
        """
        获取数据表记录
        
        Args:
            id: 数据表ID
        
        Returns:
            数据表实体
        """
        result = await self.db.execute(
            select(DataTable).filter(DataTable.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_upload_file_id_async(self, upload_file_id: int) -> Optional[DataTable]:
        """
        根据上传文件ID获取数据表记录
        
        Args:
            upload_file_id: 上传文件ID
        
        Returns:
            数据表实体
        """
        result = await self.db.execute(
            select(DataTable).filter(DataTable.upload_file_id == upload_file_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_tables_async(self, user_id: int, file_id: int = 0) -> List[DataTable]:
        """
        获取用户的所有数据表记录
        
        Args:
            user_id: 用户ID
            file_id: 可以指定文件找表，=0則是所有表
        
        Returns:
            数据表实体列表
        """
        query = select(DataTable).filter(DataTable.user_id == user_id)
        
        if file_id > 0:
            query = query.filter(DataTable.upload_file_id == file_id)
        
        result = await self.db.execute(
            query.order_by(DataTable.create_date.desc())
        )
        return list(result.scalars().all())
    
    async def delete_async(self, id: int) -> bool:
        """
        删除数据表记录
        
        Args:
            id: 数据表ID
        
        Returns:
            是否成功
        """
        # 首先获取数据表记录
        data_table = await self.get_by_id_async(id)
        if not data_table:
            return False
        
        # 删除物理表结构（如果表状态为可用）
        if data_table.status == 1:
            try:
                # 删除物理表
                await self.db.execute(text(f"DROP TABLE IF EXISTS `{data_table.table_name}`"))
            except Exception:
                # 忽略删除物理表的错误，继续删除记录
                pass
        
        # 删除数据表记录
        await self.db.delete(data_table)
        await self.db.flush()
        await self.db.commit()  # 添加commit确保数据持久化
        
        return True
    
    async def create_table_structure_async(self, table_name: str, table_desc: str, columns: List[TableColumn], storage_type: str) -> bool:
        """
        创建动态表结构
        
        Args:
            table_name: 表名
            table_desc: 表描述
            columns: 列定义列表
            storage_type: 存储类型（mysql/doris）
        
        Returns:
            是否成功
        """
        # 构建建表SQL
        sql_parts = []
        
        # MySQL和Doris有一些语法差异，需要区分处理
        if storage_type.lower() == "mysql":
            sql_parts.append(f"CREATE TABLE IF NOT EXISTS `{table_name}` (")
            
            # 添加ID列作为主键
            sql_parts.append("`id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '自增主键',")
            
            # 添加数据列
            for i, column in enumerate(columns):
                column_type = self._get_mysql_data_type(column.data_type)
                
                sql_parts.append(f"`{column.english_name}` {column_type} ")
                
                # 对于可能为空的列
                sql_parts.append("NULL ")
                
                # 添加注释
                sql_parts.append(f"COMMENT '{column.description or column.original_name}'")
                
                # 如果不是最后一列，添加逗号
                if i < len(columns) - 1:
                    sql_parts.append(",")
                else:
                    sql_parts.append("")
            
            # 添加主键定义
            sql_parts.append(",PRIMARY KEY (`id`) USING BTREE")
            sql_parts.append(f") ENGINE=InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT='{table_desc}';")
        elif storage_type.lower() == "doris":
            # Doris建表语法
            sql_parts.append(f"CREATE TABLE IF NOT EXISTS `{table_name}` (")
            
            # 添加ID列作为主键
            sql_parts.append("`id` BIGINT NOT NULL COMMENT '自增主键',")
            
            # 添加数据列
            for i, column in enumerate(columns):
                column_type = self._get_doris_data_type(column.data_type)
                
                sql_parts.append(f"`{column.english_name}` {column_type} ")
                
                # 对于可能为空的列
                sql_parts.append("NULL ")
                
                # 添加注释
                sql_parts.append(f"COMMENT '{column.description or column.original_name}'")
                
                # 如果不是最后一列，添加逗号
                if i < len(columns) - 1:
                    sql_parts.append(",")
                else:
                    sql_parts.append("")
            
            # Doris需要指定分区和分桶信息
            sql_parts.append(")")
            sql_parts.append("DUPLICATE KEY(`id`)")
            sql_parts.append("DISTRIBUTED BY HASH(`id`) BUCKETS 10")
            sql_parts.append("PROPERTIES (\"replication_num\" = \"1\");")
        else:
            raise BusinessException(f"不支持的存储类型: {storage_type}")
        
        # 执行建表SQL
        try:
            sql = "\n".join(sql_parts)
            await self.db.execute(text(sql))
            await self.db.commit()  # 添加commit确保数据持久化
            return True
        except Exception as ex:
            # 记录错误日志
            raise BusinessException(f"创建表结构失败: {table_name}, 错误: {str(ex)}")
    
    async def bulk_insert_data_async(self, table_name: str, df: pd.DataFrame) -> int:
        """
        批量插入数据到动态表
        
        Args:
            table_name: 表名
            df: pandas DataFrame对象
        
        Returns:
            插入行数
        """
        if df is None or df.empty:
            raise BusinessException("无效的数据格式")
        
        # 获取列名列表
        columns = list(df.columns)
        if not columns:
            return 0
        
        # 处理数据批量插入
        # 通过构建批量INSERT语句
        batch_size = 1000  # 每批次处理的记录数
        total_inserted = 0
        
        for i in range(0, len(df), batch_size):
            batch_df = df.iloc[i:i+batch_size]
            if batch_df.empty:
                continue
            
            # 构建插入语句
            placeholders = ", ".join(["%s"] * len(columns))
            columns_str = ", ".join([f"`{col}`" for col in columns])
            
            insert_sql = f"INSERT INTO `{table_name}` ({columns_str}) VALUES "
            
            # 添加值
            values_list = []
            params = []
            
            for _, row in batch_df.iterrows():
                row_values = []
                for col in columns:
                    val = row[col]
                    if pd.isna(val):
                        row_values.append("NULL")
                    else:
                        row_values.append("%s")
                        params.append(val)
                
                values_list.append(f"({', '.join(row_values)})")
            
            insert_sql += ", ".join(values_list)
            
            # 执行SQL
            await self.db.execute(text(insert_sql), params)
            total_inserted += len(batch_df)
        
        await self.db.flush()
        await self.db.commit()  # 添加commit确保数据持久化
        return total_inserted
    
    async def drop_temp_table_async(self, table_name: str) -> int:
        """
        如果解析失败，则删除临时表
        
        Args:
            table_name: 表名
        
        Returns:
            影响行数
        """
        sql = f"DROP TABLE IF EXISTS `{table_name}`;"
        result = await self.db.execute(text(sql))
        await self.db.commit()  # 添加commit确保数据持久化
        return result.rowcount if hasattr(result, 'rowcount') else 0
    
    def _get_mysql_data_type(self, data_type: str) -> str:
        """
        获取MySQL数据类型
        
        Args:
            data_type: 数据类型（string, integer, float, date等）
        
        Returns:
            MySQL数据类型
        """
        if data_type:
            data_type_lower = data_type.lower()
            if data_type_lower == "string":
                return "VARCHAR(255)"
            elif data_type_lower == "integer":
                return "INT"
            elif data_type_lower == "float":
                return "DOUBLE"
            elif data_type_lower == "date":
                return "DATETIME"
            elif data_type_lower == "boolean":
                return "TINYINT(1)"
            elif data_type_lower == "text":
                return "TEXT"
        
        return "VARCHAR(255)"
    
    def _get_doris_data_type(self, data_type: str) -> str:
        """
        获取Doris数据类型
        
        Args:
            data_type: 数据类型（string, integer, float, date等）
        
        Returns:
            Doris数据类型
        """
        if data_type:
            data_type_lower = data_type.lower()
            if data_type_lower == "string":
                return "VARCHAR(255)"
            elif data_type_lower == "integer":
                return "INT"
            elif data_type_lower == "float":
                return "DOUBLE"
            elif data_type_lower == "date":
                return "DATETIME"
            elif data_type_lower == "boolean":
                return "BOOLEAN"
            elif data_type_lower == "text":
                return "STRING"
        
        return "VARCHAR(255)"