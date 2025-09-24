"""数据库管理器"""
import sqlite3
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
import asyncio
from contextlib import asynccontextmanager

from .models import Customer, Message, Session, CustomerStatus, SessionStatus, MessageDirection
from ...utils.logger import get_logger
from ...utils.exceptions import DatabaseError
from ...config.settings import Settings


logger = get_logger(__name__)


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, config: Settings):
        self.config = config
        self.db_path = Path(self.config.database.path)
        self.connection: Optional[sqlite3.Connection] = None
        self._lock = asyncio.Lock()

        # 确保数据库目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        """初始化数据库"""
        async with self._lock:
            try:
                self.connection = sqlite3.connect(
                    str(self.db_path),
                    check_same_thread=False
                )
                self.connection.row_factory = sqlite3.Row
                await self._create_tables()
                logger.info(f"Database initialized at {self.db_path}")
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                raise DatabaseError(f"Database initialization failed: {e}")

    async def _create_tables(self):
        """创建数据表"""
        cursor = self.connection.cursor()

        # 客户表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT NOT NULL,
                last_name TEXT,
                language_code TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT,
                tags TEXT,
                notes TEXT
            )
        """)

        # 消息表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                direction TEXT NOT NULL,
                content TEXT,
                content_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                is_read INTEGER DEFAULT 0,
                is_replied INTEGER DEFAULT 0,
                reply_to_message_id TEXT,
                metadata TEXT,
                FOREIGN KEY (user_id) REFERENCES customers (user_id)
            )
        """)

        # 会话表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                last_message_at TEXT,
                message_count INTEGER DEFAULT 0,
                assigned_to INTEGER,
                tags TEXT,
                notes TEXT,
                metadata TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers (user_id)
            )
        """)

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_customer ON sessions(customer_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status)")

        self.connection.commit()

    @asynccontextmanager
    async def transaction(self):
        """事务上下文管理器"""
        async with self._lock:
            cursor = self.connection.cursor()
            try:
                yield cursor
                self.connection.commit()
            except Exception as e:
                self.connection.rollback()
                logger.error(f"Transaction failed: {e}")
                raise DatabaseError(f"Transaction failed: {e}")

    async def save_customer(self, customer: Customer) -> bool:
        """保存客户"""
        async with self.transaction() as cursor:
            cursor.execute("""
                INSERT OR REPLACE INTO customers (
                    user_id, username, first_name, last_name, language_code,
                    status, created_at, updated_at, metadata, tags, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                customer.user_id,
                customer.username,
                customer.first_name,
                customer.last_name,
                customer.language_code,
                customer.status.value,
                customer.created_at.isoformat(),
                customer.updated_at.isoformat(),
                json.dumps(customer.metadata),
                json.dumps(customer.tags),
                customer.notes
            ))
            return True

    async def get_customer(self, user_id: int) -> Optional[Customer]:
        """获取客户"""
        async with self._lock:
            cursor = self.connection.cursor()
            cursor.execute("SELECT * FROM customers WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()

            if row:
                return Customer(
                    user_id=row['user_id'],
                    username=row['username'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    language_code=row['language_code'],
                    status=CustomerStatus(row['status']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at']),
                    metadata=json.loads(row['metadata'] or '{}'),
                    tags=json.loads(row['tags'] or '[]'),
                    notes=row['notes']
                )
            return None

    async def get_all_customers(self, status: Optional[CustomerStatus] = None) -> List[Customer]:
        """获取所有客户"""
        async with self._lock:
            cursor = self.connection.cursor()

            if status:
                cursor.execute("SELECT * FROM customers WHERE status = ?", (status.value,))
            else:
                cursor.execute("SELECT * FROM customers")

            customers = []
            for row in cursor.fetchall():
                customers.append(Customer(
                    user_id=row['user_id'],
                    username=row['username'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    language_code=row['language_code'],
                    status=CustomerStatus(row['status']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at']),
                    metadata=json.loads(row['metadata'] or '{}'),
                    tags=json.loads(row['tags'] or '[]'),
                    notes=row['notes']
                ))

            return customers

    async def save_message(self, message: Message) -> bool:
        """保存消息"""
        async with self.transaction() as cursor:
            cursor.execute("""
                INSERT INTO messages (
                    message_id, session_id, user_id, chat_id, direction,
                    content, content_type, timestamp, is_read, is_replied,
                    reply_to_message_id, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message.message_id,
                message.session_id,
                message.user_id,
                message.chat_id,
                message.direction.value,
                message.content,
                message.content_type,
                message.timestamp.isoformat(),
                message.is_read,
                message.is_replied,
                message.reply_to_message_id,
                json.dumps(message.metadata)
            ))

            # 更新会话的最后消息时间和消息计数
            cursor.execute("""
                UPDATE sessions
                SET last_message_at = ?, message_count = message_count + 1
                WHERE session_id = ?
            """, (message.timestamp.isoformat(), message.session_id))

            return True

    async def get_messages(self, session_id: str, limit: int = 100) -> List[Message]:
        """获取会话消息"""
        async with self._lock:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT * FROM messages
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (session_id, limit))

            messages = []
            for row in cursor.fetchall():
                messages.append(Message(
                    message_id=row['message_id'],
                    session_id=row['session_id'],
                    user_id=row['user_id'],
                    chat_id=row['chat_id'],
                    direction=MessageDirection(row['direction']),
                    content=row['content'],
                    content_type=row['content_type'],
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    is_read=bool(row['is_read']),
                    is_replied=bool(row['is_replied']),
                    reply_to_message_id=row['reply_to_message_id'],
                    metadata=json.loads(row['metadata'] or '{}')
                ))

            return list(reversed(messages))  # 返回时间顺序

    async def save_session(self, session: Session) -> bool:
        """保存会话"""
        async with self.transaction() as cursor:
            cursor.execute("""
                INSERT OR REPLACE INTO sessions (
                    session_id, customer_id, chat_id, status, started_at,
                    ended_at, last_message_at, message_count, assigned_to,
                    tags, notes, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session.session_id,
                session.customer_id,
                session.chat_id,
                session.status.value,
                session.started_at.isoformat(),
                session.ended_at.isoformat() if session.ended_at else None,
                session.last_message_at.isoformat() if session.last_message_at else None,
                session.message_count,
                session.assigned_to,
                json.dumps(session.tags),
                session.notes,
                json.dumps(session.metadata)
            ))
            return True

    async def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        async with self._lock:
            cursor = self.connection.cursor()
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()

            if row:
                return Session(
                    session_id=row['session_id'],
                    customer_id=row['customer_id'],
                    chat_id=row['chat_id'],
                    status=SessionStatus(row['status']),
                    started_at=datetime.fromisoformat(row['started_at']),
                    ended_at=datetime.fromisoformat(row['ended_at']) if row['ended_at'] else None,
                    last_message_at=datetime.fromisoformat(row['last_message_at']) if row['last_message_at'] else None,
                    message_count=row['message_count'],
                    assigned_to=row['assigned_to'],
                    tags=json.loads(row['tags'] or '[]'),
                    notes=row['notes'],
                    metadata=json.loads(row['metadata'] or '{}')
                )
            return None

    async def get_active_sessions(self) -> List[Session]:
        """获取活跃会话"""
        async with self._lock:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT * FROM sessions
                WHERE status = ?
                ORDER BY last_message_at DESC
            """, (SessionStatus.ACTIVE.value,))

            sessions = []
            for row in cursor.fetchall():
                sessions.append(Session(
                    session_id=row['session_id'],
                    customer_id=row['customer_id'],
                    chat_id=row['chat_id'],
                    status=SessionStatus(row['status']),
                    started_at=datetime.fromisoformat(row['started_at']),
                    ended_at=datetime.fromisoformat(row['ended_at']) if row['ended_at'] else None,
                    last_message_at=datetime.fromisoformat(row['last_message_at']) if row['last_message_at'] else None,
                    message_count=row['message_count'],
                    assigned_to=row['assigned_to'],
                    tags=json.loads(row['tags'] or '[]'),
                    notes=row['notes'],
                    metadata=json.loads(row['metadata'] or '{}')
                ))

            return sessions

    async def update_session_status(self, session_id: str, status: SessionStatus) -> bool:
        """更新会话状态"""
        async with self.transaction() as cursor:
            ended_at = None
            if status in [SessionStatus.RESOLVED, SessionStatus.CLOSED]:
                ended_at = datetime.now().isoformat()

            cursor.execute("""
                UPDATE sessions
                SET status = ?, ended_at = ?
                WHERE session_id = ?
            """, (status.value, ended_at, session_id))

            return cursor.rowcount > 0

    async def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        async with self._lock:
            cursor = self.connection.cursor()

            # 客户统计
            cursor.execute("SELECT COUNT(*) as count FROM customers")
            total_customers = cursor.fetchone()['count']

            cursor.execute("SELECT COUNT(*) as count FROM customers WHERE status = ?",
                          (CustomerStatus.ACTIVE.value,))
            active_customers = cursor.fetchone()['count']

            # 会话统计
            cursor.execute("SELECT COUNT(*) as count FROM sessions")
            total_sessions = cursor.fetchone()['count']

            cursor.execute("SELECT COUNT(*) as count FROM sessions WHERE status = ?",
                          (SessionStatus.ACTIVE.value,))
            active_sessions = cursor.fetchone()['count']

            # 消息统计
            cursor.execute("SELECT COUNT(*) as count FROM messages")
            total_messages = cursor.fetchone()['count']

            cursor.execute("""
                SELECT COUNT(*) as count FROM messages
                WHERE direction = ? AND is_replied = 0
            """, (MessageDirection.INBOUND.value,))
            unreplied_messages = cursor.fetchone()['count']

            return {
                'customers': {
                    'total': total_customers,
                    'active': active_customers
                },
                'sessions': {
                    'total': total_sessions,
                    'active': active_sessions
                },
                'messages': {
                    'total': total_messages,
                    'unreplied': unreplied_messages
                }
            }

    async def cleanup_old_sessions(self, days: int = 30):
        """清理旧会话"""
        async with self.transaction() as cursor:
            cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
            cutoff_date_str = datetime.fromtimestamp(cutoff_date).isoformat()

            cursor.execute("""
                DELETE FROM messages
                WHERE session_id IN (
                    SELECT session_id FROM sessions
                    WHERE ended_at < ? AND status IN (?, ?)
                )
            """, (cutoff_date_str, SessionStatus.RESOLVED.value, SessionStatus.CLOSED.value))

            cursor.execute("""
                DELETE FROM sessions
                WHERE ended_at < ? AND status IN (?, ?)
            """, (cutoff_date_str, SessionStatus.RESOLVED.value, SessionStatus.CLOSED.value))

            logger.info(f"Cleaned up sessions older than {days} days")

    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")