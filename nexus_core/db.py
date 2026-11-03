"""M1 - relational schema (SQLite for development; DDL is portable to PostgreSQL/MySQL). Final DB choice pending coordinator."""
import sqlite3
from .models import *

DDL = """
CREATE TABLE IF NOT EXISTS courses(id TEXT PRIMARY KEY, title TEXT, category TEXT, credits INT);
CREATE TABLE IF NOT EXISTS course_sessions(course_id TEXT REFERENCES courses(id), k INT, duration INT, room_type TEXT, PRIMARY KEY(course_id,k));
CREATE TABLE IF NOT EXISTS sections(id TEXT PRIMARY KEY, course_id TEXT REFERENCES courses(id), capacity INT);
CREATE TABLE IF NOT EXISTS section_sessions(section_id TEXT REFERENCES sections(id), k INT, duration INT, room_type TEXT, PRIMARY KEY(section_id,k));
CREATE TABLE IF NOT EXISTS faculty(id TEXT PRIMARY KEY, name TEXT, max_hours INT);
CREATE TABLE IF NOT EXISTS faculty_qualifications(faculty_id TEXT REFERENCES faculty(id), course_id TEXT REFERENCES courses(id), PRIMARY KEY(faculty_id,course_id));
CREATE TABLE IF NOT EXISTS faculty_availability(faculty_id TEXT REFERENCES faculty(id), slot INT, PRIMARY KEY(faculty_id,slot)); -- rows = UNAVAILABLE slots
CREATE TABLE IF NOT EXISTS rooms(id TEXT PRIMARY KEY, type TEXT, capacity INT);
CREATE TABLE IF NOT EXISTS room_availability(room_id TEXT REFERENCES rooms(id), slot INT, PRIMARY KEY(room_id,slot));         -- rows = UNAVAILABLE slots
CREATE TABLE IF NOT EXISTS students(id TEXT PRIMARY KEY, programme TEXT);
CREATE TABLE IF NOT EXISTS student_selections(student_id TEXT REFERENCES students(id), course_id TEXT REFERENCES courses(id), PRIMARY KEY(student_id,course_id));
CREATE TABLE IF NOT EXISTS timetable_runs(id INTEGER PRIMARY KEY AUTOINCREMENT, dataset TEXT, method TEXT, seed INT, status TEXT, validator TEXT, runtime REAL);
CREATE TABLE IF NOT EXISTS assignments(run_id INT REFERENCES timetable_runs(id), section_id TEXT, k INT, start_slot INT, room_id TEXT, faculty_id TEXT);
CREATE TABLE IF NOT EXISTS enrolments(run_id INT REFERENCES timetable_runs(id), student_id TEXT, course_id TEXT, section_id TEXT);
"""


def connect(path=":memory:"):
    # Create the schema when opening either a file database or an in-memory database.
    con = sqlite3.connect(path)
    con.executescript(DDL)
    return con


def save_dataset(con, ds: Dataset):
    # Store each entity and its relationships in the normalized tables.
    q = con.executemany
    q("INSERT INTO courses VALUES(?,?,?,?)", [(c.id, c.title, c.category, c.credits) for c in ds.courses.values()])
    q("INSERT INTO course_sessions VALUES(?,?,?,?)", [(c.id, k, x.duration, x.room_type) for c in ds.courses.values() for k, x in enumerate(c.sessions)])
    q("INSERT INTO sections VALUES(?,?,?)", [(s.id, s.course_id, s.capacity) for s in ds.sections.values()])
    q("INSERT INTO section_sessions VALUES(?,?,?,?)",
      [(s.id, k, x.duration, x.room_type) for s in ds.sections.values() if s.sessions is not None
       for k, x in enumerate(s.sessions)])
    q("INSERT INTO faculty VALUES(?,?,?)", [(f.id, f.name, f.max_hours) for f in ds.faculty.values()])
    q("INSERT INTO faculty_qualifications VALUES(?,?)", [(f.id, c) for f in ds.faculty.values() for c in f.qualified])
    q("INSERT INTO faculty_availability VALUES(?,?)", [(f.id, t) for f in ds.faculty.values() for t in f.unavailable])
    q("INSERT INTO rooms VALUES(?,?,?)", [(r.id, r.type, r.capacity) for r in ds.rooms.values()])
    q("INSERT INTO room_availability VALUES(?,?)", [(r.id, t) for r in ds.rooms.values() for t in r.unavailable])
    q("INSERT INTO students VALUES(?,?)", [(s.id, s.programme) for s in ds.students.values()])
    q("INSERT INTO student_selections VALUES(?,?)", [(s.id, c) for s in ds.students.values() for c in s.selections])
    con.commit()


def load_dataset(con, name="db") -> Dataset:
    # Rebuild the in-memory objects from the relational rows.
    g = lambda sql: con.execute(sql).fetchall()
    sess = {}
    for cid, k, d, rt in g("SELECT * FROM course_sessions ORDER BY course_id,k"):
        sess.setdefault(cid, []).append(SessionSpec(d, rt))
    courses = {i: Course(i, t, c, cr, tuple(sess.get(i, []))) for i, t, c, cr in g("SELECT * FROM courses")}
    section_sess = {}
    for sid, k, d, rt in g("SELECT * FROM section_sessions ORDER BY section_id,k"):
        section_sess.setdefault(sid, []).append(SessionSpec(d, rt))
    sections = {
        i: Section(i, c, cap, sessions=tuple(section_sess[i]) if i in section_sess else None)
        for i, c, cap in g("SELECT * FROM sections")
    }
    q, u = {}, {}
    for f, c in g("SELECT * FROM faculty_qualifications"): q.setdefault(f, set()).add(c)
    for f, t in g("SELECT * FROM faculty_availability"): u.setdefault(f, set()).add(t)
    faculty = {i: Faculty(i, n, frozenset(q.get(i, ())), h, frozenset(u.get(i, ()))) for i, n, h in g("SELECT * FROM faculty")}
    ru = {}
    for r, t in g("SELECT * FROM room_availability"): ru.setdefault(r, set()).add(t)
    rooms = {i: Room(i, t, c, frozenset(ru.get(i, ()))) for i, t, c in g("SELECT * FROM rooms")}
    sel = {}
    for s, c in g("SELECT * FROM student_selections ORDER BY rowid"): sel.setdefault(s, []).append(c)
    students = {i: Student(i, p, tuple(sel.get(i, ()))) for i, p in g("SELECT * FROM students")}
    return Dataset(name, courses, sections, faculty, rooms, students)


def save_run(con, ds, sched, report):
    # Save the run summary along with its placements and student enrolments.
    cur = con.execute("INSERT INTO timetable_runs(dataset,method,seed,status,validator,runtime) VALUES(?,?,?,?,?,?)",
                      (ds.name, sched.method, ds.meta.get("seed"), sched.status, report.status, sched.runtime))
    rid = cur.lastrowid
    con.executemany("INSERT INTO assignments VALUES(?,?,?,?,?,?)",
                    [(rid, s, k, st, r, sched.faculty[s]) for (s, k), (st, r) in sched.placement.items()])
    con.executemany("INSERT INTO enrolments VALUES(?,?,?,?)",
                    [(rid, stid, c, s) for stid, d in sched.enrolment.items() for c, s in d.items()])
    con.commit()
    return rid
