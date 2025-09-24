#!/usr/bin/env python3
"""客服机器人主程序"""
import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.core.bot import CustomerServiceBot
from src.config.settings import Settings
from src.utils.logger import get_logger


logger = get_logger(__name__)


def main():
    """主函数"""
    try:
        # 加载配置
        config = Settings.from_env()

        # 创建并运行机器人
        bot = CustomerServiceBot(config)
        logger.info(f"Starting Customer Service Bot v{config.version}")
        bot.run()

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Bot failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()