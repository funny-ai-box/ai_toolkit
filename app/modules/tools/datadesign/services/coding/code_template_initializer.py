import datetime
import logging
from typing import List
from app.modules.tools.datadesign.entities import CodeTemplate, CodeTemplateDtl
from app.modules.tools.datadesign.enums import LanguageType, DatabaseType
from app.modules.tools.datadesign.repositories.code_template_repository import CodeTemplateRepository
# from app.modules.tools.datadesign.repositories.code_template_dtl_repository import CodeTemplateDtlRepository # Not directly used here, combined logic in CodeTemplateRepository
# from app.core.utils.snowflake import generate_id # IDs are generated in repository

class CodeTemplateInitializer:
    """代码模板初始数据帮助类"""

    def __init__(self, code_template_repository: CodeTemplateRepository, logger: logging.Logger):
        """
        构造函数

        Args:
            code_template_repository (CodeTemplateRepository): 代码模板仓库
            logger (logging.Logger): 日志记录器
        """
        self.code_template_repository = code_template_repository
        self.logger = logger

    async def initialize_templates_async(self) -> bool:
        """
        初始化代码模板 (如果尚不存在系统模板)

        Returns:
            bool: 操作结果
        """
        try:
            if await self.code_template_repository.exist_system_template_async():
                self.logger.info("系统代码模板已存在，跳过初始化。")
                return True

            self.logger.info("开始初始化系统代码模板...")

            # C# Templates
            template_csharp_dtl = [
                self._create_template_dtl("Entity", "{{pascalTableName}}.cs", _CSHARP_ENTITY_TEMPLATE),
                self._create_template_dtl("Repository Interface", "I{{pascalTableName}}Repository.cs", _CSHARP_REPOSITORY_INTERFACE_TEMPLATE),
                self._create_template_dtl("Repository Implementation", "{{pascalTableName}}Repository.cs", _CSHARP_REPOSITORY_IMPLEMENTATION_TEMPLATE),
                self._create_template_dtl("DTO", "{{pascalTableName}}Dto.cs", _CSHARP_DTO_TEMPLATE),
                self._create_template_dtl("Service Interface", "I{{pascalTableName}}Service.cs", _CSHARP_SERVICE_INTERFACE_TEMPLATE),
                self._create_template_dtl("Service Implementation", "{{pascalTableName}}Service.cs", _CSHARP_SERVICE_IMPLEMENTATION_TEMPLATE),
            ]
            template_csharp = self._create_template("C#操作Mysql数据模板", LanguageType.CSHARP, DatabaseType.MYSQL)
            await self.code_template_repository.add_template_and_dtls_async(template_csharp, template_csharp_dtl)

            # Python Templates
            template_python_dtl = [
                self._create_template_dtl("Model", "{{snake_table_name}}.py", _PYTHON_MODEL_TEMPLATE),
                self._create_template_dtl("Repository", "{{snake_table_name}}_repository.py", _PYTHON_REPOSITORY_TEMPLATE),
                self._create_template_dtl("Schema", "{{snake_table_name}}_schema.py", _PYTHON_SCHEMA_TEMPLATE),
                self._create_template_dtl("Service", "{{snake_table_name}}_service.py", _PYTHON_SERVICE_TEMPLATE),
            ]
            template_python = self._create_template("Python操作Mysql数据模板", LanguageType.PYTHON, DatabaseType.MYSQL)
            await self.code_template_repository.add_template_and_dtls_async(template_python, template_python_dtl)

            # Java Templates
            template_java_dtl = [
                self._create_template_dtl("Entity", "{{pascalTableName}}.java", _JAVA_ENTITY_TEMPLATE),
                self._create_template_dtl("Repository", "{{pascalTableName}}Repository.java", _JAVA_REPOSITORY_TEMPLATE),
                self._create_template_dtl("DTO", "{{pascalTableName}}DTO.java", _JAVA_DTO_TEMPLATE),
                self._create_template_dtl("Service Interface", "{{pascalTableName}}Service.java", _JAVA_SERVICE_INTERFACE_TEMPLATE),
                self._create_template_dtl("Service Implementation", "{{pascalTableName}}ServiceImpl.java", _JAVA_SERVICE_IMPLEMENTATION_TEMPLATE),
            ]
            template_java = self._create_template("Java操作Mysql数据模板", LanguageType.JAVA, DatabaseType.MYSQL)
            await self.code_template_repository.add_template_and_dtls_async(template_java, template_java_dtl)
            
            self.logger.info("系统代码模板初始化完成。")
            return True
        except Exception as ex:
            self.logger.error(f"初始化代码模板失败: {ex}", exc_info=True)
            return False

    def _create_template(self, name: str, language: LanguageType, database_type: DatabaseType) -> CodeTemplate:
        """创建模板实体 (不含ID和时间戳，由仓库处理)"""
        return CodeTemplate(
            template_name=name,
            language=language,
            database_type=database_type,
            user_id=0,  # 0 for system templates
            prompt_content=None # System templates typically don't have prompt content for generation
        )

    def _create_template_dtl(self, name: str, file_name: str, content: str) -> CodeTemplateDtl:
        """创建模板明细实体 (不含ID、template_id和时间戳，由仓库处理)"""
        return CodeTemplateDtl(
            template_dtl_name=name,
            file_name=file_name,
            template_content=content
        )

