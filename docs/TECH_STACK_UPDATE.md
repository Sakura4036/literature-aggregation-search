# 技术栈调整说明

## 主要变更

### 1. 技术栈更新
- **Python**: 3.13 (最新版本)
- **Web框架**: FastAPI (替代Flask，提供异步支持和自动API文档)
- **数据库**: PostgreSQL 15+ (替代MySQL，更好的JSON支持和全文搜索)
- **ORM**: SQLAlchemy 2.0 异步版本
- **HTTP客户端**: httpx (异步HTTP客户端)
- **CLI框架**: Click (命令行工具)

### 2. 架构调整
- **移除Web界面**: 专注于API和CLI工具
- **异步优先**: 全面采用异步编程模式
- **API优先**: FastAPI提供自动文档和类型验证
- **CLI工具**: 提供完整的命令行操作界面

### 3. 数据库优化
- **PostgreSQL特性**: 
  - JSONB存储原始数据
  - 全文搜索索引
  - 更好的并发性能
  - 异步连接支持

### 4. 开发效率提升
- **自动API文档**: FastAPI自动生成OpenAPI文档
- **类型安全**: Pydantic模型提供数据验证
- **异步性能**: 更好的并发处理能力
- **现代Python**: 充分利用Python 3.13新特性

## 项目结构调整

```
src/
├── api/                    # FastAPI应用
│   ├── main.py            # 应用入口
│   ├── routes/            # 路由模块
│   ├── schemas.py         # Pydantic模型
│   └── dependencies.py    # 依赖注入
├── search/                # 搜索模块 (现有)
├── database/              # 数据库模块 (更新为异步)
├── processing/            # 数据处理模块
└── download/              # 下载模块

scripts/                   # CLI工具
├── cli.py                # 主CLI入口
├── search_cli.py         # 搜索命令
├── database_cli.py       # 数据库管理
└── export_cli.py         # 导出命令
```

## 开发优势

1. **性能提升**: 异步处理提高并发能力
2. **开发效率**: FastAPI自动文档和验证
3. **类型安全**: 全面的类型注解和验证
4. **现代化**: 使用最新的Python生态系统
5. **可维护性**: 清晰的模块分离和接口定义

## 下一步行动

1. 更新项目依赖 (pyproject.toml)
2. 实现FastAPI应用骨架
3. 创建CLI工具框架
4. 迁移数据库设计到PostgreSQL
5. 更新现有搜索模块支持异步