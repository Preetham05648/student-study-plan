from flask import Flask, render_template, request, render_template_string
from model import recommend_priority
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from dotenv import load_dotenv
from datetime import date, timedelta
import os
import certifi


# --------------------------------
# 1. APPLICATION CONFIGURATION
# --------------------------------

load_dotenv()

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

mongo_uri = os.getenv("MONGO_URI")

client = None
students = None

if mongo_uri:
    client = MongoClient(
        mongo_uri,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=5000
    )

    db = client["student_study_planner"]
    students = db["students"]


# --------------------------------
# 2. STUDY TIMING SETTINGS
# --------------------------------

START_TIME = "09:00"
END_TIME = "21:00"

SESSION_MINUTES = 60
BREAK_MINUTES = 15


def time_to_minutes(time_string):

    hours, minutes = map(
        int,
        time_string.split(":")
    )

    return hours * 60 + minutes


def format_time(total_minutes):

    hours = total_minutes // 60
    minutes = total_minutes % 60

    period = "AM" if hours < 12 else "PM"

    display_hour = hours % 12

    if display_hour == 0:
        display_hour = 12

    return f"{display_hour:02d}:{minutes:02d} {period}"


# --------------------------------
# 3. CREATE DAILY STUDY SESSIONS
# --------------------------------

def create_time_slots(number_of_sessions):

    start_minutes = time_to_minutes(START_TIME)
    end_minutes = time_to_minutes(END_TIME)

    slots = []

    current_time = start_minutes

    for i in range(number_of_sessions):

        session_end = current_time + SESSION_MINUTES

        if session_end > end_minutes:
            break

        slots.append({
            "time": (
                f"{format_time(current_time)} - "
                f"{format_time(session_end)}"
            ),
            "duration": f"{SESSION_MINUTES} minutes",
            "break_after": (
                f"{BREAK_MINUTES} minutes"
                if i < number_of_sessions - 1
                else "No break needed"
            )
        })

        current_time = session_end + BREAK_MINUTES

    return slots


# --------------------------------
# 4. AUTOMATIC STUDY TIMETABLE
# --------------------------------

def create_daily_schedule(subject, hours, exam_date):

    today = date.today()

    total_days = (exam_date - today).days

    study_plan = []

    time_slots = create_time_slots(hours)

    for day_number in range(total_days + 1):

        current_date = today + timedelta(
            days=day_number
        )

        days_remaining = (
            exam_date - current_date
        ).days

        daily_tasks = []

        # Final exam day
        if days_remaining == 0:

            phase = "Final Revision"

            tasks = [
                f"Revise important {subject} concepts",
                f"Practice important {subject} questions",
                f"Review notes and difficult topics"
            ]

        # Revision phase
        elif days_remaining <= max(
            1, total_days // 4
        ):

            phase = "Revision and Practice"

            tasks = [
                f"Revise previously studied {subject} topics",
                f"Solve important {subject} questions",
                f"Practice a timed {subject} test",
                "Review mistakes and prepare short notes"
            ]

        # Learning phase
        else:

            phase = "Learning and Practice"

            tasks = [
                f"Learn new {subject} concepts",
                f"Understand examples in {subject}",
                f"Practice {subject} exercises",
                f"Prepare short revision notes for {subject}"
            ]

        for i, slot in enumerate(time_slots):

            task = tasks[i % len(tasks)]

            daily_tasks.append({
                "time": slot["time"],
                "task": task,
                "duration": slot["duration"],
                "break_after": slot["break_after"]
            })

        study_plan.append({

            "date": current_date.isoformat(),

            "phase": phase,

            "days_remaining": days_remaining,

            "tasks": daily_tasks

        })

    return study_plan


# --------------------------------
# 5. HOME PAGE
# --------------------------------

@app.route("/")
def home():

    return render_template("index.html")


# --------------------------------
# 6. GENERATE STUDY PLAN
# --------------------------------

