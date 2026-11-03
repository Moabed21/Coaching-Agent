"""PeopleHub, learning track: course enrolment for Al Dana Group (fictional).

    from peoplehub import learning
    learning.check_enrolment("E1011", "LD-103", actor="E1011")

Rules come from the Learning and Development policy HR-POL-12 v2.1 (see docs/learning_API.md).
Catalogue, completions and the mandatory matrix are the LearnDesk files from the Phase 1 pack.
"""
import calendar
import datetime as dt
import re

from .core import ApiError, TODAY, api, read_csv

TRACK = "learning"
WRITE_TABLES = ["enrolments", "learning_plans"]

HR_DEPARTMENT = "Human Resources"
HR_APPROVAL_ABOVE_QAR = 3000  # HR-POL-12 section 4: a fee above this also needs the HR head
BUDGET_BANDS = [(3, 2500), (6, 6000), (8, 12000), (10, 20000)]  # HR-POL-12 section 3: (highest grade, QAR per year)
BAND_NAMES = {2500: "G1-G3", 6000: "G4-G6", 12000: "G7-G8", 20000: "G9-G10"}
NEW_JOINER_DAYS = 60  # HR-POL-12 section 6.1


def create_schema(conn):
    conn.executescript("""
    CREATE TABLE departments (dept_code TEXT PRIMARY KEY, dept_name_en TEXT, dept_name_ar TEXT, cost_centre TEXT,
      head_employee_id TEXT);
    CREATE TABLE courses (course_id TEXT PRIMARY KEY, title_en TEXT, title_ar TEXT, level TEXT, delivery TEXT,
      duration_hours INTEGER, language TEXT, prerequisites TEXT, min_grade INTEGER, cost_qar INTEGER, status TEXT,
      mandatory_for TEXT, skills TEXT);
    CREATE TABLE completions (employee_id TEXT, course_id TEXT, completed_on TEXT, score INTEGER);
    CREATE TABLE mandatory_matrix (course_id TEXT, scope_type TEXT, applies_to TEXT, renewal_months INTEGER);
    CREATE TABLE course_sessions (session_id TEXT PRIMARY KEY, course_id TEXT, start_date TEXT, end_date TEXT,
      delivery TEXT, location TEXT, capacity INTEGER, held INTEGER);
    CREATE TABLE enrolments (enrolment_id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT, course_id TEXT,
      session_id TEXT, status TEXT, requested_by TEXT, approved_by TEXT, booked_on TEXT, cancelled_on TEXT);
    CREATE TABLE learning_plans (plan_id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT, plan_text TEXT,
      status TEXT, created_by TEXT, created_on TEXT);
    """)


def _load(conn, table, rows, cols):
    conn.executemany(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                     [[r[c] for c in cols] for r in rows])


def seed(conn, seed_dir):
    cols = lambda t: [r[1] for r in conn.execute(f"PRAGMA table_info({t})")]  # noqa: E731
    _load(conn, "departments", read_csv(seed_dir / "departments.csv"), cols("departments"))
    _load(conn, "courses", read_csv(seed_dir / "course_catalog.csv"), cols("courses"))
    _load(conn, "completions", read_csv(seed_dir / "completions.csv"), cols("completions"))
    _load(conn, "mandatory_matrix", read_csv(seed_dir / "mandatory_matrix.csv"), cols("mandatory_matrix"))
    _load(conn, "course_sessions", read_csv(seed_dir / "course_sessions.csv"), cols("course_sessions"))


# ------------------------------------------------------------------ helpers (not part of the API)
def _add_months(d, months):
    y, m = divmod(d.year * 12 + d.month - 1 + months, 12)
    return dt.date(y, m + 1, min(d.day, calendar.monthrange(y, m + 1)[1]))


def _can_see(ctx, emp):
    """The person themselves, their line manager, or anyone in HR."""
    if ctx.actor == emp["employee_id"] or ctx.actor == emp["manager_id"]:
        return True
    return ctx.employee(ctx.actor)["department"] == HR_DEPARTMENT


def _visible_employee(ctx, employee_id):
    emp = ctx.employee(employee_id)
    if not _can_see(ctx, emp):
        raise ApiError("ERR_FORBIDDEN", f"You may not see or change the learning record of {employee_id}. "
                                        "Only that person, their line manager and HR may.")
    return emp


