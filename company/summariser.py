from utils.json_utils import clean_and_parse_json
import json
import tldextract

def summarize_company_info(client, text, base_url):
    """
    Create a structured company profile JSON using the model.
    Saved as output/<domain>_company.json
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
- unique_value_proposition
- government_schemes_supported (array)
- benefits_for_bihar_homeowners (array)
- vision_statement

Make sure the summary includes:
- Subsidies & schemes: Ghar Ghar Solar, PM Surya Ghar Yojana
- Benefits: zero electricity bills, government loans at 6%, top-quality solar products
- Bihar-specific relevance and impact
- Vision for solar adoption in Bihar

Return JSON in this structure (escape braces inside JSON):
{{
  "company_name": "",
  "industry": "",
  "main_products_services": [],
  "target_audience": [],
  "tone": "",
  "keywords": [],
  "unique_value_proposition": "",
  "government_schemes_supported": [],
  "benefits_for_bihar_homeowners": [],
  "vision_statement": ""
}}

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

    domain_info = tldextract.extract(base_url)
    domain_name = f"{domain_info.domain}.{domain_info.suffix}"
    file_path = f"output/{domain_name}_company.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=2, ensure_ascii=False)
    print(f"Saved company profile → {file_path}")
    return parsed
