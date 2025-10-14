#!/usr/bin/env python3
"""
Claude Agent SDK 包装器 V3
修复事件循环冲突问题 - 在async环境中直接await
"""

import os
import asyncio
import re
from claude_agent_sdk import ClaudeSDKClient
import logging

logger = logging.getLogger(__name__)

class ClaudeAgentWrapper:
    """Claude Agent SDK 的包装器 - 支持async环境"""
    
    def __init__(self):
        self._env_set = False
        
    def _ensure_env(self):
        """确保环境变量已设置"""
        if not self._env_set:
            if not os.environ.get('ANTHROPIC_AUTH_TOKEN'):
                raise Exception("ANTHROPIC_AUTH_TOKEN not set")
            if not os.environ.get('ANTHROPIC_BASE_URL'):
                logger.warning("ANTHROPIC_BASE_URL not set, using default")
            self._env_set = True
    
    async def _async_chat(self, messages: list) -> str:
        """异步聊天（每次创建新连接）"""
        self._ensure_env()
        
        client = None
        try:
            # 创建新客户端
            client = ClaudeSDKClient()
            await client.connect()
            
            # 构建提示词
            prompt_parts = []
            for msg in messages:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                if role == 'user':
                    prompt_parts.append(f"User: {content}")
                else:
                    prompt_parts.append(f"Assistant: {content}")
            
            full_prompt = "\n\n".join(prompt_parts)
            
            # 发送查询
            await client.query(full_prompt)
            
            # 接收响应
            response_text = ''
            async for chunk in client.receive_response():
                chunk_str = str(chunk)
                if 'AssistantMessage' in chunk_str:
                    # 提取文本内容
                    match = re.search(r"text='([^']*)'", chunk_str)
                    if match:
                        response_text += match.group(1)
                    if not match:
                        match = re.search(r'text="([^"]*)"', chunk_str)
                        if match:
                            response_text += match.group(1)
            
            return response_text.strip()
            
        except Exception as e:
            logger.error(f"Chat error: {e}")
            raise
        finally:
            # 不主动断开，让客户端自然关闭
            if client:
                try:
                    await client.disconnect()
                except:
                    pass  # 忽略断开连接时的错误
    
    async def chat_async(self, messages: list, model: str = "claude-sonnet-4-20250514",
                         max_tokens: int = 512, temperature: float = 0.7) -> str:
        """异步聊天接口（在async环境中使用）"""
        return await self._async_chat(messages)
    
    def chat(self, messages: list, model: str = "claude-sonnet-4-20250514",
             max_tokens: int = 512, temperature: float = 0.7) -> str:
        """同步聊天接口（兼容原 Anthropic SDK 格式）"""
        try:
            # 尝试获取当前事件循环
            try:
                loop = asyncio.get_running_loop()
                # 如果已经在事件循环中，不能使用 run_until_complete
                # 需要使用 asyncio.create_task 或直接 await
                logger.error("Cannot use sync chat() in async context, use chat_async() instead")
                raise RuntimeError("Use chat_async() in async context")
            except RuntimeError:
                # 没有运行中的事件循环，创建新的
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    response_text = loop.run_until_complete(self._async_chat(messages))
                    return response_text
                finally:
                    loop.close()
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            raise

# 创建全局客户端实例
claude_agent_client = None

def init_claude_agent():
    """初始化 Claude Agent SDK 客户端"""
    global claude_agent_client
    
    # 确保环境变量已设置
    if not os.environ.get('ANTHROPIC_AUTH_TOKEN'):
        logger.error("ANTHROPIC_AUTH_TOKEN not set")
        return None
    
    try:
        claude_agent_client = ClaudeAgentWrapper()
        logger.info("✅ Claude Agent SDK wrapper initialized")
        return claude_agent_client
    except Exception as e:
        logger.error(f"❌ Init failed: {e}")
        return None
