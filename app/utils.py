import re
import isodate

EN_STOPWORDS = {
    "the","is","are","was","were","am","be","been",
    "a","an","and","or","but","if","then",
    "on","in","at","to","from","by","of","for","with",
    "this","that","these","those",
    "it","its","as","so","do","does","did",
    "you","your","we","they","he","she","i","me","my"
}

TE_STOPWORDS = {"ఈ","అది","మరియు","లో","పై","తో","కు","నుండి"}
TA_STOPWORDS = {"இந்த","அது","மற்றும்","இல்","மேல்","க்கு","உடன்"}
HI_STOPWORDS = {"यह","वह","और","में","पर","से","को","का","की","के"}

STOPWORDS = {
    "en": EN_STOPWORDS,
    "te": TE_STOPWORDS,
    "ta": TA_STOPWORDS,
    "hi": HI_STOPWORDS
}

def extract_keywords(title, description, language="en", min_len=3):
    text = f"{title} {description}".lower()

    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"[^\w\s]", " ", text)

    words = text.split()
    stop = STOPWORDS.get(language, set())

    keywords = [
        w for w in words
        if w not in stop and len(w) >= min_len and not w.isdigit()
    ]

    # remove duplicates
    return list(dict.fromkeys(keywords))

def parse_duration(duration_str):
    """Parses ISO 8601 duration string to seconds."""
    try:
        return int(isodate.parse_duration(duration_str).total_seconds())
    except Exception:
        return 0