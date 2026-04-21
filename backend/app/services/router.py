def is_legal_query(query: str) -> bool:
    query = query.lower()

    legal_keywords = [
        "law", "legal", "ipc", "crpc", "section",
        "court", "crime", "punishment", "constitution",
        "act", "rights", "police", "fir", "judge",
        "offence", "bail", "cyber law", "pocso",
        "evidence", "contract", "agreement"
    ]

    return any(keyword in query for keyword in legal_keywords)