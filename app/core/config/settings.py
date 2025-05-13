# app/core/config/settings.py
import os
from typing import List, Optional, Union, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, validator, Field

# 获取项目根目录
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
ENV_FILE_PATH = os.path.join(ROOT_DIR, ".env_dev")
print(f"加载 .env_dev 文件: {ENV_FILE_PATH}")
try:
    with open(ENV_FILE_PATH, 'r') as f:
        print(f"成功打开 ..env_dev 文件，内容前50个字符: {f.read(50)}...")
except Exception as e:
    print(f"无法打开 ..env_dev 文件: {e}")
class Settings(BaseSettings):
    """
    应用程序配置模型，使用 Pydantic-Settings 从 .env 文件和环境变量加载。
    """
    # --- 核心应用设置 ---
    ENVIRONMENT: str = "development" # 环境标识 (development, production, staging)
    API_HOST: str = "0.0.0.0"        # API 监听的主机
    API_PORT: int = 5740             # API 监听的端口
    LOG_LEVEL: str = "INFO"          # 日志级别
    SECRET_KEY: str                  # 用于 JWT 签名的密钥 (!!! 必须在 .env 中设置 !!!)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 访问令牌有效期 (分钟)

    # --- 数据库设置 ---
    DATABASE_URL: str                # 数据库连接字符串 (例如: "mysql+asyncmy://user:password@host:port/db_name?charset=utf8mb4")
    DATABASE_ECHO: bool = False      # 是否打印 SQLAlchemy 执行的 SQL 语句

    # --- Redis 设置 ---
    REDIS_URL: str                   # Redis 连接字符串 (例如: "redis://:password@host:port/0")

    # --- Scheduler Settings ---
    SCHEDULER_INTERVAL_SECONDS: int = Field(15, description="调度器扫描待处理任务的间隔（秒）")
    SCHEDULER_API_TIMEOUT: float = Field(120.0, description="调度器调用业务 API 的超时时间（秒）")
    SCHEDULER_FETCH_LIMIT: int = Field(10, description="调度器每次获取待处理任务数量")
    API_BASE_URL: str = Field("http://localhost:57460", description="业务 API 的基础 URL (调度器调用时使用)") # 重要！确保正确
    # INTERNAL_AUTH_TOKEN: Optional[str] = Field(None, description="用于调度器调用 API 的内部认证 Token (可选)")    
    JOB_MIGRATION_INTERVAL_MINUTES: int = Field(5, description="任务迁移到历史表间隔(分钟)") 
    # JOB_HISTORY_CLEANUP_INTERVAL_HOURS: int = Field(24, description="历史任务清理间隔(小时)") # 可选
    JOB_HISTORY_RETENTION_DAYS: int = Field(90, description="任务历史记录保留天数")
    JOB_MIGRATION_RETENTION_DAYS: int = Field(7, description="完成/失败任务在主表中保留天数（之后迁移）")

    # --- HTTP Proxy Settings ---
    PROXY_ENABLED: bool = Field(False, description="是否启用全局 HTTP/HTTPS 代理")
    PROXY_URL: Optional[str] = Field(None, description="代理服务器 URL (例如 http://localhost:7890 或 socks5://localhost:1080)")
    PROXY_USERNAME: Optional[str] = Field(None, description="代理用户名 (如果需要认证)")
    PROXY_PASSWORD: Optional[str] = Field(None, description="代理密码 (如果需要认证)")
    # 需要强制走代理的域名列表，如果为空则代理所有 https 请求
    PROXY_FORCE_DOMAINS: List[str] = Field(
        default_factory=lambda: ["api.openai.com"], # 默认只代理 OpenAI API
        description="强制通过代理访问的域名列表 (例如 ['api.openai.com', 'generativelanguage.googleapis.com'])"
    )
    
    # --- OpenAI 设置 ---
    OPENAI_API_KEY: str              # OpenAI API 密钥
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini" # OpenAI 聊天模型
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small" # OpenAI 嵌入模型
    OPENAI_MAX_TOKENS: int = 4096    # OpenAI 最大令牌数
    OPENAI_DIMENSION: int = 1536     # OpenAI 嵌入维度

    # --- 存储设置 ---
    STORAGE_PROVIDER: str = "Local"  # 存储提供者 (Local, AliyunOSS, AzureBlob)
    LOCAL_STORAGE_PATH: str = "uploads" # 本地存储路径
    LOCAL_STORAGE_BASE_URL: Optional[str] = None # 本地存储的基础 URL (用于生成可访问链接)

    # --- JWT 设置 ---
    JWT_ALGORITHM: str = "HS256"     # JWT 签名算法
    JWT_ISSUER: Optional[str] = None     # JWT 签发者 (可选)
    JWT_AUDIENCE: Optional[str] = None   # JWT 受众 (可选)

    # --- Snowflake 设置 ---
    SNOWFLAKE_WORKER_ID: int = 1     # Snowflake Worker ID
    SNOWFLAKE_DATACENTER_ID: int = 1 # Snowflake Datacenter ID

    # --- Rate Limit 设置 (示例) ---
    DEFAULT_RATE_LIMIT: str = "100/minute" # 默认速率限制

    # --- Milvus 设置 ---
    MILVUS_ALIAS: str = "default"
    MILVUS_HOST: str = "115.159.79.130"
    MILVUS_PORT: str = '19530'
    MILVUS_USER: Optional[str] = None
    MILVUS_PASSWORD: Optional[str] = None
    MILVUS_USE_SSL: bool = False
    MILVUS_SERVER_PEM_PATH: Optional[str] = None
    MILVUS_SERVER_NAME: Optional[str] = None
    MILVUS_CA_PEM_PATH: Optional[str] = None
    MILVUS_SECURE: bool = False # 用于控制 gRPC vs gRPCs

    # --- Knowledge Base 设置 (添加缺失的KB配置) ---
    KB_CHUNK_SIZE: int = Field(1000, alias="KNOWLEDGE_BASE_CHUNK_SIZE") # 使用 Field 和 alias
    KB_CHUNK_OVERLAP: int = Field(200, alias="KNOWLEDGE_BASE_CHUNK_OVERLAP")
    KB_SUPPORTED_EXTENSIONS: List[str] = Field(default=[".txt", ".html", ".htm", ".pdf", ".docx"], alias="KNOWLEDGE_BASE_SUPPORTED_FILE_EXTENSIONS")
    KB_CHAT_PROVIDER: str = Field("OpenAI", alias="KNOWLEDGE_BASE_DOCUMENT_PROCESSOR_CHAT_AI_PROVIDER_TYPE") # 用于 Graph
    KB_EMBEDDING_PROVIDER: Optional[str] = Field("OpenAI", alias="KNOWLEDGE_BASE_EMBEDDING_PROVIDER_TYPE") # (可选) 用于 Embedding
    # Milvus/Vector DB 配置
    KB_COLLECTION_NAME: str = Field("user_docs", alias="KNOWLEDGE_BASE_DOCUMENT_VECTOR_DATA_COLLECTION_NAME")
    KB_ID_FIELD: str = Field("vector_id", alias="KNOWLEDGE_BASE_DOCUMENT_VECTOR_DATA_ID_FIELD") # Milvus ID field
    KB_USER_ID_FIELD: str = Field("userId", alias="KNOWLEDGE_BASE_USER_ID_FIELD") # Milvus User ID field
    KB_APP_TYPE_FIELD: str = Field("appType", alias="KNOWLEDGE_BASE_DOCUMENT_VECTOR_DATA_APP_TYPE_FIELD")
    KB_DOC_ID_FIELD: str = Field("docId", alias="KNOWLEDGE_BASE_DOCUMENT_VECTOR_DATA_DOCUMENT_ID_FIELD")
    KB_CONTENT_FIELD: str = Field("content", alias="KNOWLEDGE_BASE_DOCUMENT_VECTOR_DATA_CONTENT_FIELD")
    KB_VECTOR_FIELD: str = Field("vector", alias="KNOWLEDGE_BASE_DOCUMENT_VECTOR_DATA_VECTOR_FIELD")
    KB_DIMENSION: int = Field(1536, alias="KNOWLEDGE_BASE_DOCUMENT_VECTOR_DATA_DIMENSION")
    KB_CONTENT_MAX_LENGTH: int = Field(65535, alias="KNOWLEDGE_BASE_CONTENT_MAX_LENGTH") # 增加默认值

    SOCIAL_CONTENT_SENSITIVE_CATEGORIES: str= Field(
        
        default="色情, 暴力, 恐怖主义, 赌博, 毒品, 诈骗, 违法犯罪, 其他",
        alias="SOCIAL_CONTENT_SENSITIVE_CATEGORIES"
    )
    SOCIAL_CONTENT_IMAGE_PATH_PREFIX: str = Field(
        default="socialcontent/images/", # 替换为实际的图片路径前缀
        alias="SOCIAL_CONTENT_IMAGE_PATH_PREFIX"
    )

    # --- Aliyun OSS 设置 ---
    ALIYUN_OSS_ACCESS_KEY_ID: Optional[str] = None
    ALIYUN_OSS_ACCESS_KEY_SECRET: Optional[str] = None
    ALIYUN_OSS_ENDPOINT: Optional[str] = None
    ALIYUN_OSS_BUCKET_NAME: Optional[str] = None
    ALIYUN_OSS_CDN_DOMAIN: Optional[str] = None
    ALIYUN_OSS_URL_EXPIRATION: int = 3600

    # --- Azure Blob Storage 设置 ---
    AZURE_STORAGE_CONNECTION_STRING: Optional[str] = None
    AZURE_STORAGE_CONTAINER_NAME: Optional[str] = None
    AZURE_STORAGE_CDN_DOMAIN: Optional[str] = None


    # --- 其他设置 ---
    SPEECH_SERVICE_TYPE: Optional[str] = None


    # Pydantic-Settings 配置
    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH, # 指定 .env 文件路径
        env_file_encoding='utf-8',
        case_sensitive=False, # 环境变量名不区分大小写
        extra='ignore',
              env_file_readonly=True      # 忽略 .env 文件中未在模型中定义的额外变量
    )
    print(f"加载配置模型: {model_config}")

    # 添加自定义验证器来处理所有值的注释
    @validator('*', pre=True)
    def strip_comments(cls, v):
        """从所有环境变量值中删除注释"""
        if isinstance(v, str) and '#' in v:
            return v.split('#')[0].strip()
        return v

    @validator("LOCAL_STORAGE_BASE_URL", pre=True, always=True)
    def set_local_storage_base_url(cls, v, values):
        """如果 LOCAL_STORAGE_BASE_URL 未设置，则根据 API_HOST/PORT 自动生成"""
        if v is None:
            host = values.get('API_HOST', 'localhost')
            if host == '0.0.0.0':
                host = 'localhost' # 在生成 URL 时使用 localhost 替代 0.0.0.0
            port = values.get('API_PORT', 8000)
            path = values.get('LOCAL_STORAGE_PATH', 'uploads').strip('/')
            # 注意: 实际生产中可能需要考虑 HTTPS
            return f"http://{host}:{port}/{path}"
        return v
    
    # 添加专门处理整数类型的环境变量
    @validator('ACCESS_TOKEN_EXPIRE_MINUTES', 'SNOWFLAKE_DATACENTER_ID', 'ALIYUN_OSS_URL_EXPIRATION', pre=True)
    def parse_integer_with_comments(cls, v):
        """处理整数类型的环境变量中的注释"""
        if isinstance(v, str) and '#' in v:
            return int(v.split('#')[0].strip())
        return v
    
    # 添加专门处理布尔类型的环境变量
    @validator('DATABASE_ECHO', 'PROXY_ENABLED', 'MILVUS_USE_SSL', 'MILVUS_SECURE', pre=True)
    def parse_boolean_with_comments(cls, v):
        """处理布尔类型的环境变量中的注释"""
        if isinstance(v, str) and '#' in v:
            value = v.split('#')[0].strip().lower()
            if value in ('true', 't', '1', 'yes', 'y'):
                return True
            elif value in ('false', 'f', '0', 'no', 'n'):
                return False
            raise ValueError(f"Cannot parse as boolean: {v}")
        return v


