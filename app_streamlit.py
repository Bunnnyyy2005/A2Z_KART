import streamlit as st
import sqlite3
import os
import pandas as pd
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

# mana libs
from agent_tools import ecommerce_tools
from backend_logic import register_user, recharge_user_vault

# --- 1. PAGE CONFIG & CUSTOM CSS (display.html design) ---
st.set_page_config(page_title="A2Z-Kart | AI Copilot", layout="wide", initial_sidebar_state="collapsed")

# Groq API Key (Replace with your actual key if needed)
try:
    # Cloud lo deploy chesinappudu Streamlit Secrets nunchi key theeskuntundi
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
except:
    # Local ga run chesetappudu idi vaadukuntundi (GitHub lo pedithe ee kinda string ni empty chesey boss)
    os.environ["GROQ_API_KEY"] = "----------"

DB_NAME = 'ecommerce.db'

link1 = "https://www.instagram.com/_bunnnyyy_._/"
# --- 2. DATABASE UPGRADE (Automatically add image_url column if not exists) ---
def setup_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Create Core Tables (For Fresh Cloud Deployment)
    cursor.execute('''CREATE TABLE IF NOT EXISTS Users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        phone_no TEXT,
        password TEXT,
        vault REAL DEFAULT 0.0
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS Items (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT,
        specifications TEXT,
        ratings REAL,
        price REAL,
        image_url TEXT DEFAULT ''
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS Orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_group_id TEXT DEFAULT '',
        customer_name TEXT,
        user_id INTEGER,
        item_id INTEGER,
        order_name TEXT,
        status TEXT,
        price REAL,
        quantity INTEGER DEFAULT 1,
        order_date TEXT DEFAULT ''
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS App_Vault (
        id INTEGER PRIMARY KEY,
        total_amount REAL DEFAULT 0.0
    )''')
    # Insert initial app vault balance if empty
    cursor.execute("INSERT OR IGNORE INTO App_Vault (id, total_amount) VALUES (1, 0.0)")
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS Settings (
        setting_key TEXT UNIQUE, 
        setting_value TEXT
    )''')
    cursor.execute("INSERT OR IGNORE INTO Settings (setting_key, setting_value) VALUES ('recharge_link', 'https://www.google.com')")
    
    conn.commit()
    
    # 2. Upgrade existing tables (Adding new columns if they don't exist)
    try:
        cursor.execute("ALTER TABLE Items ADD COLUMN image_url TEXT DEFAULT ''")
        conn.commit()
    except sqlite3.OperationalError: pass
    
    try:
        cursor.execute("ALTER TABLE Orders ADD COLUMN order_date TEXT DEFAULT ''")
        conn.commit()
    except sqlite3.OperationalError: pass
    
    try:
        cursor.execute("ALTER TABLE Orders ADD COLUMN quantity INTEGER DEFAULT 1")
        cursor.execute("ALTER TABLE Orders ADD COLUMN order_group_id TEXT DEFAULT ''")
        conn.commit()
    except sqlite3.OperationalError: pass
        
    conn.close()

def update_old_orders():
    """App open cheyagane 2 mins datina orders automatic ga Shipped status ki velthayi"""
    from datetime import datetime, timedelta
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT order_id, order_date FROM Orders WHERE status = 'Processing'")
        processing_orders = cursor.fetchall()
        
        for o_id, o_date_str in processing_orders:
            if o_date_str:
                o_date = datetime.strptime(o_date_str, "%Y-%m-%d %H:%M:%S")
                if datetime.now() - o_date > timedelta(minutes=2):
                    cursor.execute("UPDATE Orders SET status = 'Shipped' WHERE order_id = ?", (o_id,))
        conn.commit()
        conn.close()
    except:
        pass

setup_database() # Call it at startup to ensure tables exist
update_old_orders() # Update expired orders status

# Streamlit UI CSS
custom_css = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] { font-family: 'Poppins', sans-serif; }
    
    .stApp {
        background: radial-gradient(circle at top left, rgba(0,150,255,0.15), transparent 35%),
                    radial-gradient(circle at bottom right, rgba(0,200,255,0.1), transparent 35%),
                    #050816; color: white;
    }
    
    header {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    .custom-header {
        position: fixed; top: 0; left: 0; right: 0; height: 70px;
        background: rgba(10,15,30,0.85); backdrop-filter: blur(20px);
        border-bottom: 1px solid rgba(0,180,255,0.2); z-index: 99999;
        display: flex; align-items: center; justify-content: space-between; padding: 0 30px;
    }
    .custom-logo {
        font-size: 26px; font-weight: 700;
        background: linear-gradient(90deg, #00c6ff, #00e5ff);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .custom-badge {
        background: rgba(0,150,255,0.15); padding: 8px 15px; border-radius: 12px;
        color: white; font-weight: 500; font-size: 14px; border: 1px solid rgba(0,180,255,0.3);
    }
    
    .hero-box {
        border-radius: 20px; padding: 40px; margin-top: 20px; margin-bottom: 30px;
        background: linear-gradient(135deg, rgba(0,120,255,0.2), rgba(0,229,255,0.05));
        backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.08);
        box-shadow: 0 0 20px rgba(0,140,255,0.15); text-align: center;
    }
    
    .stDataFrame {
        background: rgba(255,255,255,0.02); border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.1); padding: 10px;
    }
    .stChatFloatingInputContainer { background-color: transparent; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- 3. HELPER FUNCTIONS ---
import json
SESSION_FILE = "session_cookie.json"

def save_session(user_id, name, password, vault_balance, step="main"):
    """User details ni local JSON file lo save chesthundi (Cookie lanti di)"""
    with open(SESSION_FILE, "w") as f:
        json.dump({
            "user_id": user_id,
            "name": name,
            "password": password,
            "vault_balance": vault_balance,
            "step": step
        }, f)

def load_session():
    """Local JSON file nunchi saved session ni read chesthundi"""
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r") as f:
                return json.load(f)
        except:
            return None
    return None

def clear_session_file():
    """Logout ainappudu local session file ni delete chesthundi"""
    if os.path.exists(SESSION_FILE):
        try:
            os.remove(SESSION_FILE)
        except:
            pass

def get_table_df(table_name):
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

def get_user_vault(user_id):
    """fetches user vault balance from DB"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT vault FROM Users WHERE user_id = ?", (user_id,))
        vault = cursor.fetchone()
        conn.close()
        return vault[0] if vault else 0.0
    except:
        return 0.0

def verify_login(email, password):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, name, vault FROM Users WHERE email = ? AND password = ?", (email, password))
        user = cursor.fetchone()
        conn.close()
        return user
    except:
        return None

def add_new_item_to_db(name, price, img_url):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # Default specifications and ratings assigned for newly added products
        cursor.execute("INSERT INTO Items (item_name, specifications, ratings, price, image_url) VALUES (?, ?, ?, ?, ?)",
                       (name, "Admin Added Special Item", 4.5, float(price), img_url))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        return False

def delete_item_from_db(item_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Items WHERE item_id = ?", (item_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        return False

def edit_item_in_db(item_id, name, specs, price, img_url):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE Items SET item_name = ?, specifications = ?, price = ?, image_url = ? WHERE item_id = ?", 
                       (name, specs, float(price), img_url, item_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        return False

def get_setting(key):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT setting_value FROM Settings WHERE setting_key = ?", (key,))
        val = cursor.fetchone()
        conn.close()
        return val[0] if val else link1
    except:
        return link1
        
def update_setting(key, value):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # INSERT OR REPLACE vaadithe, okavela table lekapoyina, record lekapoyina set aipothundi
        cursor.execute("INSERT OR REPLACE INTO Settings (setting_key, setting_value) VALUES (?, ?)", (key, value))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        return False

# --- 4. SESSION STATE INITIALIZATION (Browser Token Logic) ---
if "step" not in st.session_state:
    # Browser URL token ni check chesthundi (Kotha device aithe em undadu)
    token = st.query_params.get("token")
    
    if token == "admin_boss":
        st.session_state.step = "admin"
        st.session_state.user_name = "Admin Boss"
        st.session_state.user_id = None
    elif token:
        # Token tho user ni database lo vethukuthundi
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, name, vault, password FROM Users WHERE user_id = ?", (token,))
            user = cursor.fetchone()
            conn.close()
            if user:
                st.session_state.user_id = user[0]
                st.session_state.user_name = user[1]
                st.session_state.vault_balance = user[2]
                st.session_state.user_password = user[3]
                st.session_state.step = "main"
            else:
                st.session_state.step = "auth"
        except:
            st.session_state.step = "auth"
    else:
        st.session_state.step = "auth" 

if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_name" not in st.session_state:
    st.session_state.user_name = None
if "user_password" not in st.session_state:
    st.session_state.user_password = None
if "vault_balance" not in st.session_state:
    st.session_state.vault_balance = 0
if "messages" not in st.session_state:
    st.session_state.messages = []
if "trigger_ai_buy" not in st.session_state:
    st.session_state.trigger_ai_buy = None
if "reward_claimed" not in st.session_state:
    st.session_state.reward_claimed = False

# --- 5. AUTHENTICATION SCREEN ---
if st.session_state.step == "auth":
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        st.markdown("""
        <div style="text-align:center; margin-bottom:20px;">
            <h1 class="custom-logo" style="font-size: 40px;">A2Z-Kart</h1>
            <p style="color:#ccc;">HAMZA: The AI Shopping Assistant</p>
        </div>
        """, unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            st.subheader("Assalam Walekum 👋")
            login_email = st.text_input("Email Address")
            login_pass = st.text_input("Password", type="password")
            if st.button("Login", use_container_width=True, type="primary"):
                # Admin Login Verification
                if login_email == "admin.a2zkart@gmail.com" and login_pass == "admin1234":
                    st.session_state.user_name = "Admin Boss"
                    st.session_state.step = "admin"
                    # Kotha device ki idi admin ani gurthu pettukodaniki token
                    st.query_params["token"] = "admin_boss"
                    st.rerun()
                # Normal User Login Verification
                else:
                    user = verify_login(login_email, login_pass)
                    if user:
                        st.session_state.user_id = user[0]
                        st.session_state.user_name = user[1]
                        st.session_state.vault_balance = user[2]
                        st.session_state.user_password = login_pass
                        st.session_state.step = "main"
                        st.query_params["token"] = str(user[0])
                        st.rerun()
                    else:
                        st.error("Invalid Credentials! Have a look boss.")
                    
        with tab2:
            st.subheader("Create New Account")
            reg_name = st.text_input("Full Name")
            reg_email = st.text_input("New Email")
            reg_phone = st.text_input("Phone Number")
            reg_pass = st.text_input("Set Password", type="password")
            if st.button("Register & Get Vault Cash 💸", use_container_width=True):
                if reg_name and reg_email and reg_phone and reg_pass:
                    new_id = register_user(reg_name, reg_email, reg_phone, reg_pass)
                    if new_id:
                        st.session_state.user_id = new_id
                        st.session_state.user_name = reg_name
                        st.session_state.user_password = reg_pass
                        st.session_state.step = "main"
                        st.query_params["token"] = str(new_id)
                        st.rerun()
                else:
                    st.warning("Bhaai saab! Fill in all the details to register.")

# --- 6. ADMIN DASHBOARD SCREEN ---
elif st.session_state.step == "admin":
    # Custom Header for Admin
    header_html = f"""
    <div class="custom-header">
        <div class="custom-logo">A2Z-Kart Admin</div>
        <div class="custom-badge" style="background: rgba(255, 50, 50, 0.2); border: 1px solid red; color: #ffcccc;">
            👑 Admin Control Panel
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)
    st.markdown("<br><br><br>", unsafe_allow_html=True)

    st.title("🛠️ Admin Dashboard")
    
    # Logout option
    col_x, col_y = st.columns([8, 1])
    if col_y.button("Logout", type="primary"):
        # Logout ayinappudu token clear aipothundi
        st.query_params.clear()
        st.session_state.clear()
        st.rerun()

    # Product Addition Form
    with st.expander("➕ Add New Product to Store", expanded=True):
        with st.form("add_product_form"):
            c1, c2 = st.columns(2)
            new_item_name = c1.text_input("Product Name (Ex: Nike Shoes)")
            new_item_price = c1.number_input("Price (₹)", min_value=1)
            new_item_img = c2.text_input("Image URL (Unsplash/Web link)")
            
            submit_btn = st.form_submit_button("Publish Product 🚀")
            if submit_btn:
                if new_item_name and new_item_price and new_item_img:
                    success = add_new_item_to_db(new_item_name, new_item_price, new_item_img)
                    if success:
                        st.success(f"Wah! '{new_item_name}' successfully added to store.")
                    else:
                        st.error("Error occurred while adding the product.")
                else:
                    st.warning("Bhaai saab! Fill in all the details to add the product.")

    # Product Edit Form
    with st.expander("✏️ Edit Product in Store", expanded=False):
        current_items = get_table_df("Items")
        if not current_items.empty:
            # Create a dictionary to map Item Name to the entire row for dropdown
            item_options_edit = {f"{row['item_name']} (ID: {row['item_id']})": row for index, row in current_items.iterrows()}
            selected_item_label_edit = st.selectbox("Select Product to Edit", options=list(item_options_edit.keys()), key="edit_select")
            
            selected_row = item_options_edit[selected_item_label_edit]
            
            with st.form("edit_product_form"):
                c1, c2 = st.columns(2)
                edit_item_name = c1.text_input("New Product Name", value=str(selected_row['item_name']))
                edit_item_price = c1.number_input("New Price (₹)", min_value=1, value=int(selected_row['price']))
                
                # Handle empty/NaN specifications safely
                current_specs = selected_row.get('specifications', '')
                if pd.isna(current_specs): current_specs = ''
                edit_item_specs = st.text_area("Specifications", value=str(current_specs))
                
                # Handle empty/NaN image URLs safely
                current_img = selected_row.get('image_url', '')
                if pd.isna(current_img): current_img = ''
                edit_item_img = st.text_input("New Image URL", value=str(current_img))
                
                update_btn = st.form_submit_button("Update Product 🔄")
                if update_btn:
                    if edit_item_name and edit_item_price:
                        success = edit_item_in_db(selected_row['item_id'], edit_item_name, edit_item_specs, edit_item_price, edit_item_img)
                        if success:
                            st.success("Item details updated successfully!")
                            st.rerun()
                        else:
                            st.error("Error occurred while updating the product.")
                    else:
                        st.warning("Name and Price are mandatory boss!")
        else:
            st.info("Store lo items em levu boss edit cheyadaniki.")

    # Product Deletion Form
    with st.expander("🗑️ Delete Product from Store", expanded=False):
        current_items = get_table_df("Items")
        if not current_items.empty:
            # Create a dictionary to map Item Name to Item ID for dropdown
            item_options = {f"{row['item_name']} (ID: {row['item_id']} - ₹{row['price']})": row['item_id'] for index, row in current_items.iterrows()}
            selected_item_label = st.selectbox("Select Product to Delete", options=list(item_options.keys()))
            
            if st.button("Delete Product ⚠️", type="primary"):
                item_id_to_delete = item_options[selected_item_label]
                success = delete_item_from_db(item_id_to_delete)
                if success:
                    st.success("Item successfully deleted!")
                    st.rerun()
                else:
                    st.error("Error occurred while deleting the product.")
        else:
            st.info("No items available for deletion.")

    # Admin Recharge Link Manager
    with st.expander("🔗 Manage Recharge Link (For Users)", expanded=False):
        current_link = get_setting('recharge_link')
        with st.form("recharge_link_form"):
            new_link = st.text_input("Recharge Link (e.g., https://google.com)", value=current_link)
            update_btn = st.form_submit_button("Update Recharge Link 🔄")
            if update_btn:
                success = update_setting('recharge_link', new_link)
                if success:
                    st.success("Recharge link updated for all users!")
                    st.rerun()
                else:
                    st.error("Failed to update the recharge link.")

    st.markdown("---")
    st.subheader("🖥️ Current System Database")
    tab_o, tab_i, tab_v, tab_u = st.tabs(["Orders", "Items Catalog", "App Revenue", "Users Info"])
    with tab_o: 
        o_df = get_table_df("Orders")
        if not o_df.empty:
            # Render order_group_id as the primary 'Order ID' visually for same ID matching
            o_df = o_df.rename(columns={"order_group_id": "Order ID", "order_name": "Item Name", "price": "Unit Price"})
            o_df["Unit Price"] = pd.to_numeric(o_df["Unit Price"]).apply(lambda x: f"₹{x:,.2f}")
            st.dataframe(o_df[["Order ID", "customer_name", "Item Name", "quantity", "Unit Price", "status", "order_date"]], use_container_width=True, hide_index=True)
        else:
            st.dataframe(o_df, use_container_width=True, hide_index=True)
    with tab_i: 
        i_df = get_table_df("Items")
        if not i_df.empty:
            i_df["price"] = pd.to_numeric(i_df["price"]).apply(lambda x: f"₹{x:,.2f}")
            st.dataframe(i_df, use_container_width=True, hide_index=True)
        else:
            st.dataframe(i_df, use_container_width=True, hide_index=True)
    with tab_v: 
        v_df = get_table_df("App_Vault")
        if not v_df.empty:
            v_df["total_amount"] = pd.to_numeric(v_df["total_amount"]).apply(lambda x: f"₹{x:,.2f}")
            st.dataframe(v_df, use_container_width=True, hide_index=True)
        else:
            st.dataframe(v_df, use_container_width=True, hide_index=True)
    with tab_u: 
        users_df = get_table_df("Users")
        if not users_df.empty:
            users_df["vault"] = pd.to_numeric(users_df["vault"]).apply(lambda x: f"₹{x:,.2f}")
            st.dataframe(users_df[["user_id", "name", "email", "vault"]], use_container_width=True, hide_index=True)
        else:
            st.dataframe(users_df, use_container_width=True, hide_index=True)

# --- 7. MAIN APPLICATION SCREEN (NORMAL USER) ---
elif st.session_state.step == "main":
    
    header_html = f"""
    <div class="custom-header">
        <div class="custom-logo">A2Z-Kart</div>
        <div class="custom-badge">Hello, {st.session_state.user_name} 👋 | Vault: ₹{st.session_state.vault_balance:,.2f}</div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)
    st.markdown("<br><br>", unsafe_allow_html=True) 

    # Normal user logout option (Duplicate theesesi clean chesam)
    if st.button("Logout 🚪", key="main_logout_btn", type="secondary"):
        st.query_params.clear()
        st.session_state.clear()
        clear_session_file()
        st.rerun()

    # Recharge Popover (Small Dashboard for User)
    with st.popover("🔋 Recharge Vault (Free Cash)"):
        st.markdown("### 💸 Sponsored Recharge")
        link_text = get_setting('recharge_link')
        safe_link = link_text if link_text.startswith(('http://', 'https://')) else f"https://{link_text}"
        
        if not st.session_state.reward_claimed:
            st.write("Get instant ₹10,000 added to your vault!")
            # Direct JS Redirect Button
            if st.button("Claim ₹10,000 & Visit Link 🌐", use_container_width=True, type="primary"):
                success = recharge_user_vault(st.session_state.user_id, 10000)
                if success:
                    st.session_state.vault_balance += 10000
                    st.session_state.reward_claimed = True
                    st.session_state.do_redirect = safe_link
                    st.rerun()
        else:
            st.success("🎉 ₹10,000 Credited!")
            st.write("If the webpage didn't open automatically, click below:")
            
            # HTML Fallback Link (Browser pop-up block chesthe idhi vadukochu)
            html_link = f"""
            <a href="{safe_link}" target="_blank" style="display: block; text-align: center; background: linear-gradient(135deg, #009dff, #00e5ff); color: white; padding: 10px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-bottom: 10px;">
                🌐 Click here to Visit
            </a>
            """
            st.markdown(html_link, unsafe_allow_html=True)
            
            if st.button("Close / Reset", use_container_width=True):
                st.session_state.reward_claimed = False
                st.rerun()

    # Ee piece of code JS ni vaadi browser lo kotha tab open chesthundi
    if st.session_state.get("do_redirect"):
        safe_link = st.session_state.do_redirect
        st.components.v1.html(
            f"<script>window.parent.open('{safe_link}', '_blank');</script>",
            height=0
        )
        st.session_state.do_redirect = False

    left_col, right_col = st.columns([1, 2.5], gap="large")

    with right_col:
        st.markdown("""
        <div class="hero-box">
            <h1 style="margin:0; font-size:36px;">Welcome to A2Z-Kart AI Experience</h1>
            <p style="margin-top:10px; color:#ddd;">Shop Electronics, Fashion, and more by just chatting with our AI!</p>
        </div>
        """, unsafe_allow_html=True)

        st.subheader("🔥 Trending Products")
        
        items_df = get_table_df("Items")
        if not items_df.empty:
            cols = st.columns(3)
            for index, row in items_df.iterrows():
                with cols[index % 3]:
                    # Admin icchina custom image URL unda leda patha default aa ani check chestham
                    img_src = row.get('image_url', '')
                    if pd.isna(img_src) or img_src == '':
                        # Default fallback images
                        img_src = "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=400" if "MacBook" in row['item_name'] or "Laptop" in row['item_name'] else "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=400"
                    
                    # Custom HTML for uniform image sizing so items are perfectly visible
                    st.markdown(f'''
                        <div style="height: 200px; width: 100%; display: flex; align-items: center; justify-content: center; background: rgba(255,255,255,0.02); border-radius: 10px; margin-bottom: 10px; overflow: hidden;">
                            <img src="{img_src}" style="max-width: 100%; max-height: 100%; object-fit: contain;">
                        </div>
                    ''', unsafe_allow_html=True)
                    
                    st.markdown(f"**{row['item_name']}**")
                    st.markdown(f"<span style='color:#00e5ff; font-weight:bold; font-size:18px;'>₹{float(row['price']):,.2f}</span>", unsafe_allow_html=True)
                    
                    # Column nesting limit exceed ayyindi kabatti vertical ga stack chesthunnam
                    qty_key = f"qty_{row['item_id']}"
                    selected_qty = st.number_input("Quantity", min_value=1, max_value=20, value=1, step=1, key=qty_key)
                    
                    if st.button(f"Add via HAMZA", key=f"btn_{row['item_id']}", use_container_width=True):
                        # User select chesina quantity ni Agent prompt loki add chesthunnam
                        st.session_state.trigger_ai_buy = f"Buy {selected_qty} pieces of item ID {row['item_id']} ({row['item_name']})"
                        st.rerun()
        else:
            st.info("No items found in DB. Run Phase 1 script again.")

        st.markdown("---")
        st.subheader("🛒 Your Recent Orders")
        orders_df = get_table_df("Orders")
        if not orders_df.empty:
            # Filter to show only current user's orders
            user_orders = orders_df[orders_df['user_id'] == st.session_state.user_id].copy()
            user_orders = user_orders.rename(columns={"order_group_id": "Order ID", "order_name": "Item Name", "price": "Unit Price"})
            if not user_orders.empty:
                user_orders["Unit Price"] = pd.to_numeric(user_orders["Unit Price"]).apply(lambda x: f"₹{x:,.2f}")
                st.dataframe(user_orders[["Order ID", "Item Name", "quantity", "Unit Price", "status", "order_date"]], use_container_width=True, hide_index=True)

    with left_col:
        st.markdown("<h3 style='text-align:center; color:#00e5ff;'>🤖 A2Z AI Copilot</h3>", unsafe_allow_html=True)
        st.markdown("<hr style='border-color: rgba(255,255,255,0.1);'>", unsafe_allow_html=True)
        
        chat_container = st.container(height=500)
        
        with chat_container:
            if len(st.session_state.messages) == 0:
                st.chat_message("assistant").write("Assalam Walekum, I'm Hamza. Your Ai assistant, What can i do for you?")
                
            for msg in st.session_state.messages:
                if isinstance(msg, HumanMessage):
                    st.chat_message("user").write(msg.content)
                elif isinstance(msg, SystemMessage):
                    continue
                elif hasattr(msg, "content") and msg.content:
                    st.chat_message("assistant").write(msg.content)

        user_query = st.chat_input("Ask agent to order, cancel...")
        
        if st.session_state.trigger_ai_buy:
            user_query = st.session_state.trigger_ai_buy
            st.session_state.trigger_ai_buy = None 

        if user_query:
            chat_container.chat_message("user").write(user_query)
            
            try:
                llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.0)
                llm_with_tools = llm.bind_tools(ecommerce_tools)
                tool_map = {tool.name: tool for tool in ecommerce_tools}

                system_prompt = SystemMessage(content=f"""You are an expert E-commerce Customer Support Agent.
                The current logged-in user is {st.session_state.user_name} with user_id = {st.session_state.user_id}.
                If the user wants to buy/order an item or check balance, use their logged-in user_id ({st.session_state.user_id}) directly.
                Do not ask them for their user_id unless they specifically talk about another account.
                And just before executing any action like placing an order, checking vault balance, or canceling an order, 
                confirm with the user once by asking "Are you sure you want to [action]?" and make them enter their password to proceed. 
                Only proceed if the provided password exactly matches {st.session_state.user_password}, otherwise cancel it and inform the user about incorrect password.
                Do not execute any action without this confirmation step.
                Communication should be friendly and English only.
                
                 CRITICAL RULES (MUST FOLLOW STRICTLY):
                1. NO RAW TAGS: NEVER output raw function call syntax (e.g., `<function=...>`, JSON blocks) in your text responses. Just talk naturally.
                2. SMART CATALOG FILTERING: If the user asks a general question like "what do you sell?", reply: "Please check the items displayed on the website." 
                BUT, if the user asks for specific recommendations like "top 5 rated items", "best RAM in phones", "shoes under 2000", or "Any black color shoes" fetch the catalog, filter it internally, and display ONLY the matching items neatly in a human-readable list.
                if not matching then simply say "Not available Bhaai saab!".
                3. USE CORRECT TOOLS SILENTLY: When you need to check balance or buy items, invoke the tools properly. Do NOT type out the tool name to the user.
                4. NEVER guess a user_id, item_id, or order_id. Always use the logged-in user_id ({st.session_state.user_id}).
                5. PURCHASE FORMAT: Use `purchase_items_tool` and pass a list of dicts. e.g., [{{"item_id": 1, "quantity": 4}}].
                6. STRICT DOMAIN RESTRICTION: You ONLY help with A2Z-Kart shopping. Refuse anything else politely by saying "Hamza can't help you with that, cause he is loyal to his boss."
                7. NEVER dump the entire raw catalog.
                """)

                history = [system_prompt] + st.session_state.messages + [HumanMessage(content=user_query)]
                
                with chat_container:
                    with st.spinner("Agent is working..."):
                        response = llm_with_tools.invoke(history)
                        history.append(response)

                        while response.tool_calls:
                            for tool_call in response.tool_calls:
                                st.info(f"⚙️ Running DB Action: {tool_call['name']}")
                                selected_tool = tool_map[tool_call["name"]]
                                tool_output = selected_tool.invoke(tool_call["args"])
                                
                                history.append(ToolMessage(
                                    content=str(tool_output),
                                    tool_call_id=tool_call["id"]
                                ))
                            response = llm_with_tools.invoke(history)
                            history.append(response)
                        
                        st.chat_message("assistant").write(response.content)
                
                st.session_state.messages = history[1:]
                st.rerun() 
                
            except Exception as e:
                chat_container.error(f"API Error: Check your Groq API Key! Details: {str(e)}")
