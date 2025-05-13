"""
商品仓储实现
"""
import datetime
import logging
from typing import List, Tuple, Optional

from sqlalchemy import select, update, delete, desc, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException
from app.core.utils.snowflake import generate_id
from app.modules.tools.customerservice.entities import Product, ProductImage

logger = logging.getLogger(__name__)


class ProductRepository:
    """商品仓储"""

    def __init__(self, db: AsyncSession):
        """
        初始化商品仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, id: int) -> Optional[Product]:
        """
        根据ID获取商品
        
        Args:
            id: 商品ID
            
        Returns:
            商品实体
        """
        try:
            result = await self.db.execute(
                select(Product).where(Product.id == id)
            )
            product = result.scalar_one_or_none()
            
            if product:
                # 加载商品图片
                product.images = await self.get_product_images_async(id)
                
            return product
        except Exception as ex:
            logger.error(f"获取商品失败, ID: {id}", exc_info=ex)
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
            result = await self.db.execute(
                select(Product).where(Product.code == code)
            )
            product = result.scalar_one_or_none()
            
            if product:
                # 加载商品图片
                product.images = await self.get_product_images_async(product.id)
                return product
            else:
                raise BusinessException(f"商品 {code} 不存在")
        except BusinessException:
            raise
        except Exception as ex:
            logger.error(f"根据编码获取商品失败, 编码: {code}", exc_info=ex)
            raise

    async def get_paginated_async(
        self, user_id: int, keyword: str, page_index: int = 1, page_size: int = 20
    ) -> Tuple[List[Product], int]:
        """
        获取所有商品
        
        Args:
            user_id: 用户ID
            keyword: 搜索关键词
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
            
            if keyword and keyword.strip():
                query = query.where(
                    or_(
                        Product.name.contains(keyword),
                        Product.code.contains(keyword),
                        Product.description.contains(keyword),
                        Product.selling_points.contains(keyword)
                    )
                )
                
            # 查询满足条件的记录总数
            count_query = select(func.count()).select_from(
                select(Product.id).where(Product.user_id == user_id)
            )
            
            if keyword and keyword.strip():
                count_query = select(func.count()).select_from(
                    select(Product.id).where(
                        (Product.user_id == user_id) &
                        or_(
                            Product.name.contains(keyword),
                            Product.code.contains(keyword),
                            Product.description.contains(keyword),
                            Product.selling_points.contains(keyword)
                        )
                    )
                )
                
            count_result = await self.db.execute(count_query)
            total_count = count_result.scalar_one()
            
            # 查询分页数据
            query = query.order_by(desc(Product.id)).offset(skip).limit(page_size)
            
            result = await self.db.execute(query)
            items = list(result.scalars().all())
            
            # 加载商品图片
            for product in items:
                product.images = await self.get_product_images_async(product.id)
                
            return items, total_count
        except Exception as ex:
            logger.error(f"搜索商品失败, 关键词: {keyword}", exc_info=ex)
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
                (Product.user_id == user_id) & (Product.status == 1)
            )
            
            # 随机排序，获取推荐商品
            query = query.order_by(desc(Product.id)).limit(top)
            
            result = await self.db.execute(query)
            items = list(result.scalars().all())
            
            # 加载商品图片
            for product in items:
                product.images = await self.get_product_images_async(product.id)
                
            return items
        except Exception as ex:
            logger.error(f"获取热销推荐商品失败, top: {top}", exc_info=ex)
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
            now = datetime.datetime.now()
            product.create_date = now
            product.last_modify_date = now
            
            self.db.add(product)
            await self.db.flush()
            
            # 如果有图片，添加图片
            if product.images and len(product.images) > 0:
                for image in product.images:
                    image.product_id = product.id
                    await self.add_image_async(image)
                    
            return True
        except Exception as ex:
            logger.error("添加商品失败", exc_info=ex)
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
            product.last_modify_date = datetime.datetime.now()
            
            await self.db.execute(
                update(Product)
                .where(Product.id == product.id)
                .values(
                    code=product.code,
                    name=product.name,
                    price=product.price,
                    description=product.description,
                    selling_points=product.selling_points,
                    stock=product.stock,
                    status=product.status,
                    last_modify_date=product.last_modify_date
                )
            )
            await self.db.flush()
            return True
        except Exception as ex:
            logger.error(f"更新商品失败, ID: {product.id}", exc_info=ex)
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
            await self.db.execute(
                delete(Product).where(Product.id == id)
            )
            await self.db.flush()
            return True
        except Exception as ex:
            logger.error(f"删除商品失败, ID: {id}", exc_info=ex)
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
            result = await self.db.execute(
                select(ProductImage)
                .where(ProductImage.product_id == product_id)
                .order_by(ProductImage.sort_order)
            )
            return list(result.scalars().all())
        except Exception as ex:
            logger.error(f"获取商品图片失败, 商品ID: {product_id}", exc_info=ex)
            raise

    async def add_image_async(self, image: ProductImage) -> ProductImage:
        """
        添加商品图片
        
        Args:
            image: 图片实体
            
        Returns:
            操作结果
        """
        try:
            image.id = generate_id()
            now = datetime.datetime.now()
            image.create_date = now
            image.last_modify_date = now
            
            self.db.add(image)
            await self.db.flush()
            
            return image
        except Exception as ex:
            logger.error(f"添加商品图片失败, 商品ID: {image.product_id}", exc_info=ex)
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
            await self.db.execute(
                delete(ProductImage).where(
                    (ProductImage.id == image_id) & 
                    (ProductImage.product_id == product_id)
                )
            )
            await self.db.flush()
            return True
        except Exception as ex:
            logger.error(f"删除商品图片失败, ID: {image_id}", exc_info=ex)
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
            await self.db.execute(
                delete(ProductImage).where(ProductImage.product_id == product_id)
            )
            await self.db.flush()
            return True
        except Exception as ex:
            logger.error(f"删除商品所有图片失败, 商品ID: {product_id}", exc_info=ex)
            raise