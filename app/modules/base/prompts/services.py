# app/modules/base/prompts/services.py
import logging
from typing import Optional
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.base.prompts.repositories import PromptTemplateRepository
from app.modules.base.prompts.models import PromptTemplate # 导入 Model
from app.modules.base.prompts.dtos import (
    PromptTemplateAddRequestDto,
    PromptTemplateUpdateRequestDto,
    PromptTemplateResponseDto # 导入 DTO
)
from app.core.redis.service import RedisService
from app.core.exceptions import BusinessException, NotFoundException

logger = logging.getLogger(__name__)

class PromptTemplateService:
    """
    提示词模板服务，处理业务逻辑和缓存。
    对应 C# 的 IPromptTemplateService 实现。
    """
    REDIS_KEY_PREFIX = "PROMPT_TEMPLATE:"
    REDIS_CACHE_DURATION_SECONDS = 60 # 缓存 1 分钟

    def __init__(
        self,
        db: AsyncSession,
        repository: PromptTemplateRepository,
        redis_service: RedisService
    ):
        self.db = db
        self.repository = repository
        self.redis_service = redis_service


    # --- Helper function for conversion ---
    def _map_entity_to_dto(self, entity: PromptTemplate) -> PromptTemplateResponseDto:
        """将 PromptTemplate 实体转换为 PromptTemplateResponseDto"""
        return PromptTemplateResponseDto(
            id=entity.id,
            templateKey=entity.template_key, # DTO 使用别名
            templateDesc=entity.template_desc,
            templateContent=entity.template_content
        )
    # ------------------------------------
    
    async def add_async(self, request_dto: PromptTemplateAddRequestDto) -> int:
        """
        添加新的提示词模板。

        Args:
            request_dto: 添加请求 DTO。

        Returns:
            新创建模板的 ID。

        Raises:
            BusinessException: 如果模板 Key 已存在或数据库操作失败。
        """
        # 检查 Key 是否已存在
        existing = await self.repository.get_by_key_async(request_dto.template_key)
        if existing:
            raise BusinessException(f"模板 Key '{request_dto.template_key}' 已存在")

        entity = PromptTemplate(
            template_key=request_dto.template_key,
            template_desc=request_dto.template_desc,
            template_content=request_dto.template_content
        )

        try:
            new_id = await self.repository.add_async(entity)
            await self.db.commit()
            logger.info(f"成功添加提示词模板，ID: {new_id}, Key: {entity.template_key}")
            return new_id
        except Exception as e:
            await self.db.rollback()
            logger.error(f"添加提示词模板失败 (Key: {request_dto.template_key}): {e}")
            raise BusinessException(f"添加模板失败: {e}") from e

    async def update_async(self, request_dto: PromptTemplateUpdateRequestDto) -> bool:
        """
        更新现有的提示词模板。

        Args:
            request_dto: 更新请求 DTO。

        Returns:
            True 如果更新成功。

        Raises:
            NotFoundException: 如果指定 ID 的模板不存在。
            BusinessException: 如果新的模板 Key 与其他模板冲突或数据库操作失败。
        """
        # 1. 检查要更新的模板是否存在
        existing_entity = await self.repository.get_async(request_dto.id)
        if not existing_entity:
            raise NotFoundException(resource_type="提示词模板", resource_id=request_dto.id)

        # 2. 检查新的 Key 是否与 *其他* 模板冲突
        if existing_entity.template_key != request_dto.template_key:
            other_template = await self.repository.get_by_key_async(request_dto.template_key)
            if other_template and other_template.id != request_dto.id:
                raise BusinessException(f"模板 Key '{request_dto.template_key}' 已被其他模板使用")

        # 3. 清理缓存 (先于数据库更新)
        redis_key_old = f"{self.REDIS_KEY_PREFIX}{existing_entity.template_key}"
        redis_key_new = f"{self.REDIS_KEY_PREFIX}{request_dto.template_key}"
        await self.redis_service.key_delete_async(redis_key_old)
        if redis_key_old != redis_key_new: # 如果 key 也变了，新 key 的缓存也要删（以防万一）
            await self.redis_service.key_delete_async(redis_key_new)
        logger.debug(f"已删除提示词模板缓存: {redis_key_old}, {redis_key_new}")


        # 4. 更新实体字段
        update_data = request_dto.model_dump(exclude={'id'}) # 获取需要更新的字段
        for key, value in update_data.items():
             # 驼峰转蛇形，例如 templateKey -> template_key
             snake_case_key = ''.join(['_'+c.lower() if c.isupper() else c for c in key]).lstrip('_')
             if hasattr(existing_entity, snake_case_key):
                  setattr(existing_entity, snake_case_key, value)
        # last_modify_date 会自动更新

        # 5. 执行更新并提交
        try:
            # --- 更新实体字段的逻辑可以简化 ---
            existing_entity.template_key = request_dto.template_key
            existing_entity.template_desc = request_dto.template_desc
            existing_entity.template_content = request_dto.template_content
            # ---------------------------------
            await self.repository.update_async(existing_entity) # 仍然调用 repo 方法
            await self.db.commit()
            logger.info(f"成功更新提示词模板，ID: {request_dto.id}, Key: {request_dto.template_key}")
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error(f"更新提示词模板失败 (ID: {request_dto.id}): {e}")
            raise BusinessException(f"更新模板失败: {e}") from e


    async def get_async(self, template_id: int) -> PromptTemplateResponseDto:
        """
        根据 ID 获取提示词模板。
        """
        db_entity = await self.repository.get_async(template_id)
        if not db_entity:
            raise NotFoundException(resource_type="提示词模板", resource_id=template_id)
        return self._map_entity_to_dto(db_entity)
    

    async def get_by_key_async(self, template_key: str) -> PromptTemplateResponseDto:
        """
        根据 Key 获取提示词模板，优先从缓存读取。
        """
        redis_key = f"{self.REDIS_KEY_PREFIX}{template_key}"
        cached_dto_dict = await self.redis_service.get_async(redis_key)
        if cached_dto_dict:
            try:
                cached_dto = PromptTemplateResponseDto(**cached_dto_dict)
                logger.debug(f"提示词模板缓存命中: {template_key}")
                return cached_dto
            except Exception as e:
                 logger.warning(f"反序列化模板缓存失败 (Key: {template_key}): {e}. 将从数据库重新获取。")

        logger.debug(f"提示词模板缓存未命中: {template_key}. 从数据库查询...")
        db_entity = await self.repository.get_by_key_async(template_key)
        if not db_entity:
            raise NotFoundException(resource_type="提示词模板", resource_id=template_key)

        response_dto = self._map_entity_to_dto(db_entity)

        # 存入缓存
        await self.redis_service.set_async(
            redis_key,
            response_dto.model_dump(by_alias=True), # 存储转换后的 DTO 字典
            expiry_seconds=self.REDIS_CACHE_DURATION_SECONDS
        )
        logger.debug(f"提示词模板已存入缓存: {template_key}, 有效期 {self.REDIS_CACHE_DURATION_SECONDS} 秒")

        return response_dto

    async def get_content_by_key_async(self, template_key: str) -> str:
        """
        根据 Key 获取模板内容，优先从缓存读取。
        """
        try:
            template_dto = await self.get_by_key_async(template_key) # 这个方法内部处理了转换
            if not template_dto.template_content:
                 logger.warning(f"找到模板 Key '{template_key}'，但内容为空。")
                 return ""
            return template_dto.template_content
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"获取模板内容时出错 (Key: {template_key}): {e}")
            raise BusinessException(f"获取模板内容失败: {e}") from e