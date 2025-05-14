"""
商品仓储实现
"""
from typing import List, Tuple, Optional
import logging
from datetime import datetime
from sqlalchemy import select, func, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessException
from app.core.utils.snowflake import generate_id
from app.modules.tools.customerservice.entities.product import Product, ProductImage
from app.modules.tools.customerservice.repositories.iface.product_repository import IProductRepository

class ProductRepository(IProductRepository):
    """商品仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化商品仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.logger = logging.getLogger(__name__)
    
    async def get_by_id_async(self, id: int) -> Optional[Product]:
        """
        根据ID获取商品
        
        Args:
            id: 商品ID
            
        Returns:
            商品实体
        """
        try:
            query = select(Product).where(Product.id == id)
            result = await self.db.execute(query)
            product = result.scalars().first()
            
            if product:
                # 加载商品图片
                product.images = await self.get_product_images_async(id)
            
            return product
        except Exception as ex:
            self.logger.error(f"获取商品失败, ID: {id}, 错误: {str(ex)}")
            raise
    
    async def get_by_code_async(self, code: str) -> Optional[Product]:
        """
        根据编码获取商品
        
        Args:
            code: 商品编码
            
        Returns:
            商品实体
        """
        try:
            query = select(Product).where(Product.code == code)
            result = await self.db.execute(query)
            product = result.scalars().first()
            
            if product:
                # 加载商品图片
                product.images = await self.get_product_images_async(product.id)
            
            return product
        except Exception as ex:
            self.logger.error(f"根据编码获取商品失败, 编码: {code}, 错误: {str(ex)}")
            raise
    
    async def get_paginated_async(
        self, user_id: int, keyword: str, page_index: int = 1, page_size: int = 20
    ) -> Tuple[List[Product], int]:
        """
        获取所有商品
        
        Args:
            user_id: 用户ID
            keyword: 关键词
            page_index: 页码
            page_size: 每页大小
            
        Returns:
            商品列表和总数
        """
        try:
            # 确保页码和每页数量有效
            if page_index < 1:
                page_index = 1
            if page_size < 1:
                page_size = 20
                
            # 计算跳过的记录数
            skip = (page_index - 1) * page_size
            
            # 构建查询条件
            query = select(Product).where(Product.user_id == user_id)
            
            if keyword:
                query = query.where(
                    or_(
                        Product.name.contains(keyword),
                        Product.code.contains(keyword),
                        Product.description.contains(keyword),
                        Product.selling_points.contains(keyword)
                    )
                )
            
            # 查询满足条件的记录总数
            count_query = select(func.count()).select_from(query.subquery())
            total_count = await self.db.scalar(count_query) or 0
            
            # 查询分页数据
            query = query.order_by(desc(Product.id)).offset(skip).limit(page_size)
            result = await self.db.execute(query)
            items = result.scalars().all()
            
            # 加载商品图片
            for product in items:
                product.images = await self.get_product_images_async(product.id)
            
            return list(items), total_count
        except Exception as ex:
            self.logger.error(f"分页获取商品失败, 关键词: {keyword}, 错误: {str(ex)}")
            raise
    
    async def search_async(
        self, user_id: int, keyword: str, page_index: int = 1, page_size: int = 20
    ) -> Tuple[List[Product], int]:
        """
        根据关键词搜索商品
        
        Args:
            user_id: 用户ID
            keyword: 关键词
            page_index: 页码
            page_size: 每页大小
            
        Returns:
            商品列表和总数
        """
        # 与get_paginated_async实现相同，因为都是搜索
        return await self.get_paginated_async(user_id, keyword, page_index, page_size)
    
    async def get_hot_products_async(self, user_id: int, top: int) -> List[Product]:
        """
        随机获取top个商品作为热销推荐
        
        Args:
            user_id: 用户ID
            top: 数量
            
        Returns:
            商品列表
        """
        try:
            query = select(Product).where(
                Product.user_id == user_id,
                Product.status == 1
            ).order_by(desc(Product.id)).limit(top)
            
            result = await self.db.execute(query)
            items = result.scalars().all()
            
            # 加载商品图片
            for product in items:
                product.images = await self.get_product_images_async(product.id)
            
            return list(items)
        except Exception as ex:
            self.logger.error(f"获取热门商品失败, 用户ID: {user_id}, 错误: {str(ex)}")
            raise
    
    async def add_async(self, product: Product) -> bool:
        """
        添加商品
        
        Args:
            product: 商品实体
            
        Returns:
            操作结果
        """
        try:
            product.id = generate_id()
            now = datetime.now()
            product.create_date = now
            product.last_modify_date = now
            
            self.db.add(product)
            await self.db.flush()
            
            # 如果有图片，添加图片
            if product.images:
                for image in product.images:
                    image.product_id = product.id
                    await self.add_image_async(image)
            
            return True
        except Exception as ex:
            self.logger.error(f"添加商品失败, 错误: {str(ex)}")
            raise
    
    async def update_async(self, product: Product) -> bool:
        """
        更新商品
        
        Args:
            product: 商品实体
            
        Returns:
            操作结果
        """
        try:
            product.last_modify_date = datetime.now()
            await self.db.merge(product)
            await self.db.flush()
            return True
        except Exception as ex:
            self.logger.error(f"更新商品失败, ID: {product.id}, 错误: {str(ex)}")
            raise
    
    async def delete_async(self, id: int) -> bool:
        """
        删除商品
        
        Args:
            id: 商品ID
            
        Returns:
            操作结果
        """
        try:
            # 删除商品图片
            await self.delete_all_images_async(id)
            
            # 删除商品
            query = select(Product).where(Product.id == id)
            result = await self.db.execute(query)
            product = result.scalars().first()
            
            if product:
                await self.db.delete(product)
                await self.db.flush()
                return True
            
            return False
        except Exception as ex:
            self.logger.error(f"删除商品失败, ID: {id}, 错误: {str(ex)}")
            raise
    
    async def get_product_images_async(self, product_id: int) -> List[ProductImage]:
        """
        获取商品图片
        
        Args:
            product_id: 商品ID
            
        Returns:
            图片列表
        """
        try:
            query = select(ProductImage).where(
                ProductImage.product_id == product_id
            ).order_by(ProductImage.sort_order)
            
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as ex:
            self.logger.error(f"获取商品图片失败, 商品ID: {product_id}, 错误: {str(ex)}")
            raise
    
    async def add_image_async(self, image: ProductImage) -> ProductImage:
        """
        添加商品图片
        
        Args:
            image: 图片实体
            
        Returns:
            图片实体
        """
        try:
            image.id = generate_id()
            now = datetime.now()
            image.create_date = now
            image.last_modify_date = now
            
            self.db.add(image)
            await self.db.flush()
            return image
        except Exception as ex:
            self.logger.error(f"添加商品图片失败, 商品ID: {image.product_id}, 错误: {str(ex)}")
            raise
    
    async def delete_image_async(self, product_id: int, image_id: int) -> bool:
        """
        删除商品图片
        
        Args:
            product_id: 商品ID
            image_id: 图片ID
            
        Returns:
            操作结果
        """
        try:
            query = select(ProductImage).where(
                ProductImage.id == image_id,
                ProductImage.product_id == product_id
            )
            result = await self.db.execute(query)
            image = result.scalars().first()
            
            if image:
                await self.db.delete(image)
                await self.db.flush()
                return True
            
            return False
        except Exception as ex:
            self.logger.error(f"删除商品图片失败, ID: {image_id}, 错误: {str(ex)}")
            raise
    
    async def delete_all_images_async(self, product_id: int) -> bool:
        """
        删除商品所有图片
        
        Args:
            product_id: 商品ID
            
        Returns:
            操作结果
        """
        try:
            query = select(ProductImage).where(ProductImage.product_id == product_id)
            result = await self.db.execute(query)
            images = result.scalars().all()
            
            for image in images:
                await self.db.delete(image)
            
            await self.db.flush()
            return True
        except Exception as ex:
            self.logger.error(f"删除商品所有图片失败, 商品ID: {product_id}, 错误: {str(ex)}")
            raise