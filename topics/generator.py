from utils.json_utils import clean_and_parse_json
import json
import tldextract

def generate_blog_topics(client, company_profile_json, base_url):
    """Generate 10 SEO-optimized topics (JSON array) and save as output/<domain>_topics.json"""
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
    file_path = f"output/{domain_name}_topics.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=2, ensure_ascii=False)
    print(f"Saved topics → {file_path}")
    return parsed
