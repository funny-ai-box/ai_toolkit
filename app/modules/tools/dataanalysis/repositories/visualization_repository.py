from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
import datetime
import os
import json

from app.core.utils.snowflake import generate_id
from app.modules.tools.dataanalysis.models import Visualization
from app.modules.tools.dataanalysis.services.visualiz_html_service import VisualizHtmlService

class VisualizationRepository:
    """可视化配置仓储实现"""
    
    def __init__(self, db: AsyncSession, visualiz_html_service: 'VisualizHtmlService', 
                 visualization_path: str = "uploads/generate"):
        """
        初始化可视化配置仓储
        
        Args:
            db: 数据库会话
            visualiz_html_service: 可视化 HTML 服务
            visualization_path: 可视化目录路径
        """
        self.db = db
        self.visualiz_html_service = visualiz_html_service
        self.visualization_path = visualization_path
    
    async def add_async(self, visualization: Visualization) -> Visualization:
        """
        添加可视化配置
        
        Args:
            visualization: 可视化配置实体
        
        Returns:
            添加后的实体
        """
        # 使用雪花ID
        visualization.id = generate_id()
        
        # 设置创建和修改时间
        now = datetime.datetime.now()
        visualization.create_date = now
        visualization.last_modify_date = now
        
        # 插入数据
        self.db.add(visualization)
        await self.db.flush()
        
        return visualization
    
    async def update_async(self, visualization: Visualization) -> Visualization:
        """
        更新可视化配置
        
        Args:
            visualization: 可视化配置实体
        
        Returns:
            更新后的实体
        """
        # 更新最后修改时间
        visualization.last_modify_date = datetime.datetime.now()
        
        # 更新数据
        self.db.add(visualization)
        await self.db.flush()
        
        return visualization
    
    async def get_by_id_async(self, id: int) -> Optional[Visualization]:
        """
        获取可视化配置
        
        Args:
            id: 可视化配置ID
        
        Returns:
            可视化配置实体
        """
        result = await self.db.execute(
            select(Visualization).filter(Visualization.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_sql_execution_id_async(self, sql_execution_id: int) -> Optional[Visualization]:
        """
        获取SQL执行记录的可视化配置
        
        Args:
            sql_execution_id: SQL执行记录ID
        
        Returns:
            可视化配置实体
        """
        result = await self.db.execute(
            select(Visualization).filter(Visualization.sql_execution_id == sql_execution_id)
        )
        return result.scalar_one_or_none()
    
    async def generate_visualization_html_async(self, visualization: Visualization, sql_result: str) -> str:
        """
        生成可视化HTML文件
        
        Args:
            visualization: 可视化配置实体
            sql_result: SQL查询结果（JSON字符串）
        
        Returns:
            生成的HTML文件路径
        """
        # 确保目录存在
        os.makedirs(self.visualization_path, exist_ok=True)
        
        # 生成文件名
        file_name = f"{visualization.id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.html"
        file_path = os.path.join(self.visualization_path, file_name)
        
        # 生成HTML内容
        html_content = self.visualiz_html_service.generate_html_content(visualization, sql_result)
        
        # 保存HTML文件
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        