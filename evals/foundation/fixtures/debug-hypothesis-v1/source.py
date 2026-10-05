def compute(value):
    return value + 2


def cached(value):
    return value + 1


def run(value, use_cache):
    if use_cache:
        return cached(value)
    return compute(value)
