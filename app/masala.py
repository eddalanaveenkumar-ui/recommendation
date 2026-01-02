def generate_masala(niche, title, views, likes):
    t = title.lower()
    tags = []

    if any(w in t for w in ["funny","comedy","laugh"]):
        tags.append("funny")
    elif any(w in t for w in ["life","truth","reality"]):
        tags.append("life_lesson")
    else:
        tags.append("motivational")

    if niche in ["Education","Tech","Business"]:
        tags.append("educational")
    else:
        tags.append("entertainment")

    if "power" in t or "success" in t:
        tags.append("high_energy")
    else:
        tags.append("calm")

    if views > 500_000 or likes > 20_000:
        tags.append("trending")
    else:
        tags.append("addictive")

    tags.append("mindset")

    return tags[:5]