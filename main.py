import os
import time
import json
import tldextract
import trafilatura
from typing import List, Dict, Any

from utils.openai_client import get_client

from company.extractor import crawl_links, extract_homepage_info
from company.summariser import summarize_company_info
from topics.generator import generate_blog_topics
from guidelines.generator import generate_guideline_text, save_guideline_text
from blogs.generator import generate_blog_from_guideline, save_blog_md
from images.generator import generate_images_for_blog

# initialize client
client = get_client()

# ---------- helpers ----------
def load_json(path: str, default=None):
    if default is None:
        default = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: failed to load JSON {path}: {e}")
            return default
    return default

def save_json(path: str, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def extract_clean_text(url: str) -> str:
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

def normalize_topic_item(item: Any) -> Dict[str, Any]:
    """
    Accept topic item in various shapes:
      - {"title": "...", "keyword": "..."}
      - "Some title"
    Return dict with keys: title, keyword
    """
    if isinstance(item, dict):
        title = item.get("title") or item.get("name") or ""
        keyword = item.get("keyword") or item.get("keywords") or ""
        return {"title": title.strip(), "keyword": keyword}
    elif isinstance(item, str):
        return {"title": item.strip(), "keyword": ""}
    else:
        return {"title": str(item), "keyword": ""}

# ---------- main pipeline ----------
def run_full_pipeline():
    base_url = input("Enter website URL: ").strip()
    if not base_url:
        print("No URL provided. Exiting.")
        return

    # domain-based filenames
    domain_info = tldextract.extract(base_url)
    domain_name = f"{domain_info.domain}.{domain_info.suffix}"
    out_dir = "output"
    os.makedirs(out_dir, exist_ok=True)

    summary_file = f"{out_dir}/{domain_name}_summary.json"
    topics_file = f"{out_dir}/{domain_name}_topics.json"            # optional previous topics list
    all_topics_file = f"{out_dir}/{domain_name}_all_topics.json"    # master simple list (optional)
    status_file = f"{out_dir}/{domain_name}_topics_status.json"     # topic tracker (main file)

    # 1) Load or create company summary
    if os.path.exists(summary_file):
        print(f"➡ Found cached summary: {summary_file}")
        company_profile = load_json(summary_file)
    else:
        print("➡ Crawling homepage for internal links...")
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

        print("➡ Generating company summary (first time)...")
        company_profile = summarize_company_info(client, combined_text, base_url)
        if not company_profile:
            print("Company profile generation failed. Exiting.")
            return

        save_json(summary_file, company_profile)
        print(f"✔ Saved company summary → {summary_file}")

    # 2) Load topic status (main tracking file)
    topic_status: List[Dict[str, Any]] = load_json(status_file, default=[])

    # Normalize / ensure keys exist
    def ensure_status_entry(t: Dict[str, Any]):
        t.setdefault("title", "")
        t.setdefault("keyword", "")
        t.setdefault("guideline_generated", False)
        t.setdefault("blog_generated", False)
        t.setdefault("images_generated", False)
        t.setdefault("guideline_path", "")
        t.setdefault("blog_path", "")
        t.setdefault("images", [])  # optional list of image refs
        return t

    topic_status = [ensure_status_entry(t) for t in topic_status]

    # 3) Identify unfinished topics
    unfinished_status_entries = [
        t for t in topic_status
        if not (t.get("guideline_generated") and t.get("blog_generated") and t.get("images_generated"))
    ]

    # If there are no topics at all, try to seed from topics_file or all_topics_file
    if not topic_status:
        # try loading older topics files if present (backwards compatibility)
        if os.path.exists(topics_file):
            print(f"➡ Loading topics from {topics_file}")
            raw_topics = load_json(topics_file, default=[])
            for rt in raw_topics:
                nt = normalize_topic_item(rt)
                topic_status.append(ensure_status_entry({
                    "title": nt["title"], "keyword": nt["keyword"]
                }))
            save_json(status_file, topic_status)
        elif os.path.exists(all_topics_file):
            print(f"➡ Loading master topics from {all_topics_file}")
            raw_topics = load_json(all_topics_file, default=[])
            for rt in raw_topics:
                nt = normalize_topic_item(rt)
                topic_status.append(ensure_status_entry({
                    "title": nt["title"], "keyword": nt["keyword"]
                }))
            save_json(status_file, topic_status)

        unfinished_status_entries = [
            t for t in topic_status
            if not (t.get("guideline_generated") and t.get("blog_generated") and t.get("images_generated"))
        ]

    # 4) If there are unfinished topics, process them first
    if unfinished_status_entries:
        print(f"➡ Found {len(unfinished_status_entries)} unfinished topic(s). Processing them before generating new topics.")
    else:
        print("➡ No unfinished topics found. Will generate new topics.")

    # main loop: complete unfinished; if none, generate new topics and process them
    # We'll run a single pass: complete all unfinished, then (if none left) generate some new topics and process them.
    # This is safe for cron runs or manual runs; it will resume from status_file state.

    # ---------- PROCESS existing unfinished topics ----------
    for ts in list(unfinished_status_entries):  # list() to avoid mutation problems
        title = ts.get("title")
        print(f"\n--- Processing existing topic: {title}")

        # 1) Guideline
        if not ts.get("guideline_generated"):
            try:
                print(f"Generating guideline for: {title}")
                # Build a topic object expected by generate_guideline_text (adjust if your function expects different shape)
                topic_obj = {"title": title, "keyword": ts.get("keyword", "")}
                guideline_text = generate_guideline_text(client, topic_obj, company_profile)
                if guideline_text:
                    guideline_path = save_guideline_text(guideline_text, title, out_dir=os.path.join(out_dir,"guidelines"))
                    ts["guideline_generated"] = True
                    ts["guideline_path"] = guideline_path
                    save_json(status_file, topic_status)
                    print(f"✔ Guideline saved: {guideline_path}")
                else:
                    print("⚠ Guideline generation returned empty. Will retry next run.")
                    # continue to next topic without marking as generated
            except Exception as e:
                print(f"Error generating guideline for {title}: {e}")

        # 2) Blog
        if ts.get("guideline_generated") and not ts.get("blog_generated"):
            try:
                print(f"Generating blog for: {title}")
                topic_obj = {"title": title, "keyword": ts.get("keyword", "")}
                guideline_text = None
                # prefer to load guideline_text from saved path if present
                if ts.get("guideline_path") and os.path.exists(ts["guideline_path"]):
                    try:
                        with open(ts["guideline_path"], "r", encoding="utf-8") as gf:
                            guideline_text = gf.read()
                    except Exception:
                        guideline_text = None
                # fallback to calling generator if not found
                if guideline_text is None:
                    guideline_text = generate_guideline_text(client, topic_obj, company_profile)

                blog_md = generate_blog_from_guideline(client, topic_obj, guideline_text, company_profile, base_url=base_url)
                if blog_md:
                    blog_path = save_blog_md(blog_md, title, out_dir=os.path.join(out_dir,"blogs"))
                    ts["blog_generated"] = True
                    ts["blog_path"] = blog_path
                    save_json(status_file, topic_status)
                    print(f"✔ Blog saved: {blog_path}")
                else:
                    print("⚠ Blog generation returned empty. Will retry next run.")
            except Exception as e:
                print(f"Error generating blog for {title}: {e}")

        # 3) Images
        if ts.get("blog_generated") and not ts.get("images_generated"):
            try:
                print(f"Generating images for: {title}")
                # Load blog markdown if available
                blog_md = None
                if ts.get("blog_path") and os.path.exists(ts["blog_path"]):
                    try:
                        with open(ts["blog_path"], "r", encoding="utf-8") as bf:
                            blog_md = bf.read()
                    except Exception:
                        blog_md = None
                # fallback: if blog_md not loaded, call generator (this is optional; prefer not to regenerate)
                if blog_md is None:
                    print("Warning: blog content not found on disk; attempting to regenerate blog to create images.")
                    # try to regenerate blog quickly
                    topic_obj = {"title": title, "keyword": ts.get("keyword", "")}
                    guideline_text = None
                    if ts.get("guideline_path") and os.path.exists(ts["guideline_path"]):
                        with open(ts["guideline_path"], "r", encoding="utf-8") as gf:
                            guideline_text = gf.read()
                    blog_md = generate_blog_from_guideline(client, topic_obj, guideline_text, company_profile, base_url=base_url)

                # generate images (assumes this function stores images to output and returns meta)
                images_meta = generate_images_for_blog(title, blog_md, num_images=1)
                ts["images_generated"] = True
                # store any returned metadata
                if images_meta:
                    ts["images"] = images_meta
                save_json(status_file, topic_status)
                print(f"✔ Images generated for: {title}")
            except Exception as e:
                print(f"Error generating images for {title}: {e}")

    # Recompute unfinished after trying to finish existing entries
    unfinished_status_entries = [
        t for t in topic_status
        if not (t.get("guideline_generated") and t.get("blog_generated") and t.get("images_generated"))
    ]

    # ---------- IF no unfinished topics left, generate new topics ----------
    if not unfinished_status_entries:
        # decide how many new topics to create per run (configurable)
        NUM_NEW_TOPICS = 2

        # prepare existing_titles to avoid duplicates
        existing_titles_lc = {t["title"].strip().lower() for t in topic_status if t.get("title")}
        print("\n➡ Generating new topics because there are no unfinished topics.")
        try:
            # Pass existing topics (titles) to generator so it doesn't repeat
            new_raw_topics = generate_blog_topics(client, company_profile, base_url, existing_topics=list(existing_titles_lc))
        except TypeError:
            # In case old generate_blog_topics doesn't accept existing_topics param,
            # call it with original signature and filter afterwards
            new_raw_topics = generate_blog_topics(client, company_profile, base_url)

        # Normalize topics and filter duplicates
        new_topics_normalized = []
        for item in new_raw_topics or []:
            nt = normalize_topic_item(item)
            title_lc = nt["title"].lower()
            if not title_lc or title_lc in existing_titles_lc:
                continue
            new_topics_normalized.append(nt)
            existing_titles_lc.add(title_lc)
            if len(new_topics_normalized) >= NUM_NEW_TOPICS:
                break

        if not new_topics_normalized:
            print("⚠ No new topics were returned by the generator (or all were duplicates). Exiting.")
        else:
            print(f"➡ Adding {len(new_topics_normalized)} new topic(s) to the status tracker.")
            for nt in new_topics_normalized:
                status_entry = ensure_status_entry({
                    "title": nt["title"],
                    "keyword": nt.get("keyword", ""),
                    "guideline_generated": False,
                    "blog_generated": False,
                    "images_generated": False
                })
                topic_status.append(status_entry)
            save_json(status_file, topic_status)
            # Optionally update an all_topics_file & topics_file for backward compatibility
            simple_titles = [ {"title": t["title"], "keyword": t.get("keyword","")} for t in topic_status ]
            save_json(all_topics_file, simple_titles)
            save_json(topics_file, simple_titles)
            print(f"✔ New topics appended and status file updated: {status_file}")

            # Process the newly added topics in this same run:
            newly_added = [t for t in topic_status if not (t["guideline_generated"] and t["blog_generated"] and t["images_generated"])]
            print(f"Processing {len(newly_added)} newly added topic(s) now...")
            for ts in newly_added:
                # Reuse the processing logic from above, but keep it concise:
                title = ts["title"]
                try:
                    if not ts["guideline_generated"]:
                        print(f"Generating guideline for: {title}")
                        topic_obj = {"title": title, "keyword": ts.get("keyword", "")}
                        guideline_text = generate_guideline_text(client, topic_obj, company_profile)
                        if guideline_text:
                            guideline_path = save_guideline_text(guideline_text, title, out_dir=os.path.join(out_dir,"guidelines"))
                            ts["guideline_generated"] = True
                            ts["guideline_path"] = guideline_path
                            save_json(status_file, topic_status)
                            print(f"✔ Guideline saved: {guideline_path}")

                    if ts.get("guideline_generated") and not ts.get("blog_generated"):
                        print(f"Generating blog for: {title}")
                        topic_obj = {"title": title, "keyword": ts.get("keyword", "")}
                        with open(ts["guideline_path"], "r", encoding="utf-8") as gf:
                            guideline_text = gf.read()
                        blog_md = generate_blog_from_guideline(client, topic_obj, guideline_text, company_profile, base_url=base_url)
                        if blog_md:
                            blog_path = save_blog_md(blog_md, title, out_dir=os.path.join(out_dir,"blogs"))
                            ts["blog_generated"] = True
                            ts["blog_path"] = blog_path
                            save_json(status_file, topic_status)
                            print(f"✔ Blog saved: {blog_path}")

                    if ts.get("blog_generated") and not ts.get("images_generated"):
                        print(f"Generating images for: {title}")
                        with open(ts["blog_path"], "r", encoding="utf-8") as bf:
                            blog_md = bf.read()
                        images_meta = generate_images_for_blog(title, blog_md, num_images=1)
                        ts["images_generated"] = True
                        if images_meta:
                            ts["images"] = images_meta
                        save_json(status_file, topic_status)
                        print(f"✔ Images generated for: {title}")

                except Exception as e:
                    print(f"Error while processing new topic {title}: {e}")

    else:
        print("\n➡ There are still unfinished topics. New topics will not be generated until these are completed.")

    print("\nPipeline pass finished. Check output/ folder and the status file for progress.")
    print(f"Status file: {status_file}")

if __name__ == "__main__":
    run_full_pipeline()
