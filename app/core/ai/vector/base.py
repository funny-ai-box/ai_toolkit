# app/core/ai/vector/base.py
from typing import List, Optional, Protocol, runtime_checkable, Dict, Any, Union, Tuple
from abc import abstractmethod
from pydantic import BaseModel, Field # 需要导入 Pydantic

# --- DTOs ---
class VectorFieldDefine(BaseModel):
    """
    用于定义 Milvus 集合字段结构的 Pydantic 模型。
    替代 C# 中的 VectorDataFieldDefine 类。
    """
    id_field: str = Field("vector_id", description="主键 ID 字段名")
    vector_field: str = Field("vector", description="向量字段名")
    vector_dimension: int = Field(1536, description="向量维度")
    content_field: Optional[str] = Field(None, description="内容字段名 (如果存在)")
    content_max_length: int = Field(2000, description="内容字段最大长度")
    # 可以存储其他字段类型和名称
    long_fields: List[str] = Field(default_factory=list, description="INT64 类型字段列表")
    int_fields: List[str] = Field(default_factory=list, description="INT32 类型字段列表")
    varchar_fields: Dict[str, int] = Field(default_factory=dict, description="VARCHAR 类型字段及其最大长度字典")
    float_fields: List[str] = Field(default_factory=list, description="FLOAT 类型字段列表")
    double_fields: List[str] = Field(default_factory=list, description="DOUBLE 类型字段列表")
    bool_fields: List[str] = Field(default_factory=list, description="BOOL 类型字段列表")


# --- 协议 (Interfaces) ---

@runtime_checkable
class IMilvusService(Protocol):
    """基础 Milvus 服务操作接口协议"""

    @abstractmethod
    async def ensure_connection(self):
        """确保 Milvus 连接已建立"""
        ...

    @abstractmethod
    async def ensure_collection_exists(
        self,
        collection_name: str,
        field_def: VectorFieldDefine,
        primary_field_auto_id: bool = False, # Milvus 2.3+ 支持服务端生成 ID
        consistency_level: str = "Bounded" # Bounded, Strong, Session, Eventually
    ) -> bool:
        """
        确保集合存在，如果不存在则根据定义创建。

        Args:
            collection_name: 集合名称。
            field_def: 集合字段定义。
            primary_field_auto_id: 主键是否由 Milvus 自动生成 (需要 v2.3+)。
            consistency_level: 创建集合时的一致性级别。

        Returns:
            如果集合已存在或创建成功返回 True，否则 False。
        """
        ...

    @abstractmethod
    async def create_scalar_field_index(
        self,
        collection_name: str,
        field_name: str,
        index_name: Optional[str] = None,
        index_type: str = "AUTOINDEX" # 或 "inverted" 等
    ) -> bool:
        """
        为标量或 VARCHAR 字段创建索引。

        Args:
            collection_name: 集合名称。
            field_name: 要创建索引的字段名。
            index_name: 索引名称 (可选，Milvus 会自动生成)。
            index_type: 索引类型 (例如 "AUTOINDEX", "inverted")。

        Returns:
            创建是否成功。
        """
        ...

    @abstractmethod
    async def create_vector_field_index(
        self,
        collection_name: str,
        field_name: str,
        index_params: Dict[str, Any],
        index_name: Optional[str] = None
    ) -> bool:
        """
        为向量字段创建索引。

        Args:
            collection_name: 集合名称。
            field_name: 向量字段名。
            index_params: 索引参数 (包含 'index_type', 'metric_type', 'params')。
                          例如: {"index_type": "HNSW", "metric_type": "COSINE", "params": {"M": 16, "efConstruction": 200}}
            index_name: 索引名称 (可选)。

        Returns:
            创建是否成功。
        """
        ...

    @abstractmethod
    async def insert_vectors_async(
        self,
        collection_name: str,
        data: List[Dict[str, Any]], # 数据格式: [{'field1': val1, 'field2': val2}, ...]
        partition_name: Optional[str] = None
    ) -> Tuple[List[Union[str, int]], int]: # 返回 ID 列表和成功插入的数量
        """
        异步批量插入向量数据。

        Args:
            collection_name: 集合名称。
            data: 要插入的数据列表，每个字典代表一行。键是字段名。
                  例如: [{'vector_id': 1, 'userId': 10, 'vector': [0.1, ...]}, ...]
            partition_name: 可选的分区名称。

        Returns:
            一个元组，包含插入行的主键 ID 列表 (类型取决于 Milvus 是否自动生成) 和成功插入的数量。

        Raises:
            Exception: 如果插入失败。
        """
        ...

    @abstractmethod
    async def delete_vectors_async(
        self,
        collection_name: str,
        expr: str,
        partition_name: Optional[str] = None
    ) -> int: # 返回删除的数量
        """
        根据表达式异步删除向量数据。

        Args:
            collection_name: 集合名称。
            expr: 删除表达式 (例如 "userId == 10 and docId in [1, 2]")。
            partition_name: 可选的分区名称。

        Returns:
            成功删除的实体数量。

        Raises:
            Exception: 如果删除失败。
        """
        ...

    @abstractmethod
    async def search_async(
        self,
        collection_name: str,
        query_vectors: List[List[float]],
        vector_field: str,
        search_params: Dict[str, Any], # 包含 metric_type 和 params (如 {"metric_type": "COSINE", "params": {"ef": 64}})
        limit: int,
        expr: Optional[str] = None,
        output_fields: Optional[List[str]] = None,
        partition_names: Optional[List[str]] = None,
        consistency_level: Optional[str] = None # "Strong", "Bounded", "Session", "Eventually"
    ) -> List[List[Dict[str, Any]]]: # 返回原始的 Milvus 搜索结果结构
        """
        异步执行向量搜索。

        Args:
            collection_name: 集合名称。
            query_vectors: 查询向量列表 (每个向量是一个 float 列表)。
            vector_field: 要搜索的向量字段名。
            search_params: 搜索参数 (包含 'metric_type', 'params')。
            limit (top_k): 每个查询向量返回的最大结果数。
            expr: 过滤表达式 (可选)。
            output_fields: 需要返回的字段列表 (可选，默认只返回 ID 和 distance)。
            partition_names: 要搜索的分区列表 (可选)。
            consistency_level: 搜索时的一致性级别 (可选)。

        Returns:
            Milvus 的原始搜索结果，是一个列表的列表。
            外层列表对应每个查询向量，内层列表包含每个匹配的结果 (字典形式)。
            例如: [[{'id': 1, 'distance': 0.9, 'entity': {'field1': val}}], ...]

        Raises:
            Exception: 如果搜索失败。
        """
        ...

    @abstractmethod
    async def load_collection_async(self, collection_name: str):
        """加载集合到内存以供搜索"""
        ...

    @abstractmethod
    async def release_collection_async(self, collection_name: str):
        """从内存中释放集合"""
        ...

    @abstractmethod
    async def has_collection_async(self, collection_name: str) -> bool:
        """检查集合是否存在"""
        ...

    @abstractmethod
    async def drop_collection_async(self, collection_name: str):
        """删除集合"""
        ...


