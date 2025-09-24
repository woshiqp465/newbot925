"""自定义异常类"""
from typing import Optional, Any, Dict


class BotException(Exception):
    """机器人基础异常"""

    def __init__(self, message: str, code: str = None, details: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'error': self.code,
            'message': self.message,
            'details': self.details
        }


class ConfigurationError(BotException):
    """配置错误"""
    pass


class DatabaseError(BotException):
    """数据库错误"""
    pass


class TelegramError(BotException):
    """Telegram API 错误"""
    pass


class AuthenticationError(BotException):
    """认证错误"""
    pass


class AuthorizationError(BotException):
    """授权错误"""
    pass


class ValidationError(BotException):
    """验证错误"""
    pass


class RateLimitError(BotException):
    """速率限制错误"""
    pass


class SessionError(BotException):
    """会话错误"""
    pass


class MessageRoutingError(BotException):
    """消息路由错误"""
    pass


class BusinessLogicError(BotException):
    """业务逻辑错误"""
    pass


class ExternalServiceError(BotException):
    """外部服务错误"""
    pass


class ErrorHandler:
    """错误处理器"""

    @staticmethod
    async def handle_error(error: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """处理错误"""
        from ..utils.logger import get_logger
        logger = get_logger(__name__)

        error_info = {
            'type': type(error).__name__,
            'message': str(error),
            'context': context or {}
        }

        if isinstance(error, BotException):
            # 自定义异常
            error_info.update(error.to_dict())
            logger.error(f"Bot error: {error.message}", extra={'error_details': error_info})
        else:
            # 未知异常
            logger.exception(f"Unexpected error: {error}", extra={'error_details': error_info})
            error_info['message'] = "An unexpected error occurred"

        return error_info

    @staticmethod
    def create_user_message(error: Exception) -> str:
        """创建用户友好的错误消息"""
        if isinstance(error, AuthenticationError):
            return "❌ 认证失败，请重新登录"
        elif isinstance(error, AuthorizationError):
            return "❌ 您没有权限执行此操作"
        elif isinstance(error, ValidationError):
            return f"❌ 输入无效：{error.message}"
        elif isinstance(error, RateLimitError):
            return "⚠️ 操作太频繁，请稍后再试"
        elif isinstance(error, SessionError):
            return "❌ 会话已过期，请重新开始"
        elif isinstance(error, BusinessLogicError):
            return f"❌ 操作失败：{error.message}"
        elif isinstance(error, ExternalServiceError):
            return "❌ 外部服务暂时不可用，请稍后再试"
        else:
            return "❌ 系统错误，请稍后再试或联系管理员"