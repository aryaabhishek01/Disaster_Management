from flask import Flask, render_template, request, redirect, session, flash
from flask_mysqldb import MySQL
import bcrypt
import datetime
import pickle

app = Flask(__name__)
app.secret_key = "secret123"

# ================= MYSQL CONFIG =================
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'mysql'
app.config['MYSQL_DB'] = 'disaster_education'

mysql = MySQL(app)

# ================= LOAD AI MODEL =================
try:
    model = pickle.load(open("model.pkl", "rb"))
except:
    model = None


# =================================================
# LOGIN
# =================================================
@app.route('/', methods=['GET','POST'])
def login():

    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s",(email,))
        user = cur.fetchone()

        if not user:
            flash("Email does not exist")
            return redirect('/')

        if not bcrypt.checkpw(password.encode(), user[3].encode()):
            flash("Incorrect password")
            return redirect('/')

        session['user_id'] = user[0]
        session['role'] = user[4]

        cur.execute(
            "UPDATE users SET last_login=%s WHERE id=%s",
            (datetime.datetime.now(), user[0])
        )
        mysql.connection.commit()

        if user[4] == "admin":
            return redirect('/admin')
        else:
            return redirect('/user')

    return render_template("login.html")


# =================================================
# REGISTER
# =================================================
@app.route('/register',methods=['GET','POST'])
def register():

    if request.method == "POST":

        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        cur = mysql.connection.cursor()

        cur.execute("SELECT id FROM users WHERE email=%s",(email,))
        if cur.fetchone():
            flash("Email already registered")
            return redirect('/register')

        cur.execute(
            "INSERT INTO users (name,email,password,role) VALUES (%s,%s,%s,'user')",
            (name,email,hashed_pw)
        )

        mysql.connection.commit()

        return redirect('/')

    return render_template("register.html")


