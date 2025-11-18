from utils.slugify import safe_slug
import os
import json

def generate_guideline_text(client, topic, company_profile):
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


def save_guideline_text(guideline_text, topic_title, out_dir="output/guidelines"):
    os.makedirs(out_dir, exist_ok=True)
    slug = safe_slug(topic_title)
    path = os.path.join(out_dir, f"{slug}_guideline.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(guideline_text)
    return path
