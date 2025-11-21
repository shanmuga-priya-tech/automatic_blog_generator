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