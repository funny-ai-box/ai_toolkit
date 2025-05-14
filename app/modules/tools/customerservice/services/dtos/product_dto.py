"""
商品相关数据传输对象
"""
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

class ProductCreateDto(BaseModel):
    """商品创建DTO"""
    code: str = Field(..., description="商品编码")
    name: str = Field(..., description="商品名称")
    price: float = Field(..., description="商品价格", gt=0)
    description: Optional[str] = Field(None, description="商品描述")
    selling_points: Optional[str] = Field(None, description="商品卖点")
    stock: int = Field(..., description="商品库存", ge=0)
    status: int = Field(1, description="商品状态，1-正常，0-下架")
    
    model_config = ConfigDict(alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_'))))

class ProductUpdateDto(BaseModel):
    """商品更新DTO"""
    id: int = Field(..., description="商品ID")
    code: Optional[str] = Field(None, description="商品编码")
    name: Optional[str] = Field(None, description="商品名称")
    price: Optional[float] = Field(None, description="商品价格", gt=0)
    description: Optional[str] = Field(None, description="商品描述")
    selling_points: Optional[str] = Field(None, description="商品卖点")
    stock: Optional[int] = Field(None, description="商品库存", ge=0)
    status: Optional[int] = Field(None, description="商品状态，1-正常，0-下架")
    
    model_config = ConfigDict(alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_'))))

class ProductListRequestDto(BaseModel):
    """商品列表请求DTO"""
    keyword: Optional[str] = Field(None, description="搜索关键词")
    page_index: int = Field(1, description="页码", ge=1)
    page_size: int = Field(20, description="每页大小", ge=1, le=100)
    
    model_config = ConfigDict(alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_'))))

class ProductSearchRequestDto(BaseModel):
    """商品搜索请求DTO"""
    keyword: str = Field(..., description="搜索关键词")
    page_index: int = Field(1, description="页码", ge=1)
    page_size: int = Field(20, description="每页大小", ge=1, le=100)
    
    model_config = ConfigDict(alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_'))))

class GetProductByCodeRequestDto(BaseModel):
    """根据商品编码获取商品请求DTO"""
    code: str = Field(..., description="商品编码")
    
    model_config = ConfigDict(alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_'))))

class ProductStatusUpdateDto(BaseModel):
    """商品状态更新DTO"""
    id: int = Field(..., description="商品ID")
    status: int = Field(..., description="状态值，1-正常，0-下架")
    
    model_config = ConfigDict(alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_'))))

class ProductImageUploadDto(BaseModel):
    """商品图片上传DTO"""
    product_id: int = Field(..., description="商品ID")
    
    model_config = ConfigDict(alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_'))))

class ProductImageDeleteDto(BaseModel):
    """商品图片删除DTO"""
    product_id: int = Field(..., description="商品ID")
    image_id: int = Field(..., description="图片ID")
    
    model_config = ConfigDict(alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_'))))

class ProductImageDto(BaseModel):
    """商品图片DTO"""
    id: int = Field(..., description="图片ID")
    product_id: int = Field(..., description="商品ID")
    image_url: Optional[str] = Field(None, description="图片URL")
    sort_order: int = Field(0, description="排序顺序")
    
    model_config = ConfigDict(alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_'))))

class ProductListItemDto(BaseModel):
    """商品列表项DTO"""
    id: int = Field(..., description="商品ID")
    code: Optional[str] = Field(None, description="商品编码")
    name: Optional[str] = Field(None, description="商品名称")
    price: float = Field(..., description="商品价格")
    stock: int = Field(..., description="商品库存")
    status: int = Field(..., description="商品状态，1-正常，0-下架")
    main_image_url: Optional[str] = Field(None, description="商品主图URL")
    create_date: str = Field(..., description="创建时间")
    
    model_config = ConfigDict(alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_'))))

class ProductDetailDto(BaseModel):
    """商品详情DTO"""
    id: int = Field(..., description="商品ID")
    code: Optional[str] = Field(None, description="商品编码")
    name: Optional[str] = Field(None, description="商品名称")
    price: float = Field(..., description="商品价格")
    description: Optional[str] = Field(None, description="商品描述")
    selling_points: Optional[str] = Field(None, description="商品卖点")
    stock: int = Field(..., description="商品库存")
    status: int = Field(..., description="商品状态，1-正常，0-下架")
    images: List[ProductImageDto] = Field(default_factory=list, description="商品图片列表")
    create_date: str = Field(..., description="创建时间")
    last_modify_date: str = Field(..., description="最后修改时间")
    
    model_config = ConfigDict(alias_generator=lambda s: ''.join(x.capitalize() if i else x for i, x in enumerate(s.split('_'))))