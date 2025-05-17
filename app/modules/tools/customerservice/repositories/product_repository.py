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
            print(f"[DEBUG] 开始根据ID获取商品: id={id}")
            query = select(Product).where(Product.id == id)
            result = await self.db.execute(query)
            product = result.scalars().first()
            
            if product:
                print(f"[DEBUG] 商品找到，正在加载图片: id={id}")
                # 加载商品图片
                product.images = await self.get_product_images_async(id)
                print(f"[DEBUG] 商品图片加载完成，共有{len(product.images)}张图片")
            else:
                print(f"[DEBUG] 未找到商品: id={id}")
            
            return product
        except Exception as ex:
            print(f"[ERROR] 获取商品失败, ID: {id}, 错误: {str(ex)}")
            import traceback
            print(f"[ERROR] 错误堆栈: {traceback.format_exc()}")
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
            print(f"[DEBUG] 开始根据编码获取商品: code={code}")
            query = select(Product).where(Product.code == code)
            result = await self.db.execute(query)
            product = result.scalars().first()
            
            if product:
                print(f"[DEBUG] 商品找到，正在加载图片: id={product.id}")
                # 加载商品图片
                product.images = await self.get_product_images_async(product.id)
                print(f"[DEBUG] 商品图片加载完成，共有{len(product.images)}张图片")
            else:
                print(f"[DEBUG] 未找到商品: code={code}")
            
            return product
        except Exception as ex:
            print(f"[ERROR] 根据编码获取商品失败, 编码: {code}, 错误: {str(ex)}")
            import traceback
            print(f"[ERROR] 错误堆栈: {traceback.format_exc()}")
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
            print(f"[DEBUG] 开始分页获取商品: user_id={user_id}, keyword={keyword}, page_index={page_index}, page_size={page_size}")
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
            print(f"[DEBUG] 满足条件的商品总数: {total_count}")
            
            # 查询分页数据
            query = query.order_by(desc(Product.id)).offset(skip).limit(page_size)
            result = await self.db.execute(query)
            items = result.scalars().all()
            print(f"[DEBUG] 当前页面获取到商品数量: {len(items)}")
            
            # 加载商品图片
            for product in items:
                product.images = await self.get_product_images_async(product.id)
            print(f"[DEBUG] 所有商品图片加载完成")
            
            return list(items), total_count
        except Exception as ex:
            print(f"[ERROR] 分页获取商品失败, 关键词: {keyword}, 错误: {str(ex)}")
            import traceback
            print(f"[ERROR] 错误堆栈: {traceback.format_exc()}")
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
        print(f"[DEBUG] 搜索商品，转发到分页获取商品方法: keyword={keyword}")
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
            print(f"[DEBUG] 开始获取热门商品: user_id={user_id}, top={top}")
            query = select(Product).where(
                Product.user_id == user_id,
                Product.status == 1
            ).order_by(desc(Product.id)).limit(top)
            
            result = await self.db.execute(query)
            items = result.scalars().all()
            print(f"[DEBUG] 获取到热门商品数量: {len(items)}")
            
            # 加载商品图片
            for product in items:
                product.images = await self.get_product_images_async(product.id)
            print(f"[DEBUG] 所有热门商品图片加载完成")
            
            return list(items)
        except Exception as ex:
            print(f"[ERROR] 获取热门商品失败, 用户ID: {user_id}, 错误: {str(ex)}")
            import traceback
            print(f"[ERROR] 错误堆栈: {traceback.format_exc()}")
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
            print(f"[DEBUG] 开始添加商品: user_id={product.user_id}, name={product.name}")
            product.id = generate_id()
            now = datetime.now()
            product.create_date = now
            product.last_modify_date = now
            
            print(f"[DEBUG] 生成的商品ID: {product.id}")
            self.db.add(product)
            print(f"[DEBUG] 已添加商品到数据库会话，等待flush")
            await self.db.flush()
            print(f"[DEBUG] 数据库flush完成")
            
            # 如果有图片，添加图片
            if product.images:
                print(f"[DEBUG] 开始添加{len(product.images)}张商品图片")
                for image in product.images:
                    image.product_id = product.id
                    await self.add_image_async(image)
                print(f"[DEBUG] 所有商品图片添加完成")
            
            # 添加事务提交
            print(f"[DEBUG] 准备提交事务")
            await self.db.commit()
            print(f"[DEBUG] 事务提交完成")
            
            return True
        except Exception as ex:
            print(f"[ERROR] 添加商品失败, 错误: {str(ex)}")
            print(f"[ERROR] 准备回滚事务")
            await self.db.rollback()
            print(f"[ERROR] 事务回滚完成")
            import traceback
            print(f"[ERROR] 错误堆栈: {traceback.format_exc()}")
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
            print(f"[DEBUG] 开始更新商品: id={product.id}")
            product.last_modify_date = datetime.now()
            await self.db.merge(product)
            print(f"[DEBUG] 商品合并完成，等待flush")
            await self.db.flush()
            print(f"[DEBUG] 数据库flush完成")
            
            # 添加事务提交
            print(f"[DEBUG] 准备提交事务")
            await self.db.commit()
            print(f"[DEBUG] 事务提交完成")
            
            return True
        except Exception as ex:
            print(f"[ERROR] 更新商品失败, ID: {product.id}, 错误: {str(ex)}")
            print(f"[ERROR] 准备回滚事务")
            await self.db.rollback()
            print(f"[ERROR] 事务回滚完成")
            import traceback
            print(f"[ERROR] 错误堆栈: {traceback.format_exc()}")
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
            print(f"[DEBUG] 开始删除商品: id={id}")
            # 删除商品图片
            print(f"[DEBUG] 先删除所有商品图片")
            await self.delete_all_images_async(id)
            
            # 删除商品
            query = select(Product).where(Product.id == id)
            result = await self.db.execute(query)
            product = result.scalars().first()
            
            if product:
                print(f"[DEBUG] 找到商品，准备删除: id={id}")
                await self.db.delete(product)
                print(f"[DEBUG] 商品删除，等待flush")
                await self.db.flush()
                print(f"[DEBUG] 数据库flush完成")
                
                # 添加事务提交
                print(f"[DEBUG] 准备提交事务")
                await self.db.commit()
                print(f"[DEBUG] 事务提交完成")
                
                return True
            else:
                print(f"[WARNING] 要删除的商品不存在: id={id}")
                return False
        except Exception as ex:
            print(f"[ERROR] 删除商品失败, ID: {id}, 错误: {str(ex)}")
            print(f"[ERROR] 准备回滚事务")
            await self.db.rollback()
            print(f"[ERROR] 事务回滚完成")
            import traceback
            print(f"[ERROR] 错误堆栈: {traceback.format_exc()}")
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
            print(f"[DEBUG] 获取商品图片: product_id={product_id}")
            query = select(ProductImage).where(
                ProductImage.product_id == product_id
            ).order_by(ProductImage.sort_order)
            
            result = await self.db.execute(query)
            images = list(result.scalars().all())
            print(f"[DEBUG] 获取到{len(images)}张商品图片")
            return images
        except Exception as ex:
            print(f"[ERROR] 获取商品图片失败, 商品ID: {product_id}, 错误: {str(ex)}")
            import traceback
            print(f"[ERROR] 错误堆栈: {traceback.format_exc()}")
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
            print(f"[DEBUG] 开始添加商品图片: product_id={image.product_id}")
            image.id = generate_id()
            now = datetime.now()
            image.create_date = now
            image.last_modify_date = now
            
            print(f"[DEBUG] 生成的图片ID: {image.id}")
            self.db.add(image)
            print(f"[DEBUG] 已添加图片到数据库会话，等待flush")
            await self.db.flush()
            print(f"[DEBUG] 数据库flush完成")
            
            # 添加事务提交
            print(f"[DEBUG] 准备提交事务")
            await self.db.commit()
            print(f"[DEBUG] 事务提交完成")
            
            return image
        except Exception as ex:
            print(f"[ERROR] 添加商品图片失败, 商品ID: {image.product_id}, 错误: {str(ex)}")
            print(f"[ERROR] 准备回滚事务")
            await self.db.rollback()
            print(f"[ERROR] 事务回滚完成")
            import traceback
            print(f"[ERROR] 错误堆栈: {traceback.format_exc()}")
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
            print(f"[DEBUG] 开始删除商品图片: product_id={product_id}, image_id={image_id}")
            query = select(ProductImage).where(
                ProductImage.id == image_id,
                ProductImage.product_id == product_id
            )
            result = await self.db.execute(query)
            image = result.scalars().first()
            
            if image:
                print(f"[DEBUG] 找到图片，准备删除")
                await self.db.delete(image)
                print(f"[DEBUG] 图片删除，等待flush")
                await self.db.flush()
                print(f"[DEBUG] 数据库flush完成")
                
                # 添加事务提交
                print(f"[DEBUG] 准备提交事务")
                await self.db.commit()
                print(f"[DEBUG] 事务提交完成")
                
                return True
            else:
                print(f"[WARNING] 要删除的图片不存在: product_id={product_id}, image_id={image_id}")
                return False
        except Exception as ex:
            print(f"[ERROR] 删除商品图片失败, ID: {image_id}, 错误: {str(ex)}")
            print(f"[ERROR] 准备回滚事务")
            await self.db.rollback()
            print(f"[ERROR] 事务回滚完成")
            import traceback
            print(f"[ERROR] 错误堆栈: {traceback.format_exc()}")
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
            print(f"[DEBUG] 开始删除商品所有图片: product_id={product_id}")
            query = select(ProductImage).where(ProductImage.product_id == product_id)
            result = await self.db.execute(query)
            images = result.scalars().all()
            print(f"[DEBUG] 找到{len(images)}张图片需要删除")
            
            for image in images:
                print(f"[DEBUG] 删除图片: id={image.id}")
                await self.db.delete(image)
            
            print(f"[DEBUG] 所有图片删除，等待flush")
            await self.db.flush()
            print(f"[DEBUG] 数据库flush完成")
            
            # 添加事务提交
            print(f"[DEBUG] 准备提交事务")
            await self.db.commit()
            print(f"[DEBUG] 事务提交完成")
            
            return True
        except Exception as ex:
            print(f"[ERROR] 删除商品所有图片失败, 商品ID: {product_id}, 错误: {str(ex)}")
            print(f"[ERROR] 准备回滚事务")
            await self.db.rollback()
            print(f"[ERROR] 事务回滚完成")
            import traceback
            print(f"[ERROR] 错误堆栈: {traceback.format_exc()}")
            raise