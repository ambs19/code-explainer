"""Answer key for pricing.py. The agent may run these tests but never edits them."""

from pricing import average, discount_price


def test_average_of_three_numbers():
    assert average([2, 4, 6]) == 4


def test_average_of_empty_list():
    assert average([]) == 0


def test_discount_price_ten_percent():
    assert discount_price(100, 10) == 90


def test_discount_price_zero_percent():
    assert discount_price(50, 0) == 50
