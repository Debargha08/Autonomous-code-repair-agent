def can_access(age, has_permission):
    if age >= 18 and not has_permission:
        return True

    return False
