"""消息路由系统"""
import asyncio
from typing import Dict, List, Optional, Callable, Any, Type
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes

from ..utils.logger import get_logger
from ..utils.exceptions import MessageRoutingError
from ..utils.decorators import log_action, measure_performance


logger = get_logger(__name__)


class MessageType(Enum):
    """消息类型枚举"""
    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    VOICE = "voice"
    DOCUMENT = "document"
    STICKER = "sticker"
    LOCATION = "location"
    CONTACT = "contact"
    POLL = "poll"
    COMMAND = "command"
    CALLBACK = "callback"
    INLINE = "inline"


class RoutePriority(Enum):
    """路由优先级"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class RoutePattern:
    """路由模式"""
    pattern: str
    type: MessageType
    priority: RoutePriority = RoutePriority.NORMAL
    conditions: List[Callable] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def matches(self, message: Message) -> bool:
        """检查消息是否匹配模式"""
        # 检查消息类型
        if not self._check_message_type(message):
            return False

        # 检查模式匹配
        if self.type == MessageType.TEXT and message.text:
            if not self._match_text_pattern(message.text):
                return False

        # 检查条件
        for condition in self.conditions:
            if not condition(message):
                return False

        return True

    def _check_message_type(self, message: Message) -> bool:
        """检查消息类型是否匹配"""
        type_map = {
            MessageType.TEXT: lambda m: m.text is not None,
            MessageType.PHOTO: lambda m: m.photo is not None,
            MessageType.VIDEO: lambda m: m.video is not None,
            MessageType.AUDIO: lambda m: m.audio is not None,
            MessageType.VOICE: lambda m: m.voice is not None,
            MessageType.DOCUMENT: lambda m: m.document is not None,
            MessageType.STICKER: lambda m: m.sticker is not None,
            MessageType.LOCATION: lambda m: m.location is not None,
            MessageType.CONTACT: lambda m: m.contact is not None,
            MessageType.POLL: lambda m: m.poll is not None,
        }

        check_func = type_map.get(self.type)
        return check_func(message) if check_func else False

    def _match_text_pattern(self, text: str) -> bool:
        """匹配文本模式"""
        import re
        if self.pattern.startswith("^") or self.pattern.endswith("$"):
            # 正则表达式
            return bool(re.match(self.pattern, text))
        else:
            # 简单包含检查
            return self.pattern in text


@dataclass
class MessageContext:
    """消息上下文"""
    message_id: str
    user_id: int
    chat_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    message_type: MessageType
    content: Any
    timestamp: datetime
    is_admin: bool = False
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_update(cls, update: Update, admin_id: int) -> 'MessageContext':
        """从更新创建上下文"""
        message = update.effective_message
        user = update.effective_user
        chat = update.effective_chat

        # 确定消息类型
        if message.text and message.text.startswith('/'):
            msg_type = MessageType.COMMAND
        elif message.text:
            msg_type = MessageType.TEXT
        elif message.photo:
            msg_type = MessageType.PHOTO
        elif message.video:
            msg_type = MessageType.VIDEO
        elif message.voice:
            msg_type = MessageType.VOICE
        elif message.document:
            msg_type = MessageType.DOCUMENT
        elif message.location:
            msg_type = MessageType.LOCATION
        else:
            msg_type = MessageType.TEXT

        # 提取内容
        content = message.text or message.caption or ""
        if message.photo:
            content = message.photo[-1].file_id
        elif message.document:
            content = message.document.file_id
        elif message.voice:
            content = message.voice.file_id
        elif message.video:
            content = message.video.file_id

        return cls(
            message_id=str(message.message_id),
            user_id=user.id,
            chat_id=chat.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            message_type=msg_type,
            content=content,
            timestamp=datetime.now(),
            is_admin=(user.id == admin_id),
            session_id=f"{chat.id}_{user.id}"
        )


class MessageRouter:
    """消息路由器"""

    def __init__(self, config):
        self.config = config
        self.routes: Dict[RoutePriority, List[tuple[RoutePattern, Callable]]] = {
            priority: [] for priority in RoutePriority
        }
        self.middleware: List[Callable] = []
        self.default_handler: Optional[Callable] = None
        self.error_handler: Optional[Callable] = None

    def add_route(self, pattern: RoutePattern, handler: Callable):
        """添加路由"""
        self.routes[pattern.priority].append((pattern, handler))
        logger.debug(f"Added route: {pattern.pattern} with priority {pattern.priority}")

    def add_middleware(self, middleware: Callable):
        """添加中间件"""
        self.middleware.append(middleware)
        logger.debug(f"Added middleware: {middleware.__name__}")

    def set_default_handler(self, handler: Callable):
        """设置默认处理器"""
        self.default_handler = handler

    def set_error_handler(self, handler: Callable):
        """设置错误处理器"""
        self.error_handler = handler

    @measure_performance
    @log_action("route_message")
    async def route(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        """路由消息"""
        try:
            # 创建消息上下文
            msg_context = MessageContext.from_update(
                update,
                self.config.telegram.admin_id
            )

            # 应用中间件
            for middleware in self.middleware:
                result = await middleware(msg_context, context)
                if result is False:
                    logger.debug(f"Middleware {middleware.__name__} blocked message")
                    return None

            # 查找匹配的路由
            handler = await self._find_handler(update.effective_message, msg_context)

            if handler:
                logger.info(
                    f"Routing message to {handler.__name__}",
                    extra={'user_id': msg_context.user_id, 'handler': handler.__name__}
                )
                return await handler(update, context, msg_context)
            elif self.default_handler:
                logger.info(
                    f"Using default handler",
                    extra={'user_id': msg_context.user_id}
                )
                return await self.default_handler(update, context, msg_context)
            else:
                logger.warning(f"No handler found for message from user {msg_context.user_id}")
                raise MessageRoutingError("No handler found for this message type")

        except Exception as e:
            if self.error_handler:
                return await self.error_handler(update, context, e)
            else:
                logger.error(f"Error in message routing: {e}")
                raise

    async def _find_handler(self, message: Message, context: MessageContext) -> Optional[Callable]:
        """查找合适的处理器"""
        # 按优先级顺序检查路由
        for priority in RoutePriority:
            for pattern, handler in self.routes[priority]:
                if pattern.matches(message):
                    return handler
        return None


class RouteBuilder:
    """路由构建器"""

    def __init__(self, router: MessageRouter):
        self.router = router

    def text(self, pattern: str = None, priority: RoutePriority = RoutePriority.NORMAL):
        """文本消息路由装饰器"""
        def decorator(handler: Callable):
            route_pattern = RoutePattern(
                pattern=pattern or ".*",
                type=MessageType.TEXT,
                priority=priority
            )
            self.router.add_route(route_pattern, handler)
            return handler
        return decorator

    def command(self, command: str, priority: RoutePriority = RoutePriority.HIGH):
        """命令路由装饰器"""
        def decorator(handler: Callable):
            route_pattern = RoutePattern(
                pattern=f"^/{command}",
                type=MessageType.TEXT,
                priority=priority
            )
            self.router.add_route(route_pattern, handler)
            return handler
        return decorator

    def photo(self, priority: RoutePriority = RoutePriority.NORMAL):
        """图片消息路由装饰器"""
        def decorator(handler: Callable):
            route_pattern = RoutePattern(
                pattern="",
                type=MessageType.PHOTO,
                priority=priority
            )
            self.router.add_route(route_pattern, handler)
            return handler
        return decorator

    def document(self, priority: RoutePriority = RoutePriority.NORMAL):
        """文档消息路由装饰器"""
        def decorator(handler: Callable):
            route_pattern = RoutePattern(
                pattern="",
                type=MessageType.DOCUMENT,
                priority=priority
            )
            self.router.add_route(route_pattern, handler)
            return handler
        return decorator

    def voice(self, priority: RoutePriority = RoutePriority.NORMAL):
        """语音消息路由装饰器"""
        def decorator(handler: Callable):
            route_pattern = RoutePattern(
                pattern="",
                type=MessageType.VOICE,
                priority=priority
            )
            self.router.add_route(route_pattern, handler)
            return handler
        return decorator

    def middleware(self):
        """中间件装饰器"""
        def decorator(handler: Callable):
            self.router.add_middleware(handler)
            return handler
        return decorator