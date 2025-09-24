"""配置加载器"""
import os
from typing import Any, Dict
from pathlib import Path
from dotenv import load_dotenv
from .settings import (
    Settings, TelegramConfig, DatabaseConfig,
    LoggingConfig, BusinessConfig, SecurityConfig, FeatureFlags
)


class ConfigLoader:
    """配置加载器"""

    @staticmethod
    def load_env_file(env_path: str = None) -> None:
        """加载环境变量文件"""
        if env_path:
            load_dotenv(env_path)
        else:
            # 查找 .env 文件
            current_dir = Path.cwd()
            env_file = current_dir / ".env"
            if env_file.exists():
                load_dotenv(env_file)
            else:
                # 向上查找
                for parent in current_dir.parents:
                    env_file = parent / ".env"
                    if env_file.exists():
                        load_dotenv(env_file)
                        break

    @staticmethod
    def get_env(key: str, default: Any = None, cast_type: type = str) -> Any:
        """获取环境变量并转换类型"""
        value = os.getenv(key, default)
        if value is None:
            return None

        if cast_type == bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            return bool(value)
        elif cast_type == int:
            return int(value)
        elif cast_type == float:
            return float(value)
        else:
            return value

    @classmethod
    def load_from_env(cls) -> Settings:
        """从环境变量加载配置"""
        cls.load_env_file()

        # Telegram 配置
        telegram_config = TelegramConfig(
            bot_token=cls.get_env('BOT_TOKEN', ''),
            admin_id=cls.get_env('ADMIN_ID', 0, int),
            admin_username=cls.get_env('ADMIN_USERNAME', ''),
            bot_name=cls.get_env('BOT_NAME', 'Customer Service Bot')
        )

        # 数据库配置
        database_config = DatabaseConfig(
            type=cls.get_env('DATABASE_TYPE', 'sqlite'),
            path=cls.get_env('DATABASE_PATH', './data/bot.db'),
            host=cls.get_env('DATABASE_HOST'),
            port=cls.get_env('DATABASE_PORT', cast_type=int),
            user=cls.get_env('DATABASE_USER'),
            password=cls.get_env('DATABASE_PASSWORD'),
            database=cls.get_env('DATABASE_NAME')
        )

        # 日志配置
        logging_config = LoggingConfig(
            level=cls.get_env('LOG_LEVEL', 'INFO'),
            file=cls.get_env('LOG_FILE', './logs/bot.log'),
            max_size=cls.get_env('LOG_MAX_SIZE', 10485760, int),
            backup_count=cls.get_env('LOG_BACKUP_COUNT', 5, int)
        )

        # 业务配置
        business_config = BusinessConfig(
            business_hours_start=cls.get_env('BUSINESS_HOURS_START', '09:00'),
            business_hours_end=cls.get_env('BUSINESS_HOURS_END', '18:00'),
            timezone=cls.get_env('TIMEZONE', 'Asia/Shanghai'),
            auto_reply_delay=cls.get_env('AUTO_REPLY_DELAY', 1, int),
            welcome_message=cls.get_env('WELCOME_MESSAGE',
                                        '您好！我是客服助手，正在为您转接人工客服，请稍候...'),
            offline_message=cls.get_env('OFFLINE_MESSAGE',
                                        '非常抱歉，现在是非工作时间。我们的工作时间是 {start} - {end}。您的消息已记录，我们会在工作时间尽快回复您。')
        )

        # 安全配置
        security_config = SecurityConfig(
            max_messages_per_minute=cls.get_env('MAX_MESSAGES_PER_MINUTE', 30, int),
            session_timeout=cls.get_env('SESSION_TIMEOUT', 3600, int),
            enable_encryption=cls.get_env('ENABLE_ENCRYPTION', False, bool),
            blocked_words=cls.get_env('BLOCKED_WORDS', '').split(',') if cls.get_env('BLOCKED_WORDS') else []
        )

        # 功能开关
        feature_flags = FeatureFlags(
            enable_auto_reply=cls.get_env('ENABLE_AUTO_REPLY', True, bool),
            enable_statistics=cls.get_env('ENABLE_STATISTICS', True, bool),
            enable_customer_history=cls.get_env('ENABLE_CUSTOMER_HISTORY', True, bool),
            enable_multi_admin=cls.get_env('ENABLE_MULTI_ADMIN', False, bool),
            enable_file_transfer=cls.get_env('ENABLE_FILE_TRANSFER', True, bool),
            enable_voice_message=cls.get_env('ENABLE_VOICE_MESSAGE', True, bool),
            enable_location_sharing=cls.get_env('ENABLE_LOCATION_SHARING', False, bool)
        )

        # 创建设置对象
        settings = Settings(
            telegram=telegram_config,
            database=database_config,
            logging=logging_config,
            business=business_config,
            security=security_config,
            features=feature_flags,
            debug=cls.get_env('DEBUG', False, bool),
            testing=cls.get_env('TESTING', False, bool),
            version=cls.get_env('VERSION', '1.0.0')
        )

        # 验证配置
        settings.validate()
        return settings

    @classmethod
    def load_from_dict(cls, config_dict: Dict[str, Any]) -> Settings:
        """从字典加载配置"""
        telegram_config = TelegramConfig(**config_dict.get('telegram', {}))
        database_config = DatabaseConfig(**config_dict.get('database', {}))
        logging_config = LoggingConfig(**config_dict.get('logging', {}))
        business_config = BusinessConfig(**config_dict.get('business', {}))
        security_config = SecurityConfig(**config_dict.get('security', {}))
        feature_flags = FeatureFlags(**config_dict.get('features', {}))

        settings = Settings(
            telegram=telegram_config,
            database=database_config,
            logging=logging_config,
            business=business_config,
            security=security_config,
            features=feature_flags,
            **config_dict.get('runtime', {})
        )

        settings.validate()
        return settings