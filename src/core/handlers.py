"""处理器基类和上下文"""
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, List
from dataclasses import dataclass, field
from telegram import Update, Message
from telegram.ext import ContextTypes

from ..utils.logger import get_logger
from ..config.settings import Settings


logger = get_logger(__name__)


@dataclass
class HandlerContext:
    """处理器上下文"""
    update: Update
    context: ContextTypes.DEFAULT_TYPE
    config: Settings
    user_data: Dict[str, Any] = field(default_factory=dict)
    chat_data: Dict[str, Any] = field(default_factory=dict)
    session_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def message(self) -> Message:
        """获取消息"""
        return self.update.effective_message

    @property
    def user(self):
        """获取用户"""
        return self.update.effective_user

    @property
    def chat(self):
        """获取聊天"""
        return self.update.effective_chat

    def get_session_id(self) -> str:
        """获取会话ID"""
        return f"{self.chat.id}_{self.user.id}"


class BaseHandler(ABC):
    """处理器基类"""

    def __init__(self, config: Settings):
        self.config = config
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    async def handle(self, handler_context: HandlerContext) -> Any:
        """处理消息"""
        pass

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                      message_context: Any = None) -> Any:
        """调用处理器"""
        handler_context = HandlerContext(
            update=update,
            context=context,
            config=self.config,
            user_data=context.user_data,
            chat_data=context.chat_data
        )

        try:
            self.logger.debug(f"Handling message from user {handler_context.user.id}")
            result = await self.handle(handler_context)
            return result
        except Exception as e:
            self.logger.error(f"Error in handler: {e}")
            raise

    async def reply_text(self, context: HandlerContext, text: str, **kwargs) -> Message:
        """回复文本消息"""
        return await context.message.reply_text(text, **kwargs)

    async def reply_photo(self, context: HandlerContext, photo, caption: str = None, **kwargs) -> Message:
        """回复图片"""
        return await context.message.reply_photo(photo, caption=caption, **kwargs)

    async def reply_document(self, context: HandlerContext, document, caption: str = None, **kwargs) -> Message:
        """回复文档"""
        return await context.message.reply_document(document, caption=caption, **kwargs)

    async def forward_to_admin(self, context: HandlerContext) -> Message:
        """转发消息给管理员"""
        return await context.context.bot.forward_message(
            chat_id=self.config.telegram.admin_id,
            from_chat_id=context.chat.id,
            message_id=context.message.message_id
        )

    async def send_to_admin(self, context: HandlerContext, text: str, **kwargs) -> Message:
        """发送消息给管理员"""
        return await context.context.bot.send_message(
            chat_id=self.config.telegram.admin_id,
            text=text,
            **kwargs
        )


class CompositeHandler(BaseHandler):
    """组合处理器"""

    def __init__(self, config: Settings):
        super().__init__(config)
        self.handlers: List[BaseHandler] = []

    def add_handler(self, handler: BaseHandler):
        """添加处理器"""
        self.handlers.append(handler)

    async def handle(self, handler_context: HandlerContext) -> Any:
        """依次执行所有处理器"""
        results = []
        for handler in self.handlers:
            try:
                result = await handler.handle(handler_context)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Error in composite handler {handler.__class__.__name__}: {e}")
                # 可以选择继续或中断
                raise

        return results


class ConditionalHandler(BaseHandler):
    """条件处理器"""

    def __init__(self, config: Settings, condition_func):
        super().__init__(config)
        self.condition_func = condition_func
        self.true_handler: Optional[BaseHandler] = None
        self.false_handler: Optional[BaseHandler] = None

    def set_true_handler(self, handler: BaseHandler):
        """设置条件为真时的处理器"""
        self.true_handler = handler

    def set_false_handler(self, handler: BaseHandler):
        """设置条件为假时的处理器"""
        self.false_handler = handler

    async def handle(self, handler_context: HandlerContext) -> Any:
        """根据条件执行处理器"""
        if await self.condition_func(handler_context):
            if self.true_handler:
                return await self.true_handler.handle(handler_context)
        else:
            if self.false_handler:
                return await self.false_handler.handle(handler_context)

        return None