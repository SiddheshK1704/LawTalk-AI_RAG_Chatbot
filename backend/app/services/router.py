def is_legal_query(query: str) -> bool:
    legal_keywords = [
        "law", "legal", "ipc", "section",
        "court", "crime", "punishment",
        "constitution", "act", "rights"
    ]

    query = query.lower()

    return any(keyword in query for keyword in legal_keywords)