@app.route("/generate", methods=["POST"])
def generate():

    name = request.form.get("name", "").strip()

    subject = request.form.get("subject", "").strip()

    hours_text = request.form.get("hours", "").strip()

    exam_date_text = request.form.get("exam_date", "")

    difficulty_text = request.form.get("difficulty", "")

    preparation_text = request.form.get("preparation", "")

    # Validate form fields
    if not all([
        name,
        subject,
        hours_text,
        exam_date_text,
        difficulty_text,
        preparation_text
    ]):

        return "Please fill in all fields. <a href='/'>Go Back</a>", 400

    try:

        hours = int(hours_text)

        difficulty = int(difficulty_text)

        preparation = int(preparation_text)

        exam_date = date.fromisoformat(
            exam_date_text
        )

        if not 1 <= hours <= 9:
            raise ValueError

        if difficulty not in [3, 6, 9]:
            raise ValueError

        if preparation not in [2, 5, 8]:
            raise ValueError

        if exam_date < date.today():
            raise ValueError

        if (exam_date - date.today()).days > 365:
            raise ValueError

    except ValueError:

        return """
        <h2>Invalid Details!</h2>
        <p>Please check your study hours, difficulty, preparation level and exam date.</p>
        <a href="/">Go Back</a>
        """, 400

    # --------------------------------
    # 7. RANDOM FOREST RECOMMENDATION
    # --------------------------------

    days_left = (
        exam_date - date.today()
    ).days

    priority = recommend_priority(
        difficulty,
        preparation,
        days_left,
        hours
    )

    # --------------------------------
    # 8. GENERATE TIMETABLE
    # --------------------------------

    study_plan = create_daily_schedule(
        subject,
        hours,
        exam_date
    )

    # --------------------------------
    # 9. SAVE DATA IN MONGODB
    # --------------------------------

    student_data = {

        "name": name,

        "subject": subject,

        "study_hours": hours,

        "start_time": START_TIME,

        "end_time": END_TIME,

        "session_minutes": SESSION_MINUTES,

        "break_minutes": BREAK_MINUTES,

        "exam_date": exam_date.isoformat(),

        "difficulty": difficulty,

        "preparation": preparation,

        "days_left": days_left,

        "priority": priority,

        "study_plan": study_plan

    }

    database_status = "Not saved"

    try:

        if students is None:
            raise RuntimeError("MONGO_URI is missing from .env")

        client.admin.command("ping")

        students.insert_one(student_data)

        database_status = "Saved successfully in MongoDB"

    except (PyMongoError, RuntimeError) as error:

        app.logger.error("Database error: %s", error)

        database_status = "Database saving failed"

    # --------------------------------
    # 10. DISPLAY STUDY PLAN
    # --------------------------------

    return render_template_string("""

    <!DOCTYPE html>

    <html>

    <head>

        <title>Your Study Plan</title>

        <meta name="viewport"
              content="width=device-width, initial-scale=1">

        <style>

            body {
                font-family: Arial, sans-serif;
                background: #f2f5fa;
                padding: 20px;
                margin: 0;
            }

            .container {
                max-width: 900px;
                margin: auto;
                background: white;
                padding: 25px;
                border-radius: 15px;
            }

            .timing {
                background: #e9f8ee;
                padding: 15px;
                border-radius: 10px;
                margin: 20px 0;
            }

            .day {
                background: #eaf3ff;
                padding: 15px;
                margin: 15px 0;
                border-radius: 10px;
            }

            .session {
                background: white;
                padding: 12px;
                margin: 10px 0;
                border-radius: 8px;
            }

            .break {
                color: #16803c;
                font-size: 14px;
                margin-top: 8px;
            }

            li {
                margin: 10px 0;
            }

            a {
                display: inline-block;
                background: #2563eb;
                color: white;
                padding: 12px 18px;
                border-radius: 8px;
                text-decoration: none;
            }

        </style>

    </head>

    <body>

    <div class="container">

        <h1>Welcome, {{ name }}!</h1>

        <h2>Your Automatic Study Plan</h2>

        <p><b>Subject:</b> {{ subject }}</p>

        <p><b>Daily Study Sessions:</b> {{ hours }}</p>

        <p><b>Exam Date:</b> {{ exam_date }}</p>

        <p><b>Days Remaining:</b> {{ days_left }}</p>

        <div class="timing">

            <h3>Your Daily Study Timing</h3>

            <p><b>Start:</b> 09:00 AM</p>

            <p><b>End:</b> 09:00 PM</p>

            <p><b>Study Session:</b> 60 minutes</p>

            <p><b>Break:</b> 15 minutes</p>

        </div>

        <h2>AI Recommended Priority: {{ priority }}</h2>

        <h2>Your Daily Timetable</h2>

        {% for day in study_plan %}

            <div class="day">

                <h3>
                    Day {{ loop.index }} — {{ day.date }}
                </h3>

                <p><b>Phase:</b> {{ day.phase }}</p>

                <p>
                    <b>Days until exam:</b>
                    {{ day.days_remaining }}
                </p>

                {% for task in day.tasks %}

                    <div class="session">

                        <h4>{{ task.time }}</h4>

                        <p>{{ task.task }}</p>

                        <p>
                            <b>Duration:</b>
                            {{ task.duration }}
                        </p>

                        <p class="break">
                            Break: {{ task.break_after }}
                        </p>

                    </div>

                {% endfor %}

            </div>

        {% endfor %}

        <h3>Database Status: {{ database_status }}</h3>

        <a href="/">Create Another Study Plan</a>

    </div>

    </body>

    </html>

    """,

        name=name,
        subject=subject,
        hours=hours,
        exam_date=exam_date.isoformat(),
        days_left=days_left,
        priority=priority,
        study_plan=study_plan,
        database_status=database_status

    )


# --------------------------------
# 11. RUN APPLICATION
# --------------------------------

if __name__ == "__main__":

    app.run(debug=True)