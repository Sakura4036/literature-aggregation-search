 # 文献聚合搜索系统 (Literature Aggregation Search System)

一个综合性的学术文献检索和管理平台，支持跨多个学术数据库的统一搜索、智能去重、数据聚合等功能。

## 🚀 核心功能

- 🔍 **多源聚合搜索**: 同时搜索PubMed、ArXiv、bioRxiv、Semantic Scholar等数据库
- 🧠 **智能去重合并**: 基于DOI、PMID、ArXiv ID等标识符的智能去重算法
- 📊 **数据标准化**: 统一的数据格式和响应结构
- 🔧 **PubMed深度搜索**: 支持MeSH主题词和大规模结果分页处理
- ✅ **数据质量验证**: 完整的数据验证和质量评估
- 💾 **结构化存储**: 基于关系型数据库的统一数据模型

## 📋 项目状态

### ✅ 已完成功能
- [x] 多个搜索API集成 (PubMed, ArXiv, bioRxiv, Semantic Scholar, WoS)
- [x] 响应格式化器 - 统一数据格式
- [x] 搜索聚合器 - 并行搜索和结果聚合
- [x] 智能去重处理器 - 多重标识符去重
- [x] 数据合并器 - 重复文献信息合并
- [x] 数据验证器 - 质量检查和完整性验证
- [x] 完整的数据库设计文档
- [x] 项目架构设计和开发计划

### 🔄 开发中功能
- [ ] 数据库模型实现
- [ ] RESTful API接口
- [ ] Web用户界面
- [ ] 高级搜索语法

## 🛠️ 技术栈

- **后端**: Python 3.13+
- **数据库**: PostgreSQL (设计完成，待实现)
- **核心依赖**: requests, arxiv
- **API集成**: PubMed E-utilities, ArXiv API, Semantic Scholar API, bioRxiv API

## 📦 安装和使用

### 环境要求

- Python 3.13+
- 相关依赖包 (见 `pyproject.toml`)

### 安装依赖

```bash
# 使用uv (推荐)
uv sync

# 或使用pip
pip install -r requirements.txt
```

### 基本使用

#### 1. 命令行搜索

```bash
# 基本搜索
python main.py "synthetic biology" --num-results 20

# 指定数据源
python main.py "machine learning" --sources pubmed arxiv --output results.json

# 年份范围搜索
python main.py "covid-19" --sources pubmed --year 2020-2023

# 运行功能测试
python main.py --test
```

#### 2. Python API使用

```python
from src.search.aggregator import search_literature

# 执行多源搜索
results = search_literature(
    query="synthetic biology",
    sources=['pubmed', 'arxiv', 'semantic_scholar'],
    num_results=50,
    deduplicate=True
)

print(f"找到 {results['metadata']['total_results']} 篇文献")
print(f"搜索时间: {results['metadata']['search_time']:.2f}秒")
```

#### 3. 单独使用各个模块

```python
# 使用去重处理器
from src.processing.deduplicator import Deduplicator

deduplicator = Deduplicator()
unique_articles = deduplicator.deduplicate(articles)

# 使用数据验证器
from src.processing.validator import DataValidator

validator = DataValidator()
result = validator.validate_article(article)
print(f"质量分数: {result.quality_score}")
```

## 📊 数据格式

### 统一的文章数据结构

```json
{
  "article": {
    "primary_doi": "10.1000/example",
    "title": "文章标题",
    "abstract": "摘要内容",
    "publication_year": 2023,
    "publication_date": "2023-01-15",
    "citation_count": 10,
    "is_open_access": true
  },
  "authors": [
    {"full_name": "作者姓名"}
  ],
  "identifiers": [
    {
      "identifier_type": "doi",
      "identifier_value": "10.1000/example",
      "is_primary": true
    }
  ],
  "venue": {
    "venue_name": "期刊名称",
    "venue_type": "journal"
  },
  "source_specific": {
    "source": "pubmed",
    "raw": {}
  }
}
```

## 🏗️ 项目架构

```
src/
├── search/                    # 搜索模块
│   ├── aggregator.py         # 搜索聚合器 ✅
│   ├── pubmed_search.py      # PubMed搜索API ✅
│   ├── arxiv_search.py       # ArXiv搜索API ✅
│   ├── semantic_search.py    # Semantic Scholar API ✅
│   └── response_formatter.py # 响应格式化器 ✅
├── processing/                # 数据处理模块
│   ├── deduplicator.py       # 去重处理器 ✅
│   ├── merger.py             # 数据合并器 ✅
│   └── validator.py          # 数据验证器 ✅
├── database/                  # 数据库模块 (待实现)
├── api/                       # API接口模块 (待实现)
└── web/                       # Web界面模块 (待实现)
```

## 📚 文档

- [架构设计文档](docs/architecture.md) - 系统整体架构设计
- [数据库设计文档](docs/database_design.md) - 完整的数据库架构
- [产品需求文档](docs/PRD-v1.0.md) - 详细的功能规划
- [开发路线图](docs/development-roadmap.md) - 开发计划和进度

## 🧪 测试

```bash
# 运行功能测试
python test_aggregator.py

# 或通过主程序运行测试
python main.py --test
```

## 🤝 贡献

欢迎贡献代码！请查看 [开发路线图](docs/development-roadmap.md) 了解当前的开发优先级。

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🔗 相关链接

- [PubMed E-utilities API](https://www.ncbi.nlm.nih.gov/books/NBK25501/)
- [ArXiv API](https://arxiv.org/help/api)
- [Semantic Scholar API](https://api.semanticscholar.org/)
- [bioRxiv API](https://api.biorxiv.org/)

---

**注意**: 这是一个正在积极开发中的项目。核心搜索和去重功能已经可用，数据库和Web界面正在开发中。