def _course(ctx, course_id):
    row = ctx.one("SELECT * FROM courses WHERE course_id=?", (course_id,))
    if row is None:
        raise ApiError("ERR_NOT_FOUND", f"No course {course_id}")
    return row


def _hr_head(ctx):
    row = ctx.one("SELECT head_employee_id FROM departments WHERE dept_name_en=?", (HR_DEPARTMENT,))
    return row["head_employee_id"]


def _annual_budget(grade):
    return next(amount for top, amount in BUDGET_BANDS if int(grade) <= top)


def _spent_this_year(ctx, employee_id):
    """HR-POL-12 section 3.4: fees of OPTIONAL courses completed in the budget year."""
    row = ctx.one("SELECT COALESCE(SUM(c.cost_qar), 0) AS s FROM completions k JOIN courses c USING (course_id) "
                  "WHERE k.employee_id=? AND c.mandatory_for='' AND substr(k.completed_on, 1, 4)=?",
                  (employee_id, ctx.today[:4]))
    return row["s"]


def _overdue_mandatory(ctx, emp):
    """HR-POL-12 section 6: due = last completion + renewal period (never done: hire date + 60 days)."""
    out = []
    for m in ctx.all("SELECT * FROM mandatory_matrix ORDER BY course_id"):
        applies = (m["scope_type"] == "All" or (m["scope_type"] == "Department" and emp["department"] == m["applies_to"])
                   or (m["scope_type"] == "Location" and emp["location"] == m["applies_to"]))
        if not applies:
            continue
        last = ctx.one("SELECT MAX(completed_on) AS d FROM completions WHERE employee_id=? AND course_id=?",
                       (emp["employee_id"], m["course_id"]))["d"]
        if last:
            due = _add_months(dt.date.fromisoformat(last), m["renewal_months"])
        else:
            due = dt.date.fromisoformat(emp["hire_date"]) + dt.timedelta(days=NEW_JOINER_DAYS)
        if due.isoformat() < ctx.today:
            title = ctx.one("SELECT title_en FROM courses WHERE course_id=?", (m["course_id"],))["title_en"]
            out.append({"course_id": m["course_id"], "title": title, "due_date": due.isoformat(), "last_completed": last})
    return out


def _seats_left(ctx, session):
    booked = ctx.one("SELECT COUNT(*) AS n FROM enrolments WHERE session_id=? AND status='booked'",
                     (session["session_id"],))["n"]
    return max(0, session["capacity"] - session["held"] - booked)


def _approvers(ctx, emp, course):
    """Who must approve a booking, as a list of (role, employee_id). HR-POL-12 section 4."""
    if course["mandatory_for"]:
        return []
    out = [("line_manager", emp["manager_id"] or _hr_head(ctx))]
    if course["cost_qar"] > HR_APPROVAL_ABOVE_QAR and out[0][1] != _hr_head(ctx):
        out.append(("hr_head", _hr_head(ctx)))
    return out


def _reasons(ctx, emp, course):
    """Every reason the course cannot be booked for this person right now: a list of (code, detail)."""
    eid = emp["employee_id"]
    if course["mandatory_for"]:
        return [("MANDATORY_BOOKED_BY_HR", "Mandatory courses are booked by HR, not through this system.")]
    out = []
    if course["status"] != "Active":
        out.append(("RETIRED", f"{course['course_id']} has catalogue status {course['status']}."))
    if ctx.one("SELECT 1 FROM completions WHERE employee_id=? AND course_id=?", (eid, course["course_id"])):
        out.append(("ALREADY_COMPLETED", "The employee has already completed this course."))
    booked = ctx.one("SELECT enrolment_id FROM enrolments WHERE employee_id=? AND course_id=? AND status='booked'",
                     (eid, course["course_id"]))
    if booked:
        out.append(("ALREADY_BOOKED", f"The employee is already booked on it (enrolment {booked['enrolment_id']})."))
    missing = [p for p in course["prerequisites"].split(";") if p and not ctx.one(
        "SELECT 1 FROM completions WHERE employee_id=? AND course_id=?", (eid, p))]
    if missing:
        out.append(("PREREQUISITE_MISSING", f"Prerequisite not completed: {', '.join(missing)}."))
    if int(emp["grade"]) < course["min_grade"]:
        out.append(("BELOW_MIN_GRADE", f"Grade {emp['grade']} is below the minimum grade {course['min_grade']}."))
    remaining = _annual_budget(emp["grade"]) - _spent_this_year(ctx, eid)
    if course["cost_qar"] > remaining:
        out.append(("OVER_BUDGET", f"Fee QAR {course['cost_qar']} is above the remaining budget QAR {remaining}."))
    overdue = _overdue_mandatory(ctx, emp)
    if overdue:
        out.append(("MANDATORY_OVERDUE", "Overdue mandatory course(s): " + ", ".join(o["course_id"] for o in overdue) + "."))
    return out


