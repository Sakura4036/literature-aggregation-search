import xml.etree.ElementTree as ET
import json
from typing import Dict, List, Optional, Any


def parse_pubmed_article_to_json(xml_content: str) -> List[Dict[str, Any]]:
    """
    将PubmedArticle的XML内容解析为JSON格式
    
    Args:
        xml_content: PubmedArticle的XML字符串内容
        
    Returns:
        List[Dict[str, Any]]: 解析后的文章信息列表，每个元素为一个文章的字典
    """
    try:
        root = ET.fromstring(xml_content)
        articles = []
        
        # 遍历每篇文章
        for article in root.findall('.//PubmedArticle'):
            article_data = parse_single_article(article)
            if article_data:
                _data = {}
                for k in ['pmid', 'title', 'mesh_headings','abstract']:
                    _data[k] = article_data[k]
                articles.append(_data)
                
        return articles
        
    except ET.ParseError as e:
        raise ValueError(f"XML解析错误: {e}")
    except Exception as e:
        raise RuntimeError(f"解析PubMed数据时发生错误: {e}")


def parse_single_article(article: ET.Element) -> Dict[str, Any]:
    """
    解析单个PubmedArticle元素
    
    Args:
        article: PubmedArticle的XML元素
        
    Returns:
        Dict[str, Any]: 解析后的文章信息字典
    """
    article_data = {}
    
    # 基本信息
    article_data.update(_parse_basic_info(article))
    
    # 期刊信息
    article_data.update(_parse_journal_info(article))
    
    # 作者信息
    article_data['authors'] = _parse_authors(article)
    
    # 摘要信息
    article_data['abstract'] = _parse_abstract(article)
    
    # 日期信息
    article_data.update(_parse_dates(article))
    
    # 标识符信息
    article_data['identifiers'] = _parse_identifiers(article)
    
    # MeSH主题词
    article_data['mesh_headings'] = _parse_mesh_headings(article)
    
    # 发表类型
    article_data['publication_types'] = _parse_publication_types(article)
    
    # 资助信息
    article_data['grants'] = _parse_grants(article)
    
    # 参考文献
    article_data['references'] = _parse_references(article)
    
    # 语言
    article_data['language'] = _get_text_safe(article, './/Language')
    
    # 页码信息
    article_data.update(_parse_pagination(article))
    
    return article_data


def _parse_basic_info(article: ET.Element) -> Dict[str, Any]:
    """解析基本信息"""
    return {
        'pmid': _get_text_safe(article, './/PMID'),
        'title': _get_text_safe(article, './/ArticleTitle'),
        'medline_citation_status': _get_attr_safe(article, './/MedlineCitation', 'Status'),
        'medline_citation_owner': _get_attr_safe(article, './/MedlineCitation', 'Owner'),
        'indexing_method': _get_attr_safe(article, './/MedlineCitation', 'IndexingMethod'),
    }


def _parse_journal_info(article: ET.Element) -> Dict[str, Any]:
    """解析期刊信息"""
    journal_info = {
        'journal_title': _get_text_safe(article, './/Journal/Title'),
        'journal_iso_abbreviation': _get_text_safe(article, './/Journal/ISOAbbreviation'),
        'issn_print': _get_text_safe(article, './/Journal/ISSN[@IssnType="Print"]'),
        'issn_electronic': _get_text_safe(article, './/Journal/ISSN[@IssnType="Electronic"]'),
        'volume': _get_text_safe(article, './/Journal/JournalIssue/Volume'),
        'issue': _get_text_safe(article, './/Journal/JournalIssue/Issue'),
        'pub_model': _get_attr_safe(article, './/Article', 'PubModel'),
    }
    
    # 期刊发表日期
    pub_date = article.find('.//Journal/JournalIssue/PubDate')
    if pub_date is not None:
        journal_info['journal_pub_date'] = _parse_pub_date(pub_date)
    
    return journal_info


def _parse_authors(article: ET.Element) -> List[Dict[str, Any]]:
    """解析作者信息"""
    authors = []
    author_list = article.findall('.//Author')
    
    for author in author_list:
        author_info = {
            'last_name': _get_text_safe(author, 'LastName'),
            'fore_name': _get_text_safe(author, 'ForeName'),
            'initials': _get_text_safe(author, 'Initials'),
            'valid_yn': _get_attr_safe(author, '.', 'ValidYN'),
            'affiliations': []
        }
        
        # 解析作者单位信息
        affiliations = author.findall('.//AffiliationInfo/Affiliation')
        for affiliation in affiliations:
            if affiliation.text:
                author_info['affiliations'].append(affiliation.text)
        
        authors.append(author_info)
    
    return authors