# =================================================
# USER DASHBOARD
# =================================================
@app.route('/user')
def user_dashboard():

    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT disaster_type,
    ROUND(AVG((score/total)*100),2)
    FROM disaster_scores
    WHERE user_id=%s
    GROUP BY disaster_type
    """,(session['user_id'],))

    data = cur.fetchall()

    score_map = {}

    for d in data:
        score_map[d[0]] = float(d[1])

    cur.execute("SELECT DISTINCT disaster_type FROM disaster_details")
    all_disasters = [d[0] for d in cur.fetchall()]

    disasters=[]
    percentages=[]

    for d in all_disasters:
        disasters.append(d)
        percentages.append(score_map.get(d,0))

    # AI Recommendation = weakest disaster
    recommendation=None
    if percentages:
        min_score=min(percentages)
        recommendation=disasters[percentages.index(min_score)]

    # Notifications
    cur.execute("""
    SELECT id,message,admin_reply
    FROM feedback
    WHERE user_id=%s AND admin_reply IS NOT NULL
    """,(session['user_id'],))

    notifications=cur.fetchall()

    return render_template(
        "user_dashboard.html",
        disasters=disasters,
        percentages=percentages,
        recommendation=recommendation,
        notifications=notifications
    )


# =================================================
# DELETE NOTIFICATION
# =================================================
@app.route('/delete-notification/<int:id>')
def delete_notification(id):

    cur=mysql.connection.cursor()
    cur.execute("UPDATE feedback SET admin_reply=NULL WHERE id=%s",(id,))
    mysql.connection.commit()

    return redirect('/user')


# =================================================
# FEEDBACK
# =================================================
@app.route('/feedback-page',methods=['GET','POST'])
def feedback_page():

    if 'user_id' not in session:
        return redirect('/')

    if request.method=="POST":

        msg=request.form['message']

        cur=mysql.connection.cursor()

        cur.execute(
        "INSERT INTO feedback (user_id,message) VALUES (%s,%s)",
        (session['user_id'],msg)
        )

        mysql.connection.commit()

        flash("Feedback submitted")

    return render_template("feedback.html")


# =================================================
# ADMIN DASHBOARD
# =================================================
@app.route('/admin')
def admin_dashboard():

    if 'user_id' not in session or session['role']!='admin':
        return redirect('/')

    cur=mysql.connection.cursor()

    # USERS
    cur.execute("""
    SELECT id,name,email,last_login
    FROM users
    WHERE role='user'
    """)
    users=cur.fetchall()

    # FEEDBACK
    cur.execute("""
    SELECT f.id,u.name,f.message,f.admin_reply
    FROM feedback f
    JOIN users u ON f.user_id=u.id
    WHERE f.admin_reply IS NULL
    """)
    feedbacks=cur.fetchall()

    # SCORES
    cur.execute("""
    SELECT u.name,s.disaster_type,s.exercise_number,
           s.score,s.total,s.taken_at
    FROM disaster_scores s
    JOIN users u ON s.user_id=u.id
    """)

    scores=cur.fetchall()

    # GRAPH
    cur.execute("""
    SELECT d.disaster_type,
    COALESCE(ROUND(AVG((s.score/s.total)*100),2),0)
    FROM disaster_details d
    LEFT JOIN disaster_scores s
    ON d.disaster_type=s.disaster_type
    GROUP BY d.disaster_type
    """)

    analytics=cur.fetchall()

    analytics_labels=[a[0] for a in analytics]
    analytics_values=[float(a[1]) for a in analytics]

    return render_template(
        "admin_dashboard.html",
        users=users,
        feedbacks=feedbacks,
        scores=scores,
        analytics_labels=analytics_labels,
        analytics_values=analytics_values
    )


# =================================================
# ADMIN REPLY
# =================================================
@app.route('/reply/<int:id>',methods=['POST'])
def reply(id):

    reply_text=request.form['reply']

    cur=mysql.connection.cursor()

    cur.execute(
    "UPDATE feedback SET admin_reply=%s WHERE id=%s",
    (reply_text,id)
    )

    mysql.connection.commit()

    return redirect('/admin')


# =================================================
# DELETE USER
# =================================================
@app.route('/delete-user/<int:id>')
def delete_user(id):

    cur=mysql.connection.cursor()

    cur.execute("DELETE FROM disaster_scores WHERE user_id=%s",(id,))
    cur.execute("DELETE FROM feedback WHERE user_id=%s",(id,))
    cur.execute("DELETE FROM users WHERE id=%s",(id,))

    mysql.connection.commit()

    return redirect('/admin')


# =================================================
# RESET PASSWORD
# =================================================
@app.route('/reset-password/<int:id>',methods=['POST'])
def reset_password(id):

    new_password=request.form['password']

    hashed=bcrypt.hashpw(new_password.encode(),bcrypt.gensalt()).decode()

    cur=mysql.connection.cursor()

    cur.execute(
    "UPDATE users SET password=%s WHERE id=%s",
    (hashed,id)
    )

    mysql.connection.commit()

    return redirect('/admin')


# =================================================
# GENERAL DISASTERS
# =================================================
@app.route('/general')
def general_disasters():

    cur=mysql.connection.cursor()

    cur.execute("SELECT DISTINCT disaster_type FROM disaster_details")

    disasters=cur.fetchall()

    return render_template("general_disasters.html",disasters=disasters)


# =================================================
# CONTINENTS
# =================================================
@app.route('/continents')
def continents():

    continents=[
    "Asia","Africa","Europe",
    "North America","South America",
    "Australia","Antarctica"
    ]

    return render_template("continents.html",continents=continents)


# =================================================
# CONTINENT DISASTERS
# =================================================
@app.route('/continent/<continent>')
def continent_disasters(continent):

    cur=mysql.connection.cursor()

    cur.execute("""
    SELECT DISTINCT disaster_type
    FROM disaster_details
    WHERE continent=%s
    """,(continent,))

    disasters=cur.fetchall()

    return render_template(
    "continent_disasters.html",
    continent=continent,
    disasters=disasters
    )


# =================================================
# INDIA STATES
# =================================================
@app.route('/india')
def india_states():

    states=[
    "Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh",
    "Goa","Gujarat","Haryana","Himachal Pradesh","Jharkhand",
    "Karnataka","Kerala","Madhya Pradesh","Maharashtra","Manipur",
    "Meghalaya","Mizoram","Nagaland","Odisha","Punjab",
    "Rajasthan","Sikkim","Tamil Nadu","Telangana","Tripura",
    "Uttar Pradesh","Uttarakhand","West Bengal"
    ]

    return render_template("india_states.html",states=states)


# =================================================
# STATE DISASTERS
# =================================================
@app.route('/india/<state>')
def state_disasters(state):

    cur=mysql.connection.cursor()

    cur.execute("""
    SELECT DISTINCT disaster_type
    FROM disaster_details
    WHERE state=%s
    """,(state,))

    disasters=cur.fetchall()

    return render_template(
    "state_disasters.html",
    state=state,
    disasters=disasters
    )


# =================================================
# SIMULATION DETAILS
# =================================================
@app.route('/simulation/<disaster>')
def disaster_details_page(disaster):

    cur=mysql.connection.cursor()

    cur.execute("""
    SELECT description,causes,impacts,
    case_study,lessons,dos,donts
    FROM disaster_details
    WHERE disaster_type=%s
    """,(disaster,))

    details=cur.fetchone()

    return render_template(
    "disaster_details.html",
    disaster=disaster,
    details=details
    )


# =================================================
# EXERCISE SELECT
# =================================================
@app.route('/simulation/<disaster>/exercises')
def exercise_list(disaster):

    return render_template(
    "exercise_select.html",
    disaster=disaster
    )


# =================================================
# EXERCISE QUESTIONS
# =================================================
@app.route('/simulation/<disaster>/exercise/<int:exercise>',methods=['GET','POST'])
def simulation_exercise(disaster,exercise):

    cur=mysql.connection.cursor()

    cur.execute("""
    SELECT *
    FROM disaster_questions
    WHERE disaster_type=%s AND exercise_number=%s
    """,(disaster,exercise))

    questions=cur.fetchall()

    if request.method=="POST":

        score=0
        total=len(questions)
        review=[]

        for q in questions:

            user_answer=request.form.get(str(q[0]))
            correct=q[7]

            if user_answer==correct:
                score+=1
                status="correct"
            else:
                status="wrong"

            review.append({
                "question":q[2],
                "user_answer":user_answer,
                "correct_answer":correct,
                "status":status
            })

        cur.execute("""
        INSERT INTO disaster_scores
        (user_id,disaster_type,exercise_number,score,total)
        VALUES (%s,%s,%s,%s,%s)
        """,(session['user_id'],disaster,exercise,score,total))

        mysql.connection.commit()

        return render_template(
        "result.html",
        disaster=disaster,
        score=score,
        total=total,
        review=review
        )

    return render_template(
    "exercise_questions.html",
    disaster=disaster,
    exercise=exercise,
    questions=questions
    )


# =================================================
# LOGOUT
# =================================================
@app.route('/logout')
def logout():

    session.clear()

    return redirect('/')


# =================================================
# RUN
# =================================================
if __name__=="__main__":
    app.run(debug=True)