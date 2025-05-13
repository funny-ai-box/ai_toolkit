"""
商品服务实现
"""
import logging
import datetime
import os
from typing import List, Optional, Dict, Any

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException, ValidationException
from app.core.dtos import PagedResultDto
from app.core.storage.base import IStorageService
from app.modules.tools.customerservice.dtos import (
    ProductDetailDto, ProductListItemDto, ProductImageDto,
    ProductCreateDto, ProductUpdateDto, ProductSearchRequestDto
)
from app.modules.tools.customerservice.entities import Product, ProductImage
from app.modules.tools.customerservice.repositories.product_repository import ProductRepository

logger = logging.getLogger(__name__)


class ProductService:
    """商品服务"""

    def __init__(
        self,
        db: AsyncSession,
        storage_service: IStorageService
    ):
        """
        初始化商品服务
        
        Args:
            db: 数据库会话
            storage_service: 存储服务
        """
        self.db = db
        self.storage_service = storage_service
        self.repository = ProductRepository(db)
        self.image_path = "customerservice/images"

    async def get_product_async(self, user_id: int, id: int) -> ProductDetailDto:
        """
        获取商品详情
        
        Args:
            user_id: 用户ID
            id: 商品ID
            
        Returns:
            商品详情
        """
        try:
            product = await self.repository.get_by_id_async(id)
            if product is None or product.user_id != user_id:
                raise BusinessException("商品不存在或无权限访问")
                
            return self._map_to_product_detail_dto(product)
        except BusinessException:
            raise
        except Exception as ex:
            logger.error(f"获取商品详情失败，ID: {id}", exc_info=ex)
            raise

    async def get_product_by_code_async(self, user_id: int, code: str) -> ProductDetailDto:
        """
        根据编码获取商品
        
        Args:
            user_id: 用户ID
            code: 商品编码
            
        Returns:
            商品详情
        """
        try:
            product = await self.repository.get_by_code_async(code)
            if product is None or product.user_id != user_id:
                raise BusinessException("商品不存在或无权限访问")
                
            return self._map_to_product_detail_dto(product)
        except BusinessException:
            raise
        except Exception as ex:
            logger.error(f"根据编码获取商品失败，编码: {code}", exc_info=ex)
            raise

    async def get_products_async(self, user_id: int, request: Dict[str, Any]) -> PagedResultDto[ProductListItemDto]:
        """
        分页获取商品列表
        
        Args:
            user_id: 用户ID
            request: 请求参数
            
        Returns:
            分页商品列表
        """
        try:
            keyword = request.get("keyword", "")
            page_index = request.get("pageIndex", 1)
            page_size = request.get("pageSize", 20)
            
            items, total_count = await self.repository.get_paginated_async(
                user_id, keyword, page_index, page_size
            )
            
            result = PagedResultDto[ProductListItemDto](
                items=[self._map_to_product_list_item_dto(item) for item in items],
                total_count=total_count,
                page_index=page_index,
                page_size=page_size,
                total_pages=(total_count + page_size - 1) // page_size
            )
            
            return result
        except Exception as ex:
            logger.error("分页获取商品列表失败", exc_info=ex)
            raise

    async def search_products_async(self, user_id: int, request: Dict[str, Any]) -> PagedResultDto[ProductListItemDto]:
        """
        搜索商品
        
        Args:
            user_id: 用户ID
            request: 搜索请求
            
        Returns:
            搜索结果
        """
        try:
            keyword = request.get("keyword", "")
            page_index = request.get("pageIndex", 1)
            page_size = request.get("pageSize", 20)
            
            items, total_count = await self.repository.search_async(
                user_id, keyword, page_index, page_size
            )
            
            result = PagedResultDto[ProductListItemDto](
                items=[self._map_to_product_list_item_dto(item) for item in items],
                total_count=total_count,
                page_index=page_index,
                page_size=page_size,
                total_pages=(total_count + page_size - 1) // page_size
            )
            
            return result
        except Exception as ex:
            logger.error(f"搜索商品失败，关键词: {request.get('keyword')}", exc_info=ex)
            raise

    async def get_hot_products_async(self, user_id: int, top: int) -> List[ProductListItemDto]:
        """
        获取热门商品
        
        Args:
            user_id: 用户ID
            top: 数量限制
            
        Returns:
            商品列表
        """
        try:
            items = await self.repository.get_hot_products_async(user_id, top)
            return [self._map_to_product_list_item_dto(item) for item in items]
        except Exception as ex:
            logger.error(f"获取热门商品失败, top: {top}", exc_info=ex)
            raise

    async def create_product_async(self, user_id: int, request: ProductCreateDto, images: Optional[List[UploadFile]] = None) -> int:
        """
        创建商品
        
        Args:
            user_id: 用户ID
            request: 创建请求
            images: 商品图片
            
        Returns:
            商品ID
        """
        try:
            # 检查商品编码是否已存在
            try:
                await self.repository.get_by_code_async(request.code)
                raise ValidationException(f"商品编码 {request.code} 已存在")
            except BusinessException:
                # 如果商品不存在，继续创建
                pass
                
            # 创建商品
            product = Product(
                user_id=user_id,
                code=request.code,
                name=request.name,
                price=request.price,
                description=request.description,
                selling_points=request.selling_points,
                stock=request.stock,
                status=request.status,
                images=[]
            )
            
            # 添加商品
            await self.repository.add_async(product)
            
            # 上传商品图片
            if images and len(images) > 0:
                await self._upload_product_images_async(product.id, images)
                
            return product.id
        except ValidationException:
            raise
        except Exception as ex:
            logger.error("创建商品失败", exc_info=ex)
            raise

    async def update_product_async(self, user_id: int, request: ProductUpdateDto) -> bool:
        """
        更新商品
        
        Args:
            user_id: 用户ID
            request: 更新请求
            
        Returns:
            操作结果
        """
        try:
            # 检查商品是否存在
            product = await self.repository.get_by_id_async(request.id)
            if product is None or product.user_id != user_id:
                raise BusinessException("商品不存在或无权限访问")
                
            # 如果修改了商品编码，检查新编码是否已存在
            if request.code and request.code != product.code:
                try:
                    existing_product = await self.repository.get_by_code_async(request.code)
                    if existing_product.id != request.id:
                        raise ValidationException(f"商品编码 {request.code} 已存在")
                except BusinessException:
                    # 如果商品不存在，可以使用这个编码
                    product.code = request.code
                
            # 更新商品信息
            if request.name:
                product.name = request.name
                
            if request.price is not None:
                product.price = request.price
                
            if request.description is not None:
                product.description = request.description
                
            if request.selling_points is not None:
                product.selling_points = request.selling_points
                
            if request.stock is not None:
                product.stock = request.stock
                
            if request.status is not None:
                product.status = request.status
                
            # 更新商品
            result = await self.repository.update_async(product)
            
            return result
        except BusinessException:
            raise
        except ValidationException:
            raise
        except Exception as ex:
            logger.error(f"更新商品失败，ID: {request.id}", exc_info=ex)
            raise

    async def delete_product_async(self, user_id: int, id: int) -> bool:
        """
        删除商品
        
        Args:
            user_id: 用户ID
            id: 商品ID
            
        Returns:
            操作结果
        """
        try:
            # 检查商品是否存在
            product = await self.repository.get_by_id_async(id)
            if product is None or product.user_id != user_id:
                raise BusinessException("商品不存在或无权限访问")
                
            # 删除商品
            return await self.repository.delete_async(id)
        except BusinessException:
            raise
        except Exception as ex:
            logger.error(f"删除商品失败，ID: {id}", exc_info=ex)
            raise

    async def update_product_status_async(self, id: int, status: int) -> bool:
        """
        更新商品状态
        
        Args:
            id: 商品ID
            status: 状态值
            
        Returns:
            操作结果
        """
        try:
            # 检查商品是否存在
            product = await self.repository.get_by_id_async(id)
            if product is None:
                raise BusinessException(f"商品不存在，ID: {id}")
                
            # 更新状态
            product.status = status
            return await self.repository.update_async(product)
        except BusinessException:
            raise
        except Exception as ex:
            logger.error(f"更新商品状态失败，ID: {id}，状态: {status}", exc_info=ex)
            raise

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
        try:
            # 检查商品是否存在
            product = await self.repository.get_by_id_async(product_id)
            if product is None or product.user_id != user_id:
                raise BusinessException("商品不存在或无权限访问")
                
            # 获取现有图片列表，确定排序位置
            images = await self.repository.get_product_images_async(product_id)
            sort_order = max([image.sort_order for image in images]) + 1 if images else 0
            
            # 上传图片
            file_key = f"{self.image_path}/{product_id}/{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{image.filename}"
            image_url = await self.storage_service.upload_async(image.file, file_key, image.content_type)
            
            # 创建图片记录
            product_image = ProductImage(
                product_id=product_id,
                image_url=image_url,
                sort_order=sort_order
            )
            
            # 添加图片
            db_img = await self.repository.add_image_async(product_image)
            
            return ProductImageDto(
                id=db_img.id,
                product_id=db_img.product_id,
                image_url=db_img.image_url,
                sort_order=db_img.sort_order
            )
        except BusinessException:
            raise
        except Exception as ex:
            logger.error(f"上传商品图片失败，商品ID: {product_id}", exc_info=ex)
            raise

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
        try:
            product = await self.repository.get_by_id_async(product_id)
            if product is None or product.user_id != user_id:
                raise BusinessException("商品不存在或无权限访问")
                
            return await self.repository.delete_image_async(product_id, image_id)
        except BusinessException:
            raise
        except Exception as ex:
            logger.error(f"删除商品图片失败，图片ID: {image_id}", exc_info=ex)
            raise

    async def _upload_product_images_async(self, product_id: int, images: List[UploadFile]) -> bool:
        """
        批量上传商品图片
        
        Args:
            product_id: 商品ID
            images: 图片文件列表
            
        Returns:
            操作结果
        """
        try:
            if not images or len(images) == 0:
                return False
                
            # 获取现有图片列表，确定排序位置
            existing_images = await self.repository.get_product_images_async(product_id)
            start_sort_order = max([image.sort_order for image in existing_images]) + 1 if existing_images else 0
            
            for i, image in enumerate(images):
                # 上传图片
                file_key = f"{self.image_path}/{product_id}/{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{image.filename}"
                image_url = await self.storage_service.upload_async(image.file, file_key, image.content_type)
                
                # 创建图片记录
                product_image = ProductImage(
                    product_id=product_id,
                    image_url=image_url,
                    sort_order=start_sort_order + i
                )
                
                # 添加图片
                await self.repository.add_image_async(product_image)
                
            return True
        except Exception as ex:
            logger.error(f"批量上传商品图片失败，商品ID: {product_id}", exc_info=ex)
            raise

    def _map_to_product_detail_dto(self, product: Product) -> ProductDetailDto:
        """
        将Product实体映射为ProductDetailDto
        
        Args:
            product: 商品实体
            
        Returns:
            商品详情DTO
        """
        return ProductDetailDto(
            id=product.id,
            code=product.code,
            name=product.name,
            price=product.price,
            description=product.description,
            selling_points=product.selling_points,
            stock=product.stock,
            status=product.status,
            images=[
                ProductImageDto(
                    id=image.id,
                    product_id=image.product_id,
                    image_url=image.image_url,
                    sort_order=image.sort_order
                ) for image in (product.images or [])
            ],
            create_date=product.create_date,
            last_modify_date=product.last_modify_date
        )

    def _map_to_product_list_item_dto(self, product: Product) -> ProductListItemDto:
        """
        将Product实体映射为ProductListItemDto
        
        Args:
            product: 商品实体
            
        Returns:
            商品列表项DTO
        """
        # 获取主图URL
        main_image_url = ""
        if product.images and len(product.images) > 0:
            main_image = min(product.images, key=lambda x: x.sort_order)
            main_image_url = main_image.image_url or ""
            
        return ProductListItemDto(
            id=product.id,
            code=product.code,
            name=product.name,
            price=product.price,
            stock=product.stock,
            status=product.status,
            main_image_url=main_image_url,
            create_date=product.create_date
        )