def _parse_abstract(article: ET.Element) -> Dict[str, Any]:
    """解析摘要信息"""
    abstract_info = {
        'text': '',
        'structured': []
    }
    
    # 简单摘要
    abstract_text = article.find('.//AbstractText')
    if abstract_text is not None and abstract_text.text:
        abstract_info['text'] = abstract_text.text
    
    # 结构化摘要
    structured_abstracts = article.findall('.//AbstractText[@Label]')
    for abstract in structured_abstracts:
        if abstract.text:
            abstract_info['structured'].append({
                'label': abstract.get('Label', ''),
                'text': abstract.text
            })
    
    return abstract_info


def _parse_dates(article: ET.Element) -> Dict[str, Any]:
    """解析各种日期信息"""
    dates = {}
    
    # 完成日期
    date_completed = article.find('.//DateCompleted')
    if date_completed is not None:
        dates['date_completed'] = _parse_date_element(date_completed)
    
    # 修订日期
    date_revised = article.find('.//DateRevised')
    if date_revised is not None:
        dates['date_revised'] = _parse_date_element(date_revised)
    
    # 电子发表日期
    article_date = article.find('.//ArticleDate[@DateType="Electronic"]')
    if article_date is not None:
        dates['electronic_pub_date'] = _parse_date_element(article_date)
    
    # PubMed历史日期
    pub_dates = []
    history_dates = article.findall('.//PubMedPubDate')
    for pub_date in history_dates:
        pub_status = pub_date.get('PubStatus', '')
        date_info = _parse_date_element(pub_date)
        if date_info:
            date_info['pub_status'] = pub_status
            pub_dates.append(date_info)
    
    dates['pubmed_pub_dates'] = pub_dates
    
    return dates


def _parse_identifiers(article: ET.Element) -> Dict[str, str]:
    """解析各种标识符"""
    identifiers = {}
    
    article_ids = article.findall('.//ArticleId')
    for article_id in article_ids:
        id_type = article_id.get('IdType', '')
        if article_id.text and id_type:
            identifiers[id_type] = article_id.text
    
    # ELocationID (通常是DOI)
    elocation_id = article.find('.//ELocationID[@EIdType="doi"]')
    if elocation_id is not None and elocation_id.text:
        identifiers['elocation_doi'] = elocation_id.text
    
    return identifiers


def _parse_mesh_headings(article: ET.Element) -> List[Dict[str, Any]]:
    """解析MeSH主题词"""
    mesh_headings = []
    
    mesh_heading_list = article.findall('.//MeshHeading')
    for mesh_heading in mesh_heading_list:
        descriptor = mesh_heading.find('DescriptorName')
        if descriptor is not None:
            mesh_info = {
                'descriptor_name': descriptor.text or '',
                'descriptor_ui': descriptor.get('UI', ''),
                'major_topic_yn': descriptor.get('MajorTopicYN', 'N'),
                'qualifiers': []
            }
            
            # 解析限定词
            qualifiers = mesh_heading.findall('QualifierName')
            for qualifier in qualifiers:
                qualifier_info = {
                    'qualifier_name': qualifier.text or '',
                    'qualifier_ui': qualifier.get('UI', ''),
                    'major_topic_yn': qualifier.get('MajorTopicYN', 'N')
                }
                mesh_info['qualifiers'].append(qualifier_info)
            
            mesh_headings.append(mesh_info)
    
    return mesh_headings


def _parse_publication_types(article: ET.Element) -> List[Dict[str, str]]:
    """解析发表类型"""
    pub_types = []
    
    pub_type_list = article.findall('.//PublicationType')
    for pub_type in pub_type_list:
        if pub_type.text:
            pub_types.append({
                'type': pub_type.text,
                'ui': pub_type.get('UI', '')
            })
    
    return pub_types


