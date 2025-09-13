import requests
import sqlite3
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, g

APP_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(APP_DIR, "attendance.db")

app = Flask(__name__)

# ---------- DB helpers ----------
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

def init_db():
    db = get_db()
    db.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_no TEXT UNIQUE NOT NULL, name TEXT NOT NULL, codewars_username TEXT
        );
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS homework (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            posted_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS homework_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            homework_id INTEGER NOT NULL, student_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            FOREIGN KEY(homework_id) REFERENCES homework(id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
            UNIQUE(homework_id, student_id)
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
    db.execute("PRAGMA foreign_keys=off;")
    db.execute("BEGIN TRANSACTION;")
    try:
        db.execute("ALTER TABLE students ADD COLUMN codewars_username TEXT")
    except sqlite3.OperationalError: pass
    try:
        db.execute("ALTER TABLE homework ADD COLUMN posted_date TEXT")
    except sqlite3.OperationalError: pass
    db.execute("COMMIT;")
    db.execute("PRAGMA foreign_keys=on;")

    cur = db.execute("SELECT COUNT(*) c FROM subjects")
    if cur.fetchone()["c"] == 0:
        subjects = ["Software Engineering", "Mobile Applications", "Data Structure", "Mathematics", "Information Security", "Frontend Development", "Basic Indian Language", "Information Security lab", "Frontend Development lab", "Mobile Applications lab", "Data Structure lab", "Integral Yoga"]
        db.executemany("INSERT INTO subjects(name) VALUES(?)", [(s,) for s in subjects])

    cur = db.execute("SELECT COUNT(*) c FROM students")
    if cur.fetchone()["c"] == 0:
        students_with_codewars = [
            ("24820001","Aravindh","aravindh-cw"), ("24820002","Aswin","aswin-cw"), ("24820003","Bavana","bavana-cw"),
            ("24820004","Gokul","gokul-cw"), ("24820005","Hariharan","hariharan-cw"), ("24820006","Meenatchi","meenatchi-cw"),
            ("24820007","Siva Bharathi","siva-cw"), ("24820008","Visal Stephen Raj","visal-cw"),
        ]
        db.executemany("INSERT INTO students(roll_no, name, codewars_username) VALUES(?, ?, ?)", students_with_codewars)
    db.commit()

# ---------- Main Pages ----------
@app.route("/")
def home():
    return render_template("new_home.html", page="home")

@app.route("/attendance")
def attendance_home():
    return render_template("attendance_home.html", page="attendance_home")
    
@app.route("/homework")
def homework_home():
    return render_template("homework_home.html", page="homework_home")

@app.route("/manage-homework")
def manage_homework():
    db = get_db()
    homeworks = db.execute("""
        SELECT h.id, h.description, h.posted_date, h.due_date, s.name as subject, s.id as subject_id
        FROM homework h JOIN subjects s ON h.subject_id = s.id
        ORDER BY substr(h.posted_date,7,4)||'-'||substr(h.posted_date,4,2)||'-'||substr(h.posted_date,1,2) DESC
    """).fetchall()
    return render_template("manage_homework.html", page="manage_homework", homeworks=homeworks)

@app.route("/homework-status")
def homework_status():
    db = get_db()
    SIMULATED_STUDENT_ID = 1
    homeworks = db.execute("""
        SELECT h.id, h.description, h.due_date, s.name as subject,
               COALESCE(hs.status, 'Pending') as student_status
        FROM homework h JOIN subjects s ON h.subject_id = s.id
        LEFT JOIN homework_submissions hs ON hs.homework_id = h.id AND hs.student_id = ?
        ORDER BY substr(h.due_date,7,4)||'-'||substr(h.due_date,4,2)||'-'||substr(h.due_date,1,2) ASC
    """, (SIMULATED_STUDENT_ID,)).fetchall()
    return render_template("homework_status.html", page="homework_status", homeworks=homeworks)

@app.route("/codewars")
def codewars():
    db = get_db()
    students = db.execute("SELECT name, codewars_username FROM students WHERE codewars_username IS NOT NULL").fetchall()
    codewars_data = []
    for student in students:
        username = student["codewars_username"]
        try:
            response = requests.get(f"https://www.codewars.com/api/v1/users/{username}")
            response.raise_for_status()
            data = response.json()
            data['student_name'] = student['name']
            codewars_data.append(data)
        except requests.exceptions.RequestException as e:
            codewars_data.append({
                'student_name': student['name'],
                'username': username,
                'error': f"Could not fetch data. Error: {e}"
            })
    codewars_data.sort(key=lambda x: x.get('honor', 0), reverse=True)
    return render_template("codewars.html", page="codewars", profiles=codewars_data)

@app.route("/project")
def project():
    return "<h1>Project Page - Coming Soon!</h1><a href='/'>Back to Home</a>"

@app.route("/communication")
def communication():
    return "<h1>Communication Page - Coming Soon!</h1><a href='/'>Back to Home</a>"

# ---------- Attendance Module Pages ----------
@app.route("/store")
def store():
    return render_template("store.html", page="store")

@app.route("/view")
def view():
    return render_template("view.html", page="view")

@app.route("/individual")
def individual():
    return render_template("individual.html", page="individual")

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

# --- HOMEWORK APIs ---
@app.route("/api/homework", methods=["POST"])
def api_add_homework():
    data = request.get_json(force=True)
    posted_date = datetime.now().strftime("%d-%m-%Y")
    due_date = datetime.strptime(data.get("due_date"), "%Y-%m-%d").strftime("%d-%m-%Y")
    db = get_db()
    cursor = db.execute(
        "INSERT INTO homework (subject_id, description, posted_date, due_date) VALUES (?, ?, ?, ?)",
        (data.get("subject_id"), data.get("description"), posted_date, due_date)
    )
    db.commit()
    new_id = cursor.lastrowid
    return jsonify({"ok": True, "new_id": new_id, "posted_date": posted_date})

@app.route("/api/homework/<int:homework_id>", methods=["POST"])
def api_update_homework(homework_id):
    data = request.get_json(force=True)
    due_date = datetime.strptime(data.get("due_date"), "%Y-%m-%d").strftime("%d-%m-%Y")
    db = get_db()
    db.execute(
        "UPDATE homework SET subject_id = ?, description = ?, due_date = ? WHERE id = ?",
        (data.get("subject_id"), data.get("description"), due_date, homework_id)
    )
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/homework/<int:homework_id>", methods=["DELETE"])
def api_delete_homework(homework_id):
    db = get_db()
    db.execute("DELETE FROM homework WHERE id = ?", (homework_id,))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/homework_status", methods=["POST"])
def api_update_homework_status():
    data = request.get_json(force=True)
    homework_id = data.get("homework_id")
    student_id = 1
    status = data.get("status")
    db = get_db()
    db.execute("""
        INSERT INTO homework_submissions (homework_id, student_id, status)
        VALUES (?, ?, ?)
        ON CONFLICT(homework_id, student_id) DO UPDATE SET
        status = excluded.status
    """, (homework_id, student_id, status))
    db.commit()
    return jsonify({"ok": True})
    
# --- ATTENDANCE APIs ---
@app.route("/api/save_attendance", methods=["POST"])
def api_save_attendance():
    data = request.get_json(force=True)
    date = data.get("date")
    subject_id = data.get("subject_id")
    marks = data.get("marks", [])
    try:
        datetime.strptime(date, "%d-%m-%Y")
    except Exception:
        return jsonify({"ok": False, "error": "Invalid date format; use dd-mm-yyyy"}), 400
    if not subject_id or not isinstance(marks, list) or len(marks) == 0:
        return jsonify({"ok": False, "error": "Missing subject or marks"}), 400
    db = get_db()
    s = db.execute("SELECT id FROM subjects WHERE id=?", (subject_id,)).fetchone()
    if not s:
        return jsonify({"ok": False, "error": "Subject not found"}), 404
    for m in marks:
        sid = m.get("student_id")
        status = m.get("status")
        if status not in ("Present", "Absent Informed", "Absent Uninformed"):
            return jsonify({"ok": False, "error": "Invalid status"}), 400
        st = db.execute("SELECT id FROM students WHERE id=?", (sid,)).fetchone()
        if not st:
            return jsonify({"ok": False, "error": f"Student {sid} not found"}), 404
        db.execute(
            """
            INSERT INTO attendance(date, subject_id, student_id, status)
            VALUES(?,?,?,?)
            ON CONFLICT(date, subject_id, student_id)
            DO UPDATE SET status=excluded.status
            """,
            (date, subject_id, sid, status)
        )
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/get_attendance")
def api_get_attendance():
    db = get_db()
    subject_id = request.args.get("subject_id", type=int)
    filter_type = request.args.get("filter_type", "date")
    if filter_type == "date":
        date = request.args.get("date", type=str)
        if not date: return jsonify({"ok": False, "error": "Missing date parameter"}), 400
        try: datetime.strptime(date, "%d-%m-%Y")
        except (ValueError, TypeError): return jsonify({"ok": False, "error": "Invalid date format; use dd-mm-yyyy"}), 400
        rows = db.execute(
            """
            SELECT st.roll_no, st.name, COALESCE(a.status,'Absent Uninformed') AS status
            FROM students st
            LEFT JOIN attendance a
                ON a.student_id = st.id AND a.subject_id = ? AND a.date = ?
            ORDER BY st.name
            """, (subject_id, date)).fetchall()
        return jsonify({"ok": True, "records": [dict(r) for r in rows]})
    else:
        year = request.args.get("year", type=str)
        if not year: return jsonify({"ok": False, "error": "Missing year parameter"}), 400
        base_query = """
            SELECT a.date, st.roll_no, st.name, a.status
            FROM attendance a JOIN students st ON a.student_id = st.id
            WHERE a.subject_id = ? AND substr(a.date, 7, 4) = ?
        """
        params = [subject_id, year]
        if filter_type == "month":
            month = request.args.get("month", type=str)
            if not month: return jsonify({"ok": False, "error": "Missing month parameter"}), 400
            base_query += " AND substr(a.date, 4, 2) = ?"
            params.append(month)
        base_query += " ORDER BY substr(a.date,7,4), substr(a.date,4,2), substr(a.date,1,2), st.name"
        rows = db.execute(base_query, params).fetchall()
        return jsonify({"ok": True, "records": [dict(r) for r in rows]})

@app.route("/api/get_attendance_for_store")
def api_get_attendance_for_store():
    subject_id = request.args.get("subject_id", type=int)
    date = request.args.get("date", type=str)
    try:
        datetime.strptime(date, "%d-%m-%Y")
    except Exception:
        return jsonify({"ok": False, "error": "Invalid date format; use dd-mm-yyyy"}), 400
    db = get_db()
    rows = db.execute(
        """
        SELECT st.id as student_id, COALESCE(a.status, 'none') AS status
        FROM students st
        LEFT JOIN attendance a ON a.student_id = st.id AND a.subject_id = ? AND a.date = ?
        """,
        (subject_id, date)
    ).fetchall()
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
    stu = db.execute(
        "SELECT * FROM students WHERE roll_no LIKE ? OR name LIKE ? ORDER BY name LIMIT 1",
        (f"%{q}%", f"%{q}%")
    ).fetchone()
    if not stu:
        return jsonify({"ok": True, "student": None, "rows": []})
    conditions = ["a.student_id = ?"]
    params = [stu["id"]]
    if subject_id:
        conditions.append("a.subject_id = ?")
        params.append(subject_id)
    if date_type == "year" and year:
        conditions.append("substr(a.date,7,4) = ?")
        params.append(year)
    if date_type == "month" and month:
        conditions.append("substr(a.date,4,2) = ?")
        params.append(month.zfill(2))
    if date_type == "date" and date:
        try:
            dmy = datetime.strptime(date, "%Y-%m-%d").strftime("%d-%m-%Y")
            conditions.append("a.date = ?")
            params.append(dmy)
        except Exception:
            return jsonify({"ok": False, "error": "Invalid date format"}), 400
    query = f"""
        SELECT a.date, s.name AS subject, a.status
        FROM attendance a JOIN subjects s ON s.id = a.subject_id
        WHERE {' AND '.join(conditions)}
        ORDER BY substr(a.date,7,4)||'-'||substr(a.date,4,2)||'-'||substr(a.date,1,2) ASC, s.name ASC
    """
    rows = db.execute(query, params).fetchall()
    days_present = sum(1 for row in rows if row['status'] == 'Present')
    return jsonify({
        "ok": True,
        "student": {"id": stu["id"], "roll_no": stu["roll_no"], "name": stu["name"]},
        "rows": [dict(r) for r in rows],
        "days_present": days_present
    })

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)