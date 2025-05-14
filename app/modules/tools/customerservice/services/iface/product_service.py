"""
产品服务接口
"""
from typing import List, Optional
from fastapi import UploadFile

from app.core.dtos import PagedResultDto
from app.modules.tools.customerservice.services.dtos.product_dto import (
    ProductCreateDto, ProductUpdateDto, ProductDetailDto,
    ProductListRequestDto, ProductSearchRequestDto, ProductImageDto,
    ProductListItemDto
)

class IProductService:
    """商品服务接口"""
    
    async def get_product_async(self, user_id: int, id: int) -> ProductDetailDto:
        """
        获取商品详情
        
        Args:
            user_id: 用户ID
            id: 商品ID
            
        Returns:
            商品详情DTO
        """
        raise NotImplementedError()
    
    async def get_product_by_code_async(self, user_id: int, code: str) -> ProductDetailDto:
        """
        根据编码获取商品
        
        Args:
            user_id: 用户ID
            code: 商品编码
            
        Returns:
            商品详情DTO
        """
        raise NotImplementedError()
    
    async def get_products_async(self, user_id: int, request: ProductListRequestDto) -> PagedResultDto[ProductListItemDto]:
        """
        分页获取商品列表
        
        Args:
            user_id: 用户ID
            request: 请求参数
            
        Returns:
            分页商品列表
        """
        raise NotImplementedError()
    
    async def search_products_async(self, user_id: int, request: ProductSearchRequestDto) -> PagedResultDto[ProductListItemDto]:
        """
        搜索商品
        
        Args:
            user_id: 用户ID
            request: 搜索请求
            
        Returns:
            搜索结果
        """
        raise NotImplementedError()
    
    async def get_hot_products_async(self, user_id: int, top: int) -> List[ProductListItemDto]:
        """
        获取热门商品
        
        Args:
            user_id: 用户ID
            top: 数量
            
        Returns:
            热门商品列表
        """
        raise NotImplementedError()
    
    async def create_product_async(self, user_id: int, request: ProductCreateDto, images: Optional[List[UploadFile]] = None) -> int:
        """
        创建商品
        
        Args:
            user_id: 用户ID
            request: 商品信息
            images: 商品图片
            
        Returns:
            商品ID
        """
        raise NotImplementedError()
    
    async def update_product_async(self, user_id: int, request: ProductUpdateDto) -> bool:
        """
        更新商品
        
        Args:
            user_id: 用户ID
            request: 商品信息
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def delete_product_async(self, user_id: int, id: int) -> bool:
        """
        删除商品
        
        Args:
            user_id: 用户ID
            id: 商品ID
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def update_product_status_async(self, id: int, status: int) -> bool:
        """
        更新商品状态
        
        Args:
            id: 商品ID
            status: 状态值
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def upload_product_image_async(self, user_id: int, product_id: int, image: UploadFile) -> ProductImageDto:
        """
        上传商品图片
        
        Args:
            user_id: 用户ID
            product_id: 商品ID
            image: 图片文件
            
        Returns:
            图片信息
        """
        raise NotImplementedError()
    
    async def delete_product_image_async(self, user_id: int, product_id: int, image_id: int) -> bool:
        """
        删除商品图片
        
        Args:
            user_id: 用户ID
            product_id: 商品ID
            image_id: 图片ID
            
        Returns:
            操作结果
        """
        raise NotImplementedError()