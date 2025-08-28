import requests
from bs4 import BeautifulSoup
import re
import urllib.parse
import json
from typing import List, Dict, Optional
import time


def _fetch_html(url: str, headers: dict, timeout: int = 10):
    resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    return resp.text


def _extract_main_content(soup: BeautifulSoup) -> str:
    """
    尝试提取网页的主要内容，去除导航、广告等无关内容
    """
    # 移除无关标签
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside", "advertisement"]):
        tag.decompose()
    
    # 尝试查找主要内容容器
    content_selectors = [
        "article",
        "[role='main']",
        "main",
        ".content",
        ".post-content",
        ".article-content",
        ".entry-content",
        "#content",
        ".main-content"
    ]
    
    main_content = None
    for selector in content_selectors:
        elements = soup.select(selector)
        if elements:
            main_content = elements[0]
            break
    
    # 如果没找到特定的主要内容容器，则使用body
    if not main_content:
        main_content = soup.find('body')
    
    if main_content:
        # 提取文本并清理
        text = main_content.get_text(separator=' ', strip=True)
        # 清理多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        return text
    
    # 最后的备选方案
    return soup.get_text(separator=' ', strip=True)


def _generate_better_summary(text: str, max_sentences: int = 3) -> str:
    """
    生成更好的摘要，尝试提取最重要的句子
    """
    if not text:
        return ""
    
    # 分割句子，支持中英文标点
    sentences = re.split(r'[。.!?！？\n]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        return ""
    
    # 如果句子较少，直接返回
    if len(sentences) <= max_sentences:
        return ''.join(sentences) if re.search(r'[\u4e00-\u9fff]', text) else '. '.join(sentences)
    
    # 简单的关键句提取逻辑：
    # 1. 第一句通常比较重要
    # 2. 包含较多汉字或单词的句子可能更重要
    # 3. 包含数字、引号的内容可能更重要
    
    scored_sentences = []
    for i, sentence in enumerate(sentences):
        score = 0
        
        # 第一句加分
        if i == 0:
            score += 10
        
        # 计算汉字数量
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', sentence))
        score += chinese_chars * 0.5
        
        # 计算单词数量
        words = re.findall(r'[a-zA-Z]+', sentence)
        score += len(words) * 0.3
        
        # 包含数字加分
        if re.search(r'\d+', sentence):
            score += 3
        
        # 包含引号加分
        if re.search(r'[“”"\'‘’]', sentence):
            score += 2
            
        scored_sentences.append((sentence, score))
    
    # 按分数排序，取前几句
    scored_sentences.sort(key=lambda x: x[1], reverse=True)
    top_sentences = sorted(scored_sentences[:max_sentences], key=lambda x: sentences.index(x[0]))
    
    # 根据文本主要语言决定连接符
    if re.search(r'[\u4e00-\u9fff]', text):
        return ''.join([s[0] for s in top_sentences])
    else:
        return '. '.join([s[0] for s in top_sentences])


def _parse_bing_results(html: str):
    """
    解析Bing搜索结果
    """
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(".b_algo")
    if not items:
        items = soup.select("li.b_algo")
    if not items:
        items = soup.select(".b_tpcn, .b_card, .b_ans")
    return items


def _parse_google_results(html: str):
    """
    解析Google搜索结果
    """
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(".g")
    return items


def _parse_baidu_results(html: str):
    """
    解析百度搜索结果
    """
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(".result")
    return items


def _search_bing(query: str, count: int = 3) -> List[Dict]:
    """
    使用Bing搜索
    """
    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
    headers = {"User-Agent": ua, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}

    q = urllib.parse.quote_plus(query)
    search_urls = [
        f"https://www.bing.com/search?q={q}&mkt=zh-CN&setlang=zh-CN&safeSearch=Moderate",
        f"https://cn.bing.com/search?q={q}&mkt=zh-CN&setlang=zh-CN&safeSearch=Moderate",
    ]

    html = None
    last_err = None
    for url in search_urls:
        try:
            html = _fetch_html(url, headers=headers, timeout=10)
            if html and len(html) > 2000:
                break
        except Exception as e:
            last_err = e
            continue

    if not html:
        return []

    items = _parse_bing_results(html)
    results = []

    for item in items[:count]:
        title_tag = item.select_one("h2 a") or item.select_one("a")
        if not title_tag:
            continue
        link = title_tag.get("href") or ""
        title = title_tag.get_text(strip=True)

        desc_tag = item.select_one(".b_caption p") or item.select_one("p")
        snippet = desc_tag.get_text(strip=True) if desc_tag else ""

        results.append({
            "title": title,
            "url": link,
            "snippet": snippet,
            "engine": "bing"
        })

    return results


def _search_google(query: str, count: int = 3) -> List[Dict]:
    """
    使用Google搜索（受限于反爬机制）
    """
    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
    headers = {"User-Agent": ua, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}

    q = urllib.parse.quote_plus(query)
    search_url = f"https://www.google.com/search?q={q}&hl=zh-CN&num={count}"

    try:
        html = _fetch_html(search_url, headers=headers, timeout=10)
    except:
        return []

    items = _parse_google_results(html)
    results = []

    for item in items[:count]:
        title_tag = item.select_one("h3") or item.select_one("a")
        if not title_tag:
            continue
            
        # Google搜索结果链接处理
        link_elem = item.select_one("a")
        link = link_elem.get("href") if link_elem else ""
        
        title = title_tag.get_text(strip=True)
        
        # 提取描述文本
        desc_container = item.select_one(".VwiC3b") or item.select_one("span") 
        snippet = desc_container.get_text(strip=True) if desc_container else ""

        results.append({
            "title": title,
            "url": link,
            "snippet": snippet,
            "engine": "google"
        })

    return results


def _search_baidu(query: str, count: int = 3) -> List[Dict]:
    """
    使用百度搜索
    """
    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
    headers = {"User-Agent": ua, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}

    q = urllib.parse.quote_plus(query)
    search_url = f"https://www.baidu.com/s?wd={q}&rn={count}"

    try:
        html = _fetch_html(search_url, headers=headers, timeout=10)
    except:
        return []

    items = _parse_baidu_results(html)
    results = []

    for item in items[:count]:
        title_tag = item.select_one("h3 a") or item.select_one("a")
        if not title_tag:
            continue
        link = title_tag.get("href") or ""
        title = title_tag.get_text(strip=True)

        desc_tag = item.select_one(".c-abstract") or item.select_one("p")
        snippet = desc_tag.get_text(strip=True) if desc_tag else ""

        results.append({
            "title": title,
            "url": link,
            "snippet": snippet,
            "engine": "baidu"
        })

    return results


def _deduplicate_results(all_results: List[Dict]) -> List[Dict]:
    """
    基于URL去重搜索结果
    """
    unique_results = []
    seen_urls = set()
    for result in all_results:
        url = result.get('url', '')
        if url and url not in seen_urls:
            unique_results.append(result)
            seen_urls.add(url)
    return unique_results

def _fetch_and_process_webpage(link: str, headers: dict, max_length: int) -> str:
    """
    抓取并处理网页内容
    """
    try:
        page = requests.get(link, headers=headers, timeout=10)
        page.raise_for_status()
        # 检查内容类型，只处理HTML和文本内容
        content_type = page.headers.get('content-type', '').lower()
        if 'html' not in content_type and 'text' not in content_type:
            return ""
            
        psoup = BeautifulSoup(page.text, "html.parser")
        return _extract_main_content(psoup)[:max_length]
    except Exception as e:
        return f"(抓取失败: {e})"

def search_and_fetch(query: str, count: int = 3, max_length: int = 1000):
    """
    在多个搜索引擎搜索 -> 抓取网页 -> 提取关键信息
    返回列表: [{title, url, snippet, summary}]
    """
    count = max(1, int(count or 3))
    max_length = max(200, int(max_length or 1000))

    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
    headers = {"User-Agent": ua, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}

    # 从多个搜索引擎获取结果
    all_results = []
    
    search_engines = [
        ("bing", _search_bing),
        ("baidu", _search_baidu),
        ("google", _search_google)
    ]
    
    for engine_name, search_func in search_engines:
        try:
            results = search_func(query, count)
            all_results.extend(results)
            time.sleep(0.5)
        except Exception as e:
            continue

    # 去重：基于URL
    unique_results = _deduplicate_results(all_results)
    
    # 限制结果数量
    unique_results = unique_results[:count]
    results = []

    for item in unique_results:
        link = item.get("url", "")
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        engine = item.get("engine", "")

        # 抓取网页正文（容错）
        content = _fetch_and_process_webpage(link, headers, max_length)

        # 生成更好的摘要
        summary = _generate_better_summary(content) or snippet

        results.append({
            "title": title,
            "url": link,
            "snippet": snippet,
            "summary": summary,
            "engine": engine
        })

    return results