"""数据模型"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class CustomerStatus(Enum):
    """客户状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class SessionStatus(Enum):
    """会话状态"""
    ACTIVE = "active"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"


class MessageDirection(Enum):
    """消息方向"""
    INBOUND = "inbound"    # 客户发送
    OUTBOUND = "outbound"  # 管理员发送


@dataclass
class Customer:
    """客户模型"""
    user_id: int
    username: Optional[str]
    first_name: str
    last_name: Optional[str]
    language_code: Optional[str]
    status: CustomerStatus = CustomerStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    notes: Optional[str] = None

    @property
    def full_name(self) -> str:
        """获取全名"""
        parts = [self.first_name]
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts)

    @property
    def display_name(self) -> str:
        """获取显示名称"""
        if self.username:
            return f"@{self.username}"
        return self.full_name

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'language_code': self.language_code,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.metadata,
            'tags': self.tags,
            'notes': self.notes
        }


@dataclass
class Message:
    """消息模型"""
    message_id: str
    session_id: str
    user_id: int
    chat_id: int
    direction: MessageDirection
    content: str
    content_type: str  # text, photo, document, voice, etc.
    timestamp: datetime = field(default_factory=datetime.now)
    is_read: bool = False
    is_replied: bool = False
    reply_to_message_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'message_id': self.message_id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'chat_id': self.chat_id,
            'direction': self.direction.value,
            'content': self.content,
            'content_type': self.content_type,
            'timestamp': self.timestamp.isoformat(),
            'is_read': self.is_read,
            'is_replied': self.is_replied,
            'reply_to_message_id': self.reply_to_message_id,
            'metadata': self.metadata
        }


@dataclass
class Session:
    """会话模型"""
    session_id: str
    customer_id: int
    chat_id: int
    status: SessionStatus = SessionStatus.ACTIVE
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    message_count: int = 0
    assigned_to: Optional[int] = None  # 分配给哪个管理员
    tags: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> Optional[float]:
        """获取会话时长（秒）"""
        if self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        return (datetime.now() - self.started_at).total_seconds()

    @property
    def is_active(self) -> bool:
        """是否活跃"""
        return self.status == SessionStatus.ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'session_id': self.session_id,
            'customer_id': self.customer_id,
            'chat_id': self.chat_id,
            'status': self.status.value,
            'started_at': self.started_at.isoformat(),
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None,
            'message_count': self.message_count,
            'assigned_to': self.assigned_to,
            'tags': self.tags,
            'notes': self.notes,
            'metadata': self.metadata,
            'duration': self.duration
        }