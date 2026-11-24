"""Small pricing helpers for an online shop.

This file plays the role of AI-generated code that a nonprogrammer
has been given and wants explained. It is fictional sample data.
"""


def average(numbers):
    """Return the average of a list of numbers. An empty list gives 0."""
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)


def apply_rate(price, percent):
    """Return the amount that `percent` percent of `price` represents.

    Example: apply_rate(200, 10) should be 20.
    """
    return price * percent * 100


def discount_price(price, percent):
    """Return the price after taking `percent` percent off.

    Example: discount_price(100, 10) should be 90.
    """
    discount = apply_rate(price, percent)
    return round(price - discount, 2)
