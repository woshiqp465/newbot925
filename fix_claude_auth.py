#!/usr/bin/env python3
import sys

with open('integrated_bot_ai.py', 'r') as f:
    content = f.read()

# 替换初始化代码
old_init = '''    claude_client = anthropic.Anthropic(
        api_key=os.environ.get('ANTHROPIC_AUTH_TOKEN'),
        base_url=os.environ.get('ANTHROPIC_BASE_URL', 'https://api.anthropic.com')
    )'''

new_init = '''    claude_client = anthropic.Anthropic(
        auth_token=os.environ.get('ANTHROPIC_AUTH_TOKEN'),
        base_url=os.environ.get('ANTHROPIC_BASE_URL', 'https://api.anthropic.com')
    )'''

content = content.replace(old_init, new_init)

with open('integrated_bot_ai.py', 'w') as f:
    f.write(content)

print('✅ 修改完成')
