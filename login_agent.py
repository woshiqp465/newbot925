#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
from claude_agent_sdk import ClaudeSDKClient

async def login():
    print('🔐 使用提供的 API key 登录...')
    
    try:
        client = ClaudeSDKClient()
        await client.connect()
        
        # 尝试使用 /login 命令
        # 根据错误信息，需要运行 /login
        await client.query('/login cr_9792f20a98f055e204248a41f280780ca2fb8f08f35e60c785e5245653937e06')
        
        print('✅ 登录命令已发送')
        
        # 接收响应
        async for chunk in client.receive_response():
            print(f'📝 响应: {chunk}')
        
        await client.disconnect()
        
    except Exception as e:
        print(f'❌ 登录失败: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(login())
