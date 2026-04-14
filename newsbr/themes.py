"""Default theme keyword guesser. Projects override with their own taxonomies."""

DEFAULT_THEME_KEYWORDS = {
    "venda_sentenca": [
        "venda", "sentenc", "decisao", "decisão", "corrupc", "operacao",
        "operação", "preso", "afastad", "propina", "lavagem", "faroeste",
        "naufragio", "sisamnes",
    ],
    "filhotismo": [
        "filhotism", "filho", "filha", "esposa", "parente", "principe",
        "príncipe", "familiar", "conjuge", "cônjuge", "escritorio",
        "escritório", "banco-master",
    ],
    "impedimento": [
        "impediment", "suspeic", "suspeição", "recusa", "cnj", "resolucao",
        "resolução",
    ],
    "parentesco_geral": [
        "nepotism", "cla", "clã", "dinastia", "parentesco", "familia", "família",
    ],
}


def guess_theme(text: str, keywords: dict | None = None) -> str:
    """Guess a theme from URL or title text by keyword count."""
    keywords = keywords or DEFAULT_THEME_KEYWORDS
    text_lower = text.lower()
    scores = {t: sum(1 for kw in kws if kw in text_lower)
              for t, kws in keywords.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else ""
