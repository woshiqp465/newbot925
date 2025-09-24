# 上传到 GitHub 的步骤

## 1. 创建 GitHub 仓库

1. 登录 [GitHub](https://github.com)
2. 点击右上角的 "+" → "New repository"
3. 填写仓库信息：
   - Repository name: `telegram-customer-bot`
   - Description: `Telegram 客服机器人 - 自动转发客户消息给管理员`
   - 选择 Public 或 Private
   - 不要初始化 README（我们已经有了）

## 2. 连接本地仓库到 GitHub

```bash
# 添加远程仓库（替换 YOUR_USERNAME）
git remote add origin https://github.com/YOUR_USERNAME/telegram-customer-bot.git

# 或使用 SSH（如果配置了 SSH key）
git remote add origin git@github.com:YOUR_USERNAME/telegram-customer-bot.git

# 推送代码
git branch -M main
git push -u origin main
```

## 3. 项目功能说明

### 核心功能
- ✅ **消息转发**：客户消息自动转发给管理员
- ✅ **快速回复**：管理员直接输入文字即可回复最近客户
- ✅ **会话管理**：追踪所有活跃会话
- ✅ **数据持久化**：SQLite 数据库存储历史记录
- ✅ **模块化架构**：清晰的代码结构，易于维护

### 技术特点
- 🔧 生产级代码质量
- 📝 完整的错误处理
- 🎯 装饰器模式应用
- 🗂️ 分层架构设计
- ⚙️ 环境变量配置

### 目录结构
```
src/
├── core/           # 核心业务逻辑
│   ├── bot.py      # 主机器人类
│   ├── router.py   # 消息路由
│   └── handlers.py # 处理器基类
├── config/         # 配置管理
├── utils/          # 工具函数
└── modules/        # 扩展模块
    └── storage/    # 数据存储
```

## 4. 部署说明

1. 克隆仓库
2. 复制 `.env.example` 为 `.env`
3. 填写你的 Bot Token 和管理员 ID
4. 安装依赖：`pip install -r requirements.txt`
5. 运行：`python main.py`

## 5. 重要文件说明

- `.env.example` - 配置模板（不包含敏感信息）
- `.gitignore` - 忽略敏感文件（.env、数据库、日志）
- `requirements.txt` - Python 依赖
- `LICENSE` - MIT 开源协议

## 注意事项

⚠️ **安全提醒**：
- 永远不要提交 `.env` 文件
- Bot Token 必须保密
- 定期备份数据库文件

🎉 项目已准备就绪，可以上传到 GitHub！
