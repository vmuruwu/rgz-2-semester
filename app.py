from flask import Flask, redirect, request, render_template, session, url_for, flash, jsonify, current_app
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash, generate_password_hash
import os
import sqlite3
from os import path

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'секретно-секретный секрет')
app.config['DB_TYPE'] = os.getenv('DB_TYPE', 'postgres')


def db_connect():
    if current_app.config['DB_TYPE'] == 'postgres':
        conn = psycopg2.connect(
            host='127.0.0.1',
        database='kino_natalya',
        user='kino_natalya',
        password='123'
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
    else:
        dir_path = path.dirname(path.realpath(__file__))
        db_path = path.join(dir_path, "database.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

    return conn, cur

def db_close(conn, cur):
    conn.commit()
    cur.close()
    conn.close()


@app.route('/')
def menu():
    return render_template('menu.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    login = request.form.get('login')
    name = request.form.get('name')
    password = request.form.get('password')

    if not (login and name and password):
        return render_template('register.html', error='Заполните все поля')

    conn, cur = db_connect()
    if current_app.config['DB_TYPE'] == 'postgres':
        cur.execute("SELECT login FROM users WHERE login=%s;", (login,))
    else:
        cur.execute("SELECT login FROM users WHERE login=?;", (login,))
    if cur.fetchone():
        db_close(conn, cur)
        return render_template('register.html', error='Такой пользователь уже существует')

    password_hash = generate_password_hash(password)

    if current_app.config['DB_TYPE'] == 'postgres':
        cur.execute("INSERT INTO users (login, password, name) VALUES (%s, %s, %s);", (login, password_hash, name))
    else:
        cur.execute("INSERT INTO users (login, password, name) VALUES (?, ?, ?);", (login, password_hash, name))
    db_close(conn, cur)

    return render_template('success.html', login=login)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    login = request.form.get('login')
    password = request.form.get('password')
    if not (login and password):
        return render_template('login.html', error='Заполните все поля')

    conn, cur = db_connect()

    if current_app.config['DB_TYPE'] == 'postgres':
        cur.execute("SELECT * FROM users WHERE login=%s;", (login,))
    else:
        cur.execute("SELECT * FROM users WHERE login=?;", (login,))
    user = cur.fetchone()
    if not user or not check_password_hash(user['password'], password):
        db_close(conn, cur)
        return render_template('login.html', error='Логин и/или пароль неверны')

    session['login'] = user['login']
    session['name'] = user['name']
    session['id'] = user['id']
    session['is_admin'] = user['is_admin']
    db_close(conn, cur)
    return redirect(url_for('films'))


@app.route('/logout')
def logout():
    session.pop('login', None)
    session.pop('name', None)
    session.pop('id', None)
    session.pop('is_admin', None)
    return redirect(url_for('menu'))


@app.route('/delete_account', methods=['GET', 'POST'])
def delete_account():
    if not session.get('login'):
        return redirect(url_for('login'))

    if request.method == 'GET':
        return render_template('delete_account.html')

    # Проверяем, что пользователь подтвердил удаление аккаунта
    confirm = request.form.get('confirm')
    if confirm != 'yes':
        flash('Вы не подтвердили удаление аккаунта', 'error')
        return redirect(url_for('delete_account'))

    # Удаляем аккаунт из базы данных
    conn, cur = db_connect()

    if current_app.config['DB_TYPE'] == 'postgres':
        cur.execute("DELETE FROM users WHERE id=%s;", (session['id'],))
    else:
        cur.execute("DELETE FROM users WHERE id=?;", (session['id'],))
    
    db_close(conn, cur)

    # Удаляем сессию пользователя
    session.pop('login', None)
    session.pop('name', None)
    session.pop('id', None)
    session.pop('is_admin', None)

    flash('Ваш аккаунт успешно удалён', 'success')
    return redirect(url_for('menu'))


@app.route('/films')
def films():
    if not session.get('login'):
        print("Пользователь не авторизован")
        return redirect(url_for('login'))

    conn, cur = db_connect()
    cur.execute("SELECT * FROM films ORDER BY date, time;")
    films = cur.fetchall()
    db_close(conn, cur)

    return render_template('films.html', films=films)


@app.route('/film/<int:film_id>', methods=['GET'])
def film_details(film_id):
    if not session.get('login'):
        return redirect(url_for('login'))

    conn, cur = db_connect()
    
    if current_app.config['DB_TYPE'] == 'postgres':
        cur.execute("SELECT * FROM films WHERE id=%s;", (film_id,))
    else:
        cur.execute("SELECT * FROM films WHERE id=?;", (film_id,))

    film = cur.fetchone()
    if not film:
        db_close(conn, cur)
        return "Сеанс не найден", 404

    session['film_id'] = film_id
    db_close(conn, cur)
    return render_template('film_details.html', film=film)


@app.route('/admin/add_film', methods=['GET', 'POST'])
def add_film():
    if session.get('login') != 'admin':
        return "Доступ запрещён", 403

    if request.method == 'POST':
        film_name = request.form.get('film_name')
        date = request.form.get('date')
        time = request.form.get('time')

        if not (film_name and date and time):
            return "Заполните все поля", 400

        conn, cur = db_connect()

        if current_app.config['DB_TYPE'] == 'postgres':
            cur.execute("INSERT INTO films (film_name, date, time) VALUES (%s, %s, %s);", (film_name, date, time))
        else:
            cur.execute("INSERT INTO films (film_name, date, time) VALUES (?, ?, ?);", (film_name, date, time))
       
        db_close(conn, cur)
        return redirect(url_for('films'))

    return render_template('add_film.html')


@app.route('/admin/delete_film/<int:film_id>', methods=['POST'])
def delete_film(film_id):
    if session.get('login') != 'admin':
        return "Доступ запрещён", 403

    conn, cur = db_connect()

    if current_app.config['DB_TYPE'] == 'postgres':
        cur.execute("DELETE FROM films WHERE id=%s;", (film_id,))
    else:
        cur.execute("DELETE FROM films WHERE id=?;", (film_id,))
    db_close(conn, cur)
    return redirect(url_for('films'))


@app.route('/admin/cancel_booking/<int:booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    if not session.get('is_admin'):
        return "Доступ запрещён", 403

    conn, cur = db_connect()

    if current_app.config['DB_TYPE'] == 'postgres':
        cur.execute("DELETE FROM bookings WHERE id=%s;", (booking_id,))
    else:
        cur.execute("DELETE FROM bookings WHERE id=%?;", (booking_id,))
    db_close(conn, cur)
    return redirect(url_for('films'))


@app.route('/seats/json-rpc-api', methods=['POST'])
def api():
    data = request.json
    id = data['id']

    # Проверка авторизации
    if data['method'] not in ['info', 'booking', 'cancellation']:
        return jsonify({
            'jsonrpc': '2.0',
            'error': {
                'code': -32601,
                'message': 'Method not found'
            },
            'id': id
        })

    # Метод info: получение информации о забронированных местах
    if data['method'] == 'info':
        conn, cur = db_connect()
        if current_app.config['DB_TYPE'] == 'postgres':
            cur.execute("""
            SELECT b.seat_number, b.user_id, u.name AS user_name
            FROM bookings b
            LEFT JOIN users u ON b.user_id = u.id
            WHERE b.film_id=%s;
            """, (session['film_id'],))
        else:
            cur.execute("""
            SELECT b.seat_number, b.user_id, u.name AS user_name
            FROM bookings b
            LEFT JOIN users u ON b.user_id = u.id
            WHERE b.film_id=?;
            """, (session['film_id'],))
        bookings = cur.fetchall()
        db_close(conn, cur)

        # Создаем список мест (30 мест)
        seats = [{'number': i + 1, 'user_id': None, 'user_name': None} for i in range(30)]

        # Заполняем информацию о забронированных местах
        for booking in bookings:
            seat_number = booking['seat_number']
            seats[seat_number - 1]['user_id'] = booking['user_id']
            seats[seat_number - 1]['user_name'] = booking['user_name']

        return jsonify({
            'jsonrpc': '2.0',
            'result': seats,
            'id': id
        })

    # Проверка авторизации для методов booking и cancellation
    login = session.get('login')
    if not login:
        return jsonify({
            'jsonrpc': '2.0',
            'error': {
                'code': 1,
                'message': 'Unauthorized'
            },
            'id': id
        })

    # Метод booking: бронирование места
    if data['method'] == 'booking':
        seat_number = data['params']
        conn, cur = db_connect()

        if current_app.config['DB_TYPE'] == 'postgres':
            cur.execute("SELECT * FROM bookings WHERE film_id=%s AND seat_number=%s;", (session['film_id'], seat_number))
        else:
            cur.execute("SELECT * FROM bookings WHERE film_id=? AND seat_number=?;", (session['film_id'], seat_number))

        if cur.fetchone():
            db_close(conn, cur)
            return jsonify({
                'jsonrpc': '2.0',
                'error': {
                    'code': 2,
                    'message': 'Место уже занято'
                },
                'id': id
            })

        if current_app.config['DB_TYPE'] == 'postgres':
            cur.execute("INSERT INTO bookings (user_id, film_id, seat_number) VALUES (%s, %s, %s);", (session['id'], session['film_id'], seat_number))
        else:
            cur.execute("INSERT INTO bookings (user_id, film_id, seat_number) VALUES (?, ?, ?);", (session['id'], session['film_id'], seat_number))

        db_close(conn, cur)
        return jsonify({
            'jsonrpc': '2.0',
            'result': 'success',
            'id': id
        })

    # Метод cancellation: снятие брони
    if data['method'] == 'cancellation':
        seat_number = data['params']
        conn, cur = db_connect()

        if current_app.config['DB_TYPE'] == 'postgres':
            cur.execute("SELECT * FROM bookings WHERE film_id=%s AND seat_number=%s;", (session['film_id'], seat_number))
        else:
            cur.execute("SELECT * FROM bookings WHERE film_id=? AND seat_number=?;", (session['film_id'], seat_number))
        booking = cur.fetchone()

        # Проверка, что пользователь может снять только свою бронь, а администратор — любую
        if not booking or (booking['user_id'] != session['id'] and not session.get('is_admin')):
            db_close(conn, cur)
            return jsonify({
                'jsonrpc': '2.0',
                'error': {
                    'code': 3,
                    'message': 'Вы не можете освободить чужое место'
                },
                'id': id
            })

        if current_app.config['DB_TYPE'] == 'postgres':
            cur.execute("DELETE FROM bookings WHERE id=%s;", (booking['id'],))
        else:
            cur.execute("DELETE FROM bookings WHERE id=?;", (booking['id'],))
        db_close(conn, cur)
        return jsonify({
            'jsonrpc': '2.0',
            'result': 'success',
            'id': id
        })

    return jsonify({
        'jsonrpc': '2.0',
        'error': {
            'code': -32601,
            'message': 'Method not found'
        },
        'id': id
    })