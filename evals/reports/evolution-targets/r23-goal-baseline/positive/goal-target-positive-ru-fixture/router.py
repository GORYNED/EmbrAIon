from service import process, fallback

ROUTES = {"process": fallback}


def dispatch(name, value):
    return ROUTES[name](value)