# --- UserDocs Milvus 服务接口协议 ---
from app.core.ai.dtos import UserDocsVectorSearchResult # 假设已定义
from app.core.dtos import DocumentAppType # 假设已定义

@runtime_checkable
class IUserDocsMilvusService(Protocol):
    """封装了用户文档向量库操作的接口协议"""

    @abstractmethod
    async def ensure_collection_exists(self) -> bool:
        """确保用户文档集合存在并已加载"""
        ...

    @abstractmethod
    async def insert_vector_async(
        self,
        user_id: int,
        app_type: DocumentAppType,
        document_id: int,
        content: str,
        vector: List[float]
    ) -> int: # 返回插入的 Milvus 向量 ID
        """插入单个向量"""
        ...

    @abstractmethod
    async def insert_vectors_async(
        self,
        user_id: int,
        app_type: DocumentAppType,
        document_id: int,
        contents: List[str],
        vectors: List[List[float]]
    ) -> List[int]: # 返回插入的 Milvus 向量 ID 列表
        """批量插入向量"""
        ...

    @abstractmethod
    async def delete_vectors_by_document_id_async(
        self,
        user_id: int,
        document_id: int
    ) -> bool: # 返回是否成功删除了至少一个向量
        """根据用户 ID 和文档 ID 删除相关的所有向量"""
        ...

    @abstractmethod
    async def search_async(
        self,
        user_id: int,
        app_type: DocumentAppType,
        query_vector: List[float],
        document_id: Optional[int] = None, # 指定文档 ID (可选)
        top_k: int = 5,
        min_score: float = 0.7, # 最小相似度得分 (需要根据 metric_type 解释)
        consistency_level: Optional[str] = None
    ) -> List[UserDocsVectorSearchResult]: # 返回处理后的搜索结果 DTO 列表
        """根据用户、应用类型等搜索相似向量"""
        ...