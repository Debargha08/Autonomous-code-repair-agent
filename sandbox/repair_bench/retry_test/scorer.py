def normalize_score(score):
    if score < 0:
        return 0
    elif score > 100:
        return 100
    return score