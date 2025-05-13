# app/core/ai/vector/user_docs_milvus_service.py
import logging
from enum import Enum
from typing import List, Optional

from app.core.config.settings import settings
from app.core.ai.vector.base import IUserDocsMilvusService, VectorFieldDefine # 导入协议和 DTO
from app.core.ai.vector.milvus_service import MilvusService # 导入基础服务
from app.core.ai.dtos import UserDocsVectorSearchResult # 导入响应 DTO
from app.core.dtos import DocumentAppType # 导入枚举
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
        # 1. 定义集合字段结构
        field_def = VectorFieldDefine(
            id_field=self.id_field,
            vector_field=self.vector_field,
            vector_dimension=self.dimension,
            content_field=self.content_field,
            content_max_length=self.content_max_length,
            long_fields=[self.user_id_field, self.doc_id_field], # userId 和 docId 是 long
            int_fields=[self.app_type_field] # appType 是 int 枚举
            # varchar_fields, float_fields, double_fields, bool_fields 根据需要添加
        )

        # 2. 确保集合骨架存在
        created_or_existed = await self.milvus_service.ensure_collection_exists(
            collection_name=self.collection_name,
            field_def=field_def,
            primary_field_auto_id=True, # 让 Milvus 自动生成主键 ID (推荐)
            consistency_level="Bounded" # 或者根据需要调整
        )
        if not created_or_existed:
            return False # 如果集合创建失败        
        return True

    async def insert_vector_async(
        self, user_id: int, app_type: DocumentAppType, document_id: int,
        content: str, vector: List[float]
    ) -> int:
        """插入单个向量"""
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
        if not contents or not vectors or len(contents) != len(vectors):
            raise ValueError("内容列表和向量列表不能为空且长度必须一致")

        # 准备插入的数据
        data = []
        for i in range(len(contents)):
            row = {
                # self.id_field: generate_id(), # 如果让 Milvus auto_id=True 则不需要提供
                self.user_id_field: user_id,
                self.app_type_field: int(app_type.value) if isinstance(app_type, Enum) else int(app_type), # 存储枚举的整数值
                self.doc_id_field: document_id,
                self.content_field: contents[i][:self.content_max_length], # 截断内容
                self.vector_field: vectors[i]
            }
            data.append(row)

        # 调用基础服务插入
        inserted_ids, inserted_count = await self.milvus_service.insert_vectors_async(
            self.collection_name, data
        )

        if inserted_count != len(data):
             logger.warning(f"尝试插入 {len(data)} 条向量，实际成功 {inserted_count} 条。")
             # 根据业务需求决定是否抛异常

        # Milvus 返回的 primary_keys 类型可能是 list[int] 或 list[str]
        return [int(pk) for pk in inserted_ids] # 假设 ID 是整数


    async def delete_vectors_by_document_id_async(
        self, user_id: int, document_id: int
    ) -> bool:
        """根据用户 ID 和文档 ID 删除相关的所有向量"""
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
            "metric_type": "COSINE", # 或者从配置读取，需与索引一致
            "params": {"ef": 128} # ef 搜索参数，需要根据索引类型和数据调整
        }

        # 3. 定义需要返回的字段
        output_fields = [
            self.id_field, # Milvus 会自动返回 id 和 distance/score
            self.doc_id_field,
            self.content_field
            # 可以添加其他需要的字段，如 appType
        ]

        # 4. 调用基础服务搜索
        search_results = await self.milvus_service.search_async(
            collection_name=self.collection_name,
            query_vectors=[query_vector], # search_async 接受向量列表
            vector_field=self.vector_field,
            search_params=search_params,
            limit=top_k,
            expr=expr,
            output_fields=output_fields,
            consistency_level=consistency_level
        )

        # 5. 处理和过滤结果
        final_results: List[UserDocsVectorSearchResult] = []
        if search_results and search_results[0]: # search_results 是 List[List[Dict]]
            hits = search_results[0] # 获取第一个查询向量的结果列表
            for hit in hits:
                score = hit.get("score", 0.0) # 获取计算出的相似度得分
                # 应用最小得分阈值
                if score >= min_score:
                    entity_data = hit.get("entity", {})
                    result_dto = UserDocsVectorSearchResult(
                        id=hit.get("id"), # Milvus 返回的主键 ID
                        documentId=entity_data.get(self.doc_id_field), # DTO 使用 camelCase
                        content=entity_data.get(self.content_field),
                        score=round(score, 4) # 保留 4 位小数
                    )
                    final_results.append(result_dto)

        # 可以选择按得分排序
        final_results.sort(key=lambda x: x.score, reverse=True)

        logger.info(f"向量搜索完成 (User: {user_id}, App: {app_type}, Doc: {document_id}), "
                    f"找到 {len(hits) if search_results else 0} 个原始结果, "
                    f"返回 {len(final_results)} 个满足条件 (score >= {min_score}) 的结果。")

        return final_results