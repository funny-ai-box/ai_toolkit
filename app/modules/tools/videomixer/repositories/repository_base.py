"""
视频混剪仓储基类
"""
from typing import Generic, TypeVar, List, Tuple, Optional, Type, Any, Dict
from sqlalchemy import select, delete, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.snowflake import generate_id

# 定义泛型类型变量
T = TypeVar('T')

class BaseRepository(Generic[T]):
    """仓储基类"""
    
    def __init__(self, db: AsyncSession, entity_type: Type[T]):
        """
        初始化仓储
        
        Args:
            db: 数据库会话
            entity_type: 实体类型
        """
        self.db = db
        self.entity_type = entity_type
    
    async def add(self, entity: T) -> int:
        """
        添加实体
        
        Args:
            entity: 实体对象
        
        Returns:
            新增实体的ID
        """
        entity.id = generate_id()
        
        # 设置创建时间和最后修改时间
        if hasattr(entity, 'create_date') and not getattr(entity, 'create_date', None):
            import datetime
            now = datetime.datetime.now()
            entity.create_date = now
            
        if hasattr(entity, 'last_modify_date'):
            import datetime
            now = datetime.datetime.now()
            entity.last_modify_date = now
            
        self.db.add(entity)
        await self.db.flush()
        return entity.id
    
    async def add_batch(self, entities: List[T]) -> int:
        """
        批量添加实体
        
        Args:
            entities: 实体对象列表
        
        Returns:
            添加的数量
        """
        if not entities:
            return 0
            
        import datetime
        now = datetime.datetime.now()
        
        for entity in entities:
            entity.id = generate_id()
            
            # 设置创建时间和最后修改时间
            if hasattr(entity, 'create_date') and not getattr(entity, 'create_date', None):
                entity.create_date = now
                
            if hasattr(entity, 'last_modify_date'):
                entity.last_modify_date = now
        
        self.db.add_all(entities)
        await self.db.flush()
        return len(entities)
    
    async def get_by_id(self, id: int) -> Optional[T]:
        """
        根据ID获取实体
        
        Args:
            id: 实体ID
        
        Returns:
            实体对象，不存在时返回None
        """
        result = await self.db.execute(
            select(self.entity_type).where(self.entity_type.id == id)
        )
        return result.scalars().first()
    
    async def update(self, entity: T) -> bool:
        """
        更新实体
        
        Args:
            entity: 实体对象
        
        Returns:
            更新是否成功
        """
        if hasattr(entity, 'last_modify_date'):
            import datetime
            entity.last_modify_date = datetime.datetime.now()
            
        self.db.add(entity)
        await self.db.flush()
        return True
    
    async def delete(self, id: int) -> bool:
        """
        删除实体
        
        Args:
            id: 实体ID
        
        Returns:
            删除是否成功
        """
        await self.db.execute(
            delete(self.entity_type).where(self.entity_type.id == id)
        )
        await self.db.flush()
        return True