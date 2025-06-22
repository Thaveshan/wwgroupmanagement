from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3
import io
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)

# Initialize DB
def init_db():
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS cars (
        id INTEGER PRIMARY KEY,
        year TEXT,
        brand TEXT,
        model TEXT,
        colour TEXT,
        vin TEXT,
        engine_number TEXT,
        register_number TEXT,
        registration_number TEXT,
        purchase_price REAL,
        selling_price REAL,
        is_sold INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS recons (
        id INTEGER PRIMARY KEY,
        car_id INTEGER,
        description TEXT,
        amount REAL,
        FOREIGN KEY(car_id) REFERENCES cars(id)
    )''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute("SELECT * FROM cars WHERE is_sold=0")
    cars = c.fetchall()
    conn.close()
    return render_template('index.html', cars=cars)

@app.route('/add', methods=['GET', 'POST'])
def add_car():
    if request.method == 'POST':
        data = (
            request.form['year'],
            request.form['brand'],
            request.form['model'],
            request.form['colour'],
            request.form['vin'],
            request.form['engine_number'],
            request.form['register_number'],
            request.form['registration_number'],
            float(request.form['purchase_price']),
            float(request.form['selling_price'])
        )
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute('''INSERT INTO cars (
            year, brand, model, colour, vin, engine_number,
            register_number, registration_number,
            purchase_price, selling_price
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', data)
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('add_car.html')

@app.route('/car/<int:id>', methods=['GET', 'POST'])
def car_detail(id):
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()

    # Fetch car first
    c.execute("SELECT * FROM cars WHERE id=?", (id,))
    car = c.fetchone()

    if not car:
        conn.close()
        return f"<h2>Car with ID {id} not found.</h2><a href='/'>Go back</a>", 404

    # Handle recon form
    if request.method == 'POST':
        description = request.form['description']
        amount = float(request.form['amount'])
        c.execute("INSERT INTO recons (car_id, description, amount) VALUES (?, ?, ?)", (id, description, amount))
        conn.commit()

    # Fetch recon items
    c.execute("SELECT description, amount FROM recons WHERE car_id=?", (id,))
    recons = c.fetchall()
    total_recon = sum(r[1] for r in recons)
    profit = car[10] - (car[9] + total_recon)
    conn.close()

    return render_template('car_detail.html', car=car, recons=recons, total_recon=total_recon, profit=profit)

@app.route('/sell/<int:id>')
def sell_car(id):
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute("UPDATE cars SET is_sold=1 WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/sold')
def sold_cars():
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute("SELECT id, year, brand, model, purchase_price, selling_price FROM cars WHERE is_sold=1")
    sold = c.fetchall()
    sold_data = []

    for car in sold:
        car_id = car[0]
        year = car[1]
        brand = car[2]
        model = car[3]
        purchase_price = car[4]
        selling_price = car[5]

        c.execute("SELECT SUM(amount) FROM recons WHERE car_id=?", (car_id,))
        recon_total = c.fetchone()[0] or 0
        profit = selling_price - (purchase_price + recon_total)

        sold_data.append({
            "car": f"{brand} {model} ({year})",
            "purchase": purchase_price,
            "selling": selling_price,
            "recon": recon_total,
            "profit": profit
        })

    conn.close()
    return render_template('sold_cars.html', sold_data=sold_data)

@app.route('/update_price/<int:id>', methods=['POST'])
def update_price(id):
    new_price = float(request.form['selling_price'])
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute("UPDATE cars SET selling_price = ? WHERE id = ?", (new_price, id))
    conn.commit()
    conn.close()
    return redirect(url_for('car_detail', id=id))

@app.route('/stock')
def stock_on_hand():
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute("SELECT id, year, brand, model, colour, purchase_price, selling_price FROM cars WHERE is_sold=0")
    cars = c.fetchall()
    conn.close()
    return render_template('stock.html', cars=cars)

# --- Stock Report Downloads ---

@app.route('/stock/download/csv')
def download_stock_csv():
    conn = sqlite3.connect('cars.db')
    df = pd.read_sql_query("SELECT id, year, brand, model, colour, purchase_price, selling_price FROM cars WHERE is_sold=0", conn)
    conn.close()

    csv_data = df.to_csv(index=False)
    return send_file(
        io.BytesIO(csv_data.encode()),
        mimetype='text/csv',
        download_name='stock_report.csv',
        as_attachment=True
    )

@app.route('/stock/download/excel')
def download_stock_excel():
    conn = sqlite3.connect('cars.db')
    df = pd.read_sql_query("SELECT id, year, brand, model, colour, purchase_price, selling_price FROM cars WHERE is_sold=0", conn)
    conn.close()

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Stock')
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        download_name='stock_report.xlsx',
        as_attachment=True
    )


@app.route('/stock/download/pdf')
def download_stock_pdf():
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute("SELECT id, year, brand, model, colour, purchase_price, selling_price FROM cars WHERE is_sold=0")
    data = c.fetchall()
    conn.close()

    output = io.BytesIO()
    p = canvas.Canvas(output, pagesize=letter)
    width, height = letter

    p.setFont("Helvetica-Bold", 16)
    p.drawString(30, height - 40, "WW Group - Stock On Hand Report")

    p.setFont("Helvetica", 10)
    y = height - 70
    row_height = 15

    headers = ["ID", "Year", "Brand", "Model", "Colour", "Purchase Price", "Selling Price"]
    x_positions = [30, 70, 110, 170, 230, 290, 380]

    # Draw headers
    for i, header in enumerate(headers):
        p.drawString(x_positions[i], y, header)
    y -= row_height

    # Draw rows
    for row in data:
        if y < 40:
            p.showPage()
            y = height - 40
        for i, item in enumerate(row):
            if isinstance(item, float):
                text = f"R{item:.2f}"
            else:
                text = str(item)
            p.drawString(x_positions[i], y, text)
        y -= row_height

    p.save()
    output.seek(0)

    return send_file(
        output,
        mimetype='application/pdf',
        download_name='stock_report.pdf',
        as_attachment=True
    )


if __name__ == '__main__':
    app.run(debug=True)
