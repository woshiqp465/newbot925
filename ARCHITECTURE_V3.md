# Bot V3 架构设计

## 核心原则
1. 模块化设计 - 每个功能独立模块
2. 清晰的数据流 - 用户输入 → AI分析 → 按钮选择 → 执行 → 结果展示 → 可返回
3. 完整的错误处理 - 每一步都有降级方案
4. 所有bytes正确处理 - 统一转换为hex字符串存储

## 模块划分

### 1. SessionManager (会话管理)
```python
class SessionManager:
    - 管理用户会话状态
    - 存储AI分析结果
    - 存储用户选择历史
    - 支持返回上一步
```

### 2. AIAnalyzer (AI意图分析)
```python
class AIAnalyzer:
    - 调用Claude API分析用户输入
    - 生成3-5个搜索建议
    - 提取关键词和命令
    - 返回结构化数据
```

### 3. ButtonGenerator (按钮生成器)
```python
class ButtonGenerator:
    - 根据AI建议生成按钮
    - 为搜索结果添加控制按钮
    - 统一管理callback_data
```

### 4. SearchExecutor (搜索执行器)
```python
class SearchExecutor:
    - 转发搜索到目标bot
    - 接收并处理结果
    - 正确处理bytes类型
    - 触发后台翻页
```

### 5. CacheManager (缓存管理器) 
```python
class CacheManager:
    - 所有bytes转hex存储
    - 读取时hex转bytes
    - 统一的存取接口
```

## 用户交互流程

```
用户发送: "我想找德州扑克群"
    ↓
[AI分析器] 分析意图
    ↓
生成建议:
  🔍 按名称搜索"德州扑克群"
  💬 搜索讨论"德州扑克"的群
  🎯 搜索"扑克"相关内容
  ✍️ 手动输入命令
    ↓
用户点击: "搜索讨论德州扑克的群"
    ↓
[搜索执行器] 执行 /text 德州扑克
    ↓
展示结果 + 底部控制按钮:
  [...搜索结果...]
  [下一页] [上一页]
  ─────────────
  [🔙 返回重选] [🔄 优化搜索]
    ↓
用户点击: "返回重选"
    ↓
返回建议列表（从会话恢复）
```

## 数据结构

### 用户会话
```python
{
    "user_id": 123,
    "stage": "suggestions" | "searching" | "browsing",
    "history": [
        {
            "step": "input",
            "content": "我想找德州扑克群",
            "timestamp": "..."
        },
        {
            "step": "analysis",
            "suggestions": [...],
            "timestamp": "..."
        },
        {
            "step": "selected",
            "command": "/text",
            "keyword": "德州扑克",
            "timestamp": "..."
        }
    ],
    "can_go_back": True
}
```

### AI建议
```python
{
    "explanation": "根据您的需求，我推荐以下搜索方式",
    "suggestions": [
        {
            "command": "/text",
            "keyword": "德州扑克",
            "description": "搜索讨论德州扑克的群组",
            "icon": "💬",
            "priority": 1
        }
    ]
}
```

## 文件结构

```
telegram-bot/
├── bot_v3.py                    # 主程序
├── modules/
│   ├── __init__.py
│   ├── session_manager.py       # 会话管理
│   ├── ai_analyzer.py           # AI分析
│   ├── button_generator.py      # 按钮生成
│   ├── search_executor.py       # 搜索执行
│   └── cache_manager.py         # 缓存管理
├── utils/
│   ├── __init__.py
│   ├── bytes_helper.py          # bytes工具函数
│   └── logger.py                # 日志封装
└── config.py                    # 配置文件
```