def _rows(rows):
    return [dict(r) for r in rows]


# ------------------------------------------------------------------ reads
@api("read")
def get_learning_profile(ctx, employee_id, *, actor):
    """Grade, budget, completed courses, overdue mandatory courses and current bookings of one employee."""
    emp = _visible_employee(ctx, employee_id)
    annual = _annual_budget(emp["grade"])
    spent = _spent_this_year(ctx, employee_id)
    done = ctx.all("SELECT k.course_id, c.title_en AS title, k.completed_on, c.cost_qar AS fee_qar, "
                   "(c.mandatory_for != '') AS mandatory FROM completions k JOIN courses c USING (course_id) "
                   "WHERE k.employee_id=? ORDER BY k.completed_on, k.course_id", (employee_id,))
    booked = ctx.all("SELECT e.enrolment_id, e.course_id, c.title_en AS title, e.session_id, e.status, s.start_date "
                     "FROM enrolments e JOIN course_sessions s USING (session_id) JOIN courses c ON c.course_id=e.course_id "
                     "WHERE e.employee_id=? ORDER BY e.enrolment_id", (employee_id,))
    return {"employee_id": employee_id, "name": emp["full_name_en"], "grade": int(emp["grade"]),
            "line_manager_id": emp["manager_id"] or None, "budget_year": int(ctx.today[:4]),
            "grade_band": BAND_NAMES[annual], "annual_budget_qar": annual, "spent_this_year_qar": spent,
            "remaining_budget_qar": annual - spent,
            "completed": [dict(r, mandatory=bool(r["mandatory"])) for r in done],
            "overdue_mandatory": _overdue_mandatory(ctx, emp), "enrolments": _rows(booked)}


@api("read")
def find_course(ctx, query, *, actor):
    """Courses whose title matches `query`: every word you type must start a word of the English or Arabic title
    (any case), or the query is a course id. At most 10, ordered by course id. Retired courses are included and marked."""
    q = (query or "").strip().lower()
    words = re.findall(r"\w+", q)
    if len(q) < 2:
        return {"courses": []}
    out = []
    for c in ctx.all("SELECT * FROM courses ORDER BY course_id"):
        title_words = re.findall(r"\w+", f"{c['title_en']} {c['title_ar']}".lower())
        if q == c["course_id"].lower() or (words and all(any(t.startswith(w) for t in title_words) for w in words)):
            out.append({"course_id": c["course_id"], "title": c["title_en"], "status": c["status"],
                        "fee_qar": c["cost_qar"], "mandatory": bool(c["mandatory_for"])})
    return {"courses": out[:10]}


@api("read")
def check_enrolment(ctx, employee_id, course_id, *, actor):
    """Dry run of request_enrolment for the course (no session needed): is it allowed, why not, who must approve."""
    emp = _visible_employee(ctx, employee_id)
    course = _course(ctx, course_id)
    reasons = _reasons(ctx, emp, course)
    return {"employee_id": employee_id, "course_id": course_id, "title": course["title_en"],
            "fee_qar": course["cost_qar"], "mandatory": bool(course["mandatory_for"]),
            "eligible": not reasons, "reasons": [{"code": c, "detail": d} for c, d in reasons],
            "approvals_needed": [{"role": r, "employee_id": e} for r, e in _approvers(ctx, emp, course)]}


@api("read")
def list_sessions(ctx, course_id, from_date=None, *, actor):
    """Scheduled sessions of a course starting on or after from_date (default today), with seats left."""
    _course(ctx, course_id)
    start = from_date or ctx.today
    try:
        dt.date.fromisoformat(start)
    except (TypeError, ValueError):
        raise ApiError("ERR_NOT_APPLICABLE", "from_date must be an ISO date such as 2026-11-01.")
    rows = ctx.all("SELECT * FROM course_sessions WHERE course_id=? AND start_date>=? ORDER BY start_date, session_id",
                   (course_id, start))
    return {"course_id": course_id, "sessions": [
        {"session_id": s["session_id"], "start_date": s["start_date"], "end_date": s["end_date"],
         "delivery": s["delivery"], "location": s["location"], "capacity": s["capacity"],
         "seats_left": _seats_left(ctx, s)} for s in rows]}


