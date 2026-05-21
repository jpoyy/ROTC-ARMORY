from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
import qrcode
import os
from datetime import datetime, date
import urllib.parse  # ✅ ADDED (safe chart encoding)
import re

app = Flask(__name__)
app.secret_key = 'Arm0rSafe#2026$LNU'


def get_db_connection():
    conn = sqlite3.connect('database.db', timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# =========================
# NORMALIZATION (FIXED CLEANED)
# =========================
def normalize_category(category):
    mapping = {
        "Firearms": "Firearms",
        "Swords": "Swords",
        "Uniforms": "Uniforms",
        "Audio Visuals": "Audio-Visuals",
        "Audio-Visuals": "Audio-Visuals"
    }
    return mapping.get(category, category)


def normalize_condition(condition):
    mapping = {
        "Serviceable": "Serviceable",
        "Damaged": "Damaged",
        "Under Repair": "Under Repair",
        "Under repair": "Under Repair"
    }
    return mapping.get(condition, condition)

def calculate_age(date_of_birth):
    birth_date = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
    today = date.today()

    age = today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )

    return age

def is_strong_password(password):
    pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$'
    return re.match(pattern, password)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            category TEXT,
            condition TEXT,
            qr_code TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            field_changed TEXT,
            old_condition TEXT,
            new_condition TEXT,
            date TEXT
        )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS masterlist(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT UNIQUE,
        rotc_class TEXT,
        gender TEXT,
        date_of_birth TEXT,
        course TEXT
    )
''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT,
        age INTEGER,
        rotc_class TEXT,
        gender TEXT,
        date_of_birth TEXT,
        course TEXT,
        contact_number TEXT,
        email TEXT UNIQUE,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT,
        last_login TEXT
    )
''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            user_id INTEGER,
            requested_condition TEXT,
            reason TEXT,
            status TEXT,
            date TEXT
        )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS add_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        category TEXT,
        condition TEXT,
        status TEXT,
        date TEXT
    )
''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS delete_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            user_id INTEGER,
            reason TEXT,
            status TEXT,
            date TEXT
        )
    ''')

    cursor.execute("SELECT * FROM users WHERE username=?", ("Battalion_S4",))
    admin = cursor.fetchone()

    if not admin:
        cursor.execute('''
    INSERT INTO users
    (full_name, age, rotc_class, gender, date_of_birth,
     course, contact_number, email, username, password, role)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (
    "System Administrator",
    20,
    "N/A",
    "FEMALE",
    "1995-01-01",
    "N/A",
    "N/A",
    "admin@armorsafe.com",
    "Battalion_S4",
    "1234",
    "admin"
))

    conn.commit()
    conn.close()


APP_BASE_URL = "https://your-render-url.onrender.com"

def generate_qr(item_id):

    url = f"{APP_BASE_URL}/item/{item_id}"

    filename = f"qr_{item_id}.png"
    filepath = os.path.join('static', filename)

    img = qrcode.make(url)
    img.save(filepath)

    return filename

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE (username=? OR email=?) AND password=?",
            (username, username, password)
        )

        user = cursor.fetchone()
        conn.close()

        if user:
            session['user_id'] = user[0]
            session['username'] = user[9]
            session['role'] = user[11]

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE users SET last_login=? WHERE id=?",
                (datetime.now().strftime("%Y-%m-%d %H:%M"), user[0])
            )

            conn.commit()
            conn.close()

            return redirect('/dashboard')

        flash("Invalid username or password")
        return redirect('/')

    return render_template('login.html')

@app.route('/regenerate_qr')
def regenerate_qr():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM items")
    items = cursor.fetchall()

    for item in items:
        item_id = item[0]

        qr_filename = generate_qr(item_id)

        cursor.execute(
            "UPDATE items SET qr_code=? WHERE id=?",
            (qr_filename, item_id)
        )

    conn.commit()
    conn.close()

    return "All QR codes regenerated!"

