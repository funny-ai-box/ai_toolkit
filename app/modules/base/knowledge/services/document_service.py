# app/modules/base/knowledge/services/document_service.py
import logging
import json
from typing import List, Optional, Tuple
from fastapi import UploadFile
from pathlib import Path
import io
import asyncio # 用于可能的并发处理

from sqlalchemy.ext.asyncio import AsyncSession

# 导入模型、仓库、服务、DTOs 和枚举
from app.modules.base.knowledge.models import Document, DocumentContent, DocumentGraph, DocumentLog, DocumentVector
from app.modules.base.knowledge.repositories import ( # 从同级 repositories 包导入
    DocumentRepository, DocumentContentRepository, DocumentGraphRepository,
    DocumentLogRepository, DocumentVectorRepository
)
from app.modules.base.knowledge.services.extract_service import IDocumentExtractService # 导入协议
from app.modules.base.knowledge.services.graph_service import KnowledgeGraphService # 导入服务

from app.modules.base.knowledge.dtos import ( # 导入 DTO 和枚举
    DocumentStatus, DocumentLogType, PageUrlImportRequestDto,
    DocumentDetailResponseDto, DocumentStatusResponseDto, DocumentListItemDto,
    DocumentLogItemDto, DocumentContentDto, DocumentListRequestDto, KnowledgeGraphDto
)

# 导入核心依赖
from app.core.ai.chat.base import IChatAIService
from app.core.ai.vector.base import IUserDocsMilvusService # 导入向量库服务协议
from app.core.ai.vector.content_chunker import ContentChunker # 导入分块器
from app.core.storage.base import IStorageService, StorageProviderType # 导入存储服务协议和枚举
from app.core.dtos import BaseIdRequestDto, PagedResultDto, DocumentAppType # 导入核心 DTO
from app.core.exceptions import BusinessException, NotFoundException, NotSupportedException, ValidationException # 导入异常
from app.core.config.settings import Settings # 导入配置
from app.core.utils.file_validator import validate_document_file # 导入文件验证器
from app.core.utils.json_utils import safe_deserialize, safe_serialize # 导入 JSON 工具

# --- 导入核心 Job Persistence 服务 ---
from app.core.job.services import JobPersistenceService
# ----------------------------------

logger = logging.getLogger(__name__)

