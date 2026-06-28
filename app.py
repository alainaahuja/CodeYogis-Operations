from __future__ import annotations

import html
import os
import sqlite3
from datetime import date
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "program_dashboard.sqlite3"
STATIC_DIR = ROOT_DIR / "app" / "static"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with get_connection() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                parent1_name TEXT NOT NULL,
                parent2_name TEXT NOT NULL 
                email1 TEXT NOT NULL,
                email2 TEXT NOT NULL, 
                phone1 TEXT,
                phone2 TEXT,
                program TEXT NOT NULL,
                status TEXT NOT NULL,
            );

            CREATE TABLE IF NOT EXISTS instructors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT NOT NULL,
                current_classes TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                location TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                meeting_days TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                instructor_id INTEGER,
                status TEXT NOT NULL,
                FOREIGN KEY(instructor_id) REFERENCES instructors(id)
            );
            """
        )
        if db.execute("SELECT COUNT(*) FROM students").fetchone()[0]:
            return

        db.executemany(
            """
            INSERT INTO students
            (student_id, first_name, last_name, email, phone, program, status, start_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("STU-1001", "Avery", "Johnson", "avery.johnson@example.edu", "(555) 010-1101", "Cybersecurity Foundations", "Active", "2026-05-04", "Interested in SOC analyst pathway."),
                ("STU-1002", "Maya", "Patel", "maya.patel@example.edu", "(555) 010-1102", "Data Analytics", "Active", "2026-06-01", "Prefers evening cohorts."),
                ("STU-1003", "Jordan", "Kim", "jordan.kim@example.edu", "(555) 010-1103", "Cloud Administration", "Enrolled", "2026-07-13", "Needs laptop pickup confirmation."),
                ("STU-1004", "Sofia", "Garcia", "sofia.garcia@example.edu", "(555) 010-1104", "Project Management", "Completed", "2026-03-02", "Completed capstone with distinction."),
            ],
        )
        db.executemany(
            """
            INSERT INTO instructors
            (first_name, last_name, email, specialty, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("Elena", "Brooks", "elena.brooks@example.edu", "Cybersecurity", "Active"),
                ("Marcus", "Chen", "marcus.chen@example.edu", "Data Analytics", "Active"),
                ("Priya", "Singh", "priya.singh@example.edu", "Cloud Systems", "Active"),
                ("Daniel", "Rivera", "daniel.rivera@example.edu", "Project Management", "On leave"),
            ],
        )
        db.executemany(
            """
            INSERT INTO schedules
            (title, program, location, start_date, end_date, meeting_days, start_time, end_time, instructor_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("Cybersecurity Foundations - Summer A", "Cybersecurity Foundations", "Room 204", "2026-06-08", "2026-08-14", "Mon/Wed", "18:00", "20:30", 1, "Current"),
                ("Data Analytics - Summer Intensive", "Data Analytics", "Lab 3", "2026-06-15", "2026-07-31", "Tue/Thu", "17:30", "20:30", 2, "Current"),
                ("Cloud Administration - Fall Cohort", "Cloud Administration", "Virtual", "2026-08-24", "2026-11-20", "Mon/Wed/Fri", "09:00", "11:00", 3, "Upcoming"),
                ("Project Management - Fall Evening", "Project Management", "Room 118", "2026-09-01", "2026-10-27", "Tue/Thu", "18:00", "20:00", 4, "Upcoming"),
            ],
        )