@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    if request.method == 'POST':
        full_name = " ".join(request.form['full_name'].split())
        rotc_class = request.form['rotc_class'].strip()
        gender = request.form['gender'].strip().upper()
        date_of_birth = request.form['date_of_birth'].strip()

        age = calculate_age(date_of_birth)

        course = " ".join(request.form['course'].split()).upper()
        contact_number = request.form['contact_number'].strip()
        email = request.form['email'].strip()
        username = request.form['username'].strip()
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if not is_strong_password(password):
            flash("Password must be at least 8 characters and include uppercase, lowercase, number, and special character.")
            return redirect('/create_account')

        if password != confirm_password:
            flash("Passwords do not match!")
            return redirect('/create_account')

        if age < 16 or age > 60:
            flash("Invalid age.")
            return redirect('/create_account')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Flexible masterlist checking
        cursor.execute('''
            SELECT * FROM masterlist
            WHERE REPLACE(LOWER(full_name), '  ', ' ') = LOWER(?)
            AND TRIM(rotc_class) = ?
            AND UPPER(TRIM(gender)) = ?
            AND date_of_birth = ?
            AND UPPER(TRIM(course)) = ?
        ''', (
            full_name.lower(),
            rotc_class,
            gender,
            date_of_birth,
            course
        ))

        officer = cursor.fetchone()

        if not officer:
            conn.close()
            flash("Access is restricted to ROTC Officers included in the Masterlist. Please make sure to verify your credentials.")
            return redirect('/create_account')

        try:
            cursor.execute('''
                INSERT INTO users
                (full_name, age, rotc_class, gender, date_of_birth,
                course, contact_number, email, username, password, role)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                full_name,
                age,
                rotc_class,
                gender,
                date_of_birth,
                course,
                contact_number,
                email,
                username,
                password,
                "officers"
            ))

            conn.commit()

        except sqlite3.IntegrityError:
            flash("Email or username already exists!")
            conn.close()
            return redirect('/create_account')

        finally:
            conn.close()

        flash("Account created successfully!")
        return redirect('/')

    return render_template('create_account.html')


@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Inventory totals
    cursor.execute("SELECT COUNT(*) FROM items")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM items WHERE condition='Serviceable'")
    Serviceable = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM items WHERE condition='Damaged'")
    Damaged = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM items WHERE condition='Under Repair'")
    repair = cursor.fetchone()[0]

    # Category totals
    cursor.execute("SELECT COUNT(*) FROM items WHERE category='Firearms'")
    Firearms = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM items WHERE category='Swords'")
    Swords = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM items WHERE category='Uniforms'")
    Uniforms = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM items WHERE category='Audio-Visuals'")
    Audio_Visuals = cursor.fetchone()[0]

    conn.close()

    chart_config = {
        "type": "pie",
        "data": {
            "labels": ["Serviceable", "Damaged", "Under Repair"],
            "datasets": [{
                "data": [Serviceable, Damaged, repair]
            }]
        },
        "options": {
            "plugins": {
                "legend": {
                    "labels": {
                        "color": "white"
                    }
                },
                "datalabels": {
                    "color": "white",
                    "font": {
                        "size": 18,
                        "weight": "bold"
                    }
                }
            }
        }
    }

    category_config = {
        "type": "pie",
        "data": {
            "labels": ["Firearms", "Swords", "Uniforms", "Audio-Visuals"],
            "datasets": [{
                "data": [Firearms, Swords, Uniforms, Audio_Visuals]
            }]
        },
        "options": {
            "plugins": {
                "legend": {
                    "labels": {
                        "color": "white"
                    }
                },
                "datalabels": {
                    "color": "white",
                    "font": {
                        "size": 18,
                        "weight": "bold"
                    }
                }
            }
        }
    }

    chart_url = "https://quickchart.io/chart?c=" + urllib.parse.quote(str(chart_config))
    category_chart_url = "https://quickchart.io/chart?c=" + urllib.parse.quote(str(category_config))

    return render_template(
    'dashboard.html',
    total=total,
    Serviceable=Serviceable,
    Damaged=Damaged,
    repair=repair,
    Firearms=Firearms,
    Swords=Swords,
    Uniforms=Uniforms,
    Audio_Visuals=Audio_Visuals,
    chart_url=chart_url,
    category_chart_url=category_chart_url
    )

@app.route('/scan')
def scan():
    if not session.get('user_id'):
        return redirect('/')
    return render_template('scan.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if not is_strong_password(new_password):
            flash("Password must contain uppercase, lowercase, number, special character, and be at least 8 characters.")
            return redirect('/forgot_password')

        if new_password != confirm_password:
            flash("Passwords do not match")
            return redirect('/forgot_password')

        conn = get_db_connection()
        cursor = conn.cursor()

        username = request.form['username']
        date_of_birth = request.form['date_of_birth']

        cursor.execute('''
            SELECT *
            FROM users
            WHERE email=?
            AND username=?
            AND date_of_birth=?
        ''', (
            email,
            username,
            date_of_birth
        ))

        user = cursor.fetchone()

        if not user:
            flash("Provided credentials do not match any account.")
            conn.close()
            return redirect('/forgot_password')

        cursor.execute(
            "UPDATE users SET password=? WHERE email=?",
            (new_password, email)
        )

        if cursor.rowcount == 0:
            flash("Email not found")
        else:
            flash("Password updated successfully")

        conn.commit()
        conn.close()

        return redirect('/')

    return render_template('forgot_password.html')


@app.route('/add', methods=['GET', 'POST'])
def add_item():
    if session.get('role') != 'admin':
        return 'Access Denied!'

    if request.method == 'POST':
        name = request.form['name']
        category = normalize_category(request.form['category'])
        condition = normalize_condition(request.form['condition'])

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO items (name, category, condition) VALUES (?,?,?)",
            (name, category, condition)
        )

        item_id = cursor.lastrowid
        qr_filename = generate_qr(item_id)

        cursor.execute(
            "UPDATE items SET qr_code=? WHERE id=?",
            (qr_filename, item_id)
        )

        conn.commit()
        conn.close()

        return redirect('/inventory')

    return render_template('add_item.html')


@app.route('/inventory')

def inventory():
    if not session.get('user_id'):
        return redirect('/')

    condition = request.args.get('condition')
    category = request.args.get('category')

    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM items WHERE 1=1"
    params = []

    if condition:
        query += " AND condition=?"
        params.append(normalize_condition(condition))

    if category:
        query += " AND category=?"
        params.append(normalize_category(category))

    cursor.execute(query, params)
    items = cursor.fetchall()
    conn.close()

    return render_template('inventory.html', items=items)


@app.route('/item/<int:item_id>')
def view_item(item_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM items WHERE id=?", (item_id,))
    row = cursor.fetchone()

    if not row:
        return "Item not found"

    item = {
        "id": row[0],
        "name": row[1],
        "category": row[2],
        "condition": row[3],
        "qr_code": row[4]
    }

    conn.close()
    return render_template("item.html", item=item)

@app.route('/edit/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM items WHERE id=?", (item_id,))
    item = cursor.fetchone()

    if not item:
        conn.close()
        return "Item not found"

    if request.method == 'POST':
        new_name = request.form['name'].strip()
        new_category = normalize_category(request.form['category'])
        new_condition = normalize_condition(request.form['condition'])

        old_name = item[1]
        old_category = item[2]
        old_condition = item[3]

        # Update item
        cursor.execute("""
            UPDATE items
            SET name=?, category=?, condition=?
            WHERE id=?
        """, (
            new_name,
            new_category,
            new_condition,
            item_id
        ))

        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Record Name change
        if old_name != new_name:
            cursor.execute("""
                INSERT INTO history
                (item_id, field_changed, old_value, new_value, date)
                VALUES (?, ?, ?, ?, ?)
            """, (
                item_id,
                "Name",
                old_name,
                new_name,
                now
            ))

        # Record Category change
        if old_category != new_category:
            cursor.execute("""
                INSERT INTO history
                (item_id, field_changed, old_value, new_value, date)
                VALUES (?, ?, ?, ?, ?)
            """, (
                item_id,
                "Category",
                old_category,
                new_category,
                now
            ))

        # Record Condition change
        if old_condition != new_condition:
            cursor.execute("""
                INSERT INTO history
                (item_id, field_changed, old_value, new_value, date)
                VALUES (?, ?, ?, ?, ?)
            """, (
                item_id,
                "Condition",
                old_condition,
                new_condition,
                now
            ))

        conn.commit()
        conn.close()

        return redirect('/inventory')

    conn.close()
    return render_template('edit_item.html', item=item)


@app.route('/delete/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM items WHERE id=?", (item_id,))
    cursor.execute("DELETE FROM history WHERE item_id=?", (item_id,))

    conn.commit()
    conn.close()

    return redirect('/inventory')

@app.route('/history/<int:item_id>')
def history(item_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT field_changed, old_value, new_value, date
        FROM history
        WHERE item_id = ?
        ORDER BY id DESC
    """, (item_id,))

    history_data = cursor.fetchall()

    conn.close()

    return render_template(
        'history.html',
        history=history_data
    )

@app.route('/requests')
def requests_page():
    if session.get('role') != 'admin':
        return "Access Denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    all_requests = []

    # UPDATE requests
    cursor.execute("""
        SELECT
            requests.id,
            requests.item_id,
            requests.user_id,
            requests.requested_condition,
            requests.reason,
            requests.status,
            requests.date,
            users.email,
            items.name,
            items.condition,
            'UPDATE'
        FROM requests
        JOIN items ON requests.item_id = items.id
        JOIN users ON requests.user_id = users.id
        ORDER BY requests.id DESC
    """)
    all_requests.extend(cursor.fetchall())

    # ADD requests
    cursor.execute("""
        SELECT
            add_requests.id,
            NULL,
            add_requests.user_id,
            add_requests.condition,
            add_requests.category,
            add_requests.status,
            add_requests.date,
            users.email,
            add_requests.name,
            'New Item',
            'ADD'
        FROM add_requests
        JOIN users ON add_requests.user_id = users.id
        ORDER BY add_requests.id DESC
    """)
    all_requests.extend(cursor.fetchall())

    # DELETE requests
    cursor.execute("""
        SELECT
            delete_requests.id,
            delete_requests.item_id,
            delete_requests.user_id,
            'DELETE',
            delete_requests.reason,
            delete_requests.status,
            delete_requests.date,
            users.email,
            items.name,
            items.condition,
            'DELETE'
        FROM delete_requests
        JOIN items ON delete_requests.item_id = items.id
        JOIN users ON delete_requests.user_id = users.id
        ORDER BY delete_requests.id DESC
    """)
    all_requests.extend(cursor.fetchall())

    conn.close()

    return render_template("requests.html", requests=all_requests)

@app.route('/request_add', methods=['GET', 'POST'])
def request_add():
    if 'user_id' not in session:
        return redirect('/')

    if request.method == 'POST':
        name = request.form['name']
        category = normalize_category(request.form['category'])
        condition = normalize_condition(request.form['condition'])

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO add_requests
            (user_id, name, category, condition, status, date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            session['user_id'],
            name,
            category,
            condition,
            "Pending",
            datetime.now().strftime("%Y-%m-%d %H:%M")
        ))

        conn.commit()
        conn.close()

        return redirect('/inventory')

    return render_template("request_add.html")

@app.route('/request_add/approve/<int:req_id>', methods=['POST'])
def approve_add(req_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT name, category, condition FROM add_requests WHERE id=?", (req_id,))
    req = cursor.fetchone()

    if not req:
        conn.close()
        return "Request not found"

    name, category, condition = req

    cursor.execute(
        "INSERT INTO items (name, category, condition) VALUES (?, ?, ?)",
        (name, category, condition)
    )

    item_id = cursor.lastrowid
    qr_filename = generate_qr(item_id)

    cursor.execute(
        "UPDATE items SET qr_code=? WHERE id=?",
        (qr_filename, item_id)
    )

    cursor.execute(
        "UPDATE add_requests SET status='Approved' WHERE id=?",
        (req_id,)
    )

    conn.commit()
    conn.close()

    return redirect('/requests')

@app.route('/request_delete/<int:item_id>', methods=['POST'])
def request_delete(item_id):

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Prevent duplicate pending requests
    cursor.execute('''
        SELECT *
        FROM delete_requests
        WHERE item_id=?
        AND user_id=?
        AND status='Pending'
    ''', (
        item_id,
        session['user_id']
    ))

    existing_request = cursor.fetchone()

    if existing_request:
        conn.close()
        flash("You already have a pending delete request for this item.")
        return redirect('/inventory')

    cursor.execute('''
        INSERT INTO delete_requests
        (item_id, user_id, reason, status, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        item_id,
        session['user_id'],
        "User requested deletion",
        "Pending",
        datetime.now().strftime("%Y-%m-%d %H:%M")
    ))

    conn.commit()
    conn.close()

    flash("Delete request submitted successfully.")
    return redirect('/inventory')

