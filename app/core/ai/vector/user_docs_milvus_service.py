# app/core/ai/vector/user_docs_milvus_service.py
import logging
from enum import Enum
from typing import List, Optional

from app.core.config.settings import settings
from app.core.ai.vector.base import IUserDocsMilvusService, VectorFieldDefine
from app.core.ai.vector.milvus_service import MilvusService
from app.core.ai.dtos import UserDocsVectorSearchResult
from app.core.dtos import DocumentAppType
from app.core.exceptions import BusinessException

logger = logging.getLogger(__name__)

class UserDocsMilvusService(IUserDocsMilvusService):
    """用户文档向量库服务实现"""

    def __init__(self, milvus_service: MilvusService):
        self.milvus_service = milvus_service
        # 从配置加载字段名和集合信息
        self.collection_name = settings.KB_COLLECTION_NAME
        self.id_field = settings.KB_ID_FIELD
        self.user_id_field = settings.KB_USER_ID_FIELD
        self.app_type_field = settings.KB_APP_TYPE_FIELD
        self.doc_id_field = settings.KB_DOC_ID_FIELD
        self.content_field = settings.KB_CONTENT_FIELD
        self.vector_field = settings.KB_VECTOR_FIELD
        self.dimension = settings.KB_DIMENSION
        self.content_max_length = settings.KB_CONTENT_MAX_LENGTH

    async def ensure_collection_exists(self) -> bool:
        """确保用户文档集合存在，并创建必要的索引"""
        try:
            # 1. 首先检查集合是否存在
            collection_exists = await self.milvus_service.has_collection_async(self.collection_name)
            
            # 2. 如果集合不存在，创建它
            if not collection_exists:
                logger.info(f"集合 '{self.collection_name}' 不存在，将创建集合及其索引")
                # 定义集合字段结构
                field_def = VectorFieldDefine(
                    id_field=self.id_field,
                    vector_field=self.vector_field,
                    vector_dimension=self.dimension,
                    content_field=self.content_field,
                    content_max_length=self.content_max_length,
                    long_fields=[self.user_id_field, self.doc_id_field],
                    int_fields=[self.app_type_field]
                )

                # 创建集合
                created = await self.milvus_service.ensure_collection_exists(
                    collection_name=self.collection_name,
                    field_def=field_def,
                    primary_field_auto_id=True,
                    consistency_level="Bounded"
                )
                
                if not created:
                    logger.error(f"无法创建集合 '{self.collection_name}'")
                    return False
                
                # 创建必要的索引
                await self._create_indexes()
            else:
                logger.info(f"集合 '{self.collection_name}' 已存在，将检查和确保必要的索引")
                # 检查和创建必要的索引，但不触发多个索引在同一字段上的错误
                await self._check_and_ensure_indexes()
                
            # 最后，确保集合已加载到内存
            await self.milvus_service.load_collection_async(self.collection_name)
            logger.info(f"集合 '{self.collection_name}' 已创建索引并加载到内存")
            
            return True
        except Exception as e:
            logger.error(f"确保集合存在时出错: {e}")
            return False

    async def _create_indexes(self):
        """创建所有必要的索引"""
        # 创建向量字段索引
        vector_index_params = {
            "index_type": "HNSW",
            "metric_type": "COSINE",
            "params": {"M": 16, "efConstruction": 256}
        }
        
        vector_index_created = await self.milvus_service.create_vector_field_index(
            self.collection_name,
            self.vector_field,
            vector_index_params
        )
        
        if not vector_index_created:
            logger.warning(f"为向量字段 '{self.vector_field}' 创建索引失败")
        
        # 创建标量字段索引，加速过滤
        fields_to_index = [self.user_id_field, self.doc_id_field, self.app_type_field]
        for field in fields_to_index:
            result = await self.milvus_service.create_scalar_field_index(
                self.collection_name, field
            )
            if not result:
                logger.warning(f"为字段 '{field}' 创建索引失败")

    async def _check_and_ensure_indexes(self):
        """检查已有索引，并确保必要的索引存在"""
        # 获取集合对象
        await self.milvus_service.ensure_connection()
        collection = await self.milvus_service._get_collection(self.collection_name)
        
        # 获取现有的索引信息
        try:
            from pymilvus import utility
            indexes = utility.list_indexes(self.collection_name, using=self.milvus_service.alias)
            logger.info(f"集合 '{self.collection_name}' 现有索引: {indexes}")
            
            # 创建字段到索引的映射
            indexed_fields = set()
            for index_info in indexes:
                if 'field_name' in index_info:
                    indexed_fields.add(index_info['field_name'])
            
            # 只为没有索引的字段创建索引
            if self.vector_field not in indexed_fields:
                vector_index_params = {
                    "index_type": "HNSW",
                    "metric_type": "COSINE",
                    "params": {"M": 16, "efConstruction": 256}
                }
                await self.milvus_service.create_vector_field_index(
                    self.collection_name, self.vector_field, vector_index_params
                )
            
            # 检查标量字段
            fields_to_check = [self.user_id_field, self.doc_id_field, self.app_type_field]
            for field in fields_to_check:
                if field not in indexed_fields:
                    await self.milvus_service.create_scalar_field_index(
                        self.collection_name, field
                    )
        except Exception as e:
            logger.warning(f"检查或创建索引时出错: {e}")
            # 使用更简单的方法 - 尝试创建索引并忽略"索引已存在"错误
            await self._create_indexes_with_error_handling()

    async def _create_indexes_with_error_handling(self):
        """创建索引并优雅地处理"索引已存在"错误"""
        # 创建向量索引
        try:
            vector_index_params = {
                "index_type": "HNSW",
                "metric_type": "COSINE",
                "params": {"M": 16, "efConstruction": 256}
            }
            await self.milvus_service.create_vector_field_index(
                self.collection_name, self.vector_field, vector_index_params
            )
        except Exception as e:
            if "index already exist" in str(e).lower() or "multiple indexes" in str(e).lower():
                logger.info(f"向量字段 '{self.vector_field}' 已有索引")
            else:
                logger.warning(f"为向量字段创建索引失败: {e}")
        
        # 创建标量索引
        fields = [self.user_id_field, self.doc_id_field, self.app_type_field]
        for field in fields:
            try:
                await self.milvus_service.create_scalar_field_index(self.collection_name, field)
            except Exception as e:
                if "index already exist" in str(e).lower() or "multiple indexes" in str(e).lower():
                    logger.info(f"字段 '{field}' 已有索引")
                else:
                    logger.warning(f"为字段 '{field}' 创建索引失败: {e}")

    async def insert_vector_async(
        self, user_id: int, app_type: DocumentAppType, document_id: int,
        content: str, vector: List[float]
    ) -> int:
        """插入单个向量"""
        # 确保集合存在并已索引
        await self.ensure_collection_exists()
        
        ids, count = await self.insert_vectors_async(
            user_id, app_type, document_id, [content], [vector]
        )
        if count == 1 and ids:
            return ids[0]
        else:
            raise BusinessException("插入单个向量失败", code=500)

    async def insert_vectors_async(
        self, user_id: int, app_type: DocumentAppType, document_id: int,
        contents: List[str], vectors: List[List[float]]
    ) -> List[int]:
        """批量插入向量"""
        # 确保集合存在并已索引
        await self.ensure_collection_exists()
        
        if not contents or not vectors or len(contents) != len(vectors):
            raise ValueError("内容列表和向量列表不能为空且长度必须一致")

        # 准备插入的数据
        data = []
        for i in range(len(contents)):
            row = {
                self.user_id_field: user_id,
                self.app_type_field: int(app_type.value) if isinstance(app_type, Enum) else int(app_type),
                self.doc_id_field: document_id,
                self.content_field: contents[i][:self.content_max_length],
                self.vector_field: vectors[i]
            }
            data.append(row)

        # 调用基础服务插入
        inserted_ids, inserted_count = await self.milvus_service.insert_vectors_async(
            self.collection_name, data
        )

        if inserted_count != len(data):
             logger.warning(f"尝试插入 {len(data)} 条向量，实际成功 {inserted_count} 条。")

        return [int(pk) for pk in inserted_ids]

    async def delete_vectors_by_document_id_async(
        self, user_id: int, document_id: int
    ) -> bool:
        """根据用户 ID 和文档 ID 删除相关的所有向量"""
        # 确保集合存在并已索引
        await self.ensure_collection_exists()
        
        # 构建删除表达式
        expr = f"{self.user_id_field} == {user_id} and {self.doc_id_field} == {document_id}"

        # 调用基础服务删除
        deleted_count = await self.milvus_service.delete_vectors_async(
            self.collection_name, expr
        )
        return deleted_count > 0

    async def search_async(
        self, user_id: int, app_type: DocumentAppType, query_vector: List[float],
        document_id: Optional[int] = None, top_k: int = 5, min_score: float = 0.7,
        consistency_level: Optional[str] = None
    ) -> List[UserDocsVectorSearchResult]:
        """根据用户、应用类型等搜索相似向量"""
        # 确保集合存在、有索引且已加载
        collection_ready = await self.ensure_collection_exists()
        if not collection_ready:
            logger.warning(f"集合 '{self.collection_name}' 不可用，无法执行搜索")
            return []  # 返回空结果而不是抛出异常，让调用方能够优雅降级

        # 1. 构建过滤表达式
        filter_parts = [
            f"{self.user_id_field} == {user_id}",
            f"{self.app_type_field} == {int(app_type.value) if isinstance(app_type, Enum) else int(app_type)}"
        ]
        if document_id is not None:
            filter_parts.append(f"{self.doc_id_field} == {document_id}")
        expr = " and ".join(filter_parts)

        # 2. 定义搜索参数
        search_params = {
            "metric_type": "COSINE",
            "params": {"ef": 128}  # 搜索参数，需与 efConstruction 一致或更小
        }

        # 3. 定义需要返回的字段
        output_fields = [
            self.id_field,
            self.doc_id_field,
            self.content_field
        ]

        try:
            # 4. 调用基础服务搜索
            search_results = await self.milvus_service.search_async(
                collection_name=self.collection_name,
                query_vectors=[query_vector],
                vector_field=self.vector_field,
                search_params=search_params,
                limit=top_k,
                expr=expr,
                output_fields=output_fields,
                consistency_level=consistency_level
            )

            # 5. 处理和过滤结果
            final_results: List[UserDocsVectorSearchResult] = []
            if search_results and search_results[0]:
                hits = search_results[0]
                for hit in hits:
                    score = hit.get("score", 0.0)
                    if score >= min_score:
                        entity_data = hit.get("entity", {})
                        result_dto = UserDocsVectorSearchResult(
                            id=hit.get("id"),
                            documentId=entity_data.get(self.doc_id_field),
                            content=entity_data.get(self.content_field),
                            score=round(score, 4)
                        )
                        final_results.append(result_dto)

            # 可以选择按得分排序
            final_results.sort(key=lambda x: x.score, reverse=True)

            logger.info(f"向量搜索完成 (User: {user_id}, App: {app_type}, Doc: {document_id}), "
                        f"找到 {len(hits) if search_results and search_results[0] else 0} 个原始结果, "
                        f"返回 {len(final_results)} 个满足条件 (score >= {min_score}) 的结果。")

            return final_results
            
        except Exception as e:
            logger.error(f"执行向量搜索时出错: {e}")
            # 出错时返回空结果，让应用可以继续而不是完全失败
            return []