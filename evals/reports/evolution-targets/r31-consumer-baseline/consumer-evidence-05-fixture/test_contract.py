from consumer import consume
from service import process
def test_consumer():
    assert consume(2) == process(2)
