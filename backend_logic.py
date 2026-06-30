import psycopg2
import os
import random
from datetime import datetime, timedelta

def get_db_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"])

def register_user(name, email, phone_no, password):
    """Registers a new user and grants a random vault amount."""
    conn = get_db_connection()
    cursor = conn.cursor()
    vault_amount = round(random.uniform(10000, 50000), 2)
    try:
        cursor.execute(
            "INSERT INTO Users (name, email, phone_no, password, vault) VALUES (%s, %s, %s, %s, %s) RETURNING user_id",
            (name, email, phone_no, password, vault_amount)
        )
        user_id = cursor.fetchone()[0]
        conn.commit()
        return user_id
    except psycopg2.IntegrityError:
        return None
    finally:
        conn.close()

def purchase_cart(user_id, cart_items):
    """Orders multiple items under a single Order Group ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        import uuid
        order_group_id = "ORD-" + str(uuid.uuid4().hex)[:6].upper()
        total_cart_price = 0
        items_info = []

        for cart_item in cart_items:
            item_id = cart_item.get("item_id")
            quantity = cart_item.get("quantity", 1)
            
            cursor.execute("SELECT item_name, price FROM Items WHERE item_id = %s", (item_id,))
            item = cursor.fetchone()
            if not item: return f"[ERROR] Item ID {item_id} not found."
            
            item_name, price = item
            total_cart_price += (price * quantity)
            items_info.append((item_id, item_name, price, quantity))

        cursor.execute("SELECT name, vault FROM Users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        if not user: return "[ERROR] User not found."
        user_name, vault_balance = user

        if vault_balance < total_cart_price:
            return f"[FAILED] Insufficient balance. Vault: {vault_balance}, Total Cart Price: {total_cart_price}"

        new_user_balance = vault_balance - total_cart_price
        cursor.execute("UPDATE Users SET vault = %s WHERE user_id = %s", (new_user_balance, user_id))
        cursor.execute("UPDATE App_Vault SET total_amount = total_amount + %s WHERE id = 1", (total_cart_price,))
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for item_id, item_name, price, quantity in items_info:
            cursor.execute('''
                INSERT INTO Orders (customer_name, user_id, item_id, order_name, status, price, order_date, quantity, order_group_id) 
                VALUES (%s, %s, %s, %s, 'Processing', %s, %s, %s, %s)
            ''', (user_name, user_id, item_id, item_name, price, current_time, quantity, order_group_id))
        
        conn.commit()
        return f"Order placed successfully. Order ID: {order_group_id}. Total Items: {sum([q for _,_,_,q in items_info])}"

    except Exception as e:
        conn.rollback()
        return f"[ERROR] Transaction failed: {str(e)}"
    finally:
        conn.close()

def cancel_order(order_group_id):
    """Cancels an order, checks the 2 min policy, and refunds."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT user_id, price, quantity, status, order_date FROM Orders WHERE order_group_id = %s", (order_group_id,))
        orders = cursor.fetchall()
        
        if not orders: 
            # Fallback for old integer IDs casted to text safely
            cursor.execute("SELECT user_id, price, 1, status, order_date FROM Orders WHERE order_id::text = %s", (order_group_id,))
            orders = cursor.fetchall()
            if not orders: return f"[ERROR] Order {order_group_id} not found."
        
        first_order = orders[0]
        user_id = first_order[0]
        status = first_order[3]
        order_date_str = first_order[4]
        
        if status == 'Cancelled':
            return "[FAILED] Order is already cancelled."
        if status == 'Shipped' or status == 'Delivered':
            return f"[FAILED] Order is already {status}. Cancellation not possible!"

        if order_date_str:
            try:
                order_date = datetime.strptime(order_date_str, "%Y-%m-%d %H:%M:%S")
                if datetime.now() - order_date > timedelta(minutes=2):
                    cursor.execute("UPDATE Orders SET status = 'Shipped' WHERE order_group_id = %s OR order_id::text = %s", (order_group_id, order_group_id))
                    conn.commit()
                    return "[FAILED] 2 mins limit exceeded. Order is already packed and shipped! Cancellation not possible."
            except ValueError:
                pass 

        total_refund = sum([o[1] * o[2] for o in orders])

        cursor.execute("UPDATE Users SET vault = vault + %s WHERE user_id = %s", (total_refund, user_id))
        cursor.execute("UPDATE App_Vault SET total_amount = total_amount - %s WHERE id = 1", (total_refund,))
        cursor.execute("UPDATE Orders SET status = 'Cancelled' WHERE order_group_id = %s OR order_id::text = %s", (order_group_id, order_group_id))
        
        conn.commit()
        return f"Order {order_group_id} cancelled and ₹{total_refund} refunded successfully."

    except Exception as e:
        conn.rollback()
        return f"[ERROR] Cancellation failed: {str(e)}"
    finally:
        conn.close()

def recharge_user_vault(user_id, amount=10000):
    """Adds money to a user's vault."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Users SET vault = vault + %s WHERE user_id = %s", (amount, user_id))
        conn.commit()
        return True
    except Exception as e:
        return False
    finally:
        conn.close()