def query_all(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with get_connection() as db:
        return list(db.execute(sql, params))


def query_one(sql: str, params: tuple = ()) -> sqlite3.Row:
    with get_connection() as db:
        return db.execute(sql, params).fetchone()


def escape(value: object) -> str:
    return html.escape("" if value is None else str(value))


def status_class(status: str) -> str:
    return status.lower().replace(" ", "-")


def render_layout(title: str, active: str, content: str) -> bytes:
    nav_items = [
        ("/", "Dashboard"),
        ("/students", "Students"),
        ("/schedules", "Schedules"),
        ("/instructors", "Instructors"),
    ]
    nav = "".join(
        f'<a class="nav-link {"active" if active == label else ""}" href="{href}">{label}</a>'
        for href, label in nav_items
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} | Program Dashboard</title>
  <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
  <aside class="sidebar">
    <div class="brand">
      <span class="brand-mark">PD</span>
      <div><strong>Program Desk</strong><span>Training operations</span></div>
    </div>
    <nav>{nav}</nav>
  </aside>
  <main class="content">{content}</main>
</body>
</html>""".encode("utf-8")


def page_header(title: str, subtitle: str) -> str:
    today = date.today()
    try:
        formatted = today.strftime("%B %-d, %Y")
    except ValueError:
        formatted = today.strftime("%B %d, %Y").replace(" 0", " ")
    return f"""
    <header class="page-header">
      <div>
        <p class="eyebrow">Central Dashboard</p>
        <h1>{escape(title)}</h1>
        <p>{escape(subtitle)}</p>
      </div>
      <time datetime="{today.isoformat()}">{formatted}</time>
    </header>
    """


def metric_card(label: str, value: object, detail: str) -> str:
    return f"""
    <article class="metric">
      <span>{escape(label)}</span>
      <strong>{escape(value)}</strong>
      <small>{escape(detail)}</small>
    </article>
    """


def render_dashboard() -> bytes:
    totals = query_one(
        """
        SELECT
          (SELECT COUNT(*) FROM students) AS students,
          (SELECT COUNT(*) FROM schedules WHERE status = 'Current') AS current_schedules,
          (SELECT COUNT(*) FROM schedules WHERE status = 'Upcoming') AS upcoming_schedules,
          (SELECT COUNT(*) FROM instructors WHERE status = 'Active') AS active_instructors
        """
    )
    schedules = query_all(
        """
        SELECT schedules.*, instructors.first_name || ' ' || instructors.last_name AS instructor
        FROM schedules
        LEFT JOIN instructors ON schedules.instructor_id = instructors.id
        ORDER BY start_date ASC
        LIMIT 5
        """
    )
    students = query_all("SELECT * FROM students ORDER BY start_date DESC LIMIT 5")
    schedule_rows = "".join(
        f"""
        <tr>
          <td>{escape(row["title"])}</td>
          <td>{escape(row["start_date"])} - {escape(row["end_date"])}</td>
          <td>{escape(row["meeting_days"])}</td>
          <td>{escape(row["instructor"] or "Unassigned")}</td>
          <td><span class="pill {status_class(row["status"])}">{escape(row["status"])}</span></td>
        </tr>
        """
        for row in schedules
    )
    student_rows = "".join(
        f"""
        <tr>
          <td>{escape(row["first_name"])} {escape(row["last_name"])}</td>
          <td>{escape(row["program"])}</td>
          <td>{escape(row["start_date"])}</td>
          <td><span class="pill {status_class(row["status"])}">{escape(row["status"])}</span></td>
        </tr>
        """
        for row in students
    )
    content = f"""
    {page_header("Program Dashboard", "A single place to view students, schedules, and instructor assignments.")}
    <section class="metrics">
      {metric_card("Students", totals["students"], "Profiles in the database")}
      {metric_card("Current Programs", totals["current_schedules"], "Running right now")}
      {metric_card("Upcoming Programs", totals["upcoming_schedules"], "Scheduled for later")}
      {metric_card("Active Instructors", totals["active_instructors"], "Available to teach")}
    </section>
    <section class="split">
      <article class="panel">
        <div class="panel-heading"><h2>Program Schedule</h2><a href="/schedules">View all</a></div>
        <div class="table-wrap"><table>
          <thead><tr><th>Class</th><th>Dates</th><th>Days</th><th>Instructor</th><th>Status</th></tr></thead>
          <tbody>{schedule_rows}</tbody>
        </table></div>
      </article>
      <article class="panel">
        <div class="panel-heading"><h2>Recent Students</h2><a href="/students">View all</a></div>
        <div class="table-wrap"><table>
          <thead><tr><th>Name</th><th>Program</th><th>Start</th><th>Status</th></tr></thead>
          <tbody>{student_rows}</tbody>
        </table></div>
      </article>
    </section>
    """
    return render_layout("Dashboard", "Dashboard", content)


def render_students() -> bytes:
    rows = query_all("SELECT * FROM students ORDER BY last_name, first_name")
    table_rows = "".join(
        f"""
        <tr>
          <td><strong>{escape(row["first_name"])} {escape(row["last_name"])}</strong><small>{escape(row["student_id"])}</small></td>
          <td>{escape(row["program"])}</td>
          <td>{escape(row["email"])}<small>{escape(row["phone"])}</small></td>
          <td>{escape(row["start_date"])}</td>
          <td><span class="pill {status_class(row["status"])}">{escape(row["status"])}</span></td>
          <td>{escape(row["notes"])}</td>
        </tr>
        """
        for row in rows
    )
    content = f"""
    {page_header("Students", "Student records, program enrollment, contact information, and notes.")}
    <section class="panel">
      <div class="panel-heading"><h2>Student Database</h2><span>{len(rows)} records</span></div>
      <div class="table-wrap"><table>
        <thead><tr><th>Student</th><th>Program</th><th>Contact</th><th>Start Date</th><th>Status</th><th>Notes</th></tr></thead>
        <tbody>{table_rows}</tbody>
      </table></div>
    </section>
    """
    return render_layout("Students", "Students", content)


def render_schedules() -> bytes:
    rows = query_all(
        """
        SELECT schedules.*, instructors.first_name || ' ' || instructors.last_name AS instructor
        FROM schedules
        LEFT JOIN instructors ON schedules.instructor_id = instructors.id
        ORDER BY start_date ASC
        """
    )
    table_rows = "".join(
        f"""
        <tr>
          <td><strong>{escape(row["title"])}</strong><small>{escape(row["program"])}</small></td>
          <td>{escape(row["start_date"])}<small>through {escape(row["end_date"])}</small></td>
          <td>{escape(row["meeting_days"])}<small>{escape(row["start_time"])} - {escape(row["end_time"])}</small></td>
          <td>{escape(row["location"])}</td>
          <td>{escape(row["instructor"] or "Unassigned")}</td>
          <td><span class="pill {status_class(row["status"])}">{escape(row["status"])}</span></td>
        </tr>
        """
        for row in rows
    )
    content = f"""
    {page_header("Schedules", "Current and upcoming program calendars with locations and meeting times.")}
    <section class="panel">
      <div class="panel-heading"><h2>Program Schedule</h2><span>{len(rows)} classes</span></div>
      <div class="table-wrap"><table>
        <thead><tr><th>Class</th><th>Dates</th><th>Meeting Time</th><th>Location</th><th>Instructor</th><th>Status</th></tr></thead>
        <tbody>{table_rows}</tbody>
      </table></div>
    </section>
    """
    return render_layout("Schedules", "Schedules", content)


def render_instructors() -> bytes:
    rows = query_all(
        """
        SELECT
          instructors.*,
          COUNT(schedules.id) AS class_count,
          MIN(CASE WHEN schedules.start_date >= date('now') THEN schedules.start_date END) AS next_class
        FROM instructors
        LEFT JOIN schedules ON schedules.instructor_id = instructors.id
        GROUP BY instructors.id
        ORDER BY instructors.last_name, instructors.first_name
        """
    )
    cards = "".join(
        f"""
        <article class="instructor-card">
          <div>
            <h2>{escape(row["first_name"])} {escape(row["last_name"])}</h2>
            <span class="pill {status_class(row["status"])}">{escape(row["status"])}</span>
          </div>
          <p>{escape(row["specialty"])}</p>
          <dl>
            <div><dt>Email</dt><dd>{escape(row["email"])}</dd></div>
            <div><dt>Classes</dt><dd>{escape(row["class_count"])}</dd></div>
            <div><dt>Next Class</dt><dd>{escape(row["next_class"] or "No future class")}</dd></div>
          </dl>
        </article>
        """
        for row in rows
    )
    content = f"""
    {page_header("Instructors", "Instructor roster with teaching assignments and future availability.")}
    <section class="instructor-grid">{cards}</section>
    """
    return render_layout("Instructors", "Instructors", content)


def render_not_found() -> bytes:
    content = f"""
    {page_header("Page not found", "The page you requested does not exist in this starter dashboard.")}
    <section class="panel"><div class="panel-heading"><a href="/">Return to dashboard</a></div></section>
    """
    return render_layout("Not Found", "Dashboard", content)


class ProgramDashboardHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def do_HEAD(self) -> None:
        self.handle_request(send_body=False)

    def do_GET(self) -> None:
        self.handle_request(send_body=True)

    def handle_request(self, send_body: bool) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path.startswith("/static/"):
            self.serve_static(path, send_body)
            return

        routes = {
            "/": render_dashboard,
            "/students": render_students,
            "/schedules": render_schedules,
            "/instructors": render_instructors,
        }
        renderer = routes.get(path)
        if renderer is None:
            self.send_html(render_not_found(), HTTPStatus.NOT_FOUND, send_body)
            return
        self.send_html(renderer(), send_body=send_body)

    def serve_static(self, path: str, send_body: bool) -> None:
        target = STATIC_DIR / path.replace("/static/", "", 1)
        if not target.exists() or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = "text/css" if target.suffix == ".css" else "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(target.stat().st_size))
        self.end_headers()
        if send_body:
            with target.open("rb") as file:
                self.wfile.write(file.read())

    def send_html(
        self,
        body: bytes,
        status: HTTPStatus = HTTPStatus.OK,
        send_body: bool = True,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if send_body:
            self.wfile.write(body)


def main() -> None:
    initialize_database()
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("127.0.0.1", port), ProgramDashboardHandler)
    print(f"Program dashboard running at http://127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
