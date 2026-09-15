def login(username, password):
    if username == 'admin' and password == 'password123':
        return True
    elif username == 'debargha' and password == 'qwen123':
        return True
    elif username == 'admin' and password == 'wrongpassword':
        return False
    elif username == 'unknown' and password == 'password123':
        return False
    else:
        return False
