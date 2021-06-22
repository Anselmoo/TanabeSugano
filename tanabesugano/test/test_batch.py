from tanabesugano.batch import Batch


def test_batch_small():
    res = Batch()
    res.calculation()
    assert isinstance(res.result, list)


def test_batch_d2():
    res = Batch(mode=2)
    res.calculation()
    assert isinstance(res.result, list)


def test_batch_d3():
    res = Batch(mode=3)
    res.calculation()
    assert isinstance(res.result, list)


def test_batch_d4():
    res = Batch(mode=4)
    res.calculation()
    assert isinstance(res.result, list)


def test_batch_d5():
    res = Batch(mode=5)
    res.calculation()
    assert isinstance(res.result, list)


def test_batch_d6():
    res = Batch(mode=6)
    res.calculation()
    assert isinstance(res.result, list)


def test_batch_d7():
    res = Batch(mode=7)
    res.calculation()
    assert isinstance(res.result, list)


def test_batch_d8():
    res = Batch(mode=8)
    res.calculation()
    assert isinstance(res.result, list)
