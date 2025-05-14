"""
商品仓储接口
"""
from typing import List, Tuple, Optional
from app.modules.tools.customerservice.entities.product import Product, ProductImage

class IProductRepository:
    """商品仓储接口"""
    
    async def get_by_id_async(self, id: int) -> Optional[Product]:
        """
        根据ID获取商品
        
        Args:
            id: 商品ID
            
        Returns:
            商品实体
        """
        raise NotImplementedError()
    
    async def get_by_code_async(self, code: str) -> Optional[Product]:
        """
        根据编码获取商品
        
        Args:
            code: 商品编码
            
        Returns:
            商品实体
        """
        raise NotImplementedError()
    
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
        raise NotImplementedError()
    
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
        raise NotImplementedError()
    
    async def get_hot_products_async(self, user_id: int, top: int) -> List[Product]:
        """
        随机获取top个商品作为热销推荐
        
        Args:
            user_id: 用户ID
            top: 数量
            
        Returns:
            商品列表
        """
        raise NotImplementedError()
    
    async def add_async(self, product: Product) -> bool:
        """
        添加商品
        
        Args:
            product: 商品实体
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def update_async(self, product: Product) -> bool:
        """
        更新商品
        
        Args:
            product: 商品实体
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def delete_async(self, id: int) -> bool:
        """
        删除商品
        
        Args:
            id: 商品ID
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def get_product_images_async(self, product_id: int) -> List[ProductImage]:
        """
        获取商品图片
        
        Args:
            product_id: 商品ID
            
        Returns:
            图片列表
        """
        raise NotImplementedError()
    
    async def add_image_async(self, image: ProductImage) -> ProductImage:
        """
        添加商品图片
        
        Args:
            image: 图片实体
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def delete_image_async(self, product_id: int, image_id: int) -> bool:
        """
        删除商品图片
        
        Args:
            product_id: 商品ID
            image_id: 图片ID
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def delete_all_images_async(self, product_id: int) -> bool:
        """
        删除商品所有图片
        
        Args:
            product_id: 商品ID
            
        Returns:
            操作结果
        """
        raise NotImplementedError()