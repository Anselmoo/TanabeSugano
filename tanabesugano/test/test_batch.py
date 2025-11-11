"""Tests for batch processing module."""

from __future__ import annotations

from tanabesugano.batch import Batch


def test_batch_small():
    res = Batch()
    res.calculation()
    assert isinstance(res.result, list)


def test_batch_d2():
    res = Batch(d_count=2)
    res.calculation()
    assert isinstance(res.result, list)


def test_batch_d3():
    res = Batch(d_count=3)
    res.calculation()
    assert isinstance(res.result, list)


def test_batch_d4():
    res = Batch(d_count=4)
    res.calculation()
    assert isinstance(res.result, list)


def test_batch_d5():
    res = Batch(d_count=5)
    res.calculation()
    assert isinstance(res.result, list)


def test_batch_d6():
    res = Batch(d_count=6)
    res.calculation()
    assert isinstance(res.result, list)


def test_batch_d7():
    res = Batch(d_count=7)
    res.calculation()
    assert isinstance(res.result, list)


def test_batch_d8():
    res = Batch(d_count=8)
    res.calculation()
    assert isinstance(res.result, list)
