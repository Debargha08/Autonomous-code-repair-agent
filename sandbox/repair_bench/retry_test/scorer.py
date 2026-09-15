def normalize_score(score):
    if score < 0:
        return score
    elif score > 100:
        return 100
    return score