# C# Templates (Copied from C# source)
_CSHARP_ENTITY_TEMPLATE = """using System;
using System.ComponentModel.DataAnnotations;
using SqlSugar;

namespace {{namespace}}.Entities
{
    /// <summary>
    /// {{tableComment}}
    /// </summary>
    [SugarTable("{{tableName}}")]
    public class {{pascalTableName}}
    {
        {{#fields}}
        /// <summary>
        /// {{comment}}
        /// </summary>
        {{#isPrimaryKey}}
        [SugarColumn(IsPrimaryKey = true, {{#isAutoIncrement}}IsIdentity = true{{/isAutoIncrement}}{{^isAutoIncrement}}IsIdentity = false{{/isAutoIncrement}})]
        {{/isPrimaryKey}}
        {{^isPrimaryKey}}
        {{#length}}
        [SugarColumn(Length = {{length}})]
        {{/length}}
        {{/isPrimaryKey}}
        public {{codeDataType}}{{#isNullable}}?{{/isNullable}} {{pascalName}} { get; set; }

        {{/fields}}
    }
}"""
_CSHARP_REPOSITORY_INTERFACE_TEMPLATE = """using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using {{namespace}}.Entities;

namespace {{namespace}}.Repositories.IFace
{
    /// <summary>
    /// {{tableComment}}仓储接口
    /// </summary>
    public interface I{{pascalTableName}}Repository
    {
        /// <summary>
        /// 获取{{tableComment}}
        /// </summary>
        /// <param name="id">ID</param>
        /// <returns>{{tableComment}}实体</returns>
        Task<{{pascalTableName}}> GetByIdAsync({{primaryKey.codeDataType}} id);

        /// <summary>
        /// 获取所有{{tableComment}}
        /// </summary>
        /// <returns>{{tableComment}}实体列表</returns>
        Task<List<{{pascalTableName}}>> GetAllAsync();

        /// <summary>
        /// 分页获取{{tableComment}}
        /// </summary>
        /// <param name="pageIndex">页码</param>
        /// <param name="pageSize">每页大小</param>
        /// <returns>{{tableComment}}实体列表和总数</returns>
        Task<(List<{{pascalTableName}}> Items, int TotalCount)> GetPaginatedAsync(int pageIndex, int pageSize);

        /// <summary>
        /// 新增{{tableComment}}
        /// </summary>
        /// <param name="entity">{{tableComment}}实体</param>
        /// <returns>操作结果</returns>
        Task<bool> AddAsync({{pascalTableName}} entity);

        /// <summary>
        /// 更新{{tableComment}}
        /// </summary>
        /// <param name="entity">{{tableComment}}实体</param>
        /// <returns>操作结果</returns>
        Task<bool> UpdateAsync({{pascalTableName}} entity);

        /// <summary>
        /// 删除{{tableComment}}
        /// </summary>
        /// <param name="id">ID</param>
        /// <returns>操作结果</returns>
        Task<bool> DeleteAsync({{primaryKey.codeDataType}} id);
    }
}"""
_CSHARP_REPOSITORY_IMPLEMENTATION_TEMPLATE = """using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using SqlSugar;
using {{namespace}}.Entities;
using {{namespace}}.Repositories.IFace;
using AIToolkit.Application.Core.Database;

namespace {{namespace}}.Repositories
{
    /// <summary>
    /// {{tableComment}}仓储实现
    /// </summary>
    public class {{pascalTableName}}Repository : I{{pascalTableName}}Repository
    {
        private readonly DbContext<{{pascalTableName}}> _dbContext;

        /// <summary>
        /// 构造函数
        /// </summary>
        /// <param name="dbContext">数据库上下文</param>
        public {{pascalTableName}}Repository(DbContext<{{pascalTableName}}> dbContext)
        {
            _dbContext = dbContext;
        }

        /// <summary>
        /// 获取{{tableComment}}
        /// </summary>
        /// <param name="id">ID</param>
        /// <returns>{{tableComment}}实体</returns>
        public async Task<{{pascalTableName}}> GetByIdAsync({{primaryKey.codeDataType}} id)
        {
            return await _dbContext.Db.Queryable<{{pascalTableName}}>()
                .FirstAsync(x => x.{{primaryKey.pascalName}} == id);
        }

        /// <summary>
        /// 获取所有{{tableComment}}
        /// </summary>
        /// <returns>{{tableComment}}实体列表</returns>
        public async Task<List<{{pascalTableName}}>> GetAllAsync()
        {
            return await _dbContext.Db.Queryable<{{pascalTableName}}>()
                .ToListAsync();
        }

        /// <summary>
        /// 分页获取{{tableComment}}
        /// </summary>
        /// <param name="pageIndex">页码</param>
        /// <param name="pageSize">每页大小</param>
        /// <returns>{{tableComment}}实体列表和总数</returns>
        public async Task<(List<{{pascalTableName}}> Items, int TotalCount)> GetPaginatedAsync(int pageIndex, int pageSize)
        {
            // 确保页码和每页数量有效
            if (pageIndex < 1) pageIndex = 1;
            if (pageSize < 1) pageSize = 20;
            
            // 计算跳过的记录数
            int skip = (pageIndex - 1) * pageSize;
            
            // 查询满足条件的记录总数
            int totalCount = await _dbContext.Db.Queryable<{{pascalTableName}}>()
                .CountAsync();
            
            // 查询分页数据
            var items = await _dbContext.Db.Queryable<{{pascalTableName}}>()
                .OrderByDescending(p => p.{{primaryKey.pascalName}})
                .Skip(skip)
                .Take(pageSize)
                .ToListAsync();
            
            return (items, totalCount);
        }

        /// <summary>
        /// 新增{{tableComment}}
        /// </summary>
        /// <param name="entity">{{tableComment}}实体</param>
        /// <returns>操作结果</returns>
        public async Task<bool> AddAsync({{pascalTableName}} entity)
        {
            {{#primaryKey}}
            {{^isAutoIncrement}}
            entity.{{pascalName}} = _dbContext.IdGenerator.NextId();
            {{/isAutoIncrement}}
            {{/primaryKey}}
            return await _dbContext.Db.Insertable(entity).ExecuteCommandAsync() > 0;
        }

        /// <summary>
        /// 更新{{tableComment}}
        /// </summary>
        /// <param name="entity">{{tableComment}}实体</param>
        /// <returns>操作结果</returns>
        public async Task<bool> UpdateAsync({{pascalTableName}} entity)
        {
            return await _dbContext.Db.Updateable(entity).ExecuteCommandAsync() > 0;
        }

        /// <summary>
        /// 删除{{tableComment}}
        /// </summary>
        /// <param name="id">ID</param>
        /// <returns>操作结果</returns>
        public async Task<bool> DeleteAsync({{primaryKey.codeDataType}} id)
        {
            return await _dbContext.Db.Deleteable<{{pascalTableName}}>()
                .Where(x => x.{{primaryKey.pascalName}} == id)
                .ExecuteCommandAsync() > 0;
        }
    }
}"""
_CSHARP_DTO_TEMPLATE = """using System;
using System.ComponentModel.DataAnnotations;

namespace {{namespace}}.DTOs
{
    /// <summary>
    /// {{tableComment}}详情DTO
    /// </summary>
    public class {{pascalTableName}}DetailDto
    {
        {{#fields}}
        /// <summary>
        /// {{comment}}
        /// </summary>
        public {{codeDataType}}{{#isNullable}}?{{/isNullable}} {{pascalName}} { get; set; }

        {{/fields}}
    }

    /// <summary>
    /// {{tableComment}}列表项DTO
    /// </summary>
    public class {{pascalTableName}}ListItemDto
    {
        {{#fields}}
        {{#isPrimaryKey}}
        /// <summary>
        /// {{comment}}
        /// </summary>
        public {{codeDataType}} {{pascalName}} { get; set; }

        {{/isPrimaryKey}}
        {{/fields}}
        // 添加其他需要在列表中显示的字段
        
        /// <summary>
        /// 创建时间
        /// </summary>
        public DateTime CreateTime { get; set; }
    }

    /// <summary>
    /// 创建{{tableComment}}请求DTO
    /// </summary>
    public class Create{{pascalTableName}}RequestDto
    {
        {{#fields}}
        {{^isPrimaryKey}}
        {{^isAutoIncrement}}
        /// <summary>
        /// {{comment}}
        /// </summary>
        {{^isNullable}}
        [Required(ErrorMessage = "{{comment}}不能为空")]
        {{/isNullable}}
        public {{codeDataType}}{{#isNullable}}?{{/isNullable}} {{pascalName}} { get; set; }

        {{/isAutoIncrement}}
        {{/isPrimaryKey}}
        {{/fields}}
    }

    /// <summary>
    /// 更新{{tableComment}}请求DTO
    /// </summary>
    public class Update{{pascalTableName}}RequestDto
    {
        {{#fields}}
        {{#isPrimaryKey}}
        /// <summary>
        /// {{comment}}
        /// </summary>
        [Required]
        public {{codeDataType}} {{pascalName}} { get; set; }

        {{/isPrimaryKey}}
        {{^isPrimaryKey}}
        /// <summary>
        /// {{comment}}
        /// </summary>
        {{^isNullable}}
        [Required(ErrorMessage = "{{comment}}不能为空")]
        {{/isNullable}}
        public {{codeDataType}}{{#isNullable}}?{{/isNullable}} {{pascalName}} { get; set; }

        {{/isPrimaryKey}}
        {{/fields}}
    }
}"""
_CSHARP_SERVICE_INTERFACE_TEMPLATE = """using System.Collections.Generic;
using System.Threading.Tasks;
using {{namespace}}.DTOs;
using AIToolkit.Application.Core.DTOs;

namespace {{namespace}}.Services.IFace
{
    /// <summary>
    /// {{tableComment}}服务接口
    /// </summary>
    public interface I{{pascalTableName}}Service
    {
        /// <summary>
        /// 获取{{tableComment}}详情
        /// </summary>
        /// <param name="id">ID</param>
        /// <returns>{{tableComment}}详情</returns>
        Task<{{pascalTableName}}DetailDto> Get{{pascalTableName}}Async({{primaryKey.codeDataType}} id);

        /// <summary>
        /// 获取{{tableComment}}分页列表
        /// </summary>
        /// <param name="request">分页请求</param>
        /// <returns>{{tableComment}}分页列表</returns>
        Task<PagedResultDto<{{pascalTableName}}ListItemDto>> Get{{pascalTableName}}ListAsync(BasePageRequestDto request);

        /// <summary>
        /// 创建{{tableComment}}
        /// </summary>
        /// <param name="request">创建请求</param>
        /// <returns>{{tableComment}}ID</returns>
        Task<{{primaryKey.codeDataType}}> Create{{pascalTableName}}Async(Create{{pascalTableName}}RequestDto request);

        /// <summary>
        /// 更新{{tableComment}}
        /// </summary>
        /// <param name="request">更新请求</param>
        /// <returns>操作结果</returns>
        Task<bool> Update{{pascalTableName}}Async(Update{{pascalTableName}}RequestDto request);

        /// <summary>
        /// 删除{{tableComment}}
        /// </summary>
        /// <param name="id">ID</param>
        /// <returns>操作结果</returns>
        Task<bool> Delete{{pascalTableName}}Async({{primaryKey.codeDataType}} id);
    }
}"""
_CSHARP_SERVICE_IMPLEMENTATION_TEMPLATE = """using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using {{namespace}}.DTOs;
using {{namespace}}.Entities;
using {{namespace}}.Repositories.IFace;
using {{namespace}}.Services.IFace;
using AIToolkit.Application.Core.DTOs;
using AIToolkit.Application.Core.Exceptions;

namespace {{namespace}}.Services
{
    /// <summary>
    /// {{tableComment}}服务实现
    /// </summary>
    public class {{pascalTableName}}Service : I{{pascalTableName}}Service
    {
        private readonly ILogger<{{pascalTableName}}Service> _logger;
        private readonly I{{pascalTableName}}Repository _repository;

        /// <summary>
        /// 构造函数
        /// </summary>
        /// <param name="logger">日志</param>
        /// <param name="repository">仓储</param>
        public {{pascalTableName}}Service(ILogger<{{pascalTableName}}Service> logger, I{{pascalTableName}}Repository repository)
        {
            _logger = logger;
            _repository = repository;
        }

        /// <summary>
        /// 获取{{tableComment}}详情
        /// </summary>
        /// <param name="id">ID</param>
        /// <returns>{{tableComment}}详情</returns>
        public async Task<{{pascalTableName}}DetailDto> Get{{pascalTableName}}Async({{primaryKey.codeDataType}} id)
        {
            try
            {
                var entity = await _repository.GetByIdAsync(id);
                if (entity == null)
                {
                    throw new BusinessException("{{tableComment}}数据不存", id);
                }

                return MapToDetailDto(entity);
            }
            catch (Exception ex) when (!(ex is BusinessException))
            {
                _logger.LogError(ex, $"获取{{tableComment}}详情失败，ID: {id}");
                throw new BusinessException("获取{{tableComment}}详情失败", ex);
            }
        }

        /// <summary>
        /// 获取{{tableComment}}分页列表
        /// </summary>
        /// <param name="request">分页请求</param>
        /// <returns>{{tableComment}}分页列表</returns>
        public async Task<PagedResultDto<{{pascalTableName}}ListItemDto>> Get{{pascalTableName}}ListAsync(BasePageRequestDto request)
        {
            try
            {
                var (items, totalCount) = await _repository.GetPaginatedAsync(request.PageIndex, request.PageSize);
                
                var dtos = items.Select(MapToListItemDto).ToList();
                
                return new PagedResultDto<{{pascalTableName}}ListItemDto>
                {
                    Items = dtos,
                    TotalCount = totalCount,
                    PageIndex = request.PageIndex,
                    PageSize = request.PageSize,
                    TotalPages = (int)Math.Ceiling(totalCount / (double)request.PageSize)
                };
            }
            catch (Exception ex) when (!(ex is BusinessException))
            {
                _logger.LogError(ex, "获取{{tableComment}}列表失败");
                throw new BusinessException("获取{{tableComment}}列表失败", ex);
            }
        }

        /// <summary>
        /// 创建{{tableComment}}
        /// </summary>
        /// <param name="request">创建请求</param>
        /// <returns>{{tableComment}}ID</returns>
        public async Task<{{primaryKey.codeDataType}}> Create{{pascalTableName}}Async(Create{{pascalTableName}}RequestDto request)
        {
            try
            {
                var entity = MapFromCreateDto(request);
                
                var result = await _repository.AddAsync(entity);
                if (!result)
                {
                    throw new BusinessException("创建{{tableComment}}失败");
                }
                
                return entity.{{primaryKey.pascalName}};
            }
            catch (Exception ex) when (!(ex is BusinessException))
            {
                _logger.LogError(ex, "创建{{tableComment}}失败");
                throw new BusinessException("创建{{tableComment}}失败", ex);
            }
        }

        /// <summary>
        /// 更新{{tableComment}}
        /// </summary>
        /// <param name="request">更新请求</param>
        /// <returns>操作结果</returns>
        public async Task<bool> Update{{pascalTableName}}Async(Update{{pascalTableName}}RequestDto request)
        {
            try
            {
                var entity = await _repository.GetByIdAsync(request.{{primaryKey.pascalName}});
                if (entity == null)
                {
                    throw new BusinessException("{{tableComment}}数据不存在", request.{{primaryKey.pascalName}});
                }
                
                MapFromUpdateDto(request, entity);
                
                return await _repository.UpdateAsync(entity);
            }
            catch (Exception ex) when (!(ex is BusinessException))
            {
                _logger.LogError(ex, $"更新{{tableComment}}失败，ID: {request.{{primaryKey.pascalName}}}");
                throw new BusinessException("更新{{tableComment}}失败", ex);
            }
        }

        /// <summary>
        /// 删除{{tableComment}}
        /// </summary>
        /// <param name="id">ID</param>
        /// <returns>操作结果</returns>
        public async Task<bool> Delete{{pascalTableName}}Async({{primaryKey.codeDataType}} id)
        {
            try
            {
                var entity = await _repository.GetByIdAsync(id);
                if (entity == null)
                {
                    throw new BusinessException("{{tableComment}}数据不存在", id);
                }
                
                return await _repository.DeleteAsync(id);
            }
            catch (Exception ex) when (!(ex is BusinessException))
            {
                _logger.LogError(ex, $"删除{{tableComment}}失败，ID: {id}");
                throw new BusinessException("删除{{tableComment}}失败", ex);
            }
        }

        #region 映射方法

        /// <summary>
        /// 映射到详情DTO
        /// </summary>
        /// <param name="entity">实体</param>
        /// <returns>详情DTO</returns>
        private {{pascalTableName}}DetailDto MapToDetailDto({{pascalTableName}} entity)
        {
            return new {{pascalTableName}}DetailDto
            {
                {{#fields}}
                {{pascalName}} = entity.{{pascalName}},
                {{/fields}}
            };
        }

        /// <summary>
        /// 映射到列表项DTO
        /// </summary>
        /// <param name="entity">实体</param>
        /// <returns>列表项DTO</returns>
        private {{pascalTableName}}ListItemDto MapToListItemDto({{pascalTableName}} entity)
        {
            return new {{pascalTableName}}ListItemDto
            {
                {{#fields}}
                {{#isPrimaryKey}}
                {{pascalName}} = entity.{{pascalName}},
                {{/isPrimaryKey}}
                {{/fields}}
                // 添加其他需要在列表中显示的字段
            };
        }

        /// <summary>
        /// 从创建DTO映射
        /// </summary>
        /// <param name="dto">创建DTO</param>
        /// <returns>实体</returns>
        private {{pascalTableName}} MapFromCreateDto(Create{{pascalTableName}}RequestDto dto)
        {
            return new {{pascalTableName}}
            {
                {{#fields}}
                {{^isPrimaryKey}}
                {{^isAutoIncrement}}
                {{pascalName}} = dto.{{pascalName}},
                {{/isAutoIncrement}}
                {{/isPrimaryKey}}
                {{/fields}}
            };
        }

        /// <summary>
        /// 从更新DTO映射
        /// </summary>
        /// <param name="dto">更新DTO</param>
        /// <param name="entity">实体</param>
        private void MapFromUpdateDto(Update{{pascalTableName}}RequestDto dto, {{pascalTableName}} entity)
        {
            {{#fields}}
            {{^isPrimaryKey}}
            entity.{{pascalName}} = dto.{{pascalName}};
            {{/isPrimaryKey}}
            {{/fields}}
        }

        #endregion
    }
}"""

