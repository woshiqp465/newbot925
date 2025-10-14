#!/usr/bin/env python3
"""
数据库管理模块 - SQLite缓存系统
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class CacheDatabase:
    """缓存数据库管理 - 使用(command,keyword,page)作为唯一键,新数据覆盖旧数据"""

    def __init__(self, db_path="/home/atai/bot_data/cache.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 创建缓存表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command TEXT NOT NULL,
                keyword TEXT NOT NULL,
                page INTEGER NOT NULL,
                result_text TEXT,
                buttons_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                last_accessed TIMESTAMP,
                UNIQUE(command, keyword, page)
            )
        """)

        # 创建查询索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_search
            ON search_cache(command, keyword, page)
        """)

        # 创建过期时间索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_expires
            ON search_cache(expires_at)
        """)

        conn.commit()
        conn.close()
        logger.info("数据库初始化完成")

    def get_cache(self, command: str, keyword: str, page: int) -> Optional[Dict]:
        """
        获取缓存 - 返回与服务商bot完全相同的格式
        返回: {"text": str, "buttons": list} 或 None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT result_text, buttons_json, id
            FROM search_cache
            WHERE command = ? AND keyword = ? AND page = ?
            AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY created_at DESC
            LIMIT 1
        """, (command, keyword, page, datetime.now()))

        row = cursor.fetchone()

        if row:
            # 更新访问统计
            cursor.execute("""
                UPDATE search_cache
                SET access_count = access_count + 1,
                    last_accessed = ?
                WHERE id = ?
            """, (datetime.now(), row[2]))
            conn.commit()

            result = {
                "text": row[0],
                "buttons": json.loads(row[1]) if row[1] else []
            }
            conn.close()
            logger.info(f"缓存命中: {command} {keyword} page{page}")
            return result

        conn.close()
        return None

    def save_cache(self, command: str, keyword: str, page: int,
                   result_text: str, buttons: list = None, expiry_days: int = 30):
        """
        保存缓存 - 新数据自动覆盖旧数据
        使用(command, keyword, page)作为唯一键
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 计算过期时间
        expires_at = datetime.now() + timedelta(days=expiry_days)

        # 按钮JSON化
        buttons_json = json.dumps(buttons, ensure_ascii=False) if buttons else None

        try:
            # INSERT OR REPLACE: 如果(command,keyword,page)已存在,则更新
            cursor.execute("""
                INSERT OR REPLACE INTO search_cache
                (command, keyword, page, result_text, buttons_json, 
                 expires_at, last_accessed, access_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 
                    COALESCE((SELECT access_count FROM search_cache WHERE command=? AND keyword=? AND page=?), 0),
                    CURRENT_TIMESTAMP)
            """, (command, keyword, page, result_text, buttons_json,
                  expires_at, datetime.now(), command, keyword, page))

            conn.commit()
            logger.info(f"缓存已保存/更新: {command} {keyword} page{page}")
            return True

        except Exception as e:
            logger.error(f"保存缓存失败: {e}")
            return False
        finally:
            conn.close()

    def clean_expired(self):
        """清理过期缓存"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM search_cache
            WHERE expires_at IS NOT NULL AND expires_at < ?
        """, (datetime.now(),))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        if deleted > 0:
            logger.info(f"清理过期缓存: {deleted}条")
        return deleted

    def get_stats(self) -> Dict:
        """获取统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 总缓存数
        cursor.execute("SELECT COUNT(*) FROM search_cache")
        total = cursor.fetchone()[0]

        # 有效缓存数
        cursor.execute("""
            SELECT COUNT(*) FROM search_cache
            WHERE expires_at IS NULL OR expires_at > ?
        """, (datetime.now(),))
        valid = cursor.fetchone()[0]

        # 过期缓存数
        expired = total - valid

        # 最常访问
        cursor.execute("""
            SELECT command, keyword, access_count
            FROM search_cache
            ORDER BY access_count DESC
            LIMIT 10
        """)
        top_accessed = cursor.fetchall()

        conn.close()

        return {
            "total": total,
            "valid": valid,
            "expired": expired,
            "top_accessed": [
                {"command": row[0], "keyword": row[1], "count": row[2]}
                for row in top_accessed
            ]
        }
