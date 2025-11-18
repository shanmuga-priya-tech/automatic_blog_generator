import json
import re

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
        # try to extract a JSON-like block
        m = re.search(r"\{[\s\S]*\}", cleaned)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return {"raw_output": model_output}