# Python Templates
_PYTHON_MODEL_TEMPLATE = """from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text # ForeignKey
from sqlalchemy.orm import Mapped, mapped_column # new style
from sqlalchemy.ext.declarative import declarative_base
import datetime # for type hints

Base = declarative_base()

class {{pascalTableName}}(Base):
    \"\"\"
    {{tableComment}}
    \"\"\"
    __tablename__ = '{{tableName}}' # Raw table name from DB design

    {{#fields}}
    {{name}}: Mapped[{{codeDataType}}{{#isNullable}} | None{{/isNullable}}] = mapped_column({{#isPrimaryKey}}primary_key=True{{#isAutoIncrement}}, autoincrement=True{{/isAutoIncrement}}{{/isPrimaryKey}}{{#length}}, String({{length}}){{/length}}{{^length}}{{#codeDataTypeBOOL}}Boolean{{/codeDataTypeBOOL}}{{#codeDataTypeINT}}Integer{{/codeDataTypeINT}}{{#codeDataTypeFLOAT}}Float{{/codeDataTypeFLOAT}}{{#codeDataTypeSTR}}Text{{/codeDataTypeSTR}}{{#codeDataTypeDATETIME}}DateTime{{/codeDataTypeDATETIME}}{{/length}}, {{#isNullable}}nullable=True{{/isNullable}}{{^isNullable}}nullable=False{{/isNullable}}, comment='{{comment}}')
    {{/fields}}

    def __repr__(self):
        return f'<{{pascalTableName}} {{#primaryKey}}id={{self.{{name}}}}{{/primaryKey}}>'
"""
_PYTHON_REPOSITORY_TEMPLATE = """from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, update as sqlalchemy_update, delete as sqlalchemy_delete, desc
from typing import List, Optional, Tuple
from .models import {{pascalTableName}} # Assuming models.py in same dir
from app.core.utils.snowflake import generate_id # For ID generation if needed

class {{pascalTableName}}Repository:
    \"\"\"
    {{tableComment}}仓储类
    \"\"\"
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id_async(self, id: {{primaryKey.codeDataType}}) -> Optional[{{pascalTableName}}]:
        \"\"\"
        根据ID获取{{tableComment}}

        Args:
            id: {{tableComment}}ID

        Returns:
            {{tableComment}}实体
        \"\"\"
        result = await self.db.execute(select({{pascalTableName}}).filter({{pascalTableName}}.{{primaryKey.name}} == id))
        return result.scalars().first()

    async def get_all_async(self) -> List[{{pascalTableName}}]:
        \"\"\"
        获取所有{{tableComment}}

        Returns:
            {{tableComment}}实体列表
        \"\"\"
        result = await self.db.execute(select({{pascalTableName}}))
        return result.scalars().all()

    async def get_paginated_async(self, page_index: int, page_size: int) -> Tuple[List[{{pascalTableName}}], int]:
        \"\"\"
        分页获取{{tableComment}}

        Args:
            page_index: 页码
            page_size: 每页大小

        Returns:
            {{tableComment}}实体列表和总数
        \"\"\"
        if page_index < 1: page_index = 1
        if page_size < 1: page_size = 20
        
        offset = (page_index - 1) * page_size
        
        total_count_res = await self.db.execute(select(func.count()).select_from({{pascalTableName}}))
        total_count = total_count_res.scalar_one()
        
        items_res = await self.db.execute(
            select({{pascalTableName}})
            .order_by(desc({{pascalTableName}}.{{primaryKey.name}})) # Or another default sort field
            .offset(offset)
            .limit(page_size)
        )
        items = items_res.scalars().all()
        
        return items, total_count

    async def add_async(self, entity: {{pascalTableName}}) -> {{pascalTableName}}:
        \"\"\"
        新增{{tableComment}}

        Args:
            entity: {{tableComment}}实体

        Returns:
            新增的实体（可能包含数据库生成的ID）
        \"\"\"
        {{#primaryKey}}
        {{^isAutoIncrement}}
        if not entity.{{name}}: # If ID is not auto-increment and not set
            entity.{{name}} = generate_id() 
        {{/isAutoIncrement}}
        {{/primaryKey}}
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def update_async(self, entity: {{pascalTableName}}) -> bool:
        \"\"\"
        更新{{tableComment}}

        Args:
            entity: {{tableComment}}实体

        Returns:
            操作结果
        \"\"\"
        # For attached entities, changes are tracked. A flush commits.
        # For detached, or explicit update:
        # await self.db.merge(entity)
        # await self.db.flush()
        # Or use sqlalchemy_update for specific fields if entity is just a dict/DTO
        stmt = sqlalchemy_update({{pascalTableName}}).where({{pascalTableName}}.{{primaryKey.name}} == entity.{{primaryKey.name}})
        # stmt = stmt.values(**{c.name: getattr(entity, c.name) for c in entity.__table__.columns if c.name != '{{primaryKey.name}}'}) # Example to update all non-PK fields
        # This simple version assumes entity has all fields to update:
        update_dict = {c.key: getattr(entity, c.key) for c in entity.__mapper__.columns if c.key != '{{primaryKey.name}}'}
        if not update_dict: return False # Nothing to update
        stmt = stmt.values(**update_dict)

        result = await self.db.execute(stmt)
        return result.rowcount > 0


    async def delete_async(self, id: {{primaryKey.codeDataType}}) -> bool:
        \"\"\"
        删除{{tableComment}}

        Args:
            id: {{tableComment}}ID

        Returns:
            操作结果
        \"\"\"
        stmt = sqlalchemy_delete({{pascalTableName}}).where({{pascalTableName}}.{{primaryKey.name}} == id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0
"""
_PYTHON_SCHEMA_TEMPLATE = """from pydantic import BaseModel, Field
from typing import List, Optional
import datetime

# Pydantic models should use camelCase for aliases if JSON is camelCase
# Python attributes remain snake_case

class {{pascalTableName}}Base(BaseModel):
    {{#fields}}
    {{^isPrimaryKey}}
    {{^isAutoIncrement}}
    {{name}}: Optional[{{codeDataType}}]{{#isNullable}} = None{{/isNullable}} {{#isNullable}} # {{comment}} {{/isNullable}}{{^isNullable}} = Field(..., description='{{comment}}'){{/isNullable}}
    {{/isAutoIncrement}}
    {{/isPrimaryKey}}
    {{/fields}}

    class Config:
        from_attributes = True # orm_mode for Pydantic v1
        alias_generator = lambda string: ''.join(word.capitalize() if i > 0 else word for i, word in enumerate(string.split('_'))) # to_camel_case
        populate_by_name = True


class Create{{pascalTableName}}Request({{pascalTableName}}Base):
    pass

class Update{{pascalTableName}}Request({{pascalTableName}}Base):
    {{#fields}}
    {{#isPrimaryKey}}
    # id field might not be part of update request body, but in path
    {{/isPrimaryKey}}
    {{/fields}}
    pass


class {{pascalTableName}}Response({{pascalTableName}}Base):
    {{#fields}}
    {{#isPrimaryKey}}
    {{name}}: {{codeDataType}} = Field(..., description='{{comment}}')
    {{/isPrimaryKey}}
    {{/fields}}
    # Add other fields like create_date, last_modify_date if needed in response
    create_date: Optional[datetime.datetime] = None
    last_modify_date: Optional[datetime.datetime] = None

class {{pascalTableName}}ListItemResponse({{pascalTableName}}Response): # Or a subset of fields
    # Example: only show a few fields for list items
    {{#fields}}
    {{#isPrimaryKey}}
    {{name}}: {{codeDataType}} = Field(..., description='{{comment}}')
    {{/isPrimaryKey}}
    {{/fields}}
    # Add one or two more relevant fields for list view
    # e.g. some_important_field: Optional[str] = None
    pass


class Paged{{pascalTableName}}Response(BaseModel):
    items: List[{{pascalTableName}}ListItemResponse]
    total_count: int
    page_index: int
    page_size: int
    total_pages: int
    
    class Config:
        alias_generator = lambda string: ''.join(word.capitalize() if i > 0 else word for i, word in enumerate(string.split('_')))
        populate_by_name = True

"""
_PYTHON_SERVICE_TEMPLATE = """import logging
import math
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from .models import {{pascalTableName}}
from .repository import {{pascalTableName}}Repository
from .schemas import (
    Create{{pascalTableName}}Request, 
    Update{{pascalTableName}}Request, 
    {{pascalTableName}}Response,
    Paged{{pascalTableName}}Response,
    {{pascalTableName}}ListItemResponse
)
from app.core.exceptions import BusinessException, NotFoundException

class {{pascalTableName}}Service:
    \"\"\"
    {{tableComment}}服务类
    \"\"\"
    def __init__(self, repository: {{pascalTableName}}Repository, logger: logging.Logger):
        self.repository = repository
        self.logger = logger

    async def get_{{snake_table_name}}_by_id_async(self, id: {{primaryKey.codeDataType}}) -> Optional[{{pascalTableName}}Response]:
        \"\"\"
        获取{{tableComment}}详情

        Args:
            id: {{tableComment}}ID

        Returns:
            {{tableComment}}详情
        \"\"\"
        self.logger.debug(f"Fetching {{snake_table_name}} with id: {id}")
        entity = await self.repository.get_by_id_async(id)
        if not entity:
            raise NotFoundException(f"{{tableComment}} with id {id} not found.")
        return {{pascalTableName}}Response.model_validate(entity) # Pydantic v2

    async def get_{{snake_table_name}}_list_async(self, page_index: int, page_size: int) -> Paged{{pascalTableName}}Response:
        \"\"\"
        获取{{tableComment}}分页列表

        Args:
            page_index: 页码
            page_size: 每页大小

        Returns:
            {{tableComment}}分页列表
        \"\"\"
        self.logger.debug(f"Fetching {{snake_table_name}} list, page: {page_index}, size: {page_size}")
        items, total_count = await self.repository.get_paginated_async(page_index, page_size)
        
        item_dtos = [{{pascalTableName}}ListItemResponse.model_validate(item) for item in items]
            
        return Paged{{pascalTableName}}Response(
            items=item_dtos,
            total_count=total_count,
            page_index=page_index,
            page_size=page_size,
            total_pages=math.ceil(total_count / page_size) if page_size > 0 and total_count > 0 else 0
        )

    async def create_{{snake_table_name}}_async(self, request: Create{{pascalTableName}}Request) -> {{pascalTableName}}Response:
        \"\"\"
        创建{{tableComment}}

        Args:
            request: 创建请求

        Returns:
            {{tableComment}}详情
        \"\"\"
        self.logger.info(f"Creating new {{snake_table_name}} with data: {request.model_dump_json(exclude_none=True)}")
        
        # Map DTO to Entity
        # entity = {{pascalTableName}}(**request.model_dump(exclude_unset=True)) # Pydantic v2
        entity_data = request.model_dump(exclude_unset=True)
        entity = {{pascalTableName}}()
        for key, value in entity_data.items():
            if hasattr(entity, key): # Make sure attribute exists on model
                 setattr(entity, key, value)
            
        # Add creation timestamp if model requires it (SQLAlchemy handles server_default)
        # entity.create_date = datetime.datetime.now()
        # entity.last_modify_date = datetime.datetime.now()
            
        created_entity = await self.repository.add_async(entity)
        self.logger.info(f"{{pascalTableName}} created with id: {created_entity.{{primaryKey.name}}}")
        return {{pascalTableName}}Response.model_validate(created_entity)

    async def update_{{snake_table_name}}_async(self, id: {{primaryKey.codeDataType}}, request: Update{{pascalTableName}}Request) -> {{pascalTableName}}Response:
        \"\"\"
        更新{{tableComment}}

        Args:
            id: {{tableComment}}ID
            request: 更新请求

        Returns:
            更新后的{{tableComment}}详情
        \"\"\"
        self.logger.info(f"Updating {{snake_table_name}} with id: {id}, data: {request.model_dump_json(exclude_none=True)}")
        existing_entity = await self.repository.get_by_id_async(id)
        if not existing_entity:
            raise NotFoundException(f"{{tableComment}} with id {id} not found for update.")
        
        update_data = request.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(existing_entity, key):
                setattr(existing_entity, key, value)
        
        # existing_entity.last_modify_date = datetime.datetime.now() # Repository might handle this if using explicit update statement
        
        await self.repository.update_async(existing_entity) # Assuming update_async correctly persists
        # Need to re-fetch or refresh to get DB-updated values like last_modify_date
        updated_entity = await self.repository.get_by_id_async(id)
        if not updated_entity: # Should not happen if update was successful
             raise BusinessException(f"Failed to retrieve {{tableComment}} with id {id} after update.")

        self.logger.info(f"{{pascalTableName}} with id: {id} updated.")
        return {{pascalTableName}}Response.model_validate(updated_entity)


    async def delete_{{snake_table_name}}_async(self, id: {{primaryKey.codeDataType}}) -> bool:
        \"\"\"
        删除{{tableComment}}

        Args:
            id: {{tableComment}}ID

        Returns:
            操作结果 (True if successful)
        \"\"\"
        self.logger.info(f"Deleting {{snake_table_name}} with id: {id}")
        existing_entity = await self.repository.get_by_id_async(id)
        if not existing_entity:
            # Depending on desired behavior, either raise NotFoundException or return False
            self.logger.warning(f"Attempted to delete non-existent {{tableComment}} with id: {id}")
            return False # Or raise NotFoundException
            
        deleted = await self.repository.delete_async(id)
        if deleted:
            self.logger.info(f"{{pascalTableName}} with id: {id} deleted successfully.")
        else:
            self.logger.warning(f"Failed to delete {{pascalTableName}} with id: {id}.")
        return deleted
"""

