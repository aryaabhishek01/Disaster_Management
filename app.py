from flask import Flask, render_template, request, redirect, session, flash
from flask_mysqldb import MySQL
import bcrypt
import datetime
import pickle

# ================= LOAD AI MODEL =================
try:
    model = pickle.load(open("model.pkl", "rb"))
except:
    model = None

app = Flask(__name__)
app.secret_key = "secret123"

# ================= MYSQL CONFIG =================
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'mysql'
app.config['MYSQL_DB'] = 'disaster_education'

mysql = MySQL(app)

# =================================================
# ================= LOGIN =========================
# =================================================
@app.route('/', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()

        if not user:
            flash("Email does not exist", "error")
            return redirect('/')

        if not bcrypt.checkpw(password.encode(), user[3].encode()):
            flash("Incorrect password", "error")
            return redirect('/')

        session['user_id'] = user[0]
        session['role'] = user[4]

        cur.execute(
            "UPDATE users SET last_login=%s WHERE id=%s",
            (datetime.datetime.now(), user[0])
        )
        mysql.connection.commit()

        return redirect('/admin' if user[4] == 'admin' else '/user')

    return render_template('login.html')


# =================================================
# ================= REGISTER ======================
# =================================================
@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))

        if cur.fetchone():
            flash("Email already registered", "error")
            return redirect('/register')

        cur.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s,%s,%s,'user')",
            (name, email, hashed_pw)
        )
        mysql.connection.commit()

        return redirect('/')

    return render_template('register.html')


# =================================================
# ================= USER DASHBOARD ================
# =================================================
@app.route('/user')
def user_dashboard():

    if 'user_id' not in session or session['role'] != 'user':
        return redirect('/')

    cur = mysql.connection.cursor()

    # ===== USER PROGRESS =====
    cur.execute("""
        SELECT disaster_type, SUM(score), SUM(total)
        FROM disaster_scores
        WHERE user_id=%s
        GROUP BY disaster_type
    """, (session['user_id'],))

    data = cur.fetchall()

    all_disasters = ['Earthquake', 'Flood', 'Cyclone', 'Fire']

    score_map = {}
    for d in data:
        percentage = round((d[1] / d[2]) * 100, 2)
        score_map[d[0]] = percentage

    disasters = []
    percentages = []

    for d in all_disasters:
        disasters.append(d)
        percentages.append(score_map.get(d, 0))

    # ===== AI RECOMMENDATION =====
    recommended_disaster = None

    try:
        if model:
            prediction = model.predict([percentages])

            disaster_map = {
                0: "Earthquake",
                1: "Flood",
                2: "Cyclone",
                3: "Fire"
            }

            recommended_disaster = disaster_map.get(prediction[0])
    except:
        recommended_disaster = None

    # ===== FEEDBACK NOTIFICATIONS =====
    cur.execute("""
        SELECT message, admin_reply
        FROM feedback
        WHERE user_id=%s AND admin_reply IS NOT NULL
        ORDER BY id DESC
    """, (session['user_id'],))

    notifications = cur.fetchall()

    return render_template(
        'user_dashboard.html',
        disasters=disasters,
        percentages=percentages,
        notifications=notifications,
        recommendation=recommended_disaster
    )


# =================================================
# ================= FEEDBACK ======================
# =================================================
@app.route('/feedback-page', methods=['GET', 'POST'])
def feedback_page():

    if 'user_id' not in session:
        return redirect('/')

    if request.method == 'POST':
        msg = request.form['message']

        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO feedback (user_id, message) VALUES (%s,%s)",
            (session['user_id'], msg)
        )
        mysql.connection.commit()

        flash("Feedback submitted", "success")

    return render_template('feedback.html')


