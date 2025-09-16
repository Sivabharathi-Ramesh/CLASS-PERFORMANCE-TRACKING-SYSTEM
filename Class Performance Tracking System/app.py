import sqlite3
import os
from datetime import datetime
import requests
from flask import Flask, render_template, request, jsonify, g, url_for

APP_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(APP_DIR, "attendance.db")

app = Flask(__name__)

# ---------- DB Helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db:
        db.close()

# ---------- Database Initialization ----------
def init_db():
    db = get_db()
    db.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_no TEXT UNIQUE NOT NULL, name TEXT NOT NULL, exercism_username TEXT
        );
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS homework (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL, title TEXT NOT NULL, description TEXT,
            posted_date TEXT NOT NULL, due_date TEXT NOT NULL,
            FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS homework_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            homework_id INTEGER NOT NULL, student_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending', grade INTEGER,
            FOREIGN KEY(homework_id) REFERENCES homework(id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
            UNIQUE(homework_id, student_id)
        );
        CREATE TABLE IF NOT EXISTS doubts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            homework_id INTEGER NOT NULL, student_id INTEGER NOT NULL,
            question TEXT NOT NULL, answer TEXT, asked_date TEXT NOT NULL,
            FOREIGN KEY(homework_id) REFERENCES homework(id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL,
            subject_id INTEGER NOT NULL, student_id INTEGER NOT NULL,
            status TEXT CHECK(status IN ('Present','Absent Informed','Absent Uninformed')) NOT NULL,
            UNIQUE(date, subject_id, student_id),
            FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
        );
        """
    )
    try:
        cur = db.execute("PRAGMA table_info(students)")
        cols = [column[1] for column in cur.fetchall()]
        if 'exercism_username' not in cols:
            db.execute("ALTER TABLE students ADD COLUMN exercism_username TEXT")
    except sqlite3.OperationalError:
        pass

    cur = db.execute("SELECT COUNT(*) c FROM subjects")
    if cur.fetchone()["c"] == 0:
        subjects = [ "Software Engineering","Mobile Applications","Data Structure","Mathematics", "Information Security","Frontend Development","Basic Indian Language", "Information Security lab","Frontend Development lab","Mobile Applications lab", "Data Structure lab","Integral Yoga" ]
        db.executemany("INSERT INTO subjects(name) VALUES(?)", [(s,) for s in subjects])

    cur = db.execute("SELECT COUNT(*) c FROM students")
    if cur.fetchone()["c"] == 0:
        students = [
            ("24820001", "Aravindh", "devaravindh-ml-exercism"),
            ("24820002", "Aswin", "aswinas04-exercism"),
            ("24820003", "Bavana", "bhavana2912-exercism"),
            ("24820004", "Gokul", "gokulramesh502-exercism"),
            ("24820005", "Hariharan", "hariharan-exercism"),
            ("24820006", "Meenatchi", "meenatchi-exercism"),
            ("24820007", "Siva Bharathi", "Sivabharathi-Ramesh-exercism"),
            ("24820008", "Visal Stephen Raj", "Visalstephenraj-exercism"),
        ]
        db.executemany("INSERT INTO students(roll_no, name, exercism_username) VALUES(?, ?, ?)", students)
    db.commit()

# ---------- Main Pages ----------
@app.route("/")
def home():
    return render_template("new_home.html", page="home")

@app.route("/attendance")
def attendance_home():
    return render_template("attendance_home.html", page="attendance_home")

@app.route("/store")
def store():
    return render_template("store.html", page="store")

@app.route("/view")
def view():
    return render_template("view.html", page="view")

@app.route("/individual")
def individual():
    return render_template("individual.html", page="individual")

@app.route("/homework")
def homework_home():
    return render_template("homework_home.html", page="homework_home")

@app.route("/homework/manage")
def manage_homework():
    db = get_db()
    subject_filter = request.args.get("subject_id", type=int)
    date_filter = request.args.get("date", type=str)
    base_query = """
        SELECT h.id, h.title, h.description, h.posted_date, h.due_date, s.name as subject, s.id as subject_id
        FROM homework h JOIN subjects s ON h.subject_id = s.id
    """
    conditions = []; params = []
    if subject_filter:
        conditions.append("h.subject_id = ?"); params.append(subject_filter)
    if date_filter:
        dmy_date = datetime.strptime(date_filter, "%Y-%m-%d").strftime("%d-%m-%Y")
        conditions.append("h.posted_date = ?"); params.append(dmy_date)
    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)
    base_query += " ORDER BY substr(h.posted_date,7,4)||'-'||substr(h.posted_date,4,2)||'-'||substr(h.posted_date,1,2) DESC"
    
    homeworks = db.execute(base_query, params).fetchall()
    students = db.execute("SELECT id, name FROM students ORDER BY name").fetchall()
    submissions = {}
    if homeworks:
        hw_ids = [h['id'] for h in homeworks]
        submission_rows = db.execute(f"SELECT homework_id, student_id, grade FROM homework_submissions WHERE homework_id IN ({','.join(['?']*len(hw_ids))})", hw_ids).fetchall()
        for sub in submission_rows:
            if sub['homework_id'] not in submissions: submissions[sub['homework_id']] = {}
            submissions[sub['homework_id']][sub['student_id']] = sub['grade']

    return render_template("manage_homework.html", page="manage_homework", homeworks=homeworks, students=students, submissions=submissions)

@app.route("/homework/status")
def homework_status():
    db = get_db()
    SIMULATED_STUDENT_ID = 1
    homeworks = db.execute("""
        SELECT h.id, h.title, h.description, h.due_date, s.name as subject,
               COALESCE(hs.status, 'Pending') as student_status
        FROM homework h JOIN subjects s ON h.subject_id = s.id
        LEFT JOIN homework_submissions hs ON hs.homework_id = h.id AND hs.student_id = ?
        ORDER BY substr(h.due_date,7,4)||'-'||substr(h.due_date,4,2)||'-'||substr(h.due_date,1,2) ASC
    """, (SIMULATED_STUDENT_ID,)).fetchall()
    return render_template("homework_status.html", page="homework_status", homeworks=homeworks)
    
@app.route("/homework/doubts/<int:homework_id>")
def homework_doubts(homework_id):
    db = get_db()
    homework = db.execute("SELECT id, title FROM homework WHERE id = ?", (homework_id,)).fetchone()
    students = db.execute("SELECT id, name FROM students ORDER BY name").fetchall()
    doubts = db.execute("SELECT d.id, d.question, d.answer, s.name as student_name, d.asked_date FROM doubts d JOIN students s ON d.student_id = s.id WHERE d.homework_id = ? ORDER BY d.asked_date DESC", (homework_id,)).fetchall()
    return render_template("homework_doubts.html", page="homework_doubts", homework=homework, doubts=doubts, students=students)

@app.route("/homework/calendar")
def homework_calendar():
    return render_template("calendar.html", page="homework_calendar")

@app.route("/exercism")
def exercism():
    db = get_db()
    students = db.execute("SELECT name, exercism_username FROM students WHERE exercism_username IS NOT NULL").fetchall()
    return render_template("exercism.html", page="exercism", students=students)


# ---------- APIs ----------
@app.route("/api/subjects")
def api_subjects():
    db = get_db()
    rows = db.execute("SELECT id, name FROM subjects ORDER BY name").fetchall()
    return jsonify([dict(row) for row in rows])

@app.route("/api/students")
def api_students():
    db = get_db()
    rows = db.execute("SELECT id, roll_no, name FROM students ORDER BY name").fetchall()
    return jsonify([dict(row) for row in rows])

# --- ATTENDANCE APIs ---
@app.route("/api/save_attendance", methods=["POST"])
def api_save_attendance():
    data = request.get_json(force=True)
    date = data.get("date")
    subject_id = data.get("subject_id")
    marks = data.get("marks", [])
    try: datetime.strptime(date, "%d-%m-%Y")
    except Exception: return jsonify({"ok": False, "error": "Invalid date format; use dd-mm-yyyy"}), 400
    if not subject_id or not isinstance(marks, list) or len(marks) == 0: return jsonify({"ok": False, "error": "Missing subject or marks"}), 400
    db = get_db()
    s = db.execute("SELECT id FROM subjects WHERE id=?", (subject_id,)).fetchone()
    if not s: return jsonify({"ok": False, "error": "Subject not found"}), 404
    for m in marks:
        sid = m.get("student_id")
        status = m.get("status")
        if status not in ("Present", "Absent Informed", "Absent Uninformed"): return jsonify({"ok": False, "error": "Invalid status"}), 400
        st = db.execute("SELECT id FROM students WHERE id=?", (sid,)).fetchone()
        if not st: return jsonify({"ok": False, "error": f"Student {sid} not found"}), 404
        db.execute("INSERT INTO attendance(date, subject_id, student_id, status) VALUES(?,?,?,?) ON CONFLICT(date, subject_id, student_id) DO UPDATE SET status=excluded.status", (date, subject_id, sid, status))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/get_attendance_for_store")
def api_get_attendance_for_store():
    subject_id = request.args.get("subject_id", type=int)
    date = request.args.get("date", type=str)
    try: datetime.strptime(date, "%d-%m-%Y")
    except Exception: return jsonify({"ok": False, "error": "Invalid date format; use dd-mm-yyyy"}), 400
    db = get_db()
    rows = db.execute("SELECT st.id as student_id, COALESCE(a.status, 'none') AS status FROM students st LEFT JOIN attendance a ON a.student_id = st.id AND a.subject_id = ? AND a.date = ?", (subject_id, date)).fetchall()
    return jsonify({"ok": True, "records": [dict(r) for r in rows]})

@app.route("/api/get_attendance")
def api_get_attendance():
    db = get_db()
    subject_id = request.args.get("subject_id", type=int)
    filter_type = request.args.get("filter_type", "day")
    if not subject_id: return jsonify({"ok": False, "error": "Subject ID is required"}), 400
    if filter_type == "day":
        date = request.args.get("date", type=str)
        if not date: return jsonify({"ok": False, "error": "Date is required for day view"}), 400
        try: datetime.strptime(date, "%d-%m-%Y")
        except (ValueError, TypeError): return jsonify({"ok": False, "error": "Invalid date format"}), 400
        rows = db.execute("SELECT st.roll_no, st.name, COALESCE(a.status,'Absent Uninformed') AS status FROM students st LEFT JOIN attendance a ON a.student_id = st.id AND a.subject_id = ? AND a.date = ? ORDER BY st.name", (subject_id, date)).fetchall()
        return jsonify({"ok": True, "records": [dict(r) for r in rows]})
    else:
        base_query = "SELECT a.date, st.roll_no, st.name, a.status FROM attendance a JOIN students st ON a.student_id = st.id WHERE a.subject_id = ?"
        params = [subject_id]
        if filter_type == "year":
            year = request.args.get("year", type=str)
            if not year: return jsonify({"ok": False, "error": "Year is required"}), 400
            base_query += " AND substr(a.date, 7, 4) = ?"
            params.append(year)
        elif filter_type == "month":
            year = request.args.get("year", type=str)
            month = request.args.get("month", type=str)
            if not year or not month: return jsonify({"ok": False, "error": "Year and month are required"}), 400
            base_query += " AND substr(a.date, 7, 4) = ? AND substr(a.date, 4, 2) = ?"
            params.extend([year, month.zfill(2)])
        base_query += " ORDER BY substr(a.date,7,4), substr(a.date,4,2), substr(a.date,1,2), st.name"
        rows = db.execute(base_query, params).fetchall()
        return jsonify({"ok": True, "records": [dict(r) for r in rows]})

@app.route("/api/student_report")
def api_student_report():
    q = (request.args.get("query") or "").strip()
    subject_id = request.args.get("subject_id")
    date_type = request.args.get("dateType")
    year = request.args.get("year")
    month = request.args.get("month")
    date = request.args.get("date")
    db = get_db()
    stu = db.execute("SELECT * FROM students WHERE roll_no LIKE ? OR name LIKE ? ORDER BY name LIMIT 1", (f"%{q}%", f"%{q}%")).fetchone()
    if not stu: return jsonify({"ok": True, "student": None, "rows": []})
    conditions = ["a.student_id = ?"]; params = [stu["id"]]
    if subject_id: conditions.append("a.subject_id = ?"); params.append(subject_id)
    if date_type == "year" and year: conditions.append("substr(a.date,7,4) = ?"); params.append(year)
    if date_type == "month" and month and year:
        conditions.append("substr(a.date,4,2) = ? AND substr(a.date,7,4) = ?"); params.extend([month.zfill(2), year])
    if date_type == "date" and date:
        try:
            dmy = datetime.strptime(date, "%Y-%m-%d").strftime("%d-%m-%Y")
            conditions.append("a.date = ?"); params.append(dmy)
        except (ValueError, TypeError): return jsonify({"ok": False, "error": "Invalid date format"}), 400
    query = f"SELECT a.date, s.name AS subject, a.status FROM attendance a JOIN subjects s ON s.id = a.subject_id WHERE {' AND '.join(conditions)} ORDER BY substr(a.date,7,4)||'-'||substr(a.date,4,2)||'-'||substr(a.date,1,2) ASC, s.name ASC"
    rows = db.execute(query, params).fetchall()
    return jsonify({"ok": True, "student": {"id": stu["id"], "roll_no": stu["roll_no"], "name": stu["name"]}, "rows": [dict(r) for r in rows]})

# --- HOMEWORK APIs ---
@app.route("/api/homework", methods=["POST"])
def api_add_homework():
    data = request.get_json()
    posted_date = datetime.now().strftime("%d-%m-%Y")
    due_date = datetime.strptime(data['due_date'], "%Y-%m-%d").strftime("%d-%m-%Y")
    db = get_db()
    cursor = db.execute("INSERT INTO homework (subject_id, title, description, posted_date, due_date) VALUES (?, ?, ?, ?, ?)", (data['subject_id'], data['title'], data.get('description', ''), posted_date, due_date))
    db.commit()
    return jsonify({"ok": True, "new_id": cursor.lastrowid, "posted_date": posted_date})
@app.route("/api/homework/<int:homework_id>", methods=["POST"])
def api_update_homework(homework_id):
    data = request.get_json(force=True)
    due_date = datetime.strptime(data.get("due_date"), "%Y-%m-%d").strftime("%d-%m-%Y")
    db = get_db()
    db.execute("UPDATE homework SET subject_id = ?, title = ?, description = ?, due_date = ? WHERE id = ?", (data.get("subject_id"), data.get("title"), data.get("description"), due_date, homework_id))
    db.commit()
    return jsonify({"ok": True})
@app.route("/api/homework/<int:homework_id>", methods=["DELETE"])
def api_delete_homework(homework_id):
    db = get_db()
    db.execute("DELETE FROM homework WHERE id = ?", (homework_id,))
    db.commit()
    return jsonify({"ok": True})
@app.route("/api/homework/grade", methods=["POST"])
def api_grade_homework():
    data = request.get_json()
    db = get_db()
    db.execute("INSERT INTO homework_submissions (homework_id, student_id, grade, status) VALUES (?, ?, ?, 'Graded') ON CONFLICT(homework_id, student_id) DO UPDATE SET grade = excluded.grade, status = 'Graded'",(data['homework_id'], data['student_id'], data.get('grade')))
    db.commit()
    return jsonify({"ok": True})

# --- DOUBTS APIs ---
@app.route("/api/doubts/ask", methods=["POST"])
def api_ask_doubt():
    data = request.get_json()
    student_id = data.get('student_id')
    if not student_id: return jsonify({"ok": False, "message": "Please select a student."}), 400
    asked_date = datetime.now().strftime("%d-%m-%Y %H:%M")
    db = get_db()
    db.execute("INSERT INTO doubts (homework_id, student_id, question, asked_date) VALUES (?, ?, ?, ?)",(data['homework_id'], student_id, data['question'], asked_date))
    db.commit()
    return jsonify({"ok": True, "message": "Doubt posted!"})
@app.route("/api/doubts/answer", methods=["POST"])
def api_answer_doubt():
    data = request.get_json()
    db = get_db()
    db.execute("UPDATE doubts SET answer = ? WHERE id = ?",(data['answer'], data['doubt_id']))
    db.commit()
    return jsonify({"ok": True, "message": "Answer posted!"})
@app.route("/api/doubts/<int:doubt_id>", methods=["POST"])
def api_update_doubt(doubt_id):
    data = request.get_json()
    question_text = data.get("question")
    if not question_text: return jsonify({"ok": False, "message": "Question text cannot be empty."}), 400
    db = get_db()
    db.execute("UPDATE doubts SET question = ? WHERE id = ?", (question_text, doubt_id))
    db.commit()
    return jsonify({"ok": True})
@app.route("/api/doubts/<int:doubt_id>", methods=["DELETE"])
def api_delete_doubt(doubt_id):
    db = get_db()
    db.execute("DELETE FROM doubts WHERE id = ?", (doubt_id,))
    db.commit()
    return jsonify({"ok": True})

# --- CALENDAR API ---
@app.route("/api/homework/events")
def api_homework_events():
    db = get_db()
    homeworks = db.execute("SELECT id, title, due_date FROM homework").fetchall()
    events = []
    for hw in homeworks:
        try:
            d, m, y = hw['due_date'].split('-')
            start_date = f"{y}-{m}-{d}"
            events.append({'title': hw['title'],'start': start_date,'url': url_for('homework_doubts', homework_id=hw['id']),'color': '#b58900'})
        except (ValueError, IndexError): continue
    return jsonify(events)

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True, port=5001)