# Java Templates
_JAVA_ENTITY_TEMPLATE = """package {{package}}.entity;

import lombok.Data;
// import jakarta.persistence.*; // For Spring Boot 3+
import javax.persistence.*; // For Spring Boot 2
import java.io.Serializable;
import java.time.LocalDateTime; // Or java.util.Date

/**
 * {{tableComment}}实体
 */
@Data
@Entity
@Table(name = "{{tableName}}") // Raw table name from DB design
public class {{pascalTableName}} implements Serializable {

    private static final long serialVersionUID = 1L;

    {{#fields}}
    /**
     * {{comment}}
     */
    {{#isPrimaryKey}}
    @Id
    {{#isAutoIncrement}}
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    {{/isAutoIncrement}}
    {{/isPrimaryKey}}
    @Column(name = "{{name}}") // Raw column name from DB design
    private {{codeDataType}} {{camelName}};

    {{/fields}}
}"""
_JAVA_REPOSITORY_TEMPLATE = """package {{package}}.repository;

import {{package}}.entity.{{pascalTableName}};
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.stereotype.Repository;

/**
 * {{tableComment}}数据访问层
 */
@Repository
public interface {{pascalTableName}}Repository extends JpaRepository<{{pascalTableName}}, {{primaryKey.codeDataType}}>, JpaSpecificationExecutor<{{pascalTableName}}> {
    
}"""
_JAVA_DTO_TEMPLATE = """package {{package}}.dto;

import lombok.Data;
// import jakarta.validation.constraints.NotNull; // For Spring Boot 3+
import javax.validation.constraints.NotNull; // For Spring Boot 2
import java.io.Serializable;
import java.time.LocalDateTime; // Or java.util.Date
import java.util.List; // For paged results

/**
 * {{tableComment}}数据传输对象 (一般用于响应)
 */
@Data
public class {{pascalTableName}}DTO implements Serializable {
    private static final long serialVersionUID = 1L;

    {{#fields}}
    /**
     * {{comment}}
     */
    private {{codeDataType}} {{camelName}};
    {{/fields}}
}

/**
 * {{tableComment}}创建请求DTO
 */
@Data
public class Create{{pascalTableName}}DTO implements Serializable {
    private static final long serialVersionUID = 1L;

    {{#fields}}
    {{^isPrimaryKey}}
    {{^isAutoIncrement}}
    /**
     * {{comment}}
     */
    {{^isNullable}}
    @NotNull(message = "{{comment}}不能为空")
    {{/isNullable}}
    private {{codeDataType}} {{camelName}};
    {{/isAutoIncrement}}
    {{/isPrimaryKey}}
    {{/fields}}
}

/**
 * {{tableComment}}更新请求DTO
 */
@Data
public class Update{{pascalTableName}}DTO implements Serializable {
    private static final long serialVersionUID = 1L;

    {{#fields}}
    {{#isPrimaryKey}}
    /**
     * {{comment}}
     */
    @NotNull(message = "{{comment}} (ID)不能为空") // Usually ID is required for update
    private {{codeDataType}} {{camelName}};
    {{/isPrimaryKey}}
    {{^isPrimaryKey}}
    /**
     * {{comment}}
     */
    // Fields here are typically optional for partial updates, or @NotNull if all required
    private {{codeDataType}} {{camelName}};
    {{/isPrimaryKey}}
    {{/fields}}
}

/**
 * {{tableComment}}列表项DTO (可以和{{pascalTableName}}DTO一样，或更精简)
 */
@Data
public class {{pascalTableName}}ListItemDTO implements Serializable {
    private static final long serialVersionUID = 1L;

    {{#fields}}
    {{#isPrimaryKey}}
    /**
     * {{comment}}
     */
    private {{codeDataType}} {{camelName}};
    {{/isPrimaryKey}}
    {{/fields}}
    // Add other fields for list view, e.g., a name or title field
    // private String someDisplayField;
    
    /**
     * 创建时间
     */
    // private LocalDateTime createTime; // Assuming create_date exists in entity
}

/**
 * 分页结果 DTO
 */
@Data
public class PagedResultDTO<T> {
    private List<T> items;
    private long totalCount;
    private int pageIndex;
    private int pageSize;
    private int totalPages;
}
"""
_JAVA_SERVICE_INTERFACE_TEMPLATE = """package {{package}}.service;

import {{package}}.dto.{{pascalTableName}}DTO;
import {{package}}.dto.Create{{pascalTableName}}DTO;
import {{package}}.dto.Update{{pascalTableName}}DTO;
import {{package}}.dto.{{pascalTableName}}ListItemDTO;
import {{package}}.dto.PagedResultDTO; // Assuming common PagedResultDTO
import org.springframework.data.domain.Pageable; // For Spring Data pagination

/**
 * {{tableComment}}服务接口
 */
public interface {{pascalTableName}}Service {

    /**
     * 根据ID获取{{tableComment}}
     *
     * @param id ID
     * @return {{tableComment}}DTO
     */
    {{pascalTableName}}DTO findById({{primaryKey.codeDataType}} id);

    /**
     * 分页获取{{tableComment}}列表
     *
     * @param pageable 分页参数
     * @return {{tableComment}}分页列表
     */
    PagedResultDTO<{{pascalTableName}}ListItemDTO> findAll(Pageable pageable);

    /**
     * 创建{{tableComment}}
     *
     * @param dto 创建请求DTO
     * @return 创建后的{{tableComment}}DTO (通常返回带ID的完整对象)
     */
    {{pascalTableName}}DTO create(Create{{pascalTableName}}DTO dto);

    /**
     * 更新{{tableComment}}
     *
     * @param id 要更新的实体ID
     * @param dto 更新请求DTO
     * @return 更新后的{{tableComment}}DTO
     */
    {{pascalTableName}}DTO update({{primaryKey.codeDataType}} id, Update{{pascalTableName}}DTO dto);

    /**
     * 删除{{tableComment}}
     *
     * @param id ID
     */
    void delete({{primaryKey.codeDataType}} id);
}"""
_JAVA_SERVICE_IMPLEMENTATION_TEMPLATE = """package {{package}}.service.impl;

import {{package}}.dto.{{pascalTableName}}DTO;
import {{package}}.dto.Create{{pascalTableName}}DTO;
import {{package}}.dto.Update{{pascalTableName}}DTO;
import {{package}}.dto.{{pascalTableName}}ListItemDTO;
import {{package}}.dto.PagedResultDTO;
import {{package}}.entity.{{pascalTableName}};
import {{package}}.repository.{{pascalTableName}}Repository;
import {{package}}.service.{{pascalTableName}}Service;
import lombok.RequiredArgsConstructor; // Or use @Autowired constructor
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils; // For simple DTO-Entity mapping
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
// import jakarta.persistence.EntityNotFoundException; // For Spring Boot 3+
import javax.persistence.EntityNotFoundException; // For Spring Boot 2
import java.util.stream.Collectors;

/**
 * {{tableComment}}服务实现
 */
@Slf4j
@Service
@RequiredArgsConstructor // Lombok for constructor injection
@Transactional // Default transaction behavior for all public methods
public class {{pascalTableName}}ServiceImpl implements {{pascalTableName}}Service {

    private final {{pascalTableName}}Repository {{camelTableName}}Repository;
    // private final ModelMapper modelMapper; // Or use MapStruct for more complex mapping

    @Override
    @Transactional(readOnly = true)
    public {{pascalTableName}}DTO findById({{primaryKey.codeDataType}} id) {
        log.debug("Request to get {{pascalTableName}} by id : {}", id);
        return {{camelTableName}}Repository.findById(id)
                .map(this::convertToDto)
                .orElseThrow(() -> new EntityNotFoundException("{{tableComment}} not found with id: " + id));
    }

    @Override
    @Transactional(readOnly = true)
    public PagedResultDTO<{{pascalTableName}}ListItemDTO> findAll(Pageable pageable) {
        log.debug("Request to get all {{pascalTableName}}s by page: {}", pageable);
        Page<{{pascalTableName}}> page = {{camelTableName}}Repository.findAll(pageable);
        
        PagedResultDTO<{{pascalTableName}}ListItemDTO> pagedResult = new PagedResultDTO<>();
        pagedResult.setItems(page.getContent().stream().map(this::convertToListDto).collect(Collectors.toList()));
        pagedResult.setTotalCount(page.getTotalElements());
        pagedResult.setPageIndex(page.getNumber() + 1); // Pageable is 0-indexed
        pagedResult.setPageSize(page.getSize());
        pagedResult.setTotalPages(page.getTotalPages());
        return pagedResult;
    }

    @Override
    public {{pascalTableName}}DTO create(Create{{pascalTableName}}DTO dto) {
        log.debug("Request to create {{pascalTableName}} : {}", dto);
        {{pascalTableName}} entity = new {{pascalTableName}}();
        // Manual mapping or use a mapper
        BeanUtils.copyProperties(dto, entity); 
        // Set create/update dates if not handled by @PrePersist or DB
        // entity.setCreateDate(LocalDateTime.now());
        // entity.setLastModifyDate(LocalDateTime.now());
        entity = {{camelTableName}}Repository.save(entity);
        return convertToDto(entity);
    }

    @Override
    public {{pascalTableName}}DTO update({{primaryKey.codeDataType}} id, Update{{pascalTableName}}DTO dto) {
        log.debug("Request to update {{pascalTableName}} with id {}: {}", id, dto);
        {{pascalTableName}} entity = {{camelTableName}}Repository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("{{tableComment}} not found with id: " + id));
        
        // Manual mapping or use a mapper
        BeanUtils.copyProperties(dto, entity, "{{primaryKey.camelName}}"); // Exclude ID from copy
        // entity.setLastModifyDate(LocalDateTime.now());
        entity = {{camelTableName}}Repository.save(entity);
        return convertToDto(entity);
    }

    @Override
    public void delete({{primaryKey.codeDataType}} id) {
        log.debug("Request to delete {{pascalTableName}} by id : {}", id);
        if (!{{camelTableName}}Repository.existsById(id)) {
             throw new EntityNotFoundException("{{tableComment}} not found with id: " + id);
        }
        {{camelTableName}}Repository.deleteById(id);
    }

    // Helper methods for DTO conversion
    private {{pascalTableName}}DTO convertToDto({{pascalTableName}} entity) {
        {{pascalTableName}}DTO dto = new {{pascalTableName}}DTO();
        BeanUtils.copyProperties(entity, dto);
        return dto;
    }
    
    private {{pascalTableName}}ListItemDTO convertToListDto({{pascalTableName}} entity) {
        {{pascalTableName}}ListItemDTO listDto = new {{pascalTableName}}ListItemDTO();
        BeanUtils.copyProperties(entity, listDto); // Adjust if ListItemDTO has different fields
        // Example: if createTime is needed in DTO and create_date in entity
        // listDto.setCreateTime(entity.getCreateDate()); 
        return listDto;
    }
}"""