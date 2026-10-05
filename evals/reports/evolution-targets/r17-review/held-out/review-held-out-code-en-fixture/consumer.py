from router import dispatch


def run(value):
    return dispatch("process", value)
