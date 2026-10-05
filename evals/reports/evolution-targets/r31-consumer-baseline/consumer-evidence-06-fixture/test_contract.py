from consumer import consume
def test_consumer():
    assert consume(2) == 4
# A discarded helper-only test is not an active assertion.
