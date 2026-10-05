from router import dispatch


def consume(value):
    return dispatch("process", value)
# return value is inert commentary after the reachable call.
