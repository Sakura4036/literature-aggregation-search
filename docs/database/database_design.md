# 综合文献数据库设计文档 (PostgreSQL)

## 概述

本文档描述了基于PostgreSQL的多源文献数据库设计。该设计整合了ArXiv、bioRxiv、Semantic Scholar、Web of Science和PubMed等多个学术数据库的数据结构，支持完整的文献信息存储、去重、合并和检索功能，充分利用PostgreSQL的高级特性如JSONB、全文搜索和异步支持。

## 设计原则

1. **统一性**: 为不同数据源的文献提供统一的数据模型
2. **可扩展性**: 支持新增数据源和字段
3. **去重性**: 通过DOI、PMID、ArXiv ID等标识符实现文献去重
4. **完整性**: 保留各数据源的原始信息
5. **检索性**: 优化索引设计以支持高效检索

## 数据源分析

### 各数据源特点对比

| 数据源 | 主要标识符 | 特色字段 | 数据类型 |
|--------|------------|----------|----------|
| PubMed | PMID, DOI | MeSH主题词, 资助信息 | 生物医学文献 |
| ArXiv | ArXiv ID, DOI | 分类标签, PDF链接 | 预印本 |
| bioRxiv | DOI | 预印本版本, 资助信息 | 生物学预印本 |
| Semantic Scholar | Paper ID, DOI | 引用关系, 影响力指标 | 跨学科文献 |
| Web of Science | UID, DOI | 引用次数, 学科分类 | 引文数据库 |

## 数据库表结构

### 1. 文章主表 (articles)

存储文章的统一基本信息，支持多数据源。

