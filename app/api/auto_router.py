# app/api/auto_router.py
import os
import importlib
import logging
from fastapi import FastAPI, APIRouter
from pathlib import Path

logger = logging.getLogger(__name__)

def discover_and_include_routers(app: FastAPI, base_dir: str = "app/modules"):
    """
    自动发现并包含指定目录下各模块的 API 路由器。

    Args:
        app (FastAPI): FastAPI 应用实例。
        base_dir (str): 包含模块的根目录路径 (相对于项目根目录)。
    """
    print(f"开始自动发现路由器，基础目录: '{base_dir}'")
    modules_path = Path(base_dir)
    if not modules_path.is_dir():
        print(f"自动发现路由器的基础目录 '{base_dir}' 不存在或不是目录。")
        return

    # 遍历 base_dir 下的所有直接子目录 (假设每个子目录是一个模块组，如 'base')
    for group_dir in modules_path.iterdir():
        if group_dir.is_dir() and (group_dir / '__init__.py').exists():
            # 遍历模块组下的所有模块目录
            for module_dir in group_dir.iterdir():
                 print(f"检查模块目录: '{module_dir}'")
                 # 检查是否是包含 __init__.py 和 router.py 的有效模块目录
                 if module_dir.is_dir() and \
                    (module_dir / '__init__.py').exists() and \
                    (module_dir / 'router.py').exists():

                    module_name = module_dir.name
                    router_module_path = f"{base_dir.replace('/', '.')}.{group_dir.name}.{module_name}.router"

                    try:
                        # 动态导入 router 模块
                        router_module = importlib.import_module(router_module_path)

                        # 检查模块中是否有名为 'router' 的 APIRouter 实例
                        if hasattr(router_module, 'router') and isinstance(getattr(router_module, 'router'), APIRouter):
                            module_router: APIRouter = getattr(router_module, 'router')

                            # 确定 API 的前缀 (可以在 router.py 中定义，或在这里统一设置)
                            # 如果 router.py 中定义了 prefix，则使用它
                            # 如果 router.py 没有定义 prefix，可以在这里根据模块名设置
                            api_prefix = module_router.prefix or f"/{module_name}" # 默认为模块名

                            # 包含路由器到主应用，统一添加 /api 前缀
                            app.include_router(
                                module_router,
                                prefix=f"/api",
                                # prefix=f"/api{api_prefix}", # 确保前缀是 /api/module_name
                                # tags 可以从 router 定义中获取，或在这里设置
                                # tags=[module_router.tags[0]] if module_router.tags else [module_name.capitalize()]
                            )
                            print(f"已自动包含路由器: '{router_module_path}' -> Prefix: '/api{api_prefix}'")
                        else:
                            print(f"在模块 '{router_module_path}' 中未找到名为 'router' 的 APIRouter 实例。")

                    except ImportError as e:
                        logger.error(f"导入路由器模块 '{router_module_path}' 失败: {e}", exc_info=True)
                    except Exception as e:
                        logger.error(f"包含路由器 '{router_module_path}' 时发生未知错误: {e}", exc_info=True)
                 elif module_dir.is_dir() and (module_dir / 'router.py').exists():
                      print(f"目录 '{module_dir}' 包含 router.py 但缺少 __init__.py，无法作为模块导入。")


    print("路由器自动发现完成。")