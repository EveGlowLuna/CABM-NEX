import requests
from bs4 import BeautifulSoup
import re
import urllib.parse


def _fetch_html(url: str, headers: dict, timeout: int = 10):
    resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    return resp.text


def _parse_bing_results(html: str):
    soup = BeautifulSoup(html, "html.parser")
    # 常见选择器：.b_algo 或 li.b_algo
    items = soup.select(".b_algo")
    if not items:
        items = soup.select("li.b_algo")
    # Edge: 新版 Bing 可能使用 .b_card 或其他容器，尝试回退
    if not items:
        items = soup.select(".b_tpcn, .b_card, .b_ans")
    return items


def search_and_fetch(query: str, count: int = 3, max_length: int = 500):
    """
    在 Bing 搜索 -> 抓取网页 -> 提取关键信息
    返回列表: [{title, url, snippet, summary}]
    """
    count = max(1, int(count or 3))
    max_length = max(200, int(max_length or 500))

    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
    headers = {"User-Agent": ua, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}

    q = urllib.parse.quote_plus(query)
    # 尝试多个 host，附带区域与语言参数
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
        return {"status": "error", "error": f"获取搜索结果失败: {last_err}"}

    items = _parse_bing_results(html)
    results = []

    for item in items[:count]:
        # 标题与链接
        title_tag = item.select_one("h2 a") or item.select_one("a")
        if not title_tag:
            continue
        link = title_tag.get("href") or ""
        title = title_tag.get_text(strip=True)

        # 摘要（搜索页片段）
        desc_tag = item.select_one(".b_caption p") or item.select_one("p")
        snippet = desc_tag.get_text(strip=True) if desc_tag else ""

        # 抓取网页正文（容错）
        content = ""
        try:
            page = requests.get(link, headers=headers, timeout=10)
            psoup = BeautifulSoup(page.text, "html.parser")
            for s in psoup(["script", "style", "noscript", "header", "footer", "nav"]):
                s.extract()
            text = re.sub(r"\s+", " ", psoup.get_text(" ", strip=True))
            content = text[: max_length]
        except Exception as e:
            content = f"(抓取失败: {e})"

        # 简易 summary：优先按中文句号分句，不足再按英文标点
        def make_summary(txt: str) -> str:
            if not txt:
                return ""
            parts = re.split(r"[。.!?]\s*", txt)
            parts = [p for p in parts if p]
            return "。".join(parts[:3])

        summary = make_summary(content) or snippet

        results.append({
            "title": title,
            "url": link,
            "snippet": snippet,
            "summary": summary,
        })

    return results