# 创建配置实例，方便在应用中导入和使用
settings = Settings()

# 打印全部配置信息
print("\n" + "="*80)
print(" 应用程序配置信息 ".center(80, "="))
print("="*80)

# 获取所有配置项
config_dict = settings.model_dump()
# 按键排序
sorted_keys = sorted(config_dict.keys())

for key in sorted_keys:
    value = config_dict[key]
    
    # 对于密钥和敏感信息，只显示前几个字符
    if any(sensitive in key.lower() for sensitive in ['secret', 'password', 'key']):
        if value and isinstance(value, str) and len(value) > 10:
            display_value = f"{value[:5]}...{value[-2:]}" if len(value) > 7 else "***"
        else:
            display_value = "***" if value else None
    else:
        display_value = value
        
    print(f"{key.ljust(35)}: {display_value}")

print("="*80 + "\n")

# 原有的简短配置打印
print(f"加载环境: {settings.ENVIRONMENT}")
print(f"数据库 URL: {settings.DATABASE_URL}")
print(f"Redis URL: {settings.REDIS_URL}")
print(f"本地存储 URL: {settings.LOCAL_STORAGE_BASE_URL}")
print(f"SECRET_KEY 长度: {len(settings.SECRET_KEY)}")
print(f"SECRET_KEY 前5位: {settings.SECRET_KEY[:5]}...")

# 打印 Milvus 配置
print(f"Milvus Host: {settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
print(f"KB Collection: {settings.KB_COLLECTION_NAME}")