def _parse_grants(article: ET.Element) -> List[Dict[str, str]]:
    """解析资助信息"""
    grants = []
    
    grant_list = article.findall('.//Grant')
    for grant in grant_list:
        grant_info = {
            'grant_id': _get_text_safe(grant, 'GrantID'),
            'acronym': _get_text_safe(grant, 'Acronym'),
            'agency': _get_text_safe(grant, 'Agency'),
            'country': _get_text_safe(grant, 'Country')
        }
        grants.append(grant_info)
    
    return grants


def _parse_references(article: ET.Element) -> List[Dict[str, Any]]:
    """解析参考文献"""
    references = []
    
    reference_list = article.findall('.//Reference')
    for reference in reference_list:
        ref_info = {
            'citation': _get_text_safe(reference, 'Citation'),
            'article_ids': {}
        }
        
        # 解析参考文献的ArticleId
        article_ids = reference.findall('.//ArticleId')
        for article_id in article_ids:
            id_type = article_id.get('IdType', '')
            if article_id.text and id_type:
                ref_info['article_ids'][id_type] = article_id.text
        
        references.append(ref_info)
    
    return references


def _parse_pagination(article: ET.Element) -> Dict[str, str]:
    """解析页码信息"""
    return {
        'start_page': _get_text_safe(article, './/StartPage'),
        'end_page': _get_text_safe(article, './/EndPage'),
        'medline_pgn': _get_text_safe(article, './/MedlinePgn')
    }


def _parse_date_element(date_element: ET.Element) -> Optional[Dict[str, Any]]:
    """解析日期元素"""
    if date_element is None:
        return None
    
    year = _get_text_safe(date_element, 'Year')
    month = _get_text_safe(date_element, 'Month')
    day = _get_text_safe(date_element, 'Day')
    hour = _get_text_safe(date_element, 'Hour')
    minute = _get_text_safe(date_element, 'Minute')
    
    date_info = {
        'year': year,
        'month': month,
        'day': day,
        'hour': hour,
        'minute': minute
    }
    
    # 尝试构建ISO格式日期
    try:
        if year:
            date_str = year
            if month:
                # 处理月份名称
                if month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                           'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']:
                    month_num = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'].index(month) + 1
                    date_str += f"-{month_num:02d}"
                else:
                    date_str += f"-{month.zfill(2)}"
                
                if day:
                    date_str += f"-{day.zfill(2)}"
                    
                    if hour and minute:
                        date_str += f"T{hour.zfill(2)}:{minute.zfill(2)}:00"
            
            date_info['iso_date'] = date_str
    except:
        pass
    
    return date_info


def _parse_pub_date(pub_date_element: ET.Element) -> Optional[Dict[str, str]]:
    """解析发表日期"""
    if pub_date_element is None:
        return None
    
    return {
        'year': _get_text_safe(pub_date_element, 'Year'),
        'month': _get_text_safe(pub_date_element, 'Month'),
        'day': _get_text_safe(pub_date_element, 'Day'),
        'season': _get_text_safe(pub_date_element, 'Season'),
        'medline_date': _get_text_safe(pub_date_element, 'MedlineDate')
    }


def _get_text_safe(element: ET.Element, xpath: str) -> str:
    """安全获取元素文本内容"""
    try:
        found = element.find(xpath)
        return found.text if found is not None and found.text else ''
    except:
        return ''


def _get_attr_safe(element: ET.Element, xpath: str, attr: str) -> str:
    """安全获取元素属性"""
    try:
        found = element.find(xpath)
        return found.get(attr, '') if found is not None else ''
    except:
        return ''


def save_to_json_file(articles: List[Dict[str, Any]], filename: str) -> None:
    """
    将解析结果保存为JSON文件
    
    Args:
        articles: 解析后的文章列表
        filename: 输出文件名
    """
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    # 测试代码
    # with open('templates/temp_pubmed.xml', 'r', encoding='utf-8') as f:
    with open('temp.xml', 'r', encoding='utf-8') as f:
        xml_content = f.read()
    
    try:
        articles = parse_pubmed_article_to_json(xml_content)
        print(f"成功解析 {len(articles)} 篇文章")
        
        # 保存为JSON文件
        save_to_json_file(articles, 'parsed_articles.json')
        print("结果已保存到 parsed_articles.json")
        
        # 打印第一篇文章的信息（格式化输出）
        if articles:
            print("\n第一篇文章信息:")
            print(json.dumps(articles[0], ensure_ascii=False, indent=2))
            
    except Exception as e:
        print(f"解析失败: {e}")