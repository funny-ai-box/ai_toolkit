# app/modules/dataanalysis/repositories/dynamic_page_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
import datetime

from app.core.utils.snowflake import generate_id
from app.modules.tools.dataanalysis.models import DynamicPage, PageComponent

class DynamicPageRepository:
    """动态页面仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化动态页面仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def add_async(self, dynamic_page: DynamicPage) -> DynamicPage:
        """
        添加动态页面
        
        Args:
            dynamic_page: 动态页面实体
            
        Returns:
            添加后的实体
        """
        # 使用雪花ID
        dynamic_page.id = generate_id()
        
        # 设置创建和修改时间
        now = datetime.datetime.now()
        dynamic_page.create_date = now
        dynamic_page.last_modify_date = now
        
        # 插入数据
        self.db.add(dynamic_page)
        await self.db.flush()
        await self.db.commit()
        
        return dynamic_page

    async def update_async(self, dynamic_page: DynamicPage) -> DynamicPage:
        """
        更新动态页面
        
        Args:
            dynamic_page: 动态页面实体
            
        Returns:
            更新后的实体
        """
        # 更新最后修改时间
        dynamic_page.last_modify_date = datetime.datetime.now()
        
        # 更新数据
        self.db.add(dynamic_page)
        await self.db.flush()
        await self.db.commit()
        
        return dynamic_page
    
    async def get_by_id_async(self, id: int) -> Optional[DynamicPage]:
        """
        获取动态页面
        
        Args:
            id: 动态页面ID
        
        Returns:
            动态页面实体
        """
        result = await self.db.execute(
            select(DynamicPage).filter(DynamicPage.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_pages_async(self, user_id: int) -> List[DynamicPage]:
        """
        获取用户的所有动态页面
        
        Args:
            user_id: 用户ID
        
        Returns:
            动态页面实体列表
        """
        result = await self.db.execute(
            select(DynamicPage)
            .filter(DynamicPage.user_id == user_id)
            .order_by(DynamicPage.create_date.desc())
        )
        return list(result.scalars().all())
    
    async def delete_async(self, id: int) -> bool:
        """
        删除动态页面
        
        Args:
            id: 动态页面ID
            
        Returns:
            是否成功
        """
        # 先删除关联的组件
        await self.db.execute(
            delete(PageComponent).filter(PageComponent.page_id == id)
        )
        
        # 再删除页面
        result = await self.db.execute(
            delete(DynamicPage).filter(DynamicPage.id == id)
        )
        
        await self.db.commit()
        
        return result.rowcount > 0