@app.route('/ignore-feedback/<int:id>')
def ignore_feedback(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM feedback WHERE id=%s", (id,))
    mysql.connection.commit()
    return redirect('/admin')


# =================================================
# ================= ADMIN DASHBOARD ===============
# =================================================
@app.route('/admin')
def admin_dashboard():

    if 'user_id' not in session or session['role'] != 'admin':
        return redirect('/')

    cur = mysql.connection.cursor()

    # USERS
    cur.execute("""
        SELECT id, name, email, last_login
        FROM users WHERE role='user'
    """)
    users = cur.fetchall()

    # FEEDBACK
    cur.execute("""
        SELECT f.id, u.name, f.message, f.admin_reply
        FROM feedback f
        JOIN users u ON f.user_id = u.id
    """)
    feedbacks = cur.fetchall()

    # SCORES
    cur.execute("""
        SELECT u.name, s.disaster_type, s.exercise_number,
               s.score, s.total, s.taken_at
        FROM disaster_scores s
        JOIN users u ON s.user_id = u.id
    """)
    scores = cur.fetchall()

    # FORMAT DATE
    scores_formatted = []
    for s in scores:
        scores_formatted.append((
            s[0],
            s[1],
            s[2],
            s[3],
            s[4],
            s[5].strftime("%d-%m-%Y %H:%M")
        ))

    # ===== ADMIN ANALYTICS =====
    cur.execute("""
        SELECT disaster_type,
               ROUND(AVG((score/total)*100),2)
        FROM disaster_scores
        GROUP BY disaster_type
    """)

    analytics = cur.fetchall()

    analytics_labels = [a[0] for a in analytics]
    analytics_values = [float(a[1]) for a in analytics]

    return render_template(
        'admin_dashboard.html',
        users=users,
        feedbacks=feedbacks,
        scores=scores_formatted,
        analytics_labels=analytics_labels,
        analytics_values=analytics_values
    )


# =================================================
# ================= ADMIN REPLY ===================
# =================================================
@app.route('/reply/<int:id>', methods=['POST'])
def reply(id):
    reply_text = request.form['reply']

    cur = mysql.connection.cursor()
    cur.execute(
        "UPDATE feedback SET admin_reply=%s WHERE id=%s",
        (reply_text, id)
    )
    mysql.connection.commit()

    return redirect('/admin')


# =================================================
# ================= SIMULATION ====================
# =================================================
@app.route('/simulation/<disaster>')
def disaster_details_page(disaster):

    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT description, causes, impacts,
               case_study, lessons, dos, donts
        FROM disaster_details
        WHERE disaster_type=%s
    """, (disaster,))

    details = cur.fetchone()

    return render_template(
        'disaster_details.html',
        disaster=disaster,
        details=details
    )


@app.route('/simulation/<disaster>/exercises')
def exercise_list(disaster):

    if 'user_id' not in session:
        return redirect('/')

    return render_template(
        'exercise_select.html',
        disaster=disaster
    )


@app.route('/simulation/<disaster>/exercise/<int:exercise>', methods=['GET', 'POST'])
def simulation_exercise(disaster, exercise):

    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT * FROM disaster_questions
        WHERE disaster_type=%s AND exercise_number=%s
    """, (disaster, exercise))

    questions = cur.fetchall()

    if request.method == 'POST':

        score = 0
        total = len(questions)
        review = []

        for q in questions:
            user_answer = request.form.get(str(q[0]))
            correct_answer = q[7]

            if user_answer == correct_answer:
                score += 1
                status = "correct"
            else:
                status = "wrong"

            review.append({
                "question": q[2],
                "option_a": q[3],
                "option_b": q[4],
                "option_c": q[5],
                "option_d": q[6],
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "status": status
            })

        cur.execute("""
            INSERT INTO disaster_scores
            (user_id, disaster_type, exercise_number, score, total)
            VALUES (%s,%s,%s,%s,%s)
        """, (session['user_id'], disaster, exercise, score, total))

        mysql.connection.commit()

        return render_template(
            'result.html',
            disaster=disaster,
            score=score,
            total=total,
            review=review
        )

    return render_template(
        'exercise_questions.html',
        disaster=disaster,
        exercise=exercise,
        questions=questions
    )


# =================================================
# ================= LOGOUT ========================
# =================================================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


if __name__ == "__main__":
    app.run(debug=True)
