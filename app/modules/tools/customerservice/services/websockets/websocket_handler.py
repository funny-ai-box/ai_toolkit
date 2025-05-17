"""
WebSocket连接管理
"""
import logging
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

import json
from app.modules.tools.customerservice.services.iface.chat_service import IChatService
from app.modules.tools.customerservice.services.dtos.chat_dto import ChatMessageRequestDto

class WebSocketConnection:
    """WebSocket连接"""
    
    def __init__(self, websocket: WebSocket, connection_id: str, user_id: int):
        """
        初始化WebSocket连接
        
        Args:
            websocket: WebSocket实例
            connection_id: 连接ID
            user_id: 用户ID
        """
        self.websocket = websocket
        self.connection_id = connection_id
        self.user_id = user_id
        self.current_session_id: Optional[int] = None
        self.last_activity_time = datetime.now()


class WebSocketMessage:
    """WebSocket消息"""
    
    def __init__(self, type_: str, data: Any = None):
        """
        初始化WebSocket消息
        
        Args:
            type_: 消息类型
            data: 消息数据
        """
        self.type = type_
        self.data = data


class WebSocketHandler:
    """WebSocket消息处理器"""
    
    def __init__(self, chat_service: IChatService):
        """
        初始化WebSocket处理器
        
        Args:
            chat_service: 聊天服务
        """
        self.chat_service = chat_service
        self.connections: Dict[str, WebSocketConnection] = {}
        self.session_connections: Dict[int, List[str]] = {}
        self.logger = logging.getLogger(__name__)
    
    async def handle_connection(self, websocket: WebSocket, user_id: int) -> None:
        """
        处理WebSocket连接
        
        Args:
            websocket: WebSocket实例
            user_id: 用户ID
        """
        connection_id = f"{user_id}_{datetime.now().timestamp()}"
        connection = WebSocketConnection(websocket, connection_id, user_id)
        
        # 接受连接
        await websocket.accept()
        
        # 添加到连接集合
        self.connections[connection_id] = connection
        
        self.logger.info(f"WebSocket连接已建立, ConnectionId: {connection_id}, UserId: {user_id}")
        
        try:
            # 发送连接成功消息
            await self._send_message(connection_id, WebSocketMessage(
                "connected",
                {"connectionId": connection_id}
            ))
            
            # 处理消息
            await self._process_messages(connection_id)
        except WebSocketDisconnect:
            self.logger.info(f"WebSocket连接已断开, ConnectionId: {connection_id}")
        except Exception as ex:
            print(f"WebSocket连接出错, ConnectionId: {connection_id}, 错误: {str(ex)}")
        finally:
            # 关闭连接
            await self._disconnect(connection_id)
    
    async def _process_messages(self, connection_id: str) -> None:
        """
        处理接收到的消息
        
        Args:
            connection_id: 连接ID
        """
        connection = self.connections.get(connection_id)
        if not connection:
            return
        
        while True:
            try:
                # 接收消息
                data = await connection.websocket.receive_text()
                
                # 更新活动时间
                connection.last_activity_time = datetime.now()
                
                # 解析消息
                ws_message = json.loads(data)
                if not ws_message or "type" not in ws_message:
                    await self._send_error(connection_id, "无效的消息格式")
                    continue
                
                # 处理不同类型的消息
                message_type = ws_message.get("type")
                message_data = ws_message.get("data")
                
                if message_type == "join":
                    await self._handle_join_session(connection_id, message_data)
                elif message_type == "leave":
                    await self._handle_leave_session(connection_id, message_data)
                elif message_type == "message":
                    await self._handle_chat_message(connection_id, message_data)
                elif message_type == "ping":
                    await self._send_message(connection_id, WebSocketMessage("pong"))
                else:
                    await self._send_error(connection_id, f"未知的消息类型: {message_type}")
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await self._send_error(connection_id, "无法解析消息内容")
            except Exception as ex:
                print(f"处理WebSocket消息时发生错误: {str(ex)}")
                await self._send_error(connection_id, "处理消息时发生错误")
    
    async def _handle_join_session(self, connection_id: str, data: Any) -> None:
        """
        处理加入会话请求
        
        Args:
            connection_id: 连接ID
            data: 请求数据
        """
        connection = self.connections.get(connection_id)
        if not connection:
            return
        
        try:
            session_id = int(data.get("sessionId"))
            
            # 记录连接关联的会话
            connection.current_session_id = session_id
            
            # 添加到会话连接列表
            if session_id not in self.session_connections:
                self.session_connections[session_id] = []
            
            if connection_id not in self.session_connections[session_id]:
                self.session_connections[session_id].append(connection_id)
            
            # 使用ChatService记录连接
            await self.chat_service.establish_connection_async(
                session_id,
                connection_id,
                "WebSocket"
            )
            
            # 通知客户端已成功加入会话
            await self._send_message(connection_id, WebSocketMessage(
                "joined",
                {"sessionId": session_id}
            ))
            
            self.logger.info(f"连接 {connection_id} 加入会话 {session_id}")
        except (ValueError, TypeError, KeyError):
            await self._send_error(connection_id, "无效的会话ID")
        except Exception as ex:
            print(f"处理加入会话请求时发生错误: {str(ex)}")
            await self._send_error(connection_id, "处理加入会话请求时发生错误")
    
    async def _handle_leave_session(self, connection_id: str, data: Any) -> None:
        """
        处理离开会话请求
        
        Args:
            connection_id: 连接ID
            data: 请求数据
        """
        connection = self.connections.get(connection_id)
        if not connection or not connection.current_session_id:
            return
        
        try:
            session_id = connection.current_session_id
            
            # 从会话连接列表移除
            if session_id in self.session_connections and connection_id in self.session_connections[session_id]:
                self.session_connections[session_id].remove(connection_id)
                
                if not self.session_connections[session_id]:
                    self.session_connections.pop(session_id)
            
            # 使用ChatService关闭连接
            await self.chat_service.close_connection_async(connection_id)
            
            # 清除连接关联的会话
            connection.current_session_id = None
            
            # 通知客户端已成功离开会话
            await self._send_message(connection_id, WebSocketMessage(
                "left",
                {"sessionId": session_id}
            ))
            
            self.logger.info(f"连接 {connection_id} 离开会话 {session_id}")
        except Exception as ex:
            print(f"处理离开会话请求时发生错误: {str(ex)}")
            await self._send_error(connection_id, "处理离开会话请求时发生错误")
    
    async def _handle_chat_message(self, connection_id: str, data: Any) -> None:
        """
        处理聊天消息
        
        Args:
            connection_id: 连接ID
            data: 消息数据
        """
        connection = self.connections.get(connection_id)
        if not connection or not connection.current_session_id:
            await self._send_error(connection_id, "未加入任何会话，无法发送消息")
            return
        
        try:
            content = data.get("content")
            if not content:
                await self._send_error(connection_id, "消息内容不能为空")
                return
            
            # 构建消息请求
            request = ChatMessageRequestDto(
                session_id=connection.current_session_id,
                content=content
            )
            
            # 发送消息
            result = await self.chat_service.send_message_async(connection.user_id, request)
            
            # 如果发送成功，广播回复给所有会话连接
            if result.success:
                # 广播用户消息
                await self._broadcast_to_session(
                    connection.current_session_id,
                    WebSocketMessage(
                        "message",
                        {
                            "content": content,
                            "role": "user",
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                )
                
                # 广播AI回复
                await self._broadcast_to_session(
                    connection.current_session_id,
                    WebSocketMessage(
                        "reply",
                        {
                            "messageId": result.message_id,
                            "content": result.reply,
                            "role": "assistant",
                            "timestamp": datetime.now().isoformat(),
                            "intent": result.intent,
                            "callDatas": result.call_datas
                        }
                    )
                )
            else:
                # 发送失败，通知发送者
                await self._send_error(connection_id, result.error_message or "发送消息失败")
        except Exception as ex:
            print(f"处理聊天消息时发生错误: {str(ex)}")
            await self._send_error(connection_id, "处理聊天消息时发生错误")
    
    async def _send_message(self, connection_id: str, message: WebSocketMessage) -> None:
        """
        向特定连接发送消息
        
        Args:
            connection_id: 连接ID
            message: 消息对象
        """
        connection = self.connections.get(connection_id)
        if not connection or connection.websocket.client_state.name != "CONNECTED":
            return
        
        try:
            # 序列化消息
            message_json = json.dumps({
    "type": message.type,
    "data": message.data
})
            
            # 发送消息
            await connection.websocket.send_text(message_json)
        except Exception as ex:
            print(f"发送消息失败, ConnectionId: {connection_id}, 错误: {str(ex)}")
            # 出错时尝试断开连接
            await self._disconnect(connection_id)
    
    async def _send_error(self, connection_id: str, error_message: str) -> None:
        """
        发送错误消息
        
        Args:
            connection_id: 连接ID
            error_message: 错误消息
        """
        await self._send_message(
            connection_id,
            WebSocketMessage("error", {"message": error_message})
        )
    
    async def _broadcast_to_session(self, session_id: int, message: WebSocketMessage) -> None:
        """
        向会话中的所有连接广播消息
        
        Args:
            session_id: 会话ID
            message: 消息对象
        """
        if session_id not in self.session_connections:
            return
        
        tasks = []
        for conn_id in self.session_connections[session_id]:
            tasks.append(self._send_message(conn_id, message))
        
        if tasks:
            await asyncio.gather(*tasks)
    
    async def _disconnect(self, connection_id: str) -> None:
        """
        断开连接
        
        Args:
            connection_id: 连接ID
        """
        connection = self.connections.pop(connection_id, None)
        if not connection:
            return
        
        try:
            # 如果连接关联了会话，从会话连接列表中移除
            if connection.current_session_id:
                session_id = connection.current_session_id
                
                if session_id in self.session_connections and connection_id in self.session_connections[session_id]:
                    self.session_connections[session_id].remove(connection_id)
                    
                    if not self.session_connections[session_id]:
                        self.session_connections.pop(session_id)
                
                # 使用ChatService关闭连接
                await self.chat_service.close_connection_async(connection_id)
            
            # 如果连接仍处于打开状态，则尝试关闭
            if connection.websocket.client_state.name == "CONNECTED":
                await connection.websocket.close()
            
            self.logger.info(f"WebSocket连接已断开, ConnectionId: {connection_id}")
        except Exception as ex:
            print(f"关闭WebSocket连接失败, ConnectionId: {connection_id}, 错误: {str(ex)}")
    
    async def cleanup_expired_connections(self, timeout_minutes: int = 30) -> int:
        """
        清理过期连接
        
        Args:
            timeout_minutes: 超时时间（分钟）
            
        Returns:
            清理的连接数
        """
        now = datetime.now()
        expired_connections = []
        
        for connection_id, connection in list(self.connections.items()):
            if (now - connection.last_activity_time).total_seconds() > timeout_minutes * 60:
                expired_connections.append(connection_id)
        
        for connection_id in expired_connections:
            await self._disconnect(connection_id)
        
        return len(expired_connections)