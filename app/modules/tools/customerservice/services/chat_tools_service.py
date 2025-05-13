"""
客服的AI调用工具服务
"""
import logging
from typing import List, Tuple, Dict, Any, Optional

from app.core.ai.chat.base import IChatAIService
from app.core.ai.vector.base import IUserDocsMilvusService
from app.core.dtos import DocumentAppType
from app.modules.tools.customerservice.dtos import ProductListItemDto
from app.modules.tools.customerservice.services.product_service import ProductService

logger = logging.getLogger(__name__)


class ChatToolsService:
    """客服的AI调用工具服务"""

    def __init__(
        self,
        product_service: ProductService,
        ai_service: IChatAIService,
        user_docs_service: IUserDocsMilvusService,
        max_vector_search_results: int,
        min_vector_score: float
    ):
        """
        初始化客服工具服务
        
        Args:
            product_service: 商品服务
            ai_service: AI服务
            user_docs_service: 用户文档向量服务
            max_vector_search_results: 最大向量搜索结果数
            min_vector_score: 最小向量得分
        """
        self.product_service = product_service
        self.ai_service = ai_service
        self.user_docs_service = user_docs_service
        self.max_vector_search_results = max_vector_search_results
        self.min_vector_score = min_vector_score

    async def call_product_function_async(
        self, 
        user_id: int, 
        prod_id: int, 
        prod_code: str, 
        prod_name: str, 
        count: int
    ) -> str:
        """
        调用商品函数
        
        Args:
            user_id: 用户ID
            prod_id: 商品编号
            prod_code: 商品编码
            prod_name: 商品名称
            count: 返回多少个
            
        Returns:
            商品信息文本
        """
        try:
            if count < 1:
                count = 1
            if count > 5:
                count = 5
                
            items: List[ProductListItemDto] = []
            
            if prod_id > 0:  # 最优先编号
                product = await self.product_service.get_product_async(user_id, prod_id)
                items = [ProductListItemDto(
                    id=product.id,
                    code=product.code,
                    name=product.name,
                    price=product.price,
                    status=product.status,
                    stock=product.stock,
                    main_image_url=product.images[0].image_url if product.images and len(product.images) > 0 else "",
                    create_date=product.create_date
                )]
            elif prod_code:  # 优先商品编码
                product = await self.product_service.get_product_by_code_async(user_id, prod_code)
                items = [ProductListItemDto(
                    id=product.id,
                    code=product.code,
                    name=product.name,
                    price=product.price,
                    status=product.status,
                    stock=product.stock,
                    main_image_url=product.images[0].image_url if product.images and len(product.images) > 0 else "",
                    create_date=product.create_date
                )]
            elif prod_name:  # 按名称或描述搜索
                search_request = {
                    "keyword": prod_name,
                    "pageIndex": 1,
                    "pageSize": count
                }
                result = await self.product_service.search_products_async(user_id, search_request)
                items = result.items
            else:
                # 随机返回推荐的热销品
                items = await self.product_service.get_hot_products_async(user_id, count)
                
            if not items or len(items) == 0:
                return "未能找到相关商品信息。"
                
            return self._get_context_from_prod_results(items)
        except Exception as ex:
            logger.error("调用商品函数失败", exc_info=ex)
            return "查询商品信息时发生错误。"

    def _get_context_from_prod_results(self, prod_items: List[ProductListItemDto]) -> str:
        """
        构建商品结果的上下文
        
        Args:
            prod_items: 商品列表
            
        Returns:
            上下文信息
        """
        if not prod_items or len(prod_items) == 0:
            return ""
            
        result = f"以下是从商品库中找到的相关信息（找到{len(prod_items)}个商品）:\n\n"
        
        for item in prod_items:
            status = "正常" if item.status == 1 else "下架"
            result += f"id: {item.id}\n"
            result += f"code: {item.code}\n"
            result += f"name: {item.name}\n"
            result += f"price: {item.price}\n"
            result += f"stock: {item.stock}\n"
            result += f"status: {status}\n"
            result += f"imgUrl: {item.main_image_url}\n"
            result += "---\n"
            
        return result

    async def search_knowledge_base_async(
        self, 
        user_id: int, 
        query: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        查询知识库
        
        Args:
            user_id: 用户ID
            query: 查询内容
            
        Returns:
            (上下文信息, 搜索结果列表)
        """
        try:
            # 向量搜索
            embedding = await self.ai_service.get_embedding_async(query)
            search_results = await self.user_docs_service.search_async(
                user_id=user_id,
                app_type=DocumentAppType.CUSTOMER_SERVICE,
                query_vector=embedding,
                document_id=0,  # 不限定文档ID
                top_k=self.max_vector_search_results,
                min_score=self.min_vector_score
            )
            
            # 检查是否找到了相关内容
            has_relevant_content = len(search_results) > 0
            logger.info(f"向量搜索结果: 找到{len(search_results)}条相关内容, 阈值为{self.min_vector_score}")
            
            # 如果没有找到相关内容
            if not has_relevant_content:
                logger.warning(f"没有找到与问题'{query}'相关的内容")
                return "知识库中未找到相关知识", []
                
            # 构建上下文信息
            context_info = self._get_context_from_search_results(search_results)
            return context_info, search_results
        except Exception as ex:
            logger.error("查询知识库失败", exc_info=ex)
            return "", []

    def _get_context_from_search_results(self, search_results: List[Dict[str, Any]]) -> str:
        """
        从搜索结果构建上下文信息
        
        Args:
            search_results: 搜索结果
            
        Returns:
            上下文信息
        """
        if not search_results or len(search_results) == 0:
            return ""
            
        result = "以下是从知识库中找到的相关信息:\n\n"
        
        for item in search_results:
            result += f"[id: {item.id}]\n"
            result += f"[相关度: {item.score:.1%}]\n" 
            result += f"{item.content}\n"
            result += "---\n"
            
        return result