```sql
CREATE TABLE articles (
    id BIGSERIAL PRIMARY KEY,
    primary_doi VARCHAR(255) UNIQUE, -- 首选DOI，用于快速关联和保证唯一性
    title TEXT NOT NULL, -- 文章标题
    abstract TEXT, -- 摘要文本
    language VARCHAR(10) DEFAULT 'eng', -- 语言
    publication_year INTEGER, -- 发表年份
    publication_date DATE, -- 发表日期
    updated_date DATE, -- 更新日期
    
    -- 统计信息
    citation_count INTEGER DEFAULT 0, -- 引用次数
    reference_count INTEGER DEFAULT 0, -- 参考文献数量
    influential_citation_count INTEGER DEFAULT 0, -- 有影响力的引用次数
    
    -- 开放获取信息
    is_open_access BOOLEAN DEFAULT FALSE, -- 是否开放获取
    open_access_url TEXT, -- 开放获取PDF链接
    
    -- 元数据
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX idx_articles_title ON articles USING gin(to_tsvector('english', title));
CREATE INDEX idx_articles_abstract ON articles USING gin(to_tsvector('english', abstract));
CREATE INDEX idx_articles_publication_year ON articles (publication_year);
CREATE INDEX idx_articles_publication_date ON articles (publication_date);
CREATE INDEX idx_articles_citation_count ON articles (citation_count);
CREATE INDEX idx_articles_primary_doi ON articles (primary_doi);

-- 创建全文搜索索引
CREATE INDEX idx_articles_fulltext ON articles USING gin(
    to_tsvector('english', coalesce(title, '') || ' ' || coalesce(abstract, ''))
);

-- 创建更新时间触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_articles_updated_at 
    BEFORE UPDATE ON articles 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### 2. 数据源表 (data_sources)

存储各个数据源信息。

```sql
CREATE TABLE data_sources (
    id SMALLSERIAL PRIMARY KEY,
    source_name VARCHAR(50) NOT NULL UNIQUE, -- 数据源名称
    source_url VARCHAR(200), -- 数据源URL
    description TEXT, -- 数据源描述
    is_active BOOLEAN DEFAULT TRUE, -- 是否激活
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_data_sources_name ON data_sources (source_name);

-- 插入预定义数据源
INSERT INTO data_sources (source_name, source_url, description) VALUES
('pubmed', 'https://pubmed.ncbi.nlm.nih.gov/', 'PubMed生物医学文献数据库'),
('arxiv', 'https://arxiv.org/', 'ArXiv预印本服务器'),
('biorxiv', 'https://www.biorxiv.org/', 'bioRxiv生物学预印本服务器'),
('semantic_scholar', 'https://www.semanticscholar.org/', 'Semantic Scholar学术搜索引擎'),
('web_of_science', 'https://www.webofscience.com/', 'Web of Science引文数据库');
```

### 3. 文章数据源关联表 (article_sources)

记录文章来源于哪些数据源，支持同一文章来自多个数据源。

```sql
CREATE TABLE article_sources (
    id BIGSERIAL PRIMARY KEY,
    article_id BIGINT NOT NULL,
    source_id SMALLINT NOT NULL,
    source_article_id VARCHAR(100), -- 在源数据库中的ID
    source_url TEXT, -- 源数据库中的链接
    raw_data JSONB, -- 原始数据JSONB格式 (PostgreSQL优化)
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES data_sources(id),
    UNIQUE (article_id, source_id)
);

CREATE INDEX idx_article_sources_article_id ON article_sources (article_id);
CREATE INDEX idx_article_sources_source_id ON article_sources (source_id);
CREATE INDEX idx_article_sources_source_article_id ON article_sources (source_article_id);
CREATE INDEX idx_article_sources_raw_data ON article_sources USING gin(raw_data);

-- 创建更新时间触发器
CREATE TRIGGER update_article_sources_updated_at 
    BEFORE UPDATE ON article_sources 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### 4. 文章标识符表 (article_identifiers)

存储文章的各种标识符，用于去重和关联。

```sql
-- 创建标识符类型枚举
CREATE TYPE identifier_type_enum AS ENUM (
    'doi', 'pmid', 'arxiv_id', 'semantic_scholar_id', 
    'wos_uid', 'pii', 'pmc_id', 'corpus_id'
);

CREATE TABLE article_identifiers (
    id BIGSERIAL PRIMARY KEY,
    article_id BIGINT NOT NULL,
    identifier_type identifier_type_enum NOT NULL,
    identifier_value VARCHAR(200) NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE, -- 是否为主要标识符
    
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
    UNIQUE (identifier_type, identifier_value)
);

CREATE INDEX idx_article_identifiers_article_id ON article_identifiers (article_id);
CREATE INDEX idx_article_identifiers_value ON article_identifiers (identifier_value);
CREATE INDEX idx_article_identifiers_type_value ON article_identifiers (identifier_type, identifier_value);
-- 专门为DOI查询优化
CREATE INDEX idx_article_identifiers_doi ON article_identifiers (identifier_value) 
    WHERE identifier_type = 'doi';
```

### 5. 期刊/会议/预印本服务器表 (venues)

统一存储期刊、会议、预印本服务器等发表场所信息。

```sql
CREATE TABLE venues (
    id INT PRIMARY KEY AUTO_INCREMENT,
    venue_name VARCHAR(500) NOT NULL COMMENT '发表场所名称',
    venue_type ENUM('journal', 'conference', 'preprint_server', 'book', 'other') DEFAULT 'journal',
    iso_abbreviation VARCHAR(200) COMMENT 'ISO缩写',
    issn_print VARCHAR(20) COMMENT '印刷版ISSN',
    issn_electronic VARCHAR(20) COMMENT '电子版ISSN',
    publisher VARCHAR(200) COMMENT '出版商',
    country VARCHAR(100) COMMENT '国家',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_venue_name (venue_name(100)),
    INDEX idx_venue_type (venue_type),
    INDEX idx_iso_abbreviation (iso_abbreviation),
    INDEX idx_issn_print (issn_print),
    INDEX idx_issn_electronic (issn_electronic)
) COMMENT '发表场所表';
```

### 6. 文章发表信息表 (article_publications)

关联文章与发表场所，包含发表详细信息。

```sql
CREATE TABLE article_publications (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    article_id BIGINT NOT NULL,
    venue_id INT,
    volume VARCHAR(50) COMMENT '卷号',
    issue VARCHAR(50) COMMENT '期号',
    start_page VARCHAR(20) COMMENT '起始页码',
    end_page VARCHAR(20) COMMENT '结束页码',
    page_range VARCHAR(50) COMMENT '页码范围',
    article_number VARCHAR(50) COMMENT '文章编号',
    pub_model VARCHAR(100) COMMENT '发表模式',
    
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
    FOREIGN KEY (venue_id) REFERENCES venues(id),
    INDEX idx_article_id (article_id),
    INDEX idx_venue_id (venue_id),
    INDEX idx_volume_issue (volume, issue)
) COMMENT '文章发表信息表';
```

### 7. 作者表 (authors)

存储作者信息，支持多种作者名称格式。

```sql
CREATE TABLE authors (
    id INT PRIMARY KEY AUTO_INCREMENT,
    full_name VARCHAR(200) NOT NULL COMMENT '作者全名',
    last_name VARCHAR(100) COMMENT '姓',
    fore_name VARCHAR(100) COMMENT '名',
    initials VARCHAR(20) COMMENT '姓名缩写',
    orcid VARCHAR(100) COMMENT 'ORCID标识符',
    semantic_scholar_id VARCHAR(50) COMMENT 'Semantic Scholar作者ID',
    h_index INT COMMENT 'H指数',
    paper_count INT COMMENT '论文数量',
    citation_count INT COMMENT '引用次数',
    homepage VARCHAR(500) COMMENT '个人主页',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_full_name (full_name),
    INDEX idx_last_name (last_name),
    INDEX idx_fore_name (fore_name),
    INDEX idx_orcid (orcid),
    INDEX idx_semantic_scholar_id (semantic_scholar_id),
    FULLTEXT idx_author_names (full_name, last_name, fore_name)
) COMMENT '作者表';
```

### 8. 文章作者关联表 (article_authors)

关联文章与作者。

```sql
CREATE TABLE article_authors (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    article_id BIGINT NOT NULL,
    author_id INT NOT NULL,
    affiliation_id INT COMMENT '关联到affiliations表',
    author_order TINYINT NOT NULL COMMENT '作者顺序',
    is_corresponding BOOLEAN DEFAULT FALSE COMMENT '是否为通讯作者',
    
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES authors(id) ON DELETE CASCADE,
    FOREIGN KEY (affiliation_id) REFERENCES affiliations(id),
    UNIQUE KEY uk_article_author_order (article_id, author_order),
    INDEX idx_article_id (article_id),
    INDEX idx_author_id (author_id)
) COMMENT '文章作者关联表';
```

### 9. 单位表 (affiliations)

存储标准化的单位信息。

```sql
CREATE TABLE affiliations (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name TEXT NOT NULL COMMENT '单位名称',
    country VARCHAR(100) COMMENT '国家',
    ror_id VARCHAR(100) UNIQUE COMMENT 'ROR ID, 机构的唯一标识符',
    
    INDEX idx_name (name(100)),
    INDEX idx_ror_id (ror_id)
) COMMENT '单位表';
```

### 10. 学科分类表 (subject_categories)

存储各种学科分类信息（MeSH、ArXiv分类、学科领域等）。

```sql
CREATE TABLE subject_categories (
    id INT PRIMARY KEY AUTO_INCREMENT,
    category_name VARCHAR(200) NOT NULL COMMENT '分类名称',
    category_code VARCHAR(50) COMMENT '分类代码',
    category_type ENUM('mesh_descriptor', 'arxiv_category', 'field_of_study', 'wos_category', 'other') NOT NULL,
    parent_id INT COMMENT '父分类ID',
    description TEXT COMMENT '分类描述',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (parent_id) REFERENCES subject_categories(id),
    INDEX idx_category_name (category_name),
    INDEX idx_category_code (category_code),
    INDEX idx_category_type (category_type),
    INDEX idx_parent_id (parent_id)
) COMMENT '学科分类表';
```

### 11. 文章学科分类关联表 (article_categories)

关联文章与学科分类。

```sql
CREATE TABLE article_categories (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    article_id BIGINT NOT NULL,
    category_id INT NOT NULL,
    is_major_topic BOOLEAN DEFAULT FALSE COMMENT '是否为主要主题',
    confidence_score DECIMAL(3,2) COMMENT '置信度分数',
    
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES subject_categories(id) ON DELETE CASCADE,
    UNIQUE KEY uk_article_category (article_id, category_id),
    INDEX idx_article_id (article_id),
    INDEX idx_category_id (category_id),
    INDEX idx_major_topic (is_major_topic)
) COMMENT '文章学科分类关联表';
```

### 12. MeSH限定词表 (mesh_qualifiers)

存储MeSH限定词（仅用于PubMed数据）。

```sql
CREATE TABLE mesh_qualifiers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    qualifier_name VARCHAR(200) NOT NULL COMMENT 'MeSH限定词名称',
    qualifier_ui VARCHAR(20) NOT NULL COMMENT 'MeSH限定词UI',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE KEY uk_qualifier_ui (qualifier_ui),
    INDEX idx_qualifier_name (qualifier_name)
) COMMENT 'MeSH限定词表';
```

### 13. 文章MeSH限定词关联表 (article_mesh_qualifiers)

关联文章MeSH主题词与限定词。

```sql
CREATE TABLE article_mesh_qualifiers (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    article_category_id BIGINT NOT NULL COMMENT '关联到article_categories表中的MeSH记录',
    mesh_qualifier_id INT NOT NULL,
    is_major_topic BOOLEAN DEFAULT FALSE COMMENT '是否为主要主题',
    
    FOREIGN KEY (article_category_id) REFERENCES article_categories(id) ON DELETE CASCADE,
    FOREIGN KEY (mesh_qualifier_id) REFERENCES mesh_qualifiers(id) ON DELETE CASCADE,
    UNIQUE KEY uk_category_qualifier (article_category_id, mesh_qualifier_id),
    INDEX idx_article_category_id (article_category_id),
    INDEX idx_mesh_qualifier_id (mesh_qualifier_id)
) COMMENT '文章MeSH限定词关联表';
```

### 14. 发表类型表 (publication_types)

存储发表类型。

```sql
CREATE TABLE publication_types (
    id INT PRIMARY KEY AUTO_INCREMENT,
    type_name VARCHAR(200) NOT NULL COMMENT '发表类型名称',
    type_code VARCHAR(50) COMMENT '类型代码',
    source_type ENUM('pubmed', 'semantic_scholar', 'wos', 'general') DEFAULT 'general',
    description TEXT COMMENT '类型描述',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_type_name (type_name),
    INDEX idx_type_code (type_code),
    INDEX idx_source_type (source_type)
) COMMENT '发表类型表';
```

### 15. 文章发表类型关联表 (article_publication_types)

关联文章与发表类型。

```sql
CREATE TABLE article_publication_types (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    article_id BIGINT NOT NULL,
    publication_type_id INT NOT NULL,
    
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
    FOREIGN KEY (publication_type_id) REFERENCES publication_types(id) ON DELETE CASCADE,
    UNIQUE KEY uk_article_pub_type (article_id, publication_type_id),
    INDEX idx_article_id (article_id),
    INDEX idx_publication_type_id (publication_type_id)
) COMMENT '文章发表类型关联表';
```

### 16. 资助机构表 (funding_agencies)

存储资助机构信息。

```sql
CREATE TABLE funding_agencies (
    id INT PRIMARY KEY AUTO_INCREMENT,
    agency_name VARCHAR(200) NOT NULL COMMENT '机构名称',
    acronym VARCHAR(50) COMMENT '机构缩写',
    country VARCHAR(100) COMMENT '国家',
    ror_id VARCHAR(100) COMMENT 'ROR标识符',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_agency_name (agency_name),
    INDEX idx_acronym (acronym),
    INDEX idx_country (country),
    INDEX idx_ror_id (ror_id)
) COMMENT '资助机构表';
```

### 17. 文章资助信息表 (article_funding)

存储文章的资助信息。

```sql
CREATE TABLE article_funding (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    article_id BIGINT NOT NULL,
    funding_agency_id INT NOT NULL,
    grant_id VARCHAR(100) COMMENT '资助编号',
    award_id VARCHAR(100) COMMENT '奖项编号',
    
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
    FOREIGN KEY (funding_agency_id) REFERENCES funding_agencies(id) ON DELETE CASCADE,
    INDEX idx_article_id (article_id),
    INDEX idx_funding_agency_id (funding_agency_id),
    INDEX idx_grant_id (grant_id)
) COMMENT '文章资助信息表';
```

### 18. 引用关系表 (citations)

存储文章间的引用关系。

```sql
CREATE TABLE citations (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    citing_article_id BIGINT NOT NULL COMMENT '引用文章ID',
    cited_article_id BIGINT COMMENT '被引用文章ID（如果在库中）',
    cited_paper_title TEXT COMMENT '被引用文章标题',
    cited_paper_info TEXT COMMENT '被引用文章信息（原始引用格式）',
    citation_context TEXT COMMENT '引用上下文',
    is_influential BOOLEAN DEFAULT FALSE COMMENT '是否为有影响力的引用',
    
    FOREIGN KEY (citing_article_id) REFERENCES articles(id) ON DELETE CASCADE,
    FOREIGN KEY (cited_article_id) REFERENCES articles(id) ON DELETE SET NULL,
    INDEX idx_citing_article_id (citing_article_id),
    INDEX idx_cited_article_id (cited_article_id),
    INDEX idx_influential (is_influential)
) COMMENT '引用关系表';
```

### 19. 摘要结构化信息表 (abstract_sections)

存储结构化摘要信息。

```sql
CREATE TABLE abstract_sections (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    article_id BIGINT NOT NULL,
    section_label VARCHAR(100) COMMENT '章节标签(Background, Methods, Results等)',
    section_text TEXT NOT NULL COMMENT '章节内容',
    section_order TINYINT NOT NULL COMMENT '章节顺序',
    
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
    UNIQUE KEY uk_article_section_order (article_id, section_order),
    INDEX idx_article_id (article_id),
    INDEX idx_section_label (section_label)
) COMMENT '摘要结构化信息表';
```

### 20. 文章版本表 (article_versions)

存储预印本的版本信息（主要用于ArXiv和bioRxiv）。

```sql
CREATE TABLE article_versions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    article_id BIGINT NOT NULL,
    version_number VARCHAR(10) NOT NULL COMMENT '版本号',
    version_date DATE COMMENT '版本日期',
    version_comment TEXT COMMENT '版本说明',
    pdf_url TEXT COMMENT 'PDF链接',
    
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
    UNIQUE KEY uk_article_version (article_id, version_number),
    INDEX idx_article_id (article_id),
    INDEX idx_version_date (version_date)
) COMMENT '文章版本表';
```

## 数据整合策略

### 1. 文献去重规则

基于以下标识符进行去重，优先级从高到低：

1. **DOI**: 最可靠的去重标识符
2. **PMID**: PubMed唯一标识符
3. **ArXiv ID**: ArXiv预印本标识符
4. **标题+作者**: 模糊匹配作为备选方案

### 2. 数据合并策略

当发现重复文献时：

1. **保留最完整的记录**作为主记录
2. **合并所有数据源信息**到`article_sources`表
3. **统一标识符**存储到`article_identifiers`表
4. **合并统计信息**（取最大值或最新值）

### 3. 字段映射规则

| 统一字段 | PubMed | ArXiv | bioRxiv | Semantic Scholar | Web of Science |
|----------|--------|-------|---------|------------------|----------------|
| title | ArticleTitle | title | title | title | title |
| abstract | AbstractText | summary | abstract | abstract | abstract |
| authors | AuthorList | authors | authors | authors | names.authors |
| publication_date | PubDate | published | date | publicationDate | source.publishYear |
| venue | Journal.Title | journal_ref | server | venue | source.sourceTitle |
| doi | ArticleId[doi] | doi | doi | externalIds.DOI | identifiers.doi |

## 索引策略

### 主要查询索引

```sql
-- 标识符查询索引
CREATE INDEX idx_identifiers_lookup ON article_identifiers (identifier_type, identifier_value);

-- 多源文章查询索引
CREATE INDEX idx_article_sources_lookup ON article_sources (source_id, source_article_id);

-- 作者查询索引
CREATE INDEX idx_author_articles ON article_authors (author_id, article_id);

-- 时间范围查询索引
CREATE INDEX idx_publication_timeline ON articles (publication_year, publication_date);

-- 学科分类查询索引
CREATE INDEX idx_category_articles ON article_categories (category_id, is_major_topic);

-- 引用关系查询索引
CREATE INDEX idx_citation_network ON citations (citing_article_id, cited_article_id);
```

### 全文搜索索引

```sql
-- 文章内容全文搜索
ALTER TABLE articles ADD FULLTEXT(title, abstract);

-- 作者姓名全文搜索
ALTER TABLE authors ADD FULLTEXT(full_name, last_name, fore_name);

-- 期刊名称全文搜索
ALTER TABLE venues ADD FULLTEXT(venue_name, iso_abbreviation);
```

## 常用查询示例

### 1. 跨数据源查询某作者的所有文章

```sql
SELECT 
    a.title,
    a.publication_year,
    v.venue_name,
    GROUP_CONCAT(ds.source_name) as data_sources,
    GROUP_CONCAT(ai.identifier_value) as identifiers
FROM articles a
JOIN article_authors aa ON a.id = aa.article_id
JOIN authors au ON aa.author_id = au.id
LEFT JOIN article_publications ap ON a.id = ap.article_id
LEFT JOIN venues v ON ap.venue_id = v.id
JOIN article_sources asrc ON a.id = asrc.article_id
JOIN data_sources ds ON asrc.source_id = ds.id
LEFT JOIN article_identifiers ai ON a.id = ai.article_id AND ai.identifier_type = 'doi'
WHERE au.full_name LIKE '%Smith%'
GROUP BY a.id
ORDER BY a.publication_year DESC;
```

### 2. 查询特定学科领域的高引用文章

```sql
SELECT 
    a.title,
    a.citation_count,
    sc.category_name,
    GROUP_CONCAT(DISTINCT ds.source_name) as sources
FROM articles a
JOIN article_categories ac ON a.id = ac.article_id
JOIN subject_categories sc ON ac.category_id = sc.id
JOIN article_sources asrc ON a.id = asrc.article_id
JOIN data_sources ds ON asrc.source_id = ds.id
WHERE sc.category_name LIKE '%Machine Learning%'
    AND a.citation_count > 100
GROUP BY a.id
ORDER BY a.citation_count DESC
LIMIT 50;
```

### 3. 分析不同数据源的覆盖情况

```sql
SELECT 
    ds.source_name,
    COUNT(DISTINCT asrc.article_id) as article_count,
    AVG(a.citation_count) as avg_citations,
    COUNT(DISTINCT CASE WHEN ai.identifier_type = 'doi' THEN asrc.article_id END) as articles_with_doi
FROM data_sources ds
JOIN article_sources asrc ON ds.id = asrc.source_id
JOIN articles a ON asrc.article_id = a.id
LEFT JOIN article_identifiers ai ON a.id = ai.article_id
GROUP BY ds.id, ds.source_name
ORDER BY article_count DESC;
```

### 4. 查找可能重复的文献

```sql
SELECT 
    a1.id as article1_id,
    a1.title as title1,
    a2.id as article2_id,
    a2.title as title2,
    MATCH(a1.title) AGAINST(a2.title) as title_similarity
FROM articles a1
JOIN articles a2 ON a1.id < a2.id
WHERE MATCH(a1.title) AGAINST(a2.title IN BOOLEAN MODE)
    AND a1.publication_year = a2.publication_year
    AND NOT EXISTS (
        SELECT 1 FROM article_identifiers ai1
        JOIN article_identifiers ai2 ON ai1.identifier_type = ai2.identifier_type 
            AND ai1.identifier_value = ai2.identifier_value
        WHERE ai1.article_id = a1.id AND ai2.article_id = a2.id
    )
ORDER BY title_similarity DESC;
```

## 数据维护和优化

### 1. 定期维护任务

```sql
-- 更新文章统计信息
UPDATE articles a SET 
    citation_count = (
        SELECT COUNT(*) FROM citations c WHERE c.cited_article_id = a.id
    ),
    reference_count = (
        SELECT COUNT(*) FROM citations c WHERE c.citing_article_id = a.id
    );

-- 清理孤立记录
DELETE FROM article_identifiers 
WHERE article_id NOT IN (SELECT id FROM articles);

-- 更新作者统计信息
UPDATE authors au SET
    paper_count = (
        SELECT COUNT(*) FROM article_authors aa WHERE aa.author_id = au.id
    ),
    citation_count = (
        SELECT SUM(a.citation_count) 
        FROM article_authors aa 
        JOIN articles a ON aa.article_id = a.id 
        WHERE aa.author_id = au.id
    );
```

### 2. 性能优化建议

1. **分区策略**: 按发表年份对大表进行分区
2. **缓存策略**: 对热点查询结果进行缓存
3. **读写分离**: 使用主从复制分离读写操作
4. **定期分析**: 定期更新表统计信息和重建索引

### 3. 数据质量监控

```sql
-- 监控数据完整性
SELECT 
    'Articles without identifiers' as issue,
    COUNT(*) as count
FROM articles a
LEFT JOIN article_identifiers ai ON a.id = ai.article_id
WHERE ai.article_id IS NULL

UNION ALL

SELECT 
    'Articles without authors' as issue,
    COUNT(*) as count
FROM articles a
LEFT JOIN article_authors aa ON a.id = aa.article_id
WHERE aa.article_id IS NULL

UNION ALL

SELECT 
    'Invalid DOI format' as issue,
    COUNT(*) as count
FROM article_identifiers ai
WHERE ai.identifier_type = 'doi' 
    AND ai.identifier_value NOT REGEXP '^10\\.';
```

## 扩展性考虑

### 1. 新增数据源

添加新数据源时只需：

1. 在`data_sources`表中添加新记录
2. 在`article_sources`表中存储新数据源的文章
3. 根据需要扩展`identifier_type`枚举

### 2. 新增字段

可以通过以下方式扩展：

1. 在相应表中添加新字段
2. 使用JSON字段存储非结构化数据
3. 创建新的关联表存储复杂关系

### 3. 国际化支持

- 支持多语言标题和摘要
- 支持不同字符集的作者姓名
- 考虑不同地区的日期格式

这个数据库设计提供了一个完整、灵活且可扩展的解决方案，能够有效整合和管理来自多个学术数据库的文献信息。
