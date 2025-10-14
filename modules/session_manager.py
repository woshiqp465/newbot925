"""会话管理模块 - 管理用户交互状态和历史"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class SessionManager:
    """用户会话管理器"""

    def __init__(self, timeout_minutes: int = 30) -> None:
        self.sessions: Dict[int, Dict[str, Any]] = {}
        self.session_timeout = timedelta(minutes=timeout_minutes)

    def _now(self) -> datetime:
        return datetime.now()

    def create_session(self, user_id: int, initial_query: str) -> Dict[str, Any]:
        """创建新会话"""
        session = {
            "user_id": user_id,
            "stage": "initial",
            "initial_query": initial_query,
            "history": [
                {
                    "step": "input",
                    "content": initial_query,
                    "timestamp": self._now(),
                }
            ],
            "analysis": None,
            "selected_suggestion": None,
            "search_results": None,
            "can_go_back": False,
            "created_at": self._now(),
            "last_activity": self._now(),
        }
        self.sessions[user_id] = session
        logger.info("[会话] 创建新会话: user=%s, query=%s", user_id, initial_query)
        return session

    def get_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """获取会话，包含过期检查"""
        session = self.sessions.get(user_id)
        if not session:
            return None

        if self._now() - session.get("last_activity", self._now()) > self.session_timeout:
            logger.info("[会话] 会话已过期: user=%s", user_id)
            self.sessions.pop(user_id, None)
            return None

        session["last_activity"] = self._now()
        return session

    def update_stage(self, user_id: int, stage: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
        """更新会话阶段并记录历史"""
        session = self.get_session(user_id)
        if not session:
            return None

        session["stage"] = stage
        session["last_activity"] = self._now()

        history_entry = {
            "step": stage,
            "timestamp": self._now(),
        }
        history_entry.update(kwargs)
        session.setdefault("history", []).append(history_entry)

        for key, value in kwargs.items():
            session[key] = value

        logger.info("[会话] 更新阶段: user=%s, stage=%s", user_id, stage)
        return session

    def save_analysis(self, user_id: int, analysis: Dict[str, Any]) -> None:
        """保存AI分析结果"""
        session = self.get_session(user_id)
        if not session:
            return

        session["analysis"] = analysis
        session["stage"] = "suggestions"
        session["can_go_back"] = True

        suggestions = analysis.get("suggestions", [])
        logger.info("[会话] 保存分析: user=%s, suggestions=%s", user_id, len(suggestions))

    def save_selection(self, user_id: int, suggestion_index: int) -> Optional[Dict[str, Any]]:
        """保存用户选择的建议"""
        session = self.get_session(user_id)
        if not session:
            return None

        analysis = session.get("analysis") or {}
        suggestions = analysis.get("suggestions", [])
        if 0 <= suggestion_index < len(suggestions):
            selection = suggestions[suggestion_index]
            session["selected_suggestion"] = selection
            session["stage"] = "searching"
            session.setdefault("history", []).append(
                {
                    "step": "selection",
                    "timestamp": self._now(),
                    "selection": selection,
                }
            )
            logger.info(
                "[会话] 保存选择: user=%s, index=%s", user_id, suggestion_index
            )
            return selection
        logger.warning(
            "[会话] 选择索引无效: user=%s, index=%s, total=%s",
            user_id,
            suggestion_index,
            len(suggestions),
        )
        return None

    def can_go_back(self, user_id: int) -> bool:
        session = self.get_session(user_id)
        return bool(session and session.get("can_go_back", False))

    def go_back_to_suggestions(self, user_id: int) -> Optional[Dict[str, Any]]:
        """返回到建议阶段"""
        session = self.get_session(user_id)
        if not session:
            return None

        analysis = session.get("analysis")
        if not analysis:
            return None

        session["stage"] = "suggestions"
        session["selected_suggestion"] = None
        logger.info("[会话] 返回建议列表: user=%s", user_id)
        return analysis

    def clear_session(self, user_id: int) -> None:
        """清除会话"""
        if user_id in self.sessions:
            self.sessions.pop(user_id, None)
            logger.info("[会话] 清除会话: user=%s", user_id)

    def get_stats(self) -> Dict[str, Any]:
        """获取会话统计信息"""
        stage_counter: Dict[str, int] = {}
        for session in self.sessions.values():
            stage_name = session.get("stage", "unknown")
            stage_counter[stage_name] = stage_counter.get(stage_name, 0) + 1

        return {
            "active_sessions": len(self.sessions),
            "stages": stage_counter,
        }