class DocumentService:
    """
    文档服务实现，处理知识库文档的上传、导入、查询、删除和后台处理。
    对应 C# 的 IDocumentService。
    """
    def __init__(
        self,
        db: AsyncSession, # 接收数据库会话
        # 接收其他需要的外部服务实例 (由依赖注入工厂提供)
        user_docs_milvus_service: IUserDocsMilvusService,
        storage_service: Optional[IStorageService],
        extract_service: IDocumentExtractService,
        graph_service: KnowledgeGraphService,
        ai_service: IChatAIService, # 用于向量化        
        job_persistence_service: JobPersistenceService,
        settings: Settings,
        # logger: logging.Logger # 可以注入 logger
    ):
        self.db = db
        self.settings = settings
        self.user_docs_milvus_service = user_docs_milvus_service
        self.storage_service = storage_service
        self.extract_service = extract_service
        self.graph_service = graph_service
        self.ai_service = ai_service        
        self.job_persistence_service = job_persistence_service
        self.logger = logger # 使用全局或注入的 logger

        # --- 在内部创建仓库实例 ---
        self.document_repository = DocumentRepository(db)
        self.document_content_repository = DocumentContentRepository(db)
        self.document_graph_repository = DocumentGraphRepository(db)
        self.document_log_repository = DocumentLogRepository(db)
        self.document_vector_repository = DocumentVectorRepository(db)
        # --------------------------

        # 初始化文本分块器
        self.content_chunker = ContentChunker(
            chunk_size=settings.KB_CHUNK_SIZE,
            chunk_overlap=settings.KB_CHUNK_OVERLAP
        )
        self.supported_extensions = settings.KB_SUPPORTED_EXTENSIONS

    # --- API 直接调用的方法 ---

    async def upload_document_async(
    self, user_id: int, app_type: DocumentAppType, file: UploadFile,
    title: str = "", reference_id: int = 0,
    need_vector: bool = True, need_graph: bool = True
) -> int:
        """处理文档上传，保存记录，并触发后台处理任务"""
        is_valid, error_message = validate_document_file(file, self.supported_extensions)
        if not is_valid:
            raise ValidationException(error_message)
        if self.storage_service is None:
            raise BusinessException("存储服务未配置，无法上传文件。", code=503)

        original_filename = file.filename or "unknown_file"
        file_extension = Path(original_filename).suffix
        from uuid import uuid4
        unique_filename = f"{uuid4().hex}{file_extension}"
        file_key = f"documents/{user_id}/{unique_filename}"
        content_type = file.content_type or "application/octet-stream"
        cdn_url = "" # 初始化

        try:
            file_content = await file.read()
            file_stream = io.BytesIO(file_content)
            self.logger.info(f"准备上传文件: Key='{file_key}', Size={len(file_content)}")
            cdn_url = await self.storage_service.upload_async(file_stream, file_key, content_type)
            self.logger.info(f"文件上传成功: URL='{cdn_url}'")
        except Exception as e:
            print(f"上传文件到存储服务失败: {e}", exc_info=True)
            raise BusinessException(f"文件上传失败: {str(e)}") from e
        finally:
            await file.close()

        # Create document - IMPORTANT FIX: Explicitly convert app_type enum to integer value
        document = Document(
            user_id=user_id, 
            reference_id=reference_id,
            title=title or Path(original_filename).stem, 
            app_type=int(app_type.value),  # Convert enum to integer! This is the fix
            type="file", 
            original_name=original_filename, 
            cdn_url=cdn_url,
            file_size=len(file_content), 
            is_need_vector=need_vector,
            is_need_graph=need_graph, 
            status=int(DocumentStatus.PENDING),  # Also convert status enum
            vector_status=int(DocumentStatus.PENDING),  # Also convert status enum
            graph_status=int(DocumentStatus.PENDING)   # Also convert status enum
        )

        try:
            document_id = await self.document_repository.add_document_async(document)
            await self.document_log_repository.add_document_log_async(DocumentLog(
                user_id=user_id, 
                document_id=document_id,
                log_type=int(DocumentLogType.DOCUMENT_PARSING),  # Convert enum to integer
                message="文档已上传，等待后台解析"
            ))

            # --- 调用 JobPersistenceService 创建任务 ---
            await self.job_persistence_service.create_job(
                task_type="knowledge.process_document", # 定义任务类型标识符
                params_id=document_id                   # 传递文档 ID 作为主要参数
                # params_data 可以传递额外信息，例如 {'userId': user_id} (如果需要)
            )
            self.logger.info(f"已创建文档处理任务请求: JobType=knowledge.process_document, ParamsId={document_id}")
            # ------------------------------------------

            await self.db.commit()
            self.logger.info(f"文档记录创建成功: ID={document_id}")

            return document_id
        except Exception as e:
            await self.db.rollback()
            print(f"创建文档记录或触发任务失败: {e}")
            if cdn_url and self.storage_service: # 尝试回滚文件上传
                try: await self.storage_service.delete_async(file_key)
                except Exception as del_e: logger.error(f"回滚删除文件失败: {file_key} - {del_e}")
            raise BusinessException("保存文档信息失败") from e

    async def import_web_page_async(
        self, user_id: int, app_type: DocumentAppType, url: str,
        title: str = "", reference_id: int = 0,
        need_vector: bool = True, need_graph: bool = True
    ) -> int:
        """导入网页内容，保存记录，并触发后台处理任务"""
        # ... (验证和创建 Document 记录逻辑与之前相同) ...
        if not url: raise ValidationException("URL 不能为空")
        document = Document(
            user_id=user_id, reference_id=reference_id, title=title or url,
            app_type=app_type, type="url", source_url=str(url),
            is_need_vector=need_vector, is_need_graph=need_graph,
            status=DocumentStatus.PENDING, vector_status=DocumentStatus.PENDING,
            graph_status=DocumentStatus.PENDING
        )
        try:
            document_id = await self.document_repository.add_document_async(document)
            await self.document_log_repository.add_document_log_async(DocumentLog(
                user_id=user_id, document_id=document_id,
                log_type=DocumentLogType.DOCUMENT_PARSING, message="网页导入请求已创建，等待后台处理"
            ))

            # --- 调用 JobPersistenceService 创建任务 ---
            await self.job_persistence_service.create_job(
                task_type="knowledge.process_document",
                params_id=document_id
            )
            self.logger.info(f"已创建网页处理任务请求: JobType=knowledge.process_document, ParamsId={document_id}")
            # ------------------------------------------

            await self.db.commit()
            self.logger.info(f"网页导入记录创建成功: ID={document_id}, URL='{url}'")

            return document_id
        except Exception as e:
            await self.db.rollback()
            print(f"创建网页导入记录或触发任务失败: {e}", exc_info=True)
            raise BusinessException("导入网页失败") from e

    # ... (get_document_async, get_documents_async, get_document_status_async,
    #      get_document_content_async, get_document_logs_async,
    #      get_user_documents_async, delete_document_async 方法与上一版本基本一致，
    #      只需要确保内部调用的是 self.xxx_repository 即可) ...

    async def get_document_async(self, user_id: int, document_id: int) -> DocumentDetailResponseDto:
        """获取文档详情 (包含内容和图谱)"""
        document = await self.document_repository.get_document_async(document_id)
        if document is None or document.user_id != user_id:
            raise NotFoundException("文档", document_id)

        doc_content: Optional[DocumentContent] = None
        doc_graph: Optional[DocumentGraph] = None

        if document.status == DocumentStatus.COMPLETED:
            doc_content = await self.document_content_repository.get_document_content_async(document_id)
        if document.graph_status == DocumentStatus.COMPLETED:
            doc_graph = await self.document_graph_repository.get_by_document_id_async(document_id)

        response_dto = DocumentDetailResponseDto(
            id=document.id, title=document.title, type=document.type, appType=document.app_type,
            originalName=document.original_name, cdnUrl=document.cdn_url, sourceUrl=document.source_url,
            fileSize=document.file_size, contentLength=document.content_length, status=document.status,
            processMessage=document.process_message, vectorStatus=document.vector_status,
            vectorMessage=document.vector_message, graphStatus=document.graph_status,
            graphMessage=document.graph_message, createDate=document.create_date,
            content=doc_content.content if doc_content else None, knowledgeGraph=None
        )
        if doc_graph:
            response_dto.knowledge_graph = KnowledgeGraphDto(
                id=doc_graph.id, documentId=doc_graph.document_id, summary=doc_graph.summary,
                keywords=doc_graph.keywords, mindMap=doc_graph.mind_map
            )
        return response_dto # model_validator 会计算 statusName 等

    async def get_documents_async(self, user_id: int, document_ids: List[int]) -> List[DocumentDetailResponseDto]:
        """批量获取文档详情"""
        documents = await self.document_repository.get_by_ids_async(document_ids)
        if not documents: return []
        doc_ids = [doc.id for doc in documents]
        # 过滤掉非本用户的文档 (如果需要严格检查)
        valid_docs = [doc for doc in documents if doc.user_id == user_id]
        if not valid_docs: return []
        valid_doc_ids = [doc.id for doc in valid_docs]

        doc_contents = await self.document_content_repository.get_document_contents_async(valid_doc_ids)
        doc_graphs = await self.document_graph_repository.get_by_document_ids_async(valid_doc_ids)
        content_map = {c.id: c.content for c in doc_contents}
        graph_map = {g.document_id: g for g in doc_graphs}
        result_list = []
        for doc in valid_docs:
            graph = graph_map.get(doc.id)
            kg_dto = None
            if graph: kg_dto = KnowledgeGraphDto(id=graph.id, documentId=graph.document_id, summary=graph.summary, keywords=graph.keywords, mindMap=graph.mind_map)
            dto = DocumentDetailResponseDto(
                id=doc.id, title=doc.title, type=doc.type, appType=doc.app_type,
                originalName=doc.original_name, cdnUrl=doc.cdn_url, sourceUrl=doc.source_url,
                fileSize=doc.file_size, contentLength=doc.content_length, status=doc.status,
                processMessage=doc.process_message, vectorStatus=doc.vector_status,
                vectorMessage=doc.vector_message, graphStatus=doc.graph_status,
                graphMessage=doc.graph_message, createDate=doc.create_date,
                content=content_map.get(doc.id), knowledgeGraph=kg_dto
            )
            result_list.append(dto)
        return result_list


    async def get_document_status_async(self, user_id: int, document_ids: List[int]) -> List[DocumentStatusResponseDto]:
        """批量获取文档处理状态"""
        documents = await self.document_repository.get_by_ids_async(document_ids)
        result_list = []
        for doc in documents:
            if doc.user_id != user_id: continue # 过滤非本用户
            dto = DocumentStatusResponseDto(
                id=doc.id, title=doc.title, type=doc.type, appType=doc.app_type,
                status=doc.status, processMessage=doc.process_message,
                vectorStatus=doc.vector_status, vectorMessage=doc.vector_message,
                graphStatus=doc.graph_status, graphMessage=doc.graph_message
            )
            result_list.append(dto)
        return result_list

    async def get_document_content_async(self, user_id: int, document_id: int) -> DocumentContentDto:
        """获取已处理完成的文档内容"""
        document = await self.document_repository.get_document_async(document_id)
        if document is None or document.user_id != user_id: raise NotFoundException("文档", document_id)
        if document.status != DocumentStatus.COMPLETED: raise BusinessException("文档尚未处理完成", code=400)
        doc_content = await self.document_content_repository.get_document_content_async(document_id)
        return DocumentContentDto(id=document_id, content=doc_content.content if doc_content else None)


    async def get_document_logs_async(self, user_id: int, document_id: int) -> List[DocumentLogItemDto]:
        """获取文档的处理日志"""
        document = await self.document_repository.get_document_async(document_id)
        if document is None or document.user_id != user_id: raise NotFoundException("文档", document_id)
        logs = await self.document_log_repository.get_document_logs_async(document_id)
        return [DocumentLogItemDto(id=log.id, logType=log.log_type, message=log.message, createDate=log.create_date) for log in logs]


    async def get_user_documents_async(self, user_id: int, request: DocumentListRequestDto) -> PagedResultDto[DocumentListItemDto]:
        """分页获取用户文档列表"""
        items, total_count = await self.document_repository.get_user_documents_async(user_id, request.app_type, request.page_index, request.page_size)
        item_dtos = [DocumentListItemDto(id=d.id, title=d.title, type=d.type, appType=d.app_type, originalName=d.original_name, contentLength=d.content_length, fileSize=d.file_size, sourceUrl=d.source_url, status=d.status, vectorStatus=d.vector_status, createDate=d.create_date) for d in items]
        return PagedResultDto.create(item_dtos, total_count, request)


    async def delete_document_async(self, user_id: int, document_id: int) -> bool:
        """删除文档及其所有关联数据"""
        self.logger.info(f"用户 {user_id} 请求删除文档 ID: {document_id}")
        document = await self.document_repository.get_document_async(document_id)
        if document is None or document.user_id != user_id: raise NotFoundException("文档", document_id)

        # --- 并发删除关联数据 (可选优化) ---
        delete_tasks = []
        # 删除 Milvus 向量
        if document.is_need_vector:
            delete_tasks.append(self.user_docs_milvus_service.delete_vectors_by_document_id_async(user_id, document_id))
        # 删除 DB 向量记录
        delete_tasks.append(self.document_vector_repository.delete_by_document_id_async(document_id))
        # 删除知识图谱
        delete_tasks.append(self.document_graph_repository.delete_by_document_id_async(document_id))
        # 删除文档内容
        delete_tasks.append(self.document_content_repository.delete_document_content_async(document_id))

        results = await asyncio.gather(*delete_tasks, return_exceptions=True)
        # 检查并发删除结果中的错误
        errors = [res for res in results if isinstance(res, Exception)]
        if errors:
            for error in errors: logger.error(f"删除文档 {document_id} 关联数据时出错: {error}", exc_info=error)
            # 即使部分删除失败，也继续删除主记录和文件

        # 删除存储的文件
        if document.type == "file" and document.cdn_url and self.storage_service:
            try:
                url_path = Path(document.cdn_url)
                file_key = "/".join(url_path.parts[url_path.parts.index('documents'):]) # 假设结构固定
                self.logger.info(f"准备删除存储的文件: Key='{file_key}' (来自 URL='{document.cdn_url}')")
                await self.storage_service.delete_async(file_key)
            except Exception as e:
                 logger.error(f"删除存储文件失败 (文档 {document_id}, URL {document.cdn_url}): {e}", exc_info=True)

        # 删除文档主记录
        try:
            deleted_doc = await self.document_repository.delete_async(document_id)
            if deleted_doc:
                await self.db.commit()
                self.logger.info(f"文档 {document_id} 及其关联数据（可能部分失败）已删除。")
                return True
            else:
                await self.db.rollback()
                print(f"删除文档主记录失败 (ID: {document_id})，事务已回滚。")
                raise BusinessException("删除文档记录失败")
        except Exception as e:
            await self.db.rollback()
            print(f"提交删除文档事务失败 (ID: {document_id}): {e}", exc_info=True)
            raise BusinessException("删除文档时发生错误") from e


    # --- 后台处理任务调用的实际执行逻辑 ---
    async def execute_document_parsing(self, document_id: int):
        """执行文档解析的具体逻辑"""
        self.logger.info(f"[任务执行] 解析文档: ID={document_id}")

        document = await self.document_repository.get_document_async(document_id)
        if document is None:
            raise NotFoundException("文档", document_id)                
        if document.status != DocumentStatus.PENDING:
            self.logger.warning(f"文档 {document_id} 状态不适合解析，跳过。")            
            raise BusinessException(f"文档 {document_id} 状态异常，无法执行解析。")

        try:
            await self.document_repository.update_status_async(document_id, DocumentStatus.PROCESSING)
            await self.document_log_repository.add_document_log_async(DocumentLog(
                user_id=document.user_id, document_id=document_id,
                log_type=DocumentLogType.DOCUMENT_PARSING, message="开始解析文档内容"
            ))
            await self.db.commit() # 提交状态和日志

            content = ""
            if document.type == "file" and document.cdn_url:
                content = await self.extract_service.extract_file_content_async(document.cdn_url, document.original_name or "")
            elif document.type == "url" and document.source_url:
                content = await self.extract_service.extract_web_content_async(document.source_url)
            else: raise ValueError("无效的文档来源")

            content_length = len(content)
            await self.document_content_repository.add_document_content_async(DocumentContent(
                id=document_id, user_id=document.user_id, document_id=document_id, content=content
            ))
            await self.document_repository.update_status_async(document_id, DocumentStatus.COMPLETED, "文档解析完成", content_length)
            await self.document_log_repository.add_document_log_async(DocumentLog(
                 user_id=document.user_id, document_id=document_id,
                 log_type=DocumentLogType.DOCUMENT_PARSING, message=f"文档解析成功，内容长度: {content_length}"
            ))
            await self.db.commit() # 提交最终结果
            self.logger.info(f"[任务执行] 文档 {document_id} 解析成功。")

             # --- 解析成功后，触发后续任务 ---
            if document.is_need_vector:
                 await self.job_persistence_service.create_job(
                    task_type="knowledge.vectorize_document", params_id=document_id
                 )
                 self.logger.info(f"已触发文档向量化任务: ID={document_id}")
            if document.is_need_graph:
                 await self.job_persistence_service.create_job(
                    task_type="knowledge.graph_document", params_id=document_id
                 )
                 self.logger.info(f"已触发文档图谱化任务: ID={document_id}")
            # --------------------------------

        except Exception as e:
            print(f"[任务执行] 解析文档 {document_id} 失败: {e}", exc_info=True)
            await self.db.rollback()
            message = f"解析失败: {e.message}" if isinstance(e, BusinessException) else f"解析时发生内部错误: {str(e)}"
            await self.document_repository.update_status_async(document_id, DocumentStatus.FAILED, message)
            await self.document_log_repository.add_document_log_async(DocumentLog(
                 user_id=document.user_id, document_id=document_id,
                 log_type=DocumentLogType.DOCUMENT_PARSING, message=f"文档解析失败: {str(e)}"
            ))
            await self.db.commit() # 提交失败状态              
            raise BusinessException(f"文档 {document_id} 解析异常")


    async def execute_document_vectorization(self, document_id: int):
        """执行文档向量化的具体逻辑"""
        self.logger.info(f"[任务执行] 向量化文档: ID={document_id}")
        document = await self.document_repository.get_document_async(document_id)
        # 检查状态...
        if document is None or document.status != DocumentStatus.COMPLETED or not document.is_need_vector or document.vector_status != DocumentStatus.PENDING:
            self.logger.warning(f"文档 {document_id} 状态不适合向量化，跳过。")
            raise BusinessException(f"文档 {document_id} 状态不适合向量化。")

        doc_content = await self.document_content_repository.get_document_content_async(document_id)
        if doc_content is None or not doc_content.content:
            print(f"文档 {document_id} 内容为空，无法向量化。")
            await self.document_repository.update_vector_status_async(document_id, DocumentStatus.FAILED, "文档内容为空")
            await self.db.commit()
            raise BusinessException("文档内容为空，无法向量化")

        try:
            await self.document_repository.update_vector_status_async(document_id, DocumentStatus.PROCESSING)
            await self.document_log_repository.add_document_log_async(DocumentLog(
                user_id=document.user_id, document_id=document_id,
                log_type=DocumentLogType.VECTORIZATION, message="开始分块和向量化..."
            ))
            await self.db.commit()

            chunks = self.content_chunker.chunk_text(doc_content.content)
            if not chunks: raise BusinessException("文本分块结果为空")
            # 分批获取嵌入...
            batch_size = 100
            all_vectors = []
            for i in range(0, len(chunks), batch_size):
                 batch_chunks = chunks[i:min(i + batch_size, len(chunks))]
                 batch_vectors = await self.ai_service.get_embeddings_async(batch_chunks)
                 if len(batch_vectors) != len(batch_chunks): raise BusinessException("AI 嵌入返回数量不匹配")
                 all_vectors.extend(batch_vectors)

            # 删除旧向量，插入新向量...
            await self.user_docs_milvus_service.delete_vectors_by_document_id_async(document.user_id, document_id)
            inserted_vector_ids = await self.user_docs_milvus_service.insert_vectors_async(
                 user_id=document.user_id, app_type=document.app_type, document_id=document_id,
                 contents=chunks, vectors=all_vectors
            )
            if len(inserted_vector_ids) != len(chunks): logger.warning("Milvus 插入数量与预期不符")

            # 保存 DB 记录...
            await self.document_vector_repository.delete_by_document_id_async(document_id)
            db_vector_records = [DocumentVector(document_id=document_id, user_id=document.user_id, chunk_index=i, chunk_content=chunk, vector_id=vid) for i, (chunk, vid) in enumerate(zip(chunks, inserted_vector_ids))]
            await self.document_vector_repository.add_document_vectors_async(db_vector_records)

            # 更新最终状态...
            await self.document_repository.update_vector_status_async(document_id, DocumentStatus.COMPLETED, f"向量化完成 ({len(chunks)} 块)")
            await self.document_log_repository.add_document_log_async(DocumentLog(
                 user_id=document.user_id, document_id=document_id,
                 log_type=DocumentLogType.VECTORIZATION, message=f"向量化成功，共 {len(chunks)} 个分块"
            ))
            await self.db.commit()
            self.logger.info(f"[任务执行] 文档 {document_id} 向量化成功。")

        except Exception as e:
            print(f"[任务执行] 向量化文档 {document_id} 失败: {e}", exc_info=True)
            await self.db.rollback()
            try: await self.user_docs_milvus_service.delete_vectors_by_document_id_async(document.user_id, document_id)
            except Exception as del_e: logger.error(f"回滚删除 Milvus 向量失败: {del_e}")
            message = f"向量化失败: {e.message}" if isinstance(e, BusinessException) else f"向量化时发生内部错误: {str(e)}"
            await self.document_repository.update_vector_status_async(document_id, DocumentStatus.FAILED, message)
            await self.document_log_repository.add_document_log_async(DocumentLog(
                 user_id=document.user_id, document_id=document_id,
                 log_type=DocumentLogType.VECTORIZATION, message=f"向量化失败: {str(e)}"
            ))
            await self.db.commit()
            raise BusinessException(f"文档 {document_id} 向量化失败")


    async def execute_document_graphing(self, document_id: int):
        """执行文档图谱化的具体逻辑"""
        self.logger.info(f"[任务执行] 图谱化文档: ID={document_id}")
        document = await self.document_repository.get_document_async(document_id)
        # 检查状态...
        if document is None or document.status != DocumentStatus.COMPLETED or not document.is_need_graph or document.graph_status != DocumentStatus.PENDING:
            self.logger.warning(f"文档 {document_id} 状态不适合图谱化，跳过。")
            raise BusinessException(f"文档 {document_id} 尚未完成解析，无法图谱化。")

        doc_content = await self.document_content_repository.get_document_content_async(document_id)
        if doc_content is None or not doc_content.content:
            print(f"文档 {document_id} 内容为空，无法图谱化。")
            await self.document_repository.update_graph_status_async(document_id, DocumentStatus.FAILED, "文档内容为空")
            await self.db.commit()
            raise BusinessException("文档内容为空，无法图谱化")

        try:
            await self.document_repository.update_graph_status_async(document_id, DocumentStatus.PROCESSING)
            await self.document_log_repository.add_document_log_async(DocumentLog(
                user_id=document.user_id, document_id=document_id,
                log_type=DocumentLogType.GRAPH, message="开始调用 AI 生成知识图谱..."
            ))
            await self.db.commit()

            summary, keywords_json, mind_map_json = await self.graph_service.generate_knowledge_graph_async(doc_content.content)

            # 保存图谱...
            await self.document_graph_repository.delete_by_document_id_async(document_id) # 删除旧的
            graph_entity = DocumentGraph(user_id=document.user_id, document_id=document_id, summary=summary, keywords=keywords_json, mind_map=mind_map_json)
            await self.document_graph_repository.add_async(graph_entity)

            # 更新最终状态...
            await self.document_repository.update_graph_status_async(document_id, DocumentStatus.COMPLETED, "图谱化完成")
            await self.document_log_repository.add_document_log_async(DocumentLog(
                 user_id=document.user_id, document_id=document_id,
                 log_type=DocumentLogType.GRAPH, message="图谱化成功"
            ))
            await self.db.commit()
            self.logger.info(f"[任务执行] 文档 {document_id} 图谱化成功。")

        except Exception as e:
            print(f"[任务执行] 图谱化文档 {document_id} 失败: {e}", exc_info=True)
            await self.db.rollback()
            message = f"图谱化失败: {e.message}" if isinstance(e, BusinessException) else f"图谱化时发生内部错误: {str(e)}"
            await self.document_repository.update_graph_status_async(document_id, DocumentStatus.FAILED, message)
            await self.document_log_repository.add_document_log_async(DocumentLog(
                 user_id=document.user_id, document_id=document_id,
                 log_type=DocumentLogType.GRAPH, message=f"图谱化失败: {str(e)}"
            ))
            await self.db.commit()
            raise BusinessException(f"文档 {document_id} 图谱化失败")