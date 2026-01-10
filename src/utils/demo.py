"""Demo code with issues for testing inline /ask command."""


def process_data(user_input):
    """Process user input data."""
    # This function needs explanation
    result = eval(user_input)  # Unsafe eval
    return result


def calculate_total(items):
    """Calculate total price of items."""
    total = 0
    for item in items:
        # Complex calculation logic
        price = item.get("price", 0)
        quantity = item.get("quantity", 1)
        discount = item.get("discount", 0)
        total += price * quantity * (1 - discount)
    return total


def fetch_user(user_id):
    """Fetch user from database."""
    # SQL query construction
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return query
