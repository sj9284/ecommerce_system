from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import mysql.connector
from price_negotiator import PriceNegotiatorBot
import qrcode
from io import BytesIO
import base64

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Replace with a secure key in production

# Database Connection
def connect_db():
    try:
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password="12345678",
            database="ecommerce_db"
        )
    except mysql.connector.Error as e:
        print(f"Database connection error: {e}")
        return None

# Create Tables
def create_tables():
    conn = connect_db()
    if conn is None:
        return
    cursor = conn.cursor()
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(255) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL
    )""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS products (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        price DECIMAL(10,2) NOT NULL,
        category VARCHAR(255) NOT NULL
    )""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS cart (
        cart_id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        product_id INT NOT NULL,
        quantity INT DEFAULT 1,
        negotiated_price DECIMAL(10,2),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS purchases (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        product_id INT NOT NULL,
        quantity INT DEFAULT 1,
        total_price DECIMAL(10,2) NOT NULL,
        purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )""")
    
    conn.commit()
    conn.close()

# Populate sample products with more categories
def populate_sample_products():
    conn = connect_db()
    if conn is None:
        return
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:  # Only populate if table is empty
        sample_products = [
            # Electronics
            ("Smartphone", 299.99, "Electronics"),
            ("Laptop", 799.99, "Electronics"),
            ("Wireless Earbuds", 99.99, "Electronics"),
            ("Smart TV", 499.99, "Electronics"),
            # Beverages
            ("Cola", 1.99, "Beverages"),
            ("Orange Juice", 3.49, "Beverages"),
            ("Coffee", 5.99, "Beverages"),
            ("Mineral Water", 0.99, "Beverages"),
            # Food
            ("Pasta", 2.49, "Food"),
            ("Pizza", 9.99, "Food"),
            ("Burger", 5.49, "Food"),
            ("Rice", 1.99, "Food"),
            # Desserts
            ("Chocolate Cake", 12.99, "Desserts"),
            ("Ice Cream", 4.99, "Desserts"),
            ("Cookies", 3.49, "Desserts"),
            ("Donuts", 2.99, "Desserts"),
            # Appliances
            ("Microwave Oven", 89.99, "Appliances"),
            ("Blender", 49.99, "Appliances"),
            ("Toaster", 29.99, "Appliances"),
            ("Refrigerator", 599.99, "Appliances"),
            # Furniture
            ("Sofa", 399.99, "Furniture"),
            ("Dining Table", 249.99, "Furniture"),
            ("Bookshelf", 79.99, "Furniture"),
            ("Bed Frame", 199.99, "Furniture")
        ]
        cursor.executemany("INSERT INTO products (name, price, category) VALUES (%s, %s, %s)", sample_products)
        conn.commit()
    conn.close()

# Routes (unchanged from previous version)
@app.route('/')
def login_page():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']
    conn = connect_db()
    if conn is None:
        return jsonify({'error': 'Database connection failed'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
        conn.commit()
        return jsonify({'message': 'Registration successful'}), 200
    except mysql.connector.IntegrityError:
        return jsonify({'error': 'Username already exists'}), 400
    finally:
        conn.close()

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    conn = connect_db()
    if conn is None:
        return jsonify({'error': 'Database connection failed'}), 500
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
    user = cursor.fetchone()
    conn.close()
    if user:
        session['username'] = username
        return jsonify({'message': 'Login successful'}), 200
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('username', None)
    session.pop('bot', None)
    return jsonify({'message': 'Logged out'}), 200

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login_page'))
    conn = connect_db()
    if conn is None:
        return "Database connection failed", 500
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM products")
    categories = cursor.fetchall()
    products_by_category = {}
    for category in categories:
        cat_name = category[0]
        cursor.execute("SELECT id, name, price FROM products WHERE category=%s", (cat_name,))
        products_by_category[cat_name] = cursor.fetchall()
    
    cursor.execute("SELECT id FROM users WHERE username=%s", (session['username'],))
    user_id = cursor.fetchone()[0]
    cursor.execute("""
        SELECT p.name, c.quantity, p.price, c.negotiated_price,
               (c.quantity * COALESCE(c.negotiated_price, p.price)) AS total_price
        FROM cart c JOIN products p ON c.product_id = p.id WHERE c.user_id = %s
    """, (user_id,))
    cart_items = cursor.fetchall()
    total_cart_value = sum(item[4] for item in cart_items)
    conn.close()
    return render_template('dashboard.html', products_by_category=products_by_category, cart_items=cart_items, total_cart_value=total_cart_value)

@app.route('/negotiate', methods=['POST'])
def negotiate():
    product_name = request.form['product_name']
    product_price = float(request.form['product_price'])
    if 'username' not in session:
        return jsonify({'error': 'Please log in'}), 401
    bot = PriceNegotiatorBot(product_name, product_price, session['username'])
    session['bot'] = {
        'product_name': product_name,
        'base_price': product_price,
        'username': session['username'],
        'state': bot.state,
        'current_offer': bot.current_offer,
        'bot_counter': bot.bot_counter,
        'negotiation_attempts': bot.negotiation_attempts,
        'history': bot.history
    }
    initial_message = bot.process_input("")
    session['bot']['state'] = bot.state
    return render_template('chatbot.html', product_name=product_name, product_price=product_price, initial_message=initial_message)

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json['message']
    if 'bot' not in session:
        return jsonify({'error': 'Negotiation session expired. Start a new one.'}), 400
    
    bot = PriceNegotiatorBot(session['bot']['product_name'], session['bot']['base_price'], session['bot']['username'])
    bot.state = session['bot']['state']
    bot.current_offer = session['bot']['current_offer']
    bot.bot_counter = session['bot']['bot_counter']
    bot.negotiation_attempts = session['bot']['negotiation_attempts']
    bot.history = session['bot']['history']
    
    response = bot.process_input(user_input)
    
    session['bot']['state'] = bot.state
    session['bot']['current_offer'] = bot.current_offer
    session['bot']['bot_counter'] = bot.bot_counter
    session['bot']['negotiation_attempts'] = bot.negotiation_attempts
    session['bot']['history'] = bot.history
    
    return jsonify({'response': response})

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'username' not in session:
        return jsonify({'error': 'Please log in'}), 401
    product_name = request.json['product_name']
    negotiated_price = float(request.json['negotiated_price']) if request.json.get('negotiated_price') else None
    
    conn = connect_db()
    if conn is None:
        return jsonify({'error': 'Database connection failed'}), 500
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username=%s", (session['username'],))
    user_id = cursor.fetchone()[0]
    cursor.execute("SELECT id, price FROM products WHERE name=%s", (product_name,))
    product = cursor.fetchone()
    
    if product:
        product_id, original_price = product
        final_price = negotiated_price if negotiated_price is not None else original_price
        cursor.execute("SELECT quantity FROM cart WHERE user_id=%s AND product_id=%s", (user_id, product_id))
        existing_item = cursor.fetchone()
        
        if existing_item:
            new_quantity = existing_item[0] + 1
            cursor.execute("UPDATE cart SET quantity=%s, negotiated_price=%s WHERE user_id=%s AND product_id=%s",
                           (new_quantity, final_price, user_id, product_id))
        else:
            cursor.execute("INSERT INTO cart (user_id, product_id, quantity, negotiated_price) VALUES (%s, %s, %s, %s)",
                           (user_id, product_id, 1, final_price))
        conn.commit()
        conn.close()
        return jsonify({'message': f"Added {product_name} to cart at ${final_price:.2f}"}), 200
    conn.close()
    return jsonify({'error': 'Product not found'}), 404

@app.route('/buy_now', methods=['GET', 'POST'])
def buy_now():
    if 'username' not in session:
        return redirect(url_for('login_page'))
    
    if request.method == 'GET':
        conn = connect_db()
        if conn is None:
            return "Database connection failed", 500
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username=%s", (session['username'],))
        user_id = cursor.fetchone()[0]
        cursor.execute("""
            SELECT p.name, c.quantity, p.price, c.negotiated_price,
                   (c.quantity * COALESCE(c.negotiated_price, p.price)) AS total_price
            FROM cart c JOIN products p ON c.product_id = p.id WHERE c.user_id = %s
        """, (user_id,))
        cart_items = cursor.fetchall()
        total_amount = sum(item[4] for item in cart_items)
        conn.close()
        if not cart_items:
            return redirect(url_for('dashboard'))
        return render_template('payment.html', cart_items=cart_items, total_amount=total_amount)
    
    if request.method == 'POST':
        payment_method = request.form['payment_method']
        conn = connect_db()
        if conn is None:
            return jsonify({'error': 'Database connection failed'}), 500
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username=%s", (session['username'],))
        user_id = cursor.fetchone()[0]
        cursor.execute("""
            SELECT c.product_id, c.quantity, p.price, c.negotiated_price,
                   (c.quantity * COALESCE(c.negotiated_price, p.price)) AS total_price
            FROM cart c JOIN products p ON c.product_id = p.id WHERE c.user_id = %s
        """, (user_id,))
        cart_items = cursor.fetchall()
        
        if payment_method == 'upi':
            upi_url = "upi://pay?pa=yourname@upi&pn=YourName&am={:.2f}&cu=INR".format(sum(item[4] for item in cart_items))
            qr = qrcode.make(upi_url)
            buffer = BytesIO()
            qr.save(buffer, format="PNG")
            qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            for item in cart_items:
                cursor.execute("INSERT INTO purchases (user_id, product_id, quantity, total_price) VALUES (%s, %s, %s, %s)",
                               (user_id, item[0], item[1], item[4]))
            cursor.execute("DELETE FROM cart WHERE user_id=%s", (user_id,))
            conn.commit()
            conn.close()
            return jsonify({'message': 'Purchase successful with UPI!', 'qr_code': qr_base64})
        
        elif payment_method == 'net_banking':
            account_number = request.form.get('account_number')
            ifsc_code = request.form.get('ifsc_code')
            if not (account_number and ifsc_code):
                return jsonify({'error': 'Account number and IFSC code are required'}), 400
            for item in cart_items:
                cursor.execute("INSERT INTO purchases (user_id, product_id, quantity, total_price) VALUES (%s, %s, %s, %s)",
                               (user_id, item[0], item[1], item[4]))
            cursor.execute("DELETE FROM cart WHERE user_id=%s", (user_id,))
            conn.commit()
            conn.close()
            return jsonify({'message': f'Purchase successful with Net Banking! Account: {account_number}'})
        
        elif payment_method == 'credit_card':
            card_number = request.form.get('card_number')
            expiry = request.form.get('expiry')
            cvv = request.form.get('cvv')
            if not (card_number and expiry and cvv):
                return jsonify({'error': 'Card details are required'}), 400
            for item in cart_items:
                cursor.execute("INSERT INTO purchases (user_id, product_id, quantity, total_price) VALUES (%s, %s, %s, %s)",
                               (user_id, item[0], item[1], item[4]))
            cursor.execute("DELETE FROM cart WHERE user_id=%s", (user_id,))
            conn.commit()
            conn.close()
            return jsonify({'message': f'Purchase successful with Credit Card! Card: **** **** **** {card_number[-4:]}'})
        
        conn.close()
        return jsonify({'error': 'Invalid payment method'}), 400

if __name__ == '__main__':
    create_tables()
    populate_sample_products()
    app.run(debug=True)