

# Add a custom Jinja filter via hooks.py jinja configuration that formats vendor_rating as star symbols 
# (e.g., ★★★☆☆ for 3/5). Use this in a custom Print Format for Purchase Order that includes: 
# standard PO details + vendor category + vendor rating (as stars) + a note if rating is low.


def rating_to_stars(rating, max_stars=5):
    """
    Convert a numeric rating to star symbols.
    Usage in Jinja: {{ supplier.custom_vendor_rating | rating_to_stars }}
    Examples:
      3.0 → ★★★☆☆
      4.5 → ★★★★½
      5.0 → ★★★★★
    """
    try:
        rating = float(rating or 0)
    except (ValueError, TypeError):
        return "☆" * max_stars

    full  = int(rating)
    half  = 1 if (rating - full) >= 0.5 else 0
    empty = max_stars - full - half

    return "★" * full + ("½" if half else "") + "☆" * empty