@app.route('/request_delete/approve/<int:req_id>', methods=['POST'])
def approve_delete(req_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT item_id FROM delete_requests WHERE id=?", (req_id,))
    req = cursor.fetchone()

    if not req:
        conn.close()
        return "Request not found"

    item_id = req[0]

    cursor.execute("DELETE FROM items WHERE id=?", (item_id,))
    cursor.execute("DELETE FROM history WHERE item_id=?", (item_id,))
    cursor.execute("UPDATE delete_requests SET status='Approved' WHERE id=?", (req_id,))

    conn.commit()
    conn.close()

    return redirect('/requests')

# =========================
# REQUEST UPDATE (FIXED VALIDATION)
# =========================
@app.route('/request/<int:item_id>', methods=['GET', 'POST'])
def request_update(item_id):
    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM items WHERE id=?", (item_id,))
    item = cursor.fetchone()

    if not item:
        conn.close()
        return "Item not found"

    current_condition = item[3]

    if request.method == 'POST':
        requested_condition = normalize_condition(
            request.form['requested_condition']
        )
        reason = request.form['reason']

        # Prevent same-condition request
        if requested_condition == current_condition:
            flash("You cannot change condition to the same current condition.")
            conn.close()
            return redirect(f"/request/{item_id}")

        cursor.execute('''
            INSERT INTO requests
            (item_id, user_id, requested_condition, reason, status, date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            item_id,
            session['user_id'],
            requested_condition,
            reason,
            "Pending",
            datetime.now().strftime("%Y-%m-%d %H:%M")
        ))

        conn.commit()
        conn.close()

        
        return redirect('/inventory')

    conn.close()
    return render_template("request_update.html", item=item)

@app.route('/request/approve/<int:req_id>', methods=['POST'])
def approve_request(req_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT item_id, requested_condition FROM requests WHERE id=?", (req_id,))
    req = cursor.fetchone()

    if not req:
        conn.close()
        return "Request not found"

    item_id, new_condition = req

    # update item condition
    cursor.execute("UPDATE items SET condition=? WHERE id=?", (new_condition, item_id))

    # log history
    cursor.execute("INSERT INTO history (item_id, old_condition, new_condition, date) VALUES (?, ?, ?, ?)",
                   (item_id, "UPDATED", new_condition, datetime.now().strftime("%Y-%m-%d %H:%M")))

    # mark request approved
    cursor.execute("UPDATE requests SET status='Approved' WHERE id=?", (req_id,))

    conn.commit()
    conn.close()

    return redirect('/requests')

@app.route('/request_add/reject/<int:req_id>', methods=['POST'])
def reject_add(req_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE add_requests SET status='Rejected' WHERE id=?",
        (req_id,)
    )

    conn.commit()
    conn.close()

    return redirect('/requests')

@app.route('/request/reject/<int:req_id>', methods=['POST'])
def reject_request(req_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE requests SET status='Rejected' WHERE id=?",
        (req_id,)
    )

    conn.commit()
    conn.close()

    return redirect('/requests')

@app.route('/request_delete/reject/<int:req_id>', methods=['POST'])
def reject_delete(req_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE delete_requests SET status='Rejected' WHERE id=?",
        (req_id,)
    )

    conn.commit()
    conn.close()

    return redirect('/requests')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)