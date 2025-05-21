# app/core/ai/vector/milvus_service.py
import logging
from typing import List, Optional, Dict, Any, Union, Tuple

from pymilvus import (
    connections,
    utility,
    CollectionSchema, FieldSchema, DataType,
    Collection,
    MilvusException
)

from app.core.config.settings import settings
from app.core.ai.vector.base import IMilvusService, VectorFieldDefine
from app.core.exceptions import BusinessException

logger = logging.getLogger(__name__)

class MilvusService(IMilvusService):
    """基础 Milvus 服务实现"""

    def __init__(self):
        self.alias = settings.MILVUS_ALIAS
        self._connected = False # 跟踪连接状态

    async def ensure_connection(self):
        """确保与 Milvus 的连接存在"""
        if self._connected and self.alias in connections.list_connections():
            # 尝试 ping 一下确认连接有效 (可选，可能会增加延迟)
            # try:
            #     # utility.get_server_version(alias=self.alias) # 或者其他轻量级命令
            #     pass
            # except Exception:
            #     logger.warning(f"Milvus 连接 '{self.alias}' 可能已失效，尝试重连。")
            #     self._connected = False
            #     # connections.disconnect(self.alias) # 主动断开可能存在的无效连接
            # else:
                return # 连接有效

        if self.alias in connections.list_connections():
             logger.warning(f"Milvus 连接别名 '{self.alias}' 已存在但服务标记为未连接，尝试断开并重连。")
             try:
                 connections.disconnect(self.alias)
             except Exception as e:
                 logger.warning(f"断开现有 Milvus 连接 '{self.alias}' 时出错: {e}")

        logger.info(f"正在连接 Milvus ({self.alias}) at {settings.MILVUS_HOST}:{settings.MILVUS_PORT}...")
        try:
            connections.connect(
                alias=self.alias,
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT,
                user=settings.MILVUS_USER,
                password=settings.MILVUS_PASSWORD,
                secure=settings.MILVUS_SECURE,
                # SSL 相关参数 (仅当 use_ssl=True 时需要)
                # server_pem_path=settings.MILVUS_SERVER_PEM_PATH,
                # server_name=settings.MILVUS_SERVER_NAME,
                # ca_pem_path=settings.MILVUS_CA_PEM_PATH,
                timeout=10 # 设置连接超时 (秒)
            )
            self._connected = True
            logger.info(f"成功连接到 Milvus ({self.alias})。")
        except MilvusException as e:
            self._connected = False
            print(settings.MILVUS_HOST, settings.MILVUS_PORT, settings.MILVUS_USER, settings.MILVUS_PASSWORD)
            print('*'*20)
            print(type(settings.MILVUS_PORT), settings.MILVUS_PORT)
            print('*'*20)
            logger.error(f"连接 Milvus ({self.alias}) 失败: {e}", exc_info=True)
            raise BusinessException(f"无法连接到向量数据库: {e}", code=500) from e
        except Exception as e:
            self._connected = False
            logger.error(f"连接 Milvus ({self.alias}) 时发生未知错误: {e}", exc_info=True)
            raise BusinessException(f"连接向量数据库时发生未知错误: {e}", code=500) from e

    async def _get_collection(self, collection_name: str) -> Collection:
        """获取 Collection 对象，确保已连接"""
        await self.ensure_connection()
        try:
             # 检查集合是否存在，避免 Collection() 报错
            if not await self.has_collection_async(collection_name):
                 raise MilvusException(message=f"集合 '{collection_name}' 不存在。")
            return Collection(name=collection_name, using=self.alias)
        except MilvusException as e:
             logger.error(f"获取 Milvus 集合 '{collection_name}' 失败: {e}")
             raise BusinessException(f"无法访问向量集合 '{collection_name}': {e}", code=500) from e


    def _map_pymilvus_type(self, field_type: str, max_length: Optional[int] = None) -> DataType:
        """辅助函数，将字符串类型映射到 pymilvus DataType"""
        type_map = {
            "int64": DataType.INT64, "long": DataType.INT64,
            "int32": DataType.INT32, "int": DataType.INT32,
            "float": DataType.FLOAT, "float32": DataType.FLOAT,
            "double": DataType.DOUBLE, "float64": DataType.DOUBLE,
            "bool": DataType.BOOL,
            "varchar": DataType.VARCHAR, "string": DataType.VARCHAR,
            "float_vector": DataType.FLOAT_VECTOR,
        }
        lower_type = field_type.lower()
        if lower_type not in type_map:
            raise ValueError(f"不支持的 Milvus 字段类型: {field_type}")
        if lower_type == "varchar" and max_length is None:
             raise ValueError("VARCHAR 类型必须指定 max_length")
        return type_map[lower_type]

    async def ensure_collection_exists(
        self,
        collection_name: str,
        field_def: VectorFieldDefine,
        primary_field_auto_id: bool = False,
        consistency_level: str = "Bounded"
    ) -> bool:
        """确保集合存在，如果不存在则创建"""
        await self.ensure_connection()
        try:
            has_coll = utility.has_collection(collection_name, using=self.alias)
            if has_coll:
                logger.info(f"集合 '{collection_name}' 已存在。")
                # 可以在这里添加检查 schema 是否匹配的逻辑 (如果需要)
                # collection = Collection(name=collection_name, using=self.alias)
                # current_schema = collection.schema
                # Mismatched schema handling...
                return True

            logger.info(f"集合 '{collection_name}' 不存在，开始创建...")

            # 1. 定义字段 Schema
            fields = []
            # 主键字段
            pk_field = FieldSchema(
                name=field_def.id_field,
                dtype=DataType.INT64, # 假设雪花 ID 是 INT64
                is_primary=True,
                auto_id=primary_field_auto_id, # 是否由 Milvus 生成 ID
                description="主键 ID"
            )
            fields.append(pk_field)

            # 向量字段
            vector_field = FieldSchema(
                name=field_def.vector_field,
                dtype=DataType.FLOAT_VECTOR,
                dim=field_def.vector_dimension,
                description="特征向量"
            )
            fields.append(vector_field)

            # 内容字段 (如果定义)
            if field_def.content_field:
                content_field = FieldSchema(
                    name=field_def.content_field,
                    dtype=DataType.VARCHAR,
                    max_length=field_def.content_max_length,
                    description="文本内容"
                )
                fields.append(content_field)

            # 其他标量字段
            all_scalar_fields = set() # 用于检查字段名是否重复
            all_scalar_fields.add(field_def.id_field)
            if field_def.content_field: all_scalar_fields.add(field_def.content_field)

            def add_scalar_field(name: str, dtype: DataType, max_len: Optional[int] = None):
                if name in all_scalar_fields:
                     logger.warning(f"字段定义中存在重复字段名 '{name}'，将跳过。")
                     return
                desc = f"{dtype.name} 类型字段"
                params = {"name": name, "dtype": dtype, "description": desc}
                if dtype == DataType.VARCHAR:
                     if max_len is None: raise ValueError(f"字段 '{name}' 类型为 VARCHAR 但未指定 max_length")
                     params["max_length"] = max_len
                fields.append(FieldSchema(**params))
                all_scalar_fields.add(name)

            for field in field_def.long_fields: add_scalar_field(field, DataType.INT64)
            for field in field_def.int_fields: add_scalar_field(field, DataType.INT32)
            for field, length in field_def.varchar_fields.items(): add_scalar_field(field, DataType.VARCHAR, length)
            for field in field_def.float_fields: add_scalar_field(field, DataType.FLOAT)
            for field in field_def.double_fields: add_scalar_field(field, DataType.DOUBLE)
            for field in field_def.bool_fields: add_scalar_field(field, DataType.BOOL)

            # 2. 创建 Collection Schema
            schema = CollectionSchema(
                fields=fields,
                primary_field=field_def.id_field,
                description=f"集合 {collection_name} 的 Schema"
                # enable_dynamic_field=False # 是否允许动态字段 (通常不推荐)
            )

            # 3. 创建集合
            logger.info(f"使用 Schema 创建集合 '{collection_name}'...")
            # consistency_level_enum = getattr(ConsistencyLevel, consistency_level, ConsistencyLevel.Bounded)
            Collection(
                name=collection_name,
                schema=schema,
                using=self.alias,
                consistency_level=consistency_level,#consistency_level_enum
                # shards_num=2 # 可以指定分片数量
            )
            logger.info(f"集合 '{collection_name}' 创建成功。")

            # 4. 确保必要的索引存在 (创建索引前最好释放集合)
            # 为向量字段创建索引 (示例使用 HNSW)
            vector_index_name = f"{self.vector_field}_vector_idx"
            vector_index_params = {
            "index_type": "HNSW",
            "metric_type": "COSINE",
            "params": {"M": 16, "efConstruction": 256}
        }
            await self.milvus_service.create_vector_field_index(
            self.collection_name,
            self.vector_field,
            vector_index_params,
            index_name=vector_index_name  # 明确指定索引名称
        )

            # 为常用的标量字段创建索引以加速过滤
            await self.create_scalar_field_index(
                self.collection_name, self.user_id_field,
                index_name=f"{self.user_id_field}_scalar_idx"
            )
            await self.create_scalar_field_index(
                self.collection_name, self.doc_id_field,
                
            )
            await self.create_scalar_field_index(
                self.collection_name, self.app_type_field
            )
            # content 字段如果需要精确匹配或前缀匹配，可以创建 MARISA_TRIE 或 INVERTED 索引
            # await self.create_scalar_field_index(
            #     self.collection_name, self.content_field, index_type="INVERTED" # 或 MARISA_TRIE
            # )

            logger.info(f"集合 '{self.collection_name}' 的索引已确保存在。")
            
            return True # 创建成功

        except MilvusException as e:
            logger.error(f"确保/创建 Milvus 集合 '{collection_name}' 失败: {e}", exc_info=True)
            raise BusinessException(f"无法确保/创建向量集合 '{collection_name}': {e}", code=500) from e
        except Exception as e:
            logger.error(f"处理集合 '{collection_name}' 时发生未知错误: {e}", exc_info=True)
            raise BusinessException(f"处理向量集合 '{collection_name}' 时发生未知错误: {e}", code=500) from e


    async def create_scalar_field_index(
    self,
    collection_name: str,
    field_name: str,
    index_name: Optional[str] = None,
    index_type: str = "AUTOINDEX"
) -> bool:
        try:
            collection = await self._get_collection(collection_name)
            
            # 检查集合是否已加载，如果已加载则先释放
            try:
                if utility.load_state(collection_name, using=self.alias) == "Loaded":
                    logger.info(f"集合 '{collection_name}' 已加载，先释放再创建索引")
                    collection.release()
            except Exception as e:
                logger.warning(f"检查集合加载状态失败: {e}")
            
            # 使用明确的索引名
            actual_index_name = index_name or f"{field_name}_idx"
            
            logger.info(f"正在为集合 '{collection_name}' 的字段 '{field_name}' 创建索引 (类型: {index_type}, 名称: {actual_index_name})...")
            
            # 创建索引
            collection.create_index(
                field_name=field_name,
                index_params={"index_type": index_type},
                index_name=actual_index_name
            )
            
            logger.info(f"字段 '{field_name}' 的索引创建成功 (集合: '{collection_name}')。")
            
            # 不要等待索引构建完成，而是返回成功
            # utility.wait_for_index_building_complete() 可能导致问题
            return True
            
        except MilvusException as e:
            logger.error(f"为字段 '{field_name}' 创建索引失败 (集合: '{collection_name}'): {e}", exc_info=True)
            # 如果是已知的索引存在错误，可以视为成功
            if "index already exist" in str(e).lower():
                logger.info(f"索引 '{actual_index_name}' 已存在，视为成功")
                return True
            return False
        except Exception as e:
            logger.error(f"为字段 '{field_name}' 创建索引时发生未知错误: {e}", exc_info=True)
            return False

    async def create_vector_field_index(
        self,
        collection_name: str,
        field_name: str,
        index_params: Dict[str, Any], # { "index_type": "HNSW", "metric_type": "COSINE", "params": {"M": 16, ...} }
        index_name: Optional[str] = None
    ) -> bool:
        """为向量字段创建索引"""
        try:
            collection = await self._get_collection(collection_name)
            # 检查字段是否存在
            vector_field_exists = any(f.name == field_name and f.dtype == DataType.FLOAT_VECTOR for f in collection.schema.fields)
            if not vector_field_exists:
                 logger.error(f"尝试为不存在或类型错误的向量字段 '{field_name}' 创建索引 (集合: '{collection_name}')。")
                 return False

            # 检查索引是否已存在
            idx_name = index_name or f"{field_name}_idx" # 默认索引名
            if collection.has_index(index_name=idx_name):
                 logger.info(f"向量字段 '{field_name}' 的索引 '{idx_name}' 已存在于集合 '{collection_name}'。")
                 return True

            logger.info(f"正在为集合 '{collection_name}' 的向量字段 '{field_name}' 创建索引...")
            logger.debug(f"索引参数: {index_params}")

            # 确保 index_params 包含所需键
            if not all(k in index_params for k in ['index_type', 'metric_type', 'params']):
                 raise ValueError("向量索引参数 'index_params' 必须包含 'index_type', 'metric_type', 和 'params' 键。")

            # 释放集合 (如果已加载)
            # collection.release()
            collection.create_index(
                field_name=field_name,
                index_params=index_params,
                index_name=idx_name
            )
            logger.info(f"向量字段 '{field_name}' 的索引创建任务已提交 (集合: '{collection_name}')。")
            # 等待索引构建完成
            logger.info(f"等待向量字段 '{field_name}' 的索引构建完成...")
            utility.wait_for_index_building_complete(collection_name, index_name=idx_name, using=self.alias)
            logger.info(f"向量字段 '{field_name}' 的索引构建完成。")
            # collection.load() # 重新加载
            return True
        except MilvusException as e:
            logger.error(f"为向量字段 '{field_name}' 创建索引失败 (集合: '{collection_name}'): {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"为向量字段 '{field_name}' 创建索引时发生未知错误: {e}", exc_info=True)
            return False

    def _format_data_for_insert(self, data: List[Dict[str, Any]]) -> List[List[Any]]:
        """
        将 List[Dict] 格式的数据转换为 Milvus insert 需要的 List[List] 格式。
        假设所有字典具有相同的键（字段）。
        """
        if not data:
            return []
        # 获取所有字段名 (假设第一个字典包含所有字段)
        fields = list(data[0].keys())
        # 按字段组织数据
        formatted_data = [[] for _ in fields]
        for row_dict in data:
            for i, field_name in enumerate(fields):
                formatted_data[i].append(row_dict.get(field_name)) # 使用 .get() 处理可能缺失的键？ Milvus 要求数据完整
        return formatted_data

    async def insert_vectors_async(
        self,
        collection_name: str,
        data: List[Dict[str, Any]],
        partition_name: Optional[str] = None
    ) -> Tuple[List[Union[str, int]], int]:
        """异步批量插入向量数据"""
        if not data:
            return [], 0
        try:
            collection = await self._get_collection(collection_name)
            # 确保集合已加载，插入前需要加载
            # await self.load_collection_async(collection_name) # 或者在 insert 内部处理

            logger.info(f"准备向集合 '{collection_name}' 插入 {len(data)} 条数据...")
            # pymilvus insert 需要 List[list] 格式的数据
            # formatted_data = self._format_data_for_insert(data) # pymilvus 2.3+ 直接支持 List[Dict]

            # 使用 List[Dict] 格式 (pymilvus 2.3+)
            mutation_result = collection.insert(data, partition_name=partition_name, timeout=30) # 设置超时
            inserted_count = mutation_result.insert_count
            primary_keys = mutation_result.primary_keys
            logger.info(f"成功向集合 '{collection_name}' 插入 {inserted_count} 条数据。PKs: {primary_keys[:5]}...")

            # 插入后需要 flush 使数据可见 (可选，取决于一致性需求)
            # logger.info(f"Flushing collection '{collection_name}'...")
            # collection.flush()
            # logger.info(f"Collection '{collection_name}' flushed.")

            return primary_keys, inserted_count
        except MilvusException as e:
            logger.error(f"向集合 '{collection_name}' 插入数据失败: {e}", exc_info=True)
            raise BusinessException(f"向量数据插入失败: {e}", code=500) from e
        except Exception as e:
            logger.error(f"插入数据到集合 '{collection_name}' 时发生未知错误: {e}", exc_info=True)
            raise BusinessException(f"向量数据插入时发生未知错误: {e}", code=500) from e


    async def delete_vectors_async(
        self,
        collection_name: str,
        expr: str,
        partition_name: Optional[str] = None
    ) -> int:
        """根据表达式异步删除向量数据"""
        if not expr:
             logger.warning("删除表达式为空，不允许删除整个集合的数据。")
             return 0
        try:
            collection = await self._get_collection(collection_name)
            # 确保已加载
            # await self.load_collection_async(collection_name)

            logger.warning(f"准备从集合 '{collection_name}' 删除数据，表达式: '{expr}'")
            mutation_result = collection.delete(expr, partition_name=partition_name, timeout=30)
            delete_count = mutation_result.delete_count
            logger.info(f"从集合 '{collection_name}' 删除了 {delete_count} 条数据。")

            # 删除后 flush 使更改生效
            # logger.info(f"Flushing collection '{collection_name}' after delete...")
            # collection.flush()
            # logger.info(f"Collection '{collection_name}' flushed.")

            return delete_count
        except MilvusException as e:
            logger.error(f"从集合 '{collection_name}' 删除数据失败 (expr='{expr}'): {e}", exc_info=True)
            raise BusinessException(f"向量数据删除失败: {e}", code=500) from e
        except Exception as e:
            logger.error(f"删除集合 '{collection_name}' 数据时发生未知错误: {e}", exc_info=True)
            raise BusinessException(f"向量数据删除时发生未知错误: {e}", code=500) from e

    async def search_async(
        self,
        collection_name: str,
        query_vectors: List[List[float]],
        vector_field: str,
        search_params: Dict[str, Any], # {"metric_type": "COSINE", "params": {"ef": 64}}
        limit: int,
        expr: Optional[str] = None,
        output_fields: Optional[List[str]] = None,
        partition_names: Optional[List[str]] = None,
        consistency_level: Optional[str] = None
    ) -> List[List[Dict[str, Any]]]:
        """异步执行向量搜索"""
        if not query_vectors:
            return []
        try:
            collection = await self._get_collection(collection_name)
            # 确保集合已加载
            await self.load_collection_async(collection_name)

            # 确保 output_fields 包含主键和 distance/score
            if output_fields is None:
                 output_fields = ["*"] # 默认返回所有字段，或者根据需要指定
            else:
                # Milvus 默认只返回 id 和 distance，如果指定了 output_fields，则只返回这些字段
                # 如果需要 id 和 distance/score，必须显式包含或不设置 output_fields
                # 确保 id 字段在输出中 (如果需要)
                # id_field = collection.schema.primary_field.name
                # if id_field not in output_fields: output_fields.append(id_field)
                pass # pymilvus 2.3+ 似乎总是返回 id 和 distance/score

            # 确定一致性级别
            # consistency_level_enum = None
            # if consistency_level:
            #      consistency_level_enum = getattr(ConsistencyLevel, consistency_level, None)
            #      if consistency_level_enum is None:
            #           logger.warning(f"无效的一致性级别 '{consistency_level}'，将使用默认值。")

            logger.info(f"在集合 '{collection_name}' 中搜索 {len(query_vectors)} 个向量, topK={limit}, filter='{expr or 'None'}'...")
            logger.debug(f"搜索参数: {search_params}, 输出字段: {output_fields}")

            results = collection.search(
                data=query_vectors,
                anns_field=vector_field,
                param=search_params,
                limit=limit,
                expr=expr,
                output_fields=output_fields,
                partition_names=partition_names,
                consistency_level=consistency_level,#consistency_level_enum,
                timeout=30 # 搜索超时
            )
            logger.info(f"搜索完成，找到 {len(results)} 组结果。")
            # pymilvus search 返回的是 SearchResult 对象，需要转换
            # results[i] 是 Hits 对象，results[i][j] 是 Hit 对象
            # Hit 对象有 .id, .distance, .entity 属性

            # 将结果转换为 List[List[Dict]]
            formatted_results = []
            for hits in results: # 遍历每个查询向量的结果
                query_hits = []
                for hit in hits: # 遍历该查询向量的每个命中结果
                    hit_data = {
                        "id": hit.id,
                        # Milvus 的 'distance' 对于 COSINE 来说是 1-similarity，
                        # 而对于 L2/IP 是实际距离。需要根据 metric_type 转换为统一的 'score' (相似度)
                        "distance": hit.distance,
                        "score": hit.score if hasattr(hit, 'score') else self._distance_to_score(hit.distance, search_params.get("metric_type")),
                        "entity": {}
                    }
                    if output_fields and hit.entity:
                         # entity 包含请求的 output_fields
                         for field in output_fields:
                              if field == "*": # 如果请求了所有字段
                                   # entity 对象可以直接迭代或访问属性
                                   # hit_data["entity"] = {f.name: hit.entity.get(f.name) for f in collection.schema.fields if f.name != vector_field}
                                   hit_data["entity"] = hit.entity.to_dict() # 更简单的方式
                                   break # 已获取所有字段
                              elif hit.entity.get(field) is not None:
                                  hit_data["entity"][field] = hit.entity.get(field)
                    query_hits.append(hit_data)
                formatted_results.append(query_hits)

            return formatted_results

        except MilvusException as e:
            logger.error(f"在集合 '{collection_name}' 中搜索失败: {e}", exc_info=True)
            # 特殊处理: "collection not loaded"
            if "collection not loaded" in str(e):
                 logger.warning(f"搜索失败因为集合 '{collection_name}' 未加载，尝试加载...")
                 try:
                     await self.load_collection_async(collection_name)
                     logger.info("重新尝试搜索...")
                     # 再次调用搜索逻辑 (避免无限递归，需要小心)
                     # return await self.search_async(...) # 简单起见，抛出异常让调用者处理
                     raise BusinessException(f"向量集合 '{collection_name}' 未加载，请稍后重试。", code=503) from e
                 except Exception as load_e:
                     logger.error(f"加载集合 '{collection_name}' 失败: {load_e}", exc_info=True)
                     raise BusinessException(f"向量搜索失败 (加载集合时出错): {load_e}", code=500) from load_e
            raise BusinessException(f"向量搜索失败: {e}", code=500) from e
        except Exception as e:
            logger.error(f"搜索集合 '{collection_name}' 时发生未知错误: {e}", exc_info=True)
            raise BusinessException(f"向量搜索时发生未知错误: {e}", code=500) from e


    def _distance_to_score(self, distance: float, metric_type: Optional[str]) -> float:
        """根据距离和度量类型计算相似度得分 (0-1 范围)"""
        metric = str(metric_type).upper() if metric_type else "UNKNOWN"
        if metric in ["COSINE", "IP"]: # 内积和余弦相似度，Milvus 的 distance = 1 - similarity
            # score 越高越好
            score = 1.0 - distance
        elif metric == "L2": # 欧氏距离，distance 越小越好
            # 可以简单地取倒数，或者使用更复杂的归一化方法
            # score = 1.0 / (1.0 + distance) # 避免除零，范围 (0, 1]
             # 或者根据可能的距离范围进行归一化，但这比较困难
             # 暂时返回原始距离的负值，表示越小越好，上层再处理
             score = -distance # 或者返回 1 - distance? 需要明确 score 的含义
             # 决定将 score 定义为相似度，L2 距离转相似度比较复杂，暂时用 1/(1+d)
             score = 1.0 / (1.0 + distance)
        else: # JACCARD, HAMMING, etc. - 暂不处理
            score = -distance # 返回负距离表示越小越好
        # 将得分限制在 0-1 之间 (可选)
        # return max(0.0, min(1.0, score))
        return score


    async def load_collection_async(self, collection_name: str):
        """加载集合到内存"""
        try:
            collection = await self._get_collection(collection_name)
            
            # 获取集合的所有索引
            indexes = []
            try:
                # 获取索引列表而不是使用has_index()
                indexes = utility.list_indexes(collection_name, using=self.alias)
            except Exception as e:
                logger.warning(f"获取集合 '{collection_name}' 的索引列表失败: {e}")
            
            if indexes:  # 如果存在任何索引
                # 检查加载状态
                load_state = utility.load_state(collection_name, using=self.alias)
                if load_state == "Loaded" or load_state == "Loading":
                    if utility.loading_progress(collection_name, using=self.alias).get("loading_progress", 0) == 100:
                        logger.debug(f"集合 '{collection_name}' 已加载。")
                        return
                    else:
                        logger.info(f"集合 '{collection_name}' 正在加载中，等待完成...")
                        utility.wait_for_loading_complete(collection_name, using=self.alias, timeout=60)
                        logger.info(f"集合 '{collection_name}' 加载完成。")
                        return

                logger.info(f"正在加载集合 '{collection_name}' 到内存...")
                collection.load()
                # 等待加载完成
                utility.wait_for_loading_complete(collection_name, using=self.alias, timeout=60)
                logger.info(f"集合 '{collection_name}' 加载完成。")
            else:
                logger.warning(f"集合 '{collection_name}' 没有索引，无法加载。")
        except MilvusException as e:
            logger.error(f"加载集合 '{collection_name}' 失败: {e}", exc_info=True)
            raise BusinessException(f"加载向量集合失败: {e}", code=500) from e

    async def release_collection_async(self, collection_name: str):
        """从内存释放集合"""
        try:
            collection = await self._get_collection(collection_name)
            logger.info(f"正在从内存释放集合 '{collection_name}'...")
            collection.release()
            logger.info(f"集合 '{collection_name}' 已释放。")
        except MilvusException as e:
            logger.error(f"释放集合 '{collection_name}' 失败: {e}", exc_info=True)
            # 释放失败通常不是关键错误，只记录日志
        except Exception as e:
             logger.error(f"释放集合 '{collection_name}' 时发生未知错误: {e}", exc_info=True)


    async def has_collection_async(self, collection_name: str) -> bool:
        """检查集合是否存在"""
        await self.ensure_connection()
        try:
            return utility.has_collection(collection_name, using=self.alias)
        except MilvusException as e:
            logger.error(f"检查集合 '{collection_name}' 是否存在时失败: {e}")
            return False # 或者抛出异常

    async def drop_collection_async(self, collection_name: str):
        """删除集合"""
        await self.ensure_connection()
        try:
            logger.warning(f"准备删除集合 '{collection_name}'...")
            utility.drop_collection(collection_name, using=self.alias, timeout=30)
            logger.info(f"集合 '{collection_name}' 已删除。")
        except MilvusException as e:
            logger.error(f"删除集合 '{collection_name}' 失败: {e}", exc_info=True)
            raise BusinessException(f"删除向量集合失败: {e}", code=500) from e