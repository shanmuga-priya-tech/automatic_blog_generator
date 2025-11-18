import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

def crawl_links(base_url, limit=6):
    """Return up to `limit` internal links found on the base_url homepage."""
    try:
        resp = requests.get(base_url, timeout=10)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print("Crawl error:", e)
        return []
    domain = urlparse(base_url).netloc
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = urljoin(base_url, href)
        if domain in urlparse(full).netloc:
            links.add(full)
        if len(links) >= limit:
            break
    return list(links)

def extract_homepage_info(url):
    """Extract title, meta description, and h1(s) from homepage."""
    try:
        resp = requests.get(url, timeout=10)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        meta_desc = ""
        m = soup.find("meta", attrs={"name": "description"})
        if m and m.get("content"):
            meta_desc = m["content"].strip()
        h1s = [h.get_text(strip=True) for h in soup.find_all("h1")]
        return {"title": title, "meta_description": meta_desc, "headings": h1s}
    except Exception as e:
        print("extract_homepage_info error:", e)
        return {"title": "", "meta_description": "", "headings": []}
