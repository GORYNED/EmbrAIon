from router import dispatch


def consume(value):
    return dispatch("process", value)
