import sqlite3

DB_NAME = "accident_reports.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_number TEXT,
            report_type TEXT,
            location TEXT,
            severity TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def save_report(user_number, report_type, location, severity):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO reports (user_number, report_type, location, severity)
        VALUES (?, ?, ?, ?)
    """, (user_number, report_type, location, severity))

    conn.commit()
    conn.close()


def get_latest_incident_location(user_number):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT location FROM reports
        WHERE user_number=?
        ORDER BY timestamp DESC
        LIMIT 1
    """, (user_number,))

    result = cursor.fetchone()
    conn.close()

    return result[0] if result else None


def get_latest_report_by_location(location):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT location, timestamp FROM reports
        WHERE location LIKE ?
        ORDER BY timestamp DESC
        LIMIT 1
    """, (f"%{location}%",))

    result = cursor.fetchone()
    conn.close()

    return result
