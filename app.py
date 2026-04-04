import os
from flask import Flask, render_template, request, redirect, url_for, send_file
import psycopg2
import pandas as pd
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

app = Flask(__name__)

DATABASE_URL = "postgresql://car_db_i3ab_user:HPYRC5KkqLngY7gvF8QJsgcVTbpdj68R@dpg-d78b4uia214c73a3u6t0-a.singapore-postgres.render.com/car_db_i3ab"

# --- DB Helper ---
def get_db():
    return psycopg2.connect(DATABASE_URL)


# --- INIT DB ---
def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS cars (
        id SERIAL PRIMARY KEY,
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
        is_sold BOOLEAN DEFAULT FALSE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS recons (
        id SERIAL PRIMARY KEY,
        car_id INTEGER,
        description TEXT,
        amount REAL
    );
    """)

    conn.commit()
    cur.close()
    conn.close()


init_db()


# --- Helper to convert rows ---
def fetch_dicts(cur):
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


# --- Routes ---

@app.route('/')
def index():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM cars WHERE is_sold = FALSE")
    cars = fetch_dicts(cur)

    cur.close()
    conn.close()

    return render_template('index.html', cars=cars)


@app.route('/add', methods=['GET', 'POST'])
def add_car():
    if request.method == 'POST':
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO cars 
        (year, brand, model, colour, vin, engine_number, register_number, registration_number, purchase_price, selling_price, is_sold)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE)
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
        cur.close()
        conn.close()

        return redirect(url_for('index'))

    return render_template('add_car.html')


@app.route('/car/<int:car_id>', methods=['GET', 'POST'])
def car_detail(car_id):
    conn = get_db()
    cur = conn.cursor()

    # Get car
    cur.execute("SELECT * FROM cars WHERE id = %s", (car_id,))
    car = fetch_dicts(cur)
    if not car:
        return "Car not found", 404
    car = car[0]

    # Add recon
    if request.method == 'POST':
        cur.execute("""
        INSERT INTO recons (car_id, description, amount)
        VALUES (%s, %s, %s)
        """, (
            car_id,
            request.form['description'],
            float(request.form['amount'])
        ))
        conn.commit()

    # Get recons
    cur.execute("SELECT * FROM recons WHERE car_id = %s", (car_id,))
    recons = fetch_dicts(cur)

    total_recon = sum(r['amount'] for r in recons)
    profit = car['selling_price'] - (car['purchase_price'] + total_recon)

    cur.close()
    conn.close()

    return render_template('car_detail.html', car=car, recons=recons, total_recon=total_recon, profit=profit)


@app.route('/sell/<int:car_id>')
def sell_car(car_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("UPDATE cars SET is_sold = TRUE WHERE id = %s", (car_id,))
    conn.commit()

    cur.close()
    conn.close()

    return redirect(url_for('index'))


@app.route('/sold')
def sold_cars():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM cars WHERE is_sold = TRUE")
    cars = fetch_dicts(cur)

    sold_data = []

    for car in cars:
        cur.execute("SELECT * FROM recons WHERE car_id = %s", (car['id'],))
        recons = fetch_dicts(cur)

        total_recon = sum(r['amount'] for r in recons)
        profit = car['selling_price'] - (car['purchase_price'] + total_recon)

        sold_data.append({
            "car": f"{car['brand']} {car['model']} ({car['year']})",
            "purchase": car['purchase_price'],
            "selling": car['selling_price'],
            "recon": total_recon,
            "profit": profit
        })

    cur.close()
    conn.close()

    return render_template('sold_cars.html', sold_data=sold_data)


@app.route('/update_price/<int:car_id>', methods=['POST'])
def update_price(car_id):
    new_price = float(request.form['selling_price'])

    conn = get_db()
    cur = conn.cursor()

    cur.execute("UPDATE cars SET selling_price = %s WHERE id = %s", (new_price, car_id))
    conn.commit()

    cur.close()
    conn.close()

    return redirect(url_for('car_detail', car_id=car_id))


@app.route('/stock')
def stock_on_hand():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM cars WHERE is_sold = FALSE")
    cars = fetch_dicts(cur)

    cur.close()
    conn.close()

    return render_template('stock.html', cars=cars)


@app.route('/edit/<int:car_id>', methods=['GET', 'POST'])
def edit_car(car_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM cars WHERE id = %s", (car_id,))
    car = fetch_dicts(cur)
    if not car:
        return "Car not found", 404
    car = car[0]

    if request.method == 'POST':
        cur.execute("""
        UPDATE cars SET 
        year=%s, brand=%s, model=%s, colour=%s, vin=%s, engine_number=%s, register_number=%s, registration_number=%s, purchase_price=%s, selling_price=%s
        WHERE id=%s
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
        cur.close()
        conn.close()

        return redirect(url_for('index'))

    cur.close()
    conn.close()

    return render_template('edit_car.html', car=car)


@app.route('/delete/<int:car_id>')
def delete_car(car_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM cars WHERE id = %s", (car_id,))
    cur.execute("DELETE FROM recons WHERE car_id = %s", (car_id,))
    conn.commit()

    cur.close()
    conn.close()

    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM cars WHERE is_sold = TRUE")
    cars = fetch_dicts(cur)

    labels = []
    profits = []
    monthly_profit = {}

    total_profit = 0

    for car in cars:
        cur.execute("SELECT * FROM recons WHERE car_id = %s", (car['id'],))
        recons = fetch_dicts(cur)

        total_recon = sum(r['amount'] for r in recons)
        profit = car['selling_price'] - (car['purchase_price'] + total_recon)

        labels.append(f"{car['brand']} {car['model']}")
        profits.append(profit)
        total_profit += profit

        # simple grouping
        month = f"Car {car['id']}"
        monthly_profit[month] = monthly_profit.get(month, 0) + profit

    cur.close()
    conn.close()

    return render_template(
        'dashboard.html',
        labels=labels or [],
        profits=profits or [],
        total_profit=total_profit,
        total_sales=len(cars),
        months=list(monthly_profit.keys()) or [],
        monthly_values=list(monthly_profit.values()) or []
    )

if __name__ == '__main__':
    app.run(debug=True)