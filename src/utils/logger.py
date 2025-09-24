"""日志系统"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional
from pathlib import Path
import json
from datetime import datetime


class CustomFormatter(logging.Formatter):
    """自定义日志格式化器"""

    # 颜色代码
    COLORS = {
        'DEBUG': '\033[36m',    # 青色
        'INFO': '\033[32m',     # 绿色
        'WARNING': '\033[33m',  # 黄色
        'ERROR': '\033[31m',    # 红色
        'CRITICAL': '\033[35m', # 紫色
    }
    RESET = '\033[0m'

    def __init__(self, use_color: bool = True):
        super().__init__()
        self.use_color = use_color and sys.stderr.isatty()

    def format(self, record):
        # 基础格式
        log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

        # 添加额外信息
        if hasattr(record, 'user_id'):
            log_format = f"%(asctime)s | %(levelname)-8s | %(name)s | User:{record.user_id} | %(message)s"

        if hasattr(record, 'chat_id'):
            log_format = f"%(asctime)s | %(levelname)-8s | %(name)s | Chat:{record.chat_id} | %(message)s"

        # 应用颜色
        if self.use_color:
            levelname = record.levelname
            if levelname in self.COLORS:
                log_format = log_format.replace(
                    '%(levelname)-8s',
                    f"{self.COLORS[levelname]}%(levelname)-8s{self.RESET}"
                )

        formatter = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)


class JsonFormatter(logging.Formatter):
    """JSON 格式化器用于结构化日志"""

    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }

        # 添加额外字段
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename',
                          'funcName', 'levelname', 'levelno', 'lineno',
                          'module', 'msecs', 'message', 'pathname', 'process',
                          'processName', 'relativeCreated', 'thread', 'threadName']:
                log_data[key] = value

        # 添加异常信息
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class Logger:
    """日志管理器"""

    _instance = None
    _loggers = {}

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config=None):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.config = config
            self.setup_logging()

    def setup_logging(self):
        """设置日志系统"""
        # 根日志配置
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # 移除默认处理器
        root_logger.handlers = []

        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(
            getattr(logging, self.config.logging.level if self.config else 'INFO')
        )
        console_handler.setFormatter(CustomFormatter(use_color=True))
        root_logger.addHandler(console_handler)

        # 文件处理器
        if self.config and self.config.logging.file:
            file_path = Path(self.config.logging.file)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = RotatingFileHandler(
                filename=str(file_path),
                maxBytes=self.config.logging.max_size,
                backupCount=self.config.logging.backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(CustomFormatter(use_color=False))
            root_logger.addHandler(file_handler)

            # JSON 日志文件（用于分析）
            json_file_path = file_path.with_suffix('.json')
            json_handler = RotatingFileHandler(
                filename=str(json_file_path),
                maxBytes=self.config.logging.max_size,
                backupCount=self.config.logging.backup_count,
                encoding='utf-8'
            )
            json_handler.setLevel(logging.INFO)
            json_handler.setFormatter(JsonFormatter())
            root_logger.addHandler(json_handler)

    @classmethod
    def get_logger(cls, name: str, config=None) -> logging.Logger:
        """获取日志器"""
        if name not in cls._loggers:
            if not cls._instance:
                cls(config)
            cls._loggers[name] = logging.getLogger(name)
        return cls._loggers[name]


def get_logger(name: str, config=None) -> logging.Logger:
    """获取日志器的便捷方法"""
    return Logger.get_logger(name, config)


class LoggerContextFilter(logging.Filter):
    """日志上下文过滤器"""

    def __init__(self, **context):
        super().__init__()
        self.context = context

    def filter(self, record):
        for key, value in self.context.items():
            setattr(record, key, value)
        return True