# ------------------------------------------------------------------ writes
@api("write")
def request_enrolment(ctx, employee_id, course_id, session_id, *, actor, approved_by=None, idempotency_key=None):
    """Book the employee on a session. Needs the line manager's approval, and the HR head's too above QAR 3,000."""
    emp = _visible_employee(ctx, employee_id)
    course = _course(ctx, course_id)
    session = ctx.one("SELECT * FROM course_sessions WHERE session_id=?", (session_id,))
    if session is None:
        raise ApiError("ERR_NOT_FOUND", f"No session {session_id}")
    if course["mandatory_for"]:
        raise ApiError("ERR_HUMAN_ONLY", f"{course_id} is a mandatory course. HR books mandatory courses; ask HR.")
    ctx.require_approvals([{e} for _, e in _approvers(ctx, emp, course)])
    if session["course_id"] != course_id:
        raise ApiError("ERR_NOT_APPLICABLE", f"Session {session_id} belongs to {session['course_id']}, not {course_id}.")
    reasons = _reasons(ctx, emp, course)
    if any(c == "ALREADY_BOOKED" for c, _ in reasons):
        raise ApiError("ERR_DUPLICATE", f"{employee_id} is already booked on {course_id}.")
    if reasons:
        raise ApiError("ERR_NOT_ELIGIBLE", "Not eligible: " + "; ".join(f"{c} ({d})" for c, d in reasons))
    if session["start_date"] < ctx.today:
        raise ApiError("ERR_NOT_APPLICABLE", f"Session {session_id} started on {session['start_date']}.")
    if _seats_left(ctx, session) <= 0:
        raise ApiError("ERR_SESSION_FULL", f"Session {session_id} has no seats left. Choose another session.")
    cur = ctx.conn.execute(
        "INSERT INTO enrolments (employee_id, course_id, session_id, status, requested_by, approved_by, booked_on) "
        "VALUES (?,?,?,?,?,?,?)", (employee_id, course_id, session_id, "booked", actor, approved_by, ctx.today))
    return {"enrolment_id": cur.lastrowid, "employee_id": employee_id, "course_id": course_id,
            "session_id": session_id, "status": "booked", "fee_qar": course["cost_qar"], "approved_by": approved_by}


@api("write")
def cancel_enrolment(ctx, enrolment_id, *, actor, approved_by=None, idempotency_key=None):
    """Cancel a booked enrolment before its session starts. Needs the employee's line manager's approval."""
    row = ctx.one("SELECT * FROM enrolments WHERE enrolment_id=?", (enrolment_id,))
    if row is None:
        raise ApiError("ERR_NOT_FOUND", f"No enrolment {enrolment_id}")
    emp = _visible_employee(ctx, row["employee_id"])
    ctx.require_approval({emp["manager_id"] or _hr_head(ctx)})
    if row["status"] != "booked":
        raise ApiError("ERR_NOT_APPLICABLE", f"Enrolment {enrolment_id} is already {row['status']}.")
    session = ctx.one("SELECT start_date FROM course_sessions WHERE session_id=?", (row["session_id"],))
    if session["start_date"] <= ctx.today:
        raise ApiError("ERR_NOT_APPLICABLE", f"The session started on {session['start_date']}; it can no longer be cancelled.")
    ctx.conn.execute("UPDATE enrolments SET status='cancelled', cancelled_on=? WHERE enrolment_id=?",
                     (ctx.today, enrolment_id))
    return {"enrolment_id": enrolment_id, "status": "cancelled", "approved_by": approved_by}


@api("write")
def save_learning_plan(ctx, employee_id, plan_text, *, actor, idempotency_key=None):
    """Save a DRAFT learning plan (free text) for the employee. Low risk: needs no approval."""
    _visible_employee(ctx, employee_id)
    if not (plan_text or "").strip():
        raise ApiError("ERR_NOT_APPLICABLE", "plan_text is empty.")
    cur = ctx.conn.execute("INSERT INTO learning_plans (employee_id, plan_text, status, created_by, created_on) "
                           "VALUES (?,?,?,?,?)", (employee_id, plan_text.strip(), "draft", actor, ctx.today))
    return {"plan_id": cur.lastrowid, "employee_id": employee_id, "status": "draft"}
