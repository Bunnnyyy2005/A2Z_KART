from langchain_core.tools import tool
import sqlite3
import pandas as pd

DB_NAME = 'ecommerce.db'

@tool
def get_item_catalog():
    """Returns the list of available items, their IDs, specifications, ratings, and prices."""
    conn = sqlite3.connect(DB_NAME)
    # Ikkada SQL query lo 'ratings' kooda add chesam
    df = pd.read_sql_query("SELECT item_id, item_name, price, specifications, ratings FROM Items", conn)
    conn.close()
    return df.to_string(index=False)

@tool
def check_vault_balance(user_id: int):
    """Checks the vault balance for a given user_id."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT vault FROM Users WHERE user_id = ?", (user_id,))
    val = cursor.fetchone()
    conn.close()
    return f"Vault Balance: ₹{val[0]}" if val else "User not found."

@tool
def purchase_items_tool(user_id: int, items: list[dict]):
    """
    Places an order for multiple items at once.
    'items' MUST be a list of dictionaries. Each dictionary must contain:
    - 'item_id' (integer)
    - 'quantity' (integer)
    Example: [{"item_id": 1, "quantity": 4}, {"item_id": 2, "quantity": 2}]
    Even if ordering a single item, pass it as a list with one dictionary.
    """
    from backend_logic import purchase_cart
    return purchase_cart(user_id, items)

@tool
def cancel_order_tool(order_id: str):
    """Cancels an existing order using its Order ID (e.g. ORD-A1B2C3)."""
    from backend_logic import cancel_order
    return cancel_order(order_id)

ecommerce_tools = [get_item_catalog, check_vault_balance, purchase_items_tool, cancel_order_tool]