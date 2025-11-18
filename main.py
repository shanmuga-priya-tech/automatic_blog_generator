# main.py
import os
import time
import json
import tldextract
import trafilatura

from utils.openai_client import get_client

from company.extractor import crawl_links, extract_homepage_info
from company.summariser import summarize_company_info
from topics.generator import generate_blog_topics
from guidelines.generator import generate_guideline_text, save_guideline_text
from blogs.generator import generate_blog_from_guideline, save_blog_md

# initialize client
client = get_client()

def extract_clean_text(url):
    """Use trafilatura to fetch and extract readable text, then filter template junk."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return ""
        raw = trafilatura.extract(downloaded) or ""
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

def run_full_pipeline():
    base_url = input("Enter website URL: ").strip()
    if not base_url:
        print("No URL provided. Exiting.")
        return

    print("\n➡ Crawling homepage for internal links...")
    links = crawl_links(base_url, limit=6)
    print(f"Found {len(links)} links")

    homepage_info = extract_homepage_info(base_url)

    print("➡ Extracting content from links...")
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

    print("➡ Summarizing company profile...")
    company_profile = summarize_company_info(client, combined_text, base_url)
    if not company_profile:
        print("Company profile generation failed. Exiting.")
        return

    domain_info = tldextract.extract(base_url)
    domain_name = f"{domain_info.domain}.{domain_info.suffix}"
    topics_file = f"output/{domain_name}_topics.json"

    if os.path.exists(topics_file):
        print(f"Loading existing topics file: {topics_file}")
        with open(topics_file, "r", encoding="utf-8") as f:
            topics = json.load(f)
    else:
        print("➡ Generating 10 topics...")
        topics = generate_blog_topics(client, company_profile, base_url)
        if not topics:
            print("Topic generation failed. Exiting.")
            return

    # ensure output directories exist
    os.makedirs("output/guidelines", exist_ok=True)
    os.makedirs("output/blogs", exist_ok=True)

    topics_to_process = topics[-2:] if isinstance(topics, list) else []
    print(f"\nProcessing {len(topics_to_process)} topic(s) (the last batch).")

    for topic in topics_to_process:
        title = topic.get("title") or "untitled"
        print(f"\n--- Generating guideline for: {title}")
        guideline_text = generate_guideline_text(client, topic, company_profile)
        if not guideline_text:
            print("Guideline generation failed — skipping this topic.")
            continue
        guideline_path = save_guideline_text(guideline_text, title, out_dir="output/guidelines")
        print(f"Saved guideline → {guideline_path}")

        print(f"--- Generating blog for: {title}")
        blog_md = generate_blog_from_guideline(client, topic, guideline_text, company_profile, base_url=base_url)
        if not blog_md:
            print("Blog generation failed — skipping.")
            continue
        blog_path = save_blog_md(blog_md, title, out_dir="output/blogs")
        print(f"Saved blog → {blog_path}")

        time.sleep(0.5)

    print("\n Pipeline finished. Check output/guidelines/ and output/blogs/ folders.")

if __name__ == "__main__":
    run_full_pipeline()
