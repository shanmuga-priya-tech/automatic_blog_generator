import json


def generate_new_topics(company_data, existing_topics, n_new=5):
    prompt = f"""
You are an expert SEO strategist.

Company Profile:
{json.dumps(company_data, indent=2)}

Existing Topics:
{json.dumps(existing_topics, indent=2)}

Task:
Generate {n_new} completely NEW topic objects in the EXACT SAME JSON structure.
RULES:
- No duplicates of any existing titles
- Must be SEO-optimized
- Must fit the company’s brand and service area
- Should focus on topics that can rank well locally (Bihar)
- Produce pure JSON array ONLY
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    # Parse AI JSON safely
    try:
        new_topics = json.loads(response.choices[0].message["content"])
    except:
        raise ValueError("GPT returned invalid JSON.")

    return new_topics
