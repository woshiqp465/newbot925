"""系统配置定义"""
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import time
import os


@dataclass
class TelegramConfig:
    """Telegram 相关配置"""
    bot_token: str
    admin_id: int
    admin_username: str
    bot_name: str = "Customer Service Bot"

    def __post_init__(self):
        if not self.bot_token:
            raise ValueError("Bot token is required")
        if not self.admin_id:
            raise ValueError("Admin ID is required")


@dataclass
class DatabaseConfig:
    """数据库配置"""
    type: str = "sqlite"
    path: str = "./data/bot.db"
    host: Optional[str] = None
    port: Optional[int] = None
    user: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None

    def get_connection_string(self) -> str:
        """获取数据库连接字符串"""
        if self.type == "sqlite":
            return f"sqlite:///{self.path}"
        elif self.type == "postgresql":
            return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.type == "mysql":
            return f"mysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        else:
            raise ValueError(f"Unsupported database type: {self.type}")


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    file: str = "./logs/bot.log"
    max_size: int = 10485760  # 10MB
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    def __post_init__(self):
        # 确保日志目录存在
        log_dir = os.path.dirname(self.file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)


@dataclass
class BusinessConfig:
    """业务配置"""
    business_hours_start: str = "09:00"
    business_hours_end: str = "18:00"
    timezone: str = "Asia/Shanghai"
    auto_reply_delay: int = 1  # 秒
    welcome_message: str = "您好！我是客服助手，正在为您转接人工客服，请稍候..."
    offline_message: str = "非常抱歉，现在是非工作时间。我们的工作时间是 {start} - {end}。您的消息已记录，我们会在工作时间尽快回复您。"

    def get_business_hours(self) -> tuple[time, time]:
        """获取营业时间"""
        start = time.fromisoformat(self.business_hours_start)
        end = time.fromisoformat(self.business_hours_end)
        return start, end


@dataclass
class SecurityConfig:
    """安全配置"""
    max_messages_per_minute: int = 30
    session_timeout: int = 3600  # 秒
    enable_encryption: bool = False
    blocked_words: List[str] = field(default_factory=list)
    allowed_file_types: List[str] = field(default_factory=lambda: [
        '.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.docx'
    ])
    max_file_size: int = 10485760  # 10MB


@dataclass
class FeatureFlags:
    """功能开关"""
    enable_auto_reply: bool = True
    enable_statistics: bool = True
    enable_customer_history: bool = True
    enable_multi_admin: bool = False
    enable_file_transfer: bool = True
    enable_voice_message: bool = True
    enable_location_sharing: bool = False


@dataclass
class Settings:
    """主配置类"""
    telegram: TelegramConfig
    database: DatabaseConfig
    logging: LoggingConfig
    business: BusinessConfig
    security: SecurityConfig
    features: FeatureFlags

    # 运行时配置
    debug: bool = False
    testing: bool = False
    version: str = "1.0.0"

    @classmethod
    def from_env(cls) -> 'Settings':
        """从环境变量创建配置"""
        from .loader import ConfigLoader
        return ConfigLoader.load_from_env()

    def validate(self) -> bool:
        """验证配置完整性"""
        try:
            # 验证必要配置
            assert self.telegram.bot_token, "Bot token is required"
            assert self.telegram.admin_id, "Admin ID is required"

            # 验证路径
            if self.database.type == "sqlite":
                db_dir = os.path.dirname(self.database.path)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)

            return True
        except Exception as e:
            raise ValueError(f"Configuration validation failed: {e}")