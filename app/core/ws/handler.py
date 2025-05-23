# app/core/ws/handler.py
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Set, Tuple
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

class WebSocketConnection:
    """封装 WebSocket 连接及其元数据"""
    def __init__(self, websocket: WebSocket, user_id: int):
        self.websocket = websocket
        self.user_id = user_id
        self.connected_at = datetime.now(timezone.utc)
        self.last_active_at = self.connected_at

    async def send_text(self, message: str):
        """安全地发送文本消息"""
        try:
            await self.websocket.send_text(message)
            self.last_active_at = datetime.now(timezone.utc)
        except WebSocketDisconnect:
            logger.warning(f"尝试向已断开的 WebSocket (用户 {self.user_id}) 发送消息失败。")
        except Exception as e:
            logger.error(f"发送 WebSocket 消息给用户 {self.user_id} 时出错: {e}")

    async def receive_text(self) -> str:
        """接收文本消息，处理断开连接"""
        try:
            data = await self.websocket.receive_text()
            self.last_active_at = datetime.now(timezone.utc)
            return data
        except WebSocketDisconnect:
            logger.info(f"WebSocket 连接 (用户 {self.user_id}) 主动断开。")
            raise # 重新抛出，让上层处理断开逻辑
        except Exception as e:
            logger.error(f"接收 WebSocket 消息 (用户 {self.user_id}) 时出错: {e}")
            # 也可以选择在这里抛出 WebSocketDisconnect
            raise WebSocketDisconnect(code=1011, reason="接收错误")


