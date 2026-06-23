import sqlite3
import random
from datetime import datetime, timedelta

DB_NAME = 'ecommerce.db'

def register_user(name, email, phone_no, password):
    """Kotha user ni register chesi random vault amount isthundi."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    vault_amount = round(random.uniform(10000, 50000), 2)
    try:
        cursor.execute(
            "INSERT INTO Users (name, email, phone_no, password, vault) VALUES (?, ?, ?, ?, ?)",
            (name, email, phone_no, password, vault_amount)
        )
        conn.commit()
        user_id = cursor.lastrowid
        return user_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def purchase_cart(user_id, cart_items):
    """Multiple items ni oke Order Group ID tho order chesthundi."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        import uuid
        # Generate a single ID for all items in this cart (e.g., ORD-A1B2C3)
        order_group_id = "ORD-" + str(uuid.uuid4().hex)[:6].upper()
        total_cart_price = 0
        items_info = []

        # Verify items and calculate total cost
        for cart_item in cart_items:
            item_id = cart_item.get("item_id")
            quantity = cart_item.get("quantity", 1)
            
            cursor.execute("SELECT item_name, price FROM Items WHERE item_id = ?", (item_id,))
            item = cursor.fetchone()
            if not item: return f"[ERROR] Item ID {item_id} dhorakaledu."
            
            item_name, price = item
            total_cart_price += (price * quantity)
            items_info.append((item_id, item_name, price, quantity))

        # Check User Vault
        cursor.execute("SELECT name, vault FROM Users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        if not user: return "[ERROR] User dhorakaledu."
        user_name, vault_balance = user

        if vault_balance < total_cart_price:
            return f"[FAILED] Insufficient balance. Vault: {vault_balance}, Total Cart Price: {total_cart_price}"

        # Deduct from User, Add to App Vault
        new_user_balance = vault_balance - total_cart_price
        cursor.execute("UPDATE Users SET vault = ? WHERE user_id = ?", (new_user_balance, user_id))
        cursor.execute("UPDATE App_Vault SET total_amount = total_amount + ? WHERE id = 1", (total_cart_price,))
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Insert each item as a separate row but with SAME order_group_id
        for item_id, item_name, price, quantity in items_info:
            cursor.execute('''
                INSERT INTO Orders (customer_name, user_id, item_id, order_name, status, price, order_date, quantity, order_group_id) 
                VALUES (?, ?, ?, ?, 'Processing', ?, ?, ?, ?)
            ''', (user_name, user_id, item_id, item_name, price, current_time, quantity, order_group_id))
        
        conn.commit()
        return f"Order placed successfully. Order ID: {order_group_id}. Total Items: {sum([q for _,_,_,q in items_info])}"

    except Exception as e:
        conn.rollback()
        return f"[ERROR] Transaction failed: {str(e)}"
    finally:
        conn.close()

def cancel_order(order_group_id):
    """Order cancel chesi, 2 mins check chesi, refund isthundi."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # Group ID tho unna items anni theeskostham
        cursor.execute("SELECT user_id, price, quantity, status, order_date FROM Orders WHERE order_group_id = ?", (order_group_id,))
        orders = cursor.fetchall()
        
        if not orders: 
            # Backward compatibility for old single item order_ids before update
            cursor.execute("SELECT user_id, price, 1, status, order_date FROM Orders WHERE order_id = ?", (order_group_id,))
            orders = cursor.fetchall()
            if not orders: return f"[ERROR] Order {order_group_id} dhorakaledu."
        
        first_order = orders[0]
        user_id = first_order[0]
        status = first_order[3]
        order_date_str = first_order[4]
        
        if status == 'Cancelled':
            return "[FAILED] Order already cancel aipoindi."
        if status == 'Shipped' or status == 'Delivered':
            return f"[FAILED] Order already {status} aipoindi. Inka cancel cheyyalem boss!"

        # 2 Minutes Logic Check
        if order_date_str:
            try:
                order_date = datetime.strptime(order_date_str, "%Y-%m-%d %H:%M:%S")
                if datetime.now() - order_date > timedelta(minutes=2):
                    cursor.execute("UPDATE Orders SET status = 'Shipped' WHERE order_group_id = ? OR order_id = ?", (order_group_id, order_group_id))
                    conn.commit()
                    return "[FAILED] 2 mins daatipoyindi boss. Order is already packed and shipped! Cancellation not possible."
            except ValueError:
                pass 

        # Calculate total refund based on price * quantity for all items in that order
        total_refund = sum([o[1] * o[2] for o in orders])

        # Process Refund
        cursor.execute("UPDATE Users SET vault = vault + ? WHERE user_id = ?", (total_refund, user_id))
        cursor.execute("UPDATE App_Vault SET total_amount = total_amount - ? WHERE id = 1", (total_refund,))
        cursor.execute("UPDATE Orders SET status = 'Cancelled' WHERE order_group_id = ? OR order_id = ?", (order_group_id, order_group_id))
        
        conn.commit()
        return f"Order {order_group_id} cancelled and ₹{total_refund} refunded successfully."

    except Exception as e:
        conn.rollback()
        return f"[ERROR] Cancellation failed: {str(e)}"
    finally:
        conn.close()

def recharge_user_vault(user_id, amount=10000):
    """User vault loki extra money add chesthundi."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Users SET vault = vault + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        return True
    except Exception as e:
        return False
    finally:
        conn.close()