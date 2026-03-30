
from flask import Flask, render_template, request, redirect, session, url_for
from analyzer import analyze_report
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
import re

app = Flask(__name__)
app.secret_key = "secret123"

# 📂 Upload folder
UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# 🗄️ Create DB
def init_db():
    conn = sqlite3.connect("medireport.db")
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        email TEXT UNIQUE,
        password TEXT
    )
    """)

    # ✅ FIXED: reports uses email (NOT username)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        filename TEXT,
        result TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

init_db()


# Landing Page
@app.route('/')
def landing():
    return render_template('landingpage.html')


# 🔐 LOGIN
# 🔐 LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect("medireport.db")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cursor.fetchone()

        conn.close()

        # ✅ FIXED: correct password index
        if user and check_password_hash(user[3], password):
            # store username for display, email for DB
            session['user'] = user[1]      # username
            session['email'] = user[2]     # email (for DB queries)
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="Invalid email or password")

    return render_template('login.html')

# 📝 SIGNUP
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        hashed_password = generate_password_hash(password)

        conn = sqlite3.connect("medireport.db")
        cursor = conn.cursor()

        # ✅ FIXED: handle duplicate email
        try:
            cursor.execute(
                "INSERT INTO users (username,email, password) VALUES (?,?, ?)",
                (username, email, hashed_password)
            )
            conn.commit()
            conn.close()
            return redirect('/login')

        except sqlite3.IntegrityError:
            conn.close()
            return render_template('signup.html', error="Email already exists")

    return render_template('signup.html')


# 🏠 HOME
@app.route('/home')
def home():
    if 'user' not in session:
        return redirect('/')
    return render_template('home.html')


# 📄 PDF TEXT EXTRACTION
def extract_text_from_pdf(filepath):
    import PyPDF2

    text = ""
    with open(filepath, "rb") as file:
        reader = PyPDF2.PdfReader(file)

        for page in reader.pages:
            if page.extract_text():
                text += page.extract_text()

    return text


# 🖼️ IMAGE OCR
def extract_text_from_image(filepath):
    import pytesseract
    from PIL import Image

    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    img = Image.open(filepath)
    text = pytesseract.image_to_string(img)

    return text


# 📤 UPLOAD + ANALYZE
@app.route('/upload', methods=['POST'])
def upload():

    if 'user' not in session:
        return redirect('/login')

    if 'file' not in request.files:
        return "No file selected"

    file = request.files['file']

    if file.filename == "":
        return "No file selected"

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    # 🔥 Detect file type
    if file.filename.lower().endswith('.pdf'):
        text = extract_text_from_pdf(filepath)

    elif file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        text = extract_text_from_image(filepath)

    else:
        return "Unsupported file type"

    # 🔥 Analyze
    result, explanation = analyze_report(text)

    # ✅ FIXED: use email column
    conn = sqlite3.connect("medireport.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO reports (email, filename, result) VALUES (?, ?, ?)",
        (session['email'], file.filename, ", ".join(result))
    )

    conn.commit()
    conn.close()

    return render_template('result.html', result=result, explanation=explanation)


# 📜 HISTORY
@app.route('/history')
def history():
    if 'user' not in session:
        return redirect('/')

    conn = sqlite3.connect("medireport.db")
    cursor = conn.cursor()

    # ✅ FIXED: use email
    cursor.execute("SELECT filename, result, date FROM reports WHERE email=?", (session['email'],))
    data = cursor.fetchall()

    conn.close()

    return render_template('history.html', data=data)


# 👤 PROFILE
@app.route('/profile')
def profile():
    if 'user' not in session:
        return redirect('/')

    conn = sqlite3.connect("medireport.db")
    cursor = conn.cursor()

    # ✅ FIXED: use email
    cursor.execute("SELECT COUNT(*) FROM reports WHERE email=?", (session['email'],))
    count = cursor.fetchone()[0]

    conn.close()

    return render_template('profile.html', username=session['user'], count=count)


# 🚪 LOGOUT
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')


# ▶ RUN
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
