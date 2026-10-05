from service import process

ROUTES = {"process": process}


def dispatch(name, value):
    return ROUTES[name](value)
