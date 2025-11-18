from utils.slugify import safe_slug
import os
import json

def generate_blog_from_guideline(client, topic, guideline_text, company_profile, base_url=None):
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

def save_blog_md(blog_md, topic_title, out_dir="output/blogs"):
    os.makedirs(out_dir, exist_ok=True)
    slug = safe_slug(topic_title)
    path = os.path.join(out_dir, f"{slug}_blog.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(blog_md)
    return path
