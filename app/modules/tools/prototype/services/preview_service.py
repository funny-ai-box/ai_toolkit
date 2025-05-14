# app/modules/tools/prototype/services/preview_service.py
import re
from typing import List, Optional
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, BusinessException, ForbiddenException
from app.modules.tools.prototype.dtos import AppPreviewDto, PageDetailDto, ResourceDto
from app.modules.tools.prototype.models import PrototypePage, PrototypeSession
from app.modules.tools.prototype.repositories import (
    PrototypeSessionRepository, PrototypePageRepository, PrototypeResourceRepository
)


class PrototypePreviewService:
    """原型预览服务实现"""
    
    # 优化后的页面渲染器基本框架
    _html_template_for_spa = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{0}</title>
  <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/animate.css@4.1.1/animate.min.css" rel="stylesheet">
  <style>
    /* 全局动画效果 */
    .transition-all {{ transition: all 0.3s ease; }}
    
    /* 自定义样式 */
    {1}
  </style>
</head>
<body class="min-h-screen bg-gray-50">
  <!-- 页面内容将被动态加载到这里 -->
  <div id="app">
    {2}
  </div>

  <script>    
 document.addEventListener('DOMContentLoaded', () => {{
    const fallback =
      'https://images.unsplash.com/photo-1503023345310-bd7c1de61c7d?auto=format&fit=crop&w=800&q=80';
    document.querySelectorAll('img[data-fallback="true"]').forEach((img) => {{
      img.addEventListener('error', () => {{
        img.src = fallback;
      }});
    }});
  }});
  </script>
</body>
</html>"""

    # 多页面模式的HTML模板
    _html_template_for_multi_page = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{0}</title>
  <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/animate.css@4.1.1/animate.min.css" rel="stylesheet">
  <style>
    /* 全局动画效果 */
    .transition-all {{ transition: all 0.3s ease; }}
    
    /* 自定义样式 */
    {1}
  </style>
</head>
<body class="min-h-screen bg-gray-50">
  {2}
  
  <script>     
 document.addEventListener('DOMContentLoaded', () => {{
    const fallback =
      'https://images.unsplash.com/photo-1503023345310-bd7c1de61c7d?auto=format&fit=crop&w=800&q=80';
    document.querySelectorAll('img[data-fallback="true"]').forEach((img) => {{
      img.addEventListener('error', () => {{
        img.src = fallback;
      }});
    }});
  }});
  </script>
</body>
</html>"""
    
    def __init__(
        self,
        db: AsyncSession,
        session_repository: PrototypeSessionRepository,
        page_repository: PrototypePageRepository,
        resource_repository: PrototypeResourceRepository,
        logger: Optional[logging.Logger] = None
    ):
        """
        初始化
        
        Args:
            db: 数据库会话
            session_repository: 会话仓储
            page_repository: 页面仓储
            resource_repository: 资源仓储
            logger: 日志记录器
        """
        self.db = db
        self.session_repository = session_repository
        self.page_repository = page_repository
        self.resource_repository = resource_repository
        self.logger = logger or logging.getLogger(__name__)
    
    async def get_app_preview_async(self, user_id: int, session_id: int) -> AppPreviewDto:
        """
        获取应用预览
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            
        Returns:
            应用预览
        """
        # 检查用户权限
        session = await self.session_repository.get_by_id_async(session_id)
        if session is None or session.user_id != user_id:
            raise ForbiddenException("无权访问该会话")
        
        # 获取所有页面
        pages = await self.page_repository.get_by_session_id_async(session_id)
        
        # 如果没有页面，返回空预览
        if not pages:
            raise BusinessException("该会话没有可预览的页面")
        
        # 获取所有资源
        resources = await self.resource_repository.get_by_session_id_async(session_id)
        
        # 构建预览对象
        preview = AppPreviewDto(
            session_id=session_id,
            name=session.name,
            pages=[
                PageDetailDto(
                    id=p.id,
                    session_id=p.session_id,
                    name=p.name,
                    path=p.path,
                    description=p.description,
                    content=p.content,
                    status=p.status,
                    status_description=self._get_page_status_description(p.status),
                    error_message=p.error_message,
                    order=p.order,
                    version=p.version,
                    create_date=p.create_date,
                    last_modify_date=p.last_modify_date
                )
                for p in pages
            ],
            resources=[
                ResourceDto(
                    id=r.id,
                    session_id=r.session_id,
                    name=r.name,
                    resource_type=r.resource_type,
                    url=r.url,
                    content=r.content,
                    create_date=r.create_date
                )
                for r in resources
            ]
        )
        
        # 设置入口URL
        home_page = next((p for p in pages if p.path.endswith("index.html") or p.path.endswith("/")), None)
        if home_page is None:
            home_page = min(pages, key=lambda p: p.order) if pages else None
        
        if home_page:
            preview.entry_url = f"/api/prototype/preview/{session_id}{home_page.path}"
        
        return preview
    
    async def get_page_html_async(self, session_id: int, path: str) -> str:
        """
        获取页面HTML内容
        
        Args:
            session_id: 会话ID
            path: 页面路径
            
        Returns:
            完整HTML内容
        """
        # 检查会话是否存在
        session = await self.session_repository.get_by_id_async(session_id)
        if session is None:
            raise NotFoundException("会话不存在")
        
        # 标准化路径
        if not path.startswith("/"):
            path = "/" + path
        
        # 获取页面
        page = await self.page_repository.get_by_path_async(session_id, path)
        if page is None:
            raise NotFoundException(f"页面不存在: {path}")
        
        # 获取页面内容
        if not page.content:
            raise BusinessException(f"页面内容为空: {path}")
        
        # 获取所有页面以构建导航
        all_pages = await self.page_repository.get_by_session_id_async(session_id)
        
        # 检查是否应用SPA模式或多页面模式
        is_spa_mode = self._is_spa_application(session, all_pages)
        
        # 提取自定义样式
        custom_css = self._extract_custom_styles(page.content)
        
        # 根据模式生成完整HTML
        if is_spa_mode:
            return self._generate_spa_html(session.name or "原型应用", custom_css, page.content, all_pages, session_id)
        else:
            return self._generate_multi_page_html(page.name or path, custom_css, page.content, all_pages, session_id)
    
    def _is_spa_application(self, session: PrototypeSession, pages: List[PrototypePage]) -> bool:
        """
        判断是否应使用SPA模式
        
        Args:
            session: 会话
            pages: 所有页面
            
        Returns:
            是否SPA模式
        """
        # 从需求中判断
        if session.requirements:
            requirements = session.requirements.lower()
            if "spa" in requirements or "single page application" in requirements or "单页应用" in requirements:
                return True
        
        # 检查页面内容是否含有SPA特征
        for page in pages:
            if page.content:
                if (
                    'data-spa="true"' in page.content
                    or 'id="spa-app"' in page.content
                    or 'class="spa-' in page.content
                ):
                    return True
        
        # 如果页面少于3个，默认使用SPA模式
        if len(pages) <= 3:
            return True
        
        return False
    
    def _extract_custom_styles(self, content: str) -> str:
        """
        提取自定义样式
        
        Args:
            content: 页面内容
            
        Returns:
            CSS样式内容
        """
        # 提取<style>标签中的内容
        style_pattern = r"<style[^>]*>([\s\S]*?)<\/style>"
        style_matches = re.finditer(style_pattern, content)
        
        custom_css = []
        for match in style_matches:
            if len(match.groups()) > 0:
                custom_css.append(match.group(1).strip())
        
        return "\n".join(custom_css)
    
    def _generate_spa_html(
        self, title: str, custom_css: str, content: str, all_pages: List[PrototypePage], session_id: int
    ) -> str:
        """
        生成SPA模式的HTML
        
        Args:
            title: 标题
            custom_css: 自定义CSS
            content: 页面内容
            all_pages: 所有页面
            session_id: 会话ID
            
        Returns:
            完整HTML
        """
        # 从内容中移除<style>标签
        clean_content = re.sub(r"<style[^>]*>[\s\S]*?<\/style>", "", content)
        
        # 处理内容中的相对链接，添加sessionId
        clean_content = self._process_links(clean_content, session_id)
        
        # 填充模板
        return self._html_template_for_spa.format(title, custom_css, clean_content)
    
    def _generate_multi_page_html(
        self, title: str, custom_css: str, content: str, all_pages: List[PrototypePage], session_id: int
    ) -> str:
        """
        生成多页面模式的HTML
        
        Args:
            title: 标题
            custom_css: 自定义CSS
            content: 页面内容
            all_pages: 所有页面
            session_id: 会话ID
            
        Returns:
            完整HTML
        """
        # 从内容中移除<style>标签
        clean_content = re.sub(r"<style[^>]*>[\s\S]*?<\/style>", "", content)
        
        # 处理内容中的相对链接，添加sessionId
        clean_content = self._process_links(clean_content, session_id)
        
        # 填充模板
        return self._html_template_for_multi_page.format(title, custom_css, clean_content)
    
    def _process_links(self, html: str, session_id: int) -> str:
        """
        处理HTML中的链接，添加sessionId参数
        这里简化实现，只返回原始内容
        
        Args:
            html: HTML内容
            session_id: 会话ID
            
        Returns:
            处理后的HTML
        """
        return html
    
    def _get_page_status_description(self, status: int) -> str:
        """
        获取页面状态描述
        
        Args:
            status: 状态
            
        Returns:
            状态描述
        """
        status_descriptions = {
            0: "待生成",
            1: "生成中",
            2: "已生成",
            3: "生成失败",
            4: "已修改"
        }
        return status_descriptions.get(status, "未知状态")