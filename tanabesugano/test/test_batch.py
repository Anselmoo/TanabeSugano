from tanabesugano.batch import Batch


def test_batch_small():
    res = Batch()
    res.calculation()
    assert isinstance(res.result, list)