class WebSocketHandler:
    """
    管理 WebSocket 连接和消息处理。
    """
    def __init__(self):
        # 使用字典存储活跃连接，键为 user_id，值为 WebSocketConnection 对象
        # 注意：一个用户可能建立多个连接，这里简化为只允许一个？
        # 如果允许多个，key 可以是 websocket 对象本身或生成唯一 ID
        # 或者 value 是一个 WebSocketConnection 列表
        # 暂时简化为 user_id -> WebSocketConnection (覆盖旧连接)
        self.active_connections: Dict[int, WebSocketConnection] = {}
        self._lock = asyncio.Lock() # 用于保护 active_connections 的并发访问

    async def connect(self, websocket: WebSocket, user_id: int):
        """接受新的 WebSocket 连接"""
        await websocket.accept()
        connection = WebSocketConnection(websocket, user_id)
        async with self._lock:
            # 如果用户已有连接，先断开旧的？或者允许？取决于业务需求
            if user_id in self.active_connections:
                logger.warning(f"用户 {user_id} 已存在 WebSocket 连接，将断开旧连接。")
                old_connection = self.active_connections[user_id]
                # 尝试礼貌地关闭旧连接
                try:
                    await old_connection.websocket.close(code=1008, reason="新的连接已建立")
                except Exception:
                    pass # 忽略关闭旧连接时的错误
            self.active_connections[user_id] = connection
        logger.info(f"WebSocket 连接已接受: 用户 {user_id}，来自 {websocket.client.host}:{websocket.client.port}")

    async def disconnect(self, user_id: int, websocket: WebSocket):
        """断开指定用户的 WebSocket 连接"""
        async with self._lock:
            # 检查存储的连接是否是当前要断开的连接
            if user_id in self.active_connections and self.active_connections[user_id].websocket == websocket:
                del self.active_connections[user_id]
                logger.info(f"WebSocket 连接已移除: 用户 {user_id}")
            else:
                # 可能是在 connect 时旧连接被替换，或者 disconnect 被重复调用
                 logger.debug(f"尝试移除用户 {user_id} 的 WebSocket 连接，但未找到或不匹配。")
        # 尝试关闭连接，忽略错误
        try:
            # await websocket.close() # 通常 WebSocketDisconnect 异常发生时连接已关闭
            pass
        except Exception:
            pass

    async def broadcast(self, message: str):
        """向所有连接的客户端广播消息 (如果需要)"""
        # 创建副本以防在迭代时字典被修改
        async with self._lock:
            connections_to_send = list(self.active_connections.values())

        if connections_to_send:
            logger.info(f"正在向 {len(connections_to_send)} 个客户端广播消息: {message[:50]}...")
            # 并发发送消息
            results = await asyncio.gather(
                *[conn.send_text(message) for conn in connections_to_send],
                return_exceptions=True # 捕获发送错误，而不是让一个失败中断所有
            )
            # 检查发送结果中的异常
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                     conn = connections_to_send[i]
                     logger.error(f"广播消息给用户 {conn.user_id} 时失败: {result}")


    async def send_personal_message(self, user_id: int, message: str) -> bool:
        """向指定用户发送私信"""
        async with self._lock:
            connection = self.active_connections.get(user_id)

        if connection:
            logger.info(f"正在向用户 {user_id} 发送消息: {message[:50]}...")
            await connection.send_text(message)
            return True
        else:
            logger.warning(f"尝试向用户 {user_id} 发送消息，但未找到活动连接。")
            return False

    async def handle_websocket_async(self, websocket: WebSocket, user_id: int):
        """处理单个 WebSocket 连接的生命周期"""
        await self.connect(websocket, user_id)
        connection = self.active_connections.get(user_id) # 获取刚刚创建的连接对象

        if not connection: # 理论上不会发生，除非并发问题
             logger.error(f"未能获取用户 {user_id} 的 WebSocketConnection 对象。")
             return

        try:
            while True:
                # 等待接收消息
                data = await connection.receive_text()
                logger.info(f"收到来自用户 {user_id} 的消息: {data[:100]}")

                # --- 在这里处理收到的消息 ---
                # 例如，将消息转发给 AI 服务，然后将 AI 的回复发送回客户端
                # ai_response = await process_message_with_ai(user_id, data)
                # await self.send_personal_message(user_id, ai_response)

                # 示例：简单的 echo 回复
                await connection.send_text(f"服务器收到: {data}")
                # ---------------------------

        except WebSocketDisconnect:
            # 客户端断开连接
            logger.info(f"WebSocket 连接 (用户 {user_id}) 检测到断开。")
            await self.disconnect(user_id, websocket)
        except Exception as e:
            # 发生其他错误
            logger.error(f"处理 WebSocket 连接 (用户 {user_id}) 时发生异常: {e}")
            await self.disconnect(user_id, websocket)
            # 可以尝试发送错误信息给客户端，如果连接还允许的话
            # try:
            #     await websocket.close(code=1011, reason="服务器内部错误")
            # except: pass

    async def cleanup_expired_connections_async(self, timeout_minutes: int = 30) -> int:
        """定期清理长时间不活动的连接"""
        async with self._lock:
            now = datetime.now(timezone.utc)
            expired_user_ids: Set[int] = set()
            connections_to_check = list(self.active_connections.items()) # 创建副本

            for user_id, connection in connections_to_check:
                if now - connection.last_active_at > timedelta(minutes=timeout_minutes):
                    expired_user_ids.add(user_id)
                    logger.info(f"检测到用户 {user_id} 的 WebSocket 连接超时 (最后活动于 {connection.last_active_at})，准备关闭。")
                    # 尝试关闭连接
                    try:
                        await connection.websocket.close(code=1000, reason="连接超时")
                    except Exception:
                        logger.debug(f"关闭超时的 WebSocket 连接 (用户 {user_id}) 时出错，将直接移除。")

            # 从字典中移除已标记的连接
            cleaned_count = 0
            for user_id in expired_user_ids:
                if user_id in self.active_connections:
                     del self.active_connections[user_id]
                     cleaned_count += 1

            if cleaned_count > 0:
                logger.info(f"成功清理了 {cleaned_count} 个过期的 WebSocket 连接。")
            return cleaned_count