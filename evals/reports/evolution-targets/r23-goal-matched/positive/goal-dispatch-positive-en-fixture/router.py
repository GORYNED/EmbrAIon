from service import process, fallback

ROUTES = {"process": process}


def dispatch(name, value):
    return value
