#!/usr/bin/env python3
"""
automatic_blog_pipeline.py

Single-file POC:
- Crawl (small depth) -> extract text -> company profile
- Generate topics (10)
- For last-10 topics: generate guideline -> generate blog -> save
"""

import os
import re
import json
import time
import requests
import tldextract
import trafilatura
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv
from openai import AzureOpenAI  

# ---------------------------
# Load env
# ---------------------------
load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_API_VERSION")
)

# ---------------------------
# Utilities
# ---------------------------

def safe_slug(text: str, max_length: int = 80) -> str:
    """Create a safe underscore_slug from a title (lowercase, alnum + _)."""
    text = (text or "").lower().strip()
    # replace & with and
    text = text.replace("&", "and")
    # remove anything not alnum or whitespace or hyphen
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    # convert whitespace to underscore
    text = re.sub(r"\s+", "_", text)
    # shorten
    return text[:max_length].strip("_")

def clean_and_parse_json(model_output: str):
    """
    Remove markdown fences like ```json ... ``` and parse JSON.
    Returns a Python object or {'raw_output': <string>} on parse failure.
    """
    if not model_output:
        return {}
    cleaned = re.sub(r"^```(?:json)?\s*|```$", "", model_output.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # best-effort: try to find a JSON block inside text
        m = re.search(r"\{[\s\S]*\}", cleaned)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        # fallback
        return {"raw_output": model_output}

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

# ---------------------------
# Crawling & extraction
# ---------------------------

def crawl_links(base_url, limit=5):
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

def extract_clean_text(url):
    """Use trafilatura to fetch and extract readable text, then filter template junk."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return ""
        raw = trafilatura.extract(downloaded) or ""
        # heuristics to remove nav/template junk
        blacklist = [
            "home", "about us", "service", "menu", "shop", "team", "cms", "blog",
            "portfolio", "sign in", "sign up", "login", "password", "404", "licenses",
            "changelog", "privacy", "terms", "utility", "book a meeting",
            "product is not available in this quantity",
            "request a free quote", "thank you! your submission has been received",
            "oops! something went wrong"
        ]
        filtered = []
        for line in raw.splitlines():
            if not line:
                continue
            low = line.lower()
            if any(b in low for b in blacklist):
                continue
            if len(line.strip()) < 30:
                continue
            filtered.append(line.strip())
        return "\n".join(filtered)
    except Exception as e:
        print(f"extract_clean_text error for {url}:", e)
        return ""

# ---------------------------
# generation
# ---------------------------

def summarize_company_info(text, base_url):
    """
    Create a structured company profile JSON using the model.
    Saved as <domain>_company.json
    """
    prompt = f"""You are a business analyst.
Summarize the company from the following website text. If company name isn't explicit, infer it from the title/meta.
Return ONLY valid JSON with keys:
- company_name
- industry
- main_products_services (array)
- target_audience
- tone
- keywords (array)
    
Website text (truncated to 8000 chars):
{text[:8000]}
"""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a structured JSON data extractor."},
                {"role": "user", "content": prompt}
            ]
        )
    except Exception as e:
        print("OpenAI summarize_company_info API error:", e)
        return {}

    raw = resp.choices[0].message.content.strip()
    parsed = clean_and_parse_json(raw)

    # save file
    domain_info = tldextract.extract(base_url)
    domain_name = f"{domain_info.domain}.{domain_info.suffix}"
    file_name = f"{domain_name}_company.json"
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=2, ensure_ascii=False)
    print(f"Saved company profile → {file_name}")
    return parsed

def generate_blog_topics(company_profile_json, base_url):
    """Generate 10 SEO-optimized topics (JSON array) and save as <domain>_topics.json"""
    prompt = f"""You are an expert SEO content strategist.
Input company profile:
{json.dumps(company_profile_json, ensure_ascii=False)}

Generate 10 blog post topics tailored to this company with high ranking potential.
Return a JSON array of 10 objects with:
- title
- primary_keyword
- long_tail_keywords (array, 2-3 items)
- intent (informational/commercial/transactional)
- why_it_fits_company (1-2 lines)
- SEO_priority_score (1-100)

Return ONLY JSON (no commentary, no markdown fences).
"""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an SEO strategist that returns only JSON arrays."},
                {"role": "user", "content": prompt}
            ]
        )
    except Exception as e:
        print("OpenAI generate_blog_topics API error:", e)
        return []

    raw = resp.choices[0].message.content.strip()
    parsed = clean_and_parse_json(raw)

    domain_info = tldextract.extract(base_url)
    domain_name = f"{domain_info.domain}.{domain_info.suffix}"
    file_name = f"{domain_name}_topics.json"
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=2, ensure_ascii=False)
    print(f"Saved topics → {file_name}")
    return parsed

def generate_guideline_text(topic, company_profile):
    """Return a concise guideline text (plain text) for a given topic and company profile."""
    prompt = f"""
You are an expert SEO content strategist and editor.
Create a detailed, structured writing guideline for the blog topic below.
Return the guideline as plain text (not JSON). Make it concise but actionable.

TOPIC:
Title: {topic.get('title')}
Primary Keyword: {topic.get('primary_keyword')}
Long-tail Keywords: {', '.join(topic.get('long_tail_keywords', []) or [])}
Intent: {topic.get('intent')}

COMPANY PROFILE:
{json.dumps(company_profile, indent=2, ensure_ascii=False)}

Guideline must include (clearly labelled sections):
- Suggested final blog title
- Meta description (<= 155 characters)
- Target audience
- Tone & voice
- Target word count
- H1, H2 (4-7 headings), with 1–3 bullet points under each H2 describing what to cover
- Suggested CTAs
- SEO notes: primary+long-tail placement advice, LSI ideas, keyword density target
"""
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are an SEO guideline generator."},
                      {"role": "user", "content": prompt}]
        )
    except Exception as e:
        print("OpenAI generate_guideline_text API error:", e)
        return ""

    return res.choices[0].message.content.strip()

def generate_blog_from_guideline(topic, guideline_text, company_profile, base_url=None):
    """Generate a full SEO-optimized blog (Markdown) using guideline + topic + company_profile."""
    prompt = f"""
You are an expert SEO copywriter. Using the guideline below, write a full SEO-optimized blog article in Markdown.
Follow the guideline strictly. Use headings (H1, H2, H3) and include paragraphs and bullet lists where applicable.

TOPIC:
{json.dumps(topic, indent=2, ensure_ascii=False)}

GUIDELINE:
{guideline_text}

COMPANY PROFILE:
{json.dumps(company_profile, indent=2, ensure_ascii=False)}

REQUIREMENTS:
- Output in Markdown (.md). Start with the meta title and meta description as HTML comments at the top:
  <!-- META_TITLE: ... -->
  <!-- META_DESC: ... -->
- Use the title from the guideline (or topic title) as H1.
- For each H2 in the guideline, create a well-written section of ~150-400 words (adjust to reach the target word count).
- Use bullet points for any lists specified in the guideline.
- Include local references / the company name naturally (do not spam).
- Insert suggested CTAs near the end and include an example button text.
- SEO: aim for ~1% keyword density for the primary keyword (use it naturally), include 2–3 long-tail keywords and LSI words.
- Include a short FAQ section if the guideline suggests.
- Do not invent unsupported statistics. If you include numbers, mark them as 'source needed'.
- Do NOT output JSON, only Markdown content.

{("BASE_URL: " + base_url) if base_url else ""}
"""
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are an SEO blog writer."},
                      {"role": "user", "content": prompt}]
        )
    except Exception as e:
        print("OpenAI generate_blog_from_guideline API error:", e)
        return ""

    return res.choices[0].message.content.strip()

# ---------------------------
# Pipeline
# ---------------------------

def run_full_pipeline():
    base_url = input("Enter website URL: ").strip()
    if not base_url:
        print("No URL provided. Exiting.")
        return

    # Crawl links
    print("\nCrawling homepage for internal links...")
    links = crawl_links(base_url, limit=6)
    print(f"Found {len(links)} links.")

    # Extract homepage info
    homepage_info = extract_homepage_info(base_url)

    # Extract text from links and combine
    print("Extracting content from links...")
    texts = []
    for u in links:
        t = extract_clean_text(u)
        if t:
            texts.append(t)
        time.sleep(0.2)

    combined_text = (
        f"WEBSITE TITLE: {homepage_info.get('title','')}\n"
        f"META DESCRIPTION: {homepage_info.get('meta_description','')}\n"
        f"HEADINGS: {', '.join(homepage_info.get('headings',[]))}\n\n"
        + "\n\n".join(texts)
    )

    # Summarize company profile
    print("Summarizing company profile...")
    company_profile = summarize_company_info(combined_text, base_url)

    if not company_profile:
        print("Company profile generation failed.")
        return

    # Generate topics (or reuse existing topics file if exists)
    domain_info = tldextract.extract(base_url)
    domain_name = f"{domain_info.domain}.{domain_info.suffix}"
    topics_file = f"{domain_name}_topics.json"

    if os.path.exists(topics_file):
        print(f"Loading existing topics file: {topics_file}")
        with open(topics_file, "r", encoding="utf-8") as f:
            topics = json.load(f)
    else:
        print("Generating 10 topics...")
        topics = generate_blog_topics(company_profile, base_url)
        if not topics:
            print("Topic generation failed.")
            return

    # Ensure output dirs
    ensure_dir("guidelines")
    ensure_dir("blogs")

    # Process only last 10 topics
    topics_to_process = topics[-2:] if isinstance(topics, list) else []
    print(f"\nProcessing {len(topics_to_process)} topic(s) (the last batch).")

    for topic in topics_to_process:
        title = topic.get("title") or "untitled"
        slug = safe_slug(title)
        guideline_path = f"guidelines/{slug}_guideline.txt"
        blog_path = f"blogs/{slug}_blog.md"

        if os.path.exists(guideline_path) and os.path.exists(blog_path):
            print(f"Skipping '{title}' — guideline and blog already exist.")
            continue

        # 1) Generate guideline text and save
        print(f"\n--- Generating guideline for: {title}")
        guideline_text = generate_guideline_text(topic, company_profile)
        if not guideline_text:
            print("Guideline generation failed — skipping this topic.")
            continue
        with open(guideline_path, "w", encoding="utf-8") as f:
            f.write(guideline_text)
        print(f"Saved guideline → {guideline_path}")

        # 2) Generate blog from guideline and save
        print(f"--- Generating blog for: {title}")
        blog_md = generate_blog_from_guideline(topic, guideline_text, company_profile, base_url=base_url)
        if not blog_md:
            print("Blog generation failed — skipping.")
            continue
        with open(blog_path, "w", encoding="utf-8") as f:
            f.write(blog_md)
        print(f"Saved blog → {blog_path}")

        time.sleep(0.5)

    print("\n✅ Pipeline finished. Check guidelines/ and blogs/ folders.")

# ---------------------------
# Entry
# ---------------------------
if __name__ == "__main__":
    run_full_pipeline()
