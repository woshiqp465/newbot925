"""装饰器工具"""
import functools
import time
import asyncio
from typing import Callable, Any, Optional, Dict
from datetime import datetime, timedelta
from collections import defaultdict
from .logger import get_logger
from .exceptions import RateLimitError, AuthorizationError, ValidationError


logger = get_logger(__name__)


def async_retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0,
                exceptions: tuple = (Exception,)):
    """异步重试装饰器"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            attempt = 1
            current_delay = delay

            while attempt <= max_attempts:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        logger.error(f"Max retries ({max_attempts}) reached for {func.__name__}")
                        raise

                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}. "
                        f"Retrying in {current_delay:.2f}s..."
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
                    attempt += 1

        return wrapper
    return decorator


def rate_limit(max_calls: int, period: float):
    """速率限制装饰器"""
    def decorator(func: Callable) -> Callable:
        calls = defaultdict(list)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 获取调用者标识（假设第一个参数是 self，第二个是 update）
            caller_id = None
            if len(args) >= 2 and hasattr(args[1], 'effective_user'):
                caller_id = args[1].effective_user.id
            else:
                caller_id = 'global'

            now = time.time()
            calls[caller_id] = [t for t in calls[caller_id] if now - t < period]

            if len(calls[caller_id]) >= max_calls:
                raise RateLimitError(
                    f"Rate limit exceeded: {max_calls} calls per {period} seconds",
                    details={'caller_id': caller_id, 'limit': max_calls, 'period': period}
                )

            calls[caller_id].append(now)
            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_admin(func: Callable) -> Callable:
    """需要管理员权限装饰器"""
    @functools.wraps(func)
    async def wrapper(self, update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != self.config.telegram.admin_id:
            if not (hasattr(self, 'is_admin') and await self.is_admin(user_id)):
                raise AuthorizationError(
                    "Admin privileges required",
                    details={'user_id': user_id}
                )
        return await func(self, update, context, *args, **kwargs)
    return wrapper


def log_action(action_type: str = None):
    """记录操作日志装饰器"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            action = action_type or func.__name__

            # 提取用户信息
            user_info = {}
            if len(args) >= 2 and hasattr(args[1], 'effective_user'):
                user = args[1].effective_user
                user_info = {
                    'user_id': user.id,
                    'username': user.username,
                    'name': user.first_name
                }

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                # 创建额外信息，避免覆盖保留字段
                extra_info = {
                    'action': action,
                    'duration': duration,
                    'status': 'success'
                }
                # 添加用户信息，使用前缀避免冲突
                for k, v in user_info.items():
                    extra_info[f'user_{k}' if k in ['name'] else k] = v

                logger.info(
                    f"Action completed: {action}",
                    extra=extra_info
                )
                return result

            except Exception as e:
                duration = time.time() - start_time

                # 创建额外信息，避免覆盖保留字段
                extra_info = {
                    'action': action,
                    'duration': duration,
                    'status': 'failed',
                    'error': str(e)
                }
                # 添加用户信息，使用前缀避免冲突
                for k, v in user_info.items():
                    extra_info[f'user_{k}' if k in ['name'] else k] = v

                logger.error(
                    f"Action failed: {action}",
                    extra=extra_info
                )
                raise

        return wrapper
    return decorator


def validate_input(**validators):
    """输入验证装饰器"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 合并位置参数和关键字参数
            bound_args = func.__code__.co_varnames[:func.__code__.co_argcount]
            all_args = dict(zip(bound_args, args))
            all_args.update(kwargs)

            # 执行验证
            for param_name, validator in validators.items():
                if param_name in all_args:
                    value = all_args[param_name]
                    if not validator(value):
                        raise ValidationError(
                            f"Validation failed for parameter: {param_name}",
                            details={'parameter': param_name, 'value': value}
                        )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def cache_result(ttl: int = 300):
    """结果缓存装饰器"""
    def decorator(func: Callable) -> Callable:
        cache: Dict[str, tuple[Any, datetime]] = {}

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 创建缓存键
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

            # 检查缓存
            if cache_key in cache:
                result, timestamp = cache[cache_key]
                if datetime.now() - timestamp < timedelta(seconds=ttl):
                    logger.debug(f"Cache hit for {func.__name__}")
                    return result

            # 执行函数
            result = await func(*args, **kwargs)

            # 存储结果
            cache[cache_key] = (result, datetime.now())
            logger.debug(f"Cache miss for {func.__name__}, cached for {ttl}s")

            return result

        # 添加清除缓存方法
        wrapper.clear_cache = lambda: cache.clear()
        return wrapper
    return decorator


def measure_performance(func: Callable) -> Callable:
    """性能测量装饰器"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        start_memory = 0  # 可以添加内存测量

        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            end_time = time.perf_counter()
            duration = end_time - start_time

            if duration > 1.0:  # 超过1秒的操作记录警告
                logger.warning(
                    f"Slow operation detected: {func.__name__} took {duration:.2f}s",
                    extra={
                        'function': func.__name__,
                        'duration': duration
                    }
                )
            else:
                logger.debug(f"{func.__name__} completed in {duration:.4f}s")

    return wrapper