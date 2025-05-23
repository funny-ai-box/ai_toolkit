# app/api/main.py
import asyncio
import logging
from typing import Optional, Dict
from fastapi import FastAPI, Depends, Request, status
from contextlib import asynccontextmanager
import httpx
from app.core.config.settings import settings

# --- 配置日志记录 ---
from app.core.logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__) # 获取 main 模块的 logger
# ----------------------------------------------------
settings.DATABASE_ECHO = False
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

from app.core.database.session import engine, Base
from app.api.middleware.exception_handlers import register_exception_handlers
from app.core.redis.service import RedisService

# --- 导入自动发现函数 ---
from app.api.auto_router import discover_and_include_routers

# --- 导入需要在 lifespan 中实例化的服务 ---
from app.core.ai.vector.milvus_service import MilvusService
from app.core.ai.vector.user_docs_milvus_service import UserDocsMilvusService
from app.core.ai.chat.factory import get_chat_ai_service
from app.core.storage.factory import get_storage_service # Storage 使用工厂获取
from app.core.auth.jwt_service import JwtService # JWT 服务也需要 Redis
from app.core.ai.speech.factory import get_speech_service # 导入语音服务工厂


# --- 导入 APScheduler 启动/关闭函数 ---
from app.core.scheduler import start_scheduler, stop_scheduler

# --- 辅助函数：创建带代理的 httpx 客户端 ---
def create_proxied_http_client() -> Optional[httpx.AsyncClient]:
    """根据配置创建可能带特定域名代理的 httpx 客户端"""
    proxies: Optional[Dict[str, Optional[str]]] = None

    if settings.PROXY_ENABLED and settings.PROXY_URL:
        proxy_url_with_auth = settings.PROXY_URL
        # 处理认证
        if settings.PROXY_USERNAME and settings.PROXY_PASSWORD:
            try:
                parts = httpx.URL(settings.PROXY_URL)
                proxy_url_with_auth = str(parts.copy_with(username=settings.PROXY_USERNAME, password=settings.PROXY_PASSWORD))
                logger.info(f"代理认证信息已准备。")
            except Exception as e:
                 logger.error(f"解析代理 URL 或添加认证失败: {e}")
                 # 如果认证失败，可以选择不启用代理或使用无认证 URL
                 proxy_url_with_auth = settings.PROXY_URL # 回退

        if settings.PROXY_FORCE_DOMAINS:
            # --- 按域名配置代理 ---
            logger.info(f"为特定域名配置代理: {settings.PROXY_FORCE_DOMAINS}")
            mounts = {}
            # 为每个需要代理的域名添加规则 (同时匹配 http 和 https)
            for domain in settings.PROXY_FORCE_DOMAINS:
                domain = domain.strip()
                if domain:
                    # 同时挂载 http 和 https
                    mounts[f"http://{domain}"] = httpx.AsyncHTTPTransport(proxy=httpx.Proxy(url=proxy_url_with_auth))
                    mounts[f"https://{domain}"] = httpx.AsyncHTTPTransport(proxy=httpx.Proxy(url=proxy_url_with_auth))
                    # 注意：httpx v0.23+ 推荐使用 httpx.Proxy 对象
                    # 对于旧版本可能是直接传字符串:
                    # mounts[f"all://{domain}"] = proxy_url_with_auth # 匹配 http 和 https
            # 对于所有其他域名，不使用代理 (mounts 中未指定的默认不走代理)
            # 如果想让其他域名也走特定配置（比如不走代理），可以添加 'all://': None
            # 但 httpx 的默认行为就是不走代理，所以通常不需要显式设置 None
            # ----------------------
            timeout = httpx.Timeout(120.0, connect=30.0)
            # 使用 mounts 参数创建客户端
            return httpx.AsyncClient(mounts=mounts, timeout=timeout, follow_redirects=True)

        else:
            # --- 如果没有指定域名，则代理所有 HTTPS (之前的逻辑) ---
            logger.warning("PROXY_FORCE_DOMAINS 未配置或为空，将代理所有 HTTPS 请求。")
            proxies = {"https://": proxy_url_with_auth, "http://": proxy_url_with_auth} # 同时代理 http 和 https
            timeout = httpx.Timeout(120.0, connect=30.0)
            return httpx.AsyncClient(proxies=proxies, timeout=timeout, follow_redirects=True)
            # ----------------------------------------------------

    else:
         logger.info("未启用代理或未配置代理 URL。")
         # 返回不带代理的客户端
         return httpx.AsyncClient(timeout=60.0, follow_redirects=True)

# --- 应用生命周期事件 (使用 app.state) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 应用的生命周期管理"""
    logger.info("--- 应用启动 ---")

    # 1. 初始化核心服务并存入 app.state
    # Redis
    logger.info("初始化并存储 Redis Service...")
    redis_service_instance = RedisService()
    await redis_service_instance.initialize()
    app.state.redis_service = redis_service_instance
    logger.info("Redis Service 已存入 app.state")

    # JWT Service (依赖 Redis)
    logger.info("初始化并存储 JWT Service...")
    app.state.jwt_service = JwtService(settings=settings, redis_service=app.state.redis_service)

    # 创建并存储共享 HTTP 客户端
    logger.info("创建共享 HTTP 客户端(具备代理能力)...")
    app.state.http_client = create_proxied_http_client()
    if app.state.http_client: logger.info("共享 HTTP 客户端已创建并存入 app.state。")
    else: logger.warning("未能创建共享 HTTP 客户端。")

    # Milvus Base Service
    logger.info("初始化并存储 Milvus Service...")
    app.state.milvus_service = MilvusService()

    # User Docs Milvus Service (依赖 Milvus Base Service)
    logger.info("初始化并存储 User Docs Milvus Service...")
    user_docs_milvus_service_instance = UserDocsMilvusService(milvus_service=app.state.milvus_service)
    app.state.user_docs_milvus_service = user_docs_milvus_service_instance

    # 初始化用户文档集合
    try:
        # logger.info("正在确保 Milvus 连接和集合...")
        # await app.state.milvus_service.ensure_connection() # 确保首次连接（或让其在使用时连接）
        logger.info("正在确保 Milvus 用户文档集合存在...")
        success = await app.state.user_docs_milvus_service.ensure_collection_exists()
        if success: logger.info("Milvus 用户文档集合已准备就绪。")
        else: logger.warning("警告：Milvus 用户文档集合初始化失败。")
    except Exception as e: logger.error(f"启动时初始化 Milvus 失败")

    # AI Service
    try:
        logger.info("初始化并存储 AI Service...")
        chat_provider = settings.KB_CHAT_PROVIDER or "OpenAI"
        app.state.ai_services = get_chat_ai_service(chat_provider, app.state.http_client) # 传递 client
        # embedding如果要用特殊的，那么在具体的AIService里面去实现.
        # embed_provider = settings.KB_EMBEDDING_PROVIDER or chat_provider
        # app.state.ai_services = {} # 使用字典存储
        # app.state.ai_services[chat_provider] = get_chat_ai_service(chat_provider)
        # if embed_provider != chat_provider: app.state.ai_services[embed_provider] = get_chat_ai_service(embed_provider)
    except Exception as e: logger.error(f"初始化 AI Service 失败: {e}")

    # Storage Service (使用工厂)
    try:
        logger.info(f"初始化并存储 Storage Service (Provider: {settings.STORAGE_PROVIDER})...")
        app.state.storage_service = get_storage_service()
        if app.state.storage_service: logger.info("Storage Service 已存入 app.state")
        else: logger.info("未配置 Storage Service。")
    except Exception as e: logger.error(f"初始化 Storage Service 失败: {e}")

    try:
        logger.info("初始化并存储 Speech Service...")
        app.state.speech_service = get_speech_service()
        if app.state.speech_service: logger.info("Speech Service 已存入 app.state")
        else: logger.info("未配置 Speech Service。")
    except Exception as e: logger.error(f"初始化 Speech Service 失败: {e}")

    # 2. 启动 APScheduler
    start_scheduler() # <--- 调用启动函数

    yield # 应用运行

    logger.info("--- 应用关闭 ---")
    # 3. 关闭 APScheduler
    stop_scheduler() # <--- 调用关闭函数
    
    # 4. 关闭共享 HTTP 客户端
    if hasattr(app.state, 'http_client') and app.state.http_client:
        logger.info("正在关闭共享 HTTP 客户端...")
        await app.state.http_client.aclose()

    # 5. 关闭其他服务连接
    logger.info("正在关闭 Redis 连接...")
    if hasattr(app.state, 'redis_service') and app.state.redis_service:
        await app.state.redis_service.close()
    
    # 6. 关闭 Milvus 连接
    if hasattr(app.state, 'milvus_service') and app.state.milvus_service:
        try:
            from pymilvus import connections
            if settings.MILVUS_ALIAS in connections.list_connections():
                connections.disconnect(settings.MILVUS_ALIAS)
                logger.info(f"Milvus 连接 '{settings.MILVUS_ALIAS}' 已断开。")
        except Exception as e: logger.warning(f"关闭 Milvus 连接时出错: {e}")

    # 关闭数据库引擎
    logger.info("正在关闭数据库引擎...")
    await engine.dispose()
    
    logger.info("所有服务已关闭。")

# --- 创建 FastAPI 应用实例 ---
app = FastAPI(
    title="AI Toolkit API (Python)",
    description="AI 工具集后端 API (Python 版本)",
    version="1.0.0",
    lifespan=lifespan, # 注册生命周期事件
)

# --- 注册全局异常处理器 ---
register_exception_handlers(app)
logger.info("全局异常处理器已注册。")

# --- 自动发现并包含路由器 ---
# 指定包含模块路由器的基础目录
discover_and_include_routers(app, base_dir="app/modules")


# --- 根路由 ---
@app.get("/", tags=["Root"], include_in_schema=False) # 不在 Swagger 中显示根路径
async def read_root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs") # 重定向到 Swagger UI

# --- 用于本地运行的入口 (如果直接运行 main.py) ---
if __name__ == "__main__":
    import uvicorn    
    logger.info(f"启动 Uvicorn 服务器: http://{settings.API_HOST}:{settings.API_PORT}")
    uvicorn.run("app.api.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True, log_level=settings.LOG_LEVEL.lower())