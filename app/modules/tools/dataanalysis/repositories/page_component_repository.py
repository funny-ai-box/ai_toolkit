# app/modules/dataanalysis/repositories/page_component_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
import datetime

from app.core.utils.snowflake import generate_id
from app.modules.tools.dataanalysis.models import PageComponent

class PageComponentRepository:
    """页面组件仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化页面组件仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def add_async(self, page_component: PageComponent) -> PageComponent:
        """
        添加页面组件
        
        Args:
            page_component: 页面组件实体
        
        Returns:
            添加后的实体
        """
        # 使用雪花ID
        page_component.id = generate_id()
        
        # 设置创建和修改时间
        now = datetime.datetime.now()
        page_component.create_date = now
        page_component.last_modify_date = now
        
        # 插入数据
        self.db.add(page_component)
        await self.db.flush()
        await self.db.commit()  # 添加commit确保数据持久化
        
        return page_component
    
    async def update_async(self, page_component: PageComponent) -> PageComponent:
        """
        更新页面组件
        
        Args:
            page_component: 页面组件实体
        
        Returns:
            更新后的实体
        """
        # 更新最后修改时间
        page_component.last_modify_date = datetime.datetime.now()
        
        # 更新数据
        self.db.add(page_component)
        await self.db.flush()
        await self.db.commit()  # 添加commit确保数据持久化
        
        return page_component
    
    async def get_by_id_async(self, id: int) -> Optional[PageComponent]:
        """
        获取页面组件
        
        Args:
            id: 页面组件ID
        
        Returns:
            页面组件实体
        """
        result = await self.db.execute(
            select(PageComponent).filter(PageComponent.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_page_components_async(self, page_id: int) -> List[PageComponent]:
        """
        获取动态页面的所有组件
        
        Args:
            page_id: 动态页面ID
        
        Returns:
            页面组件实体列表
        """
        result = await self.db.execute(
            select(PageComponent)
            .filter(PageComponent.page_id == page_id)
            .order_by(PageComponent.id)
        )
        return list(result.scalars().all())
    
    async def delete_async(self, id: int) -> bool:
        """
        删除页面组件
        
        Args:
            id: 页面组件ID
        
        Returns:
            是否成功
        """
        result = await self.db.execute(
            delete(PageComponent).filter(PageComponent.id == id)
        )
        await self.db.commit()  # 添加commit确保数据持久化
        return result.rowcount > 0