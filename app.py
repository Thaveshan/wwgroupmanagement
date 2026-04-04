import os
from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3
import pandas as pd
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

app = Flask(__name__)
#DATABASE = 'cars.db'
#DATABASE = os.path.join('/data', 'cars.db')
DATABASE = os.environ.get("DATABASE_PATH", "cars.db")

def init_db():
    db_dir = os.path.dirname(DATABASE)

    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    
    if not os.path.exists(DATABASE):
        conn = sqlite3.connect(DATABASE)
        conn.execute("""
        CREATE TABLE cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        );
        """)
        conn.execute("""
        CREATE TABLE recons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            car_id INTEGER,
            description TEXT,
            amount REAL
        );
        """)
        conn.commit()
        conn.close()

init_db()


# --- DB Helper ---
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# --- Routes ---

@app.route('/')
def index():
    conn = get_db()
    cars = conn.execute("SELECT * FROM cars WHERE is_sold = 0").fetchall()
    conn.close()
    return render_template('index.html', cars=cars)


@app.route('/add', methods=['GET', 'POST'])
def add_car():
    if request.method == 'POST':
        conn = get_db()
        conn.execute("""
            INSERT INTO cars 
            (year, brand, model, colour, vin, engine_number, register_number, registration_number, purchase_price, selling_price, is_sold)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (
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
        ))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    return render_template('add_car.html')


@app.route('/car/<int:car_id>', methods=['GET', 'POST'])
def car_detail(car_id):
    conn = get_db()

    car = conn.execute("SELECT * FROM cars WHERE id = ?", (car_id,)).fetchone()
    if not car:
        return "Car not found", 404

    if request.method == 'POST':
        conn.execute("""
            INSERT INTO recons (car_id, description, amount)
            VALUES (?, ?, ?)
        """, (
            car_id,
            request.form['description'],
            float(request.form['amount'])
        ))
        conn.commit()

    recons = conn.execute("SELECT * FROM recons WHERE car_id = ?", (car_id,)).fetchall()
    total_recon = sum(r['amount'] for r in recons)
    profit = car['selling_price'] - (car['purchase_price'] + total_recon)

    conn.close()

    return render_template('car_detail.html', car=car, recons=recons, total_recon=total_recon, profit=profit)


@app.route('/sell/<int:car_id>')
def sell_car(car_id):
    conn = get_db()
    conn.execute("UPDATE cars SET is_sold = 1 WHERE id = ?", (car_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))


@app.route('/sold')
def sold_cars():
    conn = get_db()
    cars = conn.execute("SELECT * FROM cars WHERE is_sold = 1").fetchall()

    sold_data = []
    for car in cars:
        recons = conn.execute("SELECT * FROM recons WHERE car_id = ?", (car['id'],)).fetchall()
        total_recon = sum(r['amount'] for r in recons)
        profit = car['selling_price'] - (car['purchase_price'] + total_recon)

        sold_data.append({
            "car": f"{car['brand']} {car['model']} ({car['year']})",
            "purchase": car['purchase_price'],
            "selling": car['selling_price'],
            "recon": total_recon,
            "profit": profit
        })

    conn.close()
    return render_template('sold_cars.html', sold_data=sold_data)


@app.route('/update_price/<int:car_id>', methods=['POST'])
def update_price(car_id):
    new_price = float(request.form['selling_price'])

    conn = get_db()
    conn.execute("UPDATE cars SET selling_price = ? WHERE id = ?", (new_price, car_id))
    conn.commit()
    conn.close()

    return redirect(url_for('car_detail', car_id=car_id))


@app.route('/stock')
def stock_on_hand():
    conn = get_db()
    cars = conn.execute("SELECT * FROM cars WHERE is_sold = 0").fetchall()
    conn.close()
    return render_template('stock.html', cars=cars)


@app.route('/edit/<int:car_id>', methods=['GET', 'POST'])
def edit_car(car_id):
    conn = get_db()
    car = conn.execute("SELECT * FROM cars WHERE id = ?", (car_id,)).fetchone()

    if not car:
        return "Car not found", 404

    if request.method == 'POST':
        conn.execute("""
            UPDATE cars SET 
            year=?, brand=?, model=?, colour=?, vin=?, engine_number=?, register_number=?, registration_number=?, purchase_price=?, selling_price=?
            WHERE id=?
        """, (
            request.form['year'],
            request.form['brand'],
            request.form['model'],
            request.form['colour'],
            request.form['vin'],
            request.form['engine_number'],
            request.form['register_number'],
            request.form['registration_number'],
            float(request.form['purchase_price']),
            float(request.form['selling_price']),
            car_id
        ))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    conn.close()
    return render_template('edit_car.html', car=car)


@app.route('/delete/<int:car_id>')
def delete_car(car_id):
    conn = get_db()
    conn.execute("DELETE FROM cars WHERE id = ?", (car_id,))
    conn.execute("DELETE FROM recons WHERE car_id = ?", (car_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))


# --- Download Reports ---

@app.route('/stock/download/csv')
def download_stock_csv():
    conn = get_db()
    cars = conn.execute("SELECT * FROM cars WHERE is_sold = 0").fetchall()
    conn.close()

    df = pd.DataFrame(cars, columns=cars[0].keys() if cars else [])
    df = df[["year", "brand", "model", "colour", "purchase_price", "selling_price"]]

    return send_file(io.BytesIO(df.to_csv(index=False).encode()),
                     mimetype='text/csv',
                     download_name='stock_report.csv',
                     as_attachment=True)


@app.route('/stock/download/excel')
def download_stock_excel():
    conn = get_db()
    cars = conn.execute("SELECT * FROM cars WHERE is_sold = 0").fetchall()
    conn.close()

    df = pd.DataFrame(cars, columns=cars[0].keys() if cars else [])
    df = df[["year", "brand", "model", "colour", "purchase_price", "selling_price"]]

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)

    output.seek(0)

    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     download_name='stock_report.xlsx',
                     as_attachment=True)


@app.route('/stock/download/pdf')
def download_stock_pdf():
    conn = get_db()
    cars = conn.execute("SELECT * FROM cars WHERE is_sold = 0").fetchall()
    conn.close()

    output = io.BytesIO()
    p = canvas.Canvas(output, pagesize=letter)
    width, height = letter

    y = height - 40

    for car in cars:
        p.drawString(30, y, f"{car['brand']} {car['model']} - R{car['selling_price']}")
        y -= 15

    p.save()
    output.seek(0)

    return send_file(output,
                     mimetype='application/pdf',
                     download_name='stock_report.pdf',
                     as_attachment=True)
    
@app.route('/dashboard')
def dashboard():
    conn = get_db()

    # Get sold cars
    cars = conn.execute("SELECT * FROM cars WHERE is_sold = 1").fetchall()

    labels = []
    profits = []
    monthly_profit = {}

    total_profit = 0

    for car in cars:
        car_id = car['id']

        recons = conn.execute("SELECT * FROM recons WHERE car_id = ?", (car_id,)).fetchall()
        total_recon = sum(r['amount'] for r in recons)

        profit = car['selling_price'] - (car['purchase_price'] + total_recon)
        total_profit += profit

        # Bar chart data
        labels.append(f"{car['brand']} {car['model']}")
        profits.append(profit)

        # Monthly grouping (simple version using ID order as fallback)
        month = "Month " + str(car_id)  # we improve this later if you add date field
        monthly_profit[month] = monthly_profit.get(month, 0) + profit

    conn.close()

    return render_template(
        'dashboard.html',
        labels=labels,
        profits=profits,
        total_profit=total_profit,
        total_sales=len(cars),
        months=list(monthly_profit.keys()),
        monthly_values=list(monthly_profit.values())
    )


if __name__ == '__main__':
    app.run(debug=True)