# 增强数据库实现任务列表

## 任务概述

基于设计文档，实现UUID主键转换、任务管理系统、文件存储管理、搜索结果格式统一，以及遵循FastAPI最佳实践的模块化服务架构。

## 实施任务

- [x] 1. UUID主键转换和数据库模型重构
  - 创建UUIDMixin基类提供统一的UUID主键支持
  - 修改所有现有模型类继承UUIDMixin，将主键从Integer/BigInteger改为UUID
  - 更新所有外键引用使用UUID类型
  - 创建数据库迁移脚本实现安全的主键类型转换
  - 更新索引和约束以支持UUID主键
  - _需求: 需求4_

- [ ] 2. 任务管理系统数据模型实现
  - 创建TaskStatus和TaskType枚举类
  - 实现Task基础模型支持Celery任务跟踪
  - 创建SearchTask模型记录搜索任务详情
  - 创建DownloadTask模型记录下载任务详情
  - 添加任务进度跟踪和重试机制字段
  - 实现任务状态变更的数据库触发器
  - _需求: 需求2_

- [ ] 3. 文件存储系统数据模型实现
  - 创建FileType枚举和File模型
  - 实现ArticleFile关联模型支持多种文件类型
  - 添加文件版本控制和哈希去重机制
  - 创建文件存储路径生成和管理逻辑
  - 实现文件元数据的JSONB存储
  - _需求: 需求3_

- [ ] 4. Pydantic Schema类重构和统一
  - 创建完整的ArticleSchema、AuthorSchema等响应模型
  - 实现LiteratureSchema与数据库模型的双向转换方法
  - 添加数据验证规则和自定义验证器
  - 创建Create、Update、Response等不同用途的Schema变体
  - 确保所有Schema支持from_orm和to_dict方法
  - _需求: 需求1, 需求6_

- [ ] 5. 模块化仓储层实现
  - 重构BaseRepository支持UUID主键和泛型类型
  - 实现ArticleRepository包含去重和复杂查询方法
  - 创建AuthorRepository支持模糊匹配和ORCID查询
  - 实现TaskRepository支持状态更新和进度跟踪
  - 创建FileRepository支持文件哈希查询和版本管理
  - 添加LiteratureRepository处理跨实体的复杂操作
  - _需求: 需求5_

- [ ] 6. 模块化服务层实现
  - 创建article_service.py实现文章CRUD操作
  - 实现author_service.py包含查找或创建作者逻辑
  - 创建task_service.py支持任务状态和进度管理
  - 实现file_service.py包含文件存储和版本控制
  - 创建literature_service.py处理文献聚合和批量操作
  - 实现query_service.py支持复杂的跨表查询
  - _需求: 需求5, 需求6_

- [ ] 7. 搜索结果格式统一和数据转换
  - 修改所有搜索引擎的_response_format方法返回LiteratureSchema
  - 实现LiteratureSchema到数据库模型的完整转换逻辑
  - 添加数据源信息的标准化处理
  - 创建搜索结果批量保存的事务处理机制
  - 实现智能去重和数据合并算法
  - _需求: 需求1_

- [ ] 8. FastAPI依赖注入和错误处理
  - 创建get_db_session依赖提供数据库会话管理
  - 实现统一的异常处理中间件
  - 添加数据验证错误的标准化响应格式
  - 创建自定义异常类和错误代码系统
  - 实现请求日志和性能监控
  - _需求: 需求6_

- [ ] 9. 文件存储服务实现
  - 创建FileStorageService支持异步文件操作
  - 实现文件哈希计算和重复检测
  - 添加文件路径生成和目录管理逻辑
  - 创建文件版本控制和回滚机制
  - 实现文件访问权限和安全检查
  - _需求: 需求3_

- [ ] 10. 数据库迁移和版本管理
  - 创建Alembic迁移环境配置
  - 编写UUID主键转换的安全迁移脚本
  - 实现新表结构的创建迁移
  - 添加数据完整性检查和验证脚本
  - 创建回滚和数据恢复机制
  - _需求: 需求7_

- [ ] 11. 集成测试和性能优化
  - 编写服务层的单元测试覆盖所有CRUD操作
  - 创建仓储层的集成测试验证数据库交互
  - 实现文献保存流程的端到端测试
  - 添加UUID性能基准测试和索引优化
  - 创建并发访问和事务处理的压力测试
  - _需求: 需求5, 需求6_

- [ ] 12. 文档和部署准备
  - 编写API文档和Schema说明
  - 创建数据库架构图和ER关系图
  - 编写部署指南和环境配置说明
  - 添加性能调优和监控配置
  - 创建数据备份和恢复流程文档
  - _需求: 需求7_