import os
import csv
import io
import time
import json
from datetime import date, datetime, timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, jsonify, session,
    send_file, redirect, url_for, flash
)
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()

from models import db, User, Resume, Job, Application, PasswordResetToken
from resume_parser import parse_resume
from job_fetcher import search_all
from cover_letter import generate_cover_letter
from email_sender import send_application_email, is_email_configured, send_password_reset_email

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.environ.get("SESSION_SECRET", "dev-secret-key"))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///jobapp.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")

CORS(app)
db.init_app(app)


ALLOWED_EXTENSIONS = {"pdf", "docx", "doc"}
DAILY_GOAL = 50

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def run_migrations():
    """Safely add new columns to existing tables without losing data."""
    with db.engine.connect() as conn:
        for sql in [
            "ALTER TABLE resumes ADD COLUMN user_id INTEGER",
            "ALTER TABLE applications ADD COLUMN user_id INTEGER",
        ]:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # Column already exists — safe to ignore


with app.app_context():
    db.create_all()
    run_migrations()


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def current_user():
    if "user_id" not in session:
        return None
    return User.query.get(session["user_id"])


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


def api_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Please log in to continue"}), 401
        return f(*args, **kwargs)
    return decorated


# ─── Auth routes ──────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET"])
def login_page():
    if "user_id" in session:
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login_post():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        flash("Invalid email or password.", "error")
        return redirect(url_for("login_page"))
    session.clear()
    session["user_id"] = user.id
    session["user_email"] = user.email
    session["user_name"] = user.name or user.email.split("@")[0]
    return redirect(url_for("index"))


@app.route("/register", methods=["POST"])
def register_post():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    if not email or not password:
        flash("Email and password are required.", "error")
        return redirect(url_for("login_page") + "?tab=register")
    if len(password) < 6:
        flash("Password must be at least 6 characters.", "error")
        return redirect(url_for("login_page") + "?tab=register")
    if User.query.filter_by(email=email).first():
        flash("An account with that email already exists.", "error")
        return redirect(url_for("login_page") + "?tab=register")
    user = User(email=email, name=name)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    session.clear()
    session["user_id"] = user.id
    session["user_email"] = user.email
    session["user_name"] = name or email.split("@")[0]
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("forgot_password.html")

    email = request.form.get("email", "").strip().lower()
    if not email:
        flash("Please enter your email address.", "error")
        return render_template("forgot_password.html")

    user = User.query.filter_by(email=email).first()

    if user:
        # Invalidate any existing tokens for this user
        PasswordResetToken.query.filter_by(user_id=user.id, used=False).update({"used": True})
        db.session.commit()

        import secrets as _secrets
        token_str = _secrets.token_urlsafe(32)
        expiry = datetime.utcnow() + timedelta(hours=1)
        prt = PasswordResetToken(user_id=user.id, token=token_str, expires_at=expiry)
        db.session.add(prt)
        db.session.commit()

        reset_url = url_for("reset_password", token=token_str, _external=True)
        result = send_password_reset_email(email, reset_url, user.name or "")

        if result.get("error") == "smtp_not_configured":
            # No SMTP — show the link directly so the developer/owner can still reset
            return render_template("forgot_password.html", reset_link=reset_url)

    # Always show the same confirmation regardless of whether email was found (security)
    return render_template("forgot_password.html", sent=True)


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    prt = PasswordResetToken.query.filter_by(token=token, used=False).first()
    if not prt or prt.expires_at < datetime.utcnow():
        return render_template("reset_password.html", invalid=True)

    if request.method == "GET":
        return render_template("reset_password.html", token=token)

    password = request.form.get("password", "")
    confirm = request.form.get("confirm_password", "")

    if len(password) < 6:
        flash("Password must be at least 6 characters.", "error")
        return render_template("reset_password.html", token=token)
    if password != confirm:
        flash("Passwords don't match.", "error")
        return render_template("reset_password.html", token=token)

    user = User.query.get(prt.user_id)
    user.set_password(password)
    prt.used = True
    db.session.commit()

    return render_template("reset_password.html", success=True)


# ─── Page routes ──────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    user = current_user()
    resume = None
    if "resume_id" in session:
        resume = Resume.query.filter_by(id=session["resume_id"], user_id=user.id).first()
    return render_template("index.html", resume=resume, daily_goal=DAILY_GOAL, user=user)


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    uid = user.id
    today = date.today()

    today_count = Application.query.filter_by(user_id=uid).filter(
        Application.date_applied == today
    ).count()
    total = Application.query.filter_by(user_id=uid).count()
    statuses = db.session.query(
        Application.status, db.func.count(Application.id)
    ).filter_by(user_id=uid).group_by(Application.status).all()
    status_map = {s: c for s, c in statuses}

    applications = Application.query.filter_by(user_id=uid).order_by(
        Application.date_applied.desc(), Application.created_at.desc()
    ).all()

    interviews = status_map.get("Interview", 0)
    response_rate = round((interviews / total * 100), 1) if total > 0 else 0

    return render_template(
        "dashboard.html",
        applications=applications,
        today_count=today_count,
        total=total,
        daily_goal=DAILY_GOAL,
        response_rate=response_rate,
        status_map=status_map,
        user=user,
    )


# ─── API routes ───────────────────────────────────────────────────────────────

@app.route("/api/upload-resume", methods=["POST"])
@api_login_required
def upload_resume():
    if "resume" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["resume"]
    if not file or not file.filename:
        return jsonify({"error": "No file selected"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Please upload a PDF or DOCX file."}), 400

    filename = secure_filename(file.filename)
    if not filename:
        return jsonify({"error": "Invalid filename"}), 400

    # Make filename unique per user to avoid collisions
    uid = session["user_id"]
    filename = f"user{uid}_{filename}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    try:
        file.save(filepath)
    except Exception as e:
        return jsonify({"error": f"Failed to save file: {e}"}), 500

    try:
        parsed = parse_resume(filepath)
    except Exception as e:
        return jsonify({"error": f"Failed to parse resume: {e}"}), 500

    # Check if text extraction actually worked
    raw = parsed.get("raw_text", "")
    if raw.startswith("Error parsing"):
        return jsonify({"error": raw}), 500

    resume = Resume(
        user_id=uid,
        filename=file.filename,
        name=parsed.get("name", ""),
        email=parsed.get("email", ""),
        phone=parsed.get("phone", ""),
        skills=",".join(parsed.get("skills", [])),
        experience=parsed.get("experience", ""),
        education=parsed.get("education", ""),
        job_titles=",".join(parsed.get("job_titles", [])),
        raw_text=raw,
    )
    db.session.add(resume)
    db.session.commit()
    session["resume_id"] = resume.id
    session["resume_filepath"] = filepath

    return jsonify({"success": True, "resume": resume.to_dict()})


@app.route("/api/search-jobs", methods=["POST"])
@api_login_required
def api_search_jobs():
    data = request.get_json() or {}
    query = data.get("query", "software engineer")
    location = data.get("location", "")
    remote = data.get("remote", False)
    salary_min = data.get("salary_min") or None

    resume_skills = []
    resume_titles = []
    uid = session["user_id"]
    if "resume_id" in session:
        resume = Resume.query.filter_by(id=session["resume_id"], user_id=uid).first()
        if resume:
            resume_skills = resume.skills.split(",") if resume.skills else []
            resume_titles = resume.job_titles.split(",") if resume.job_titles else []

    jobs = search_all(
        query=query,
        location=location,
        remote=remote,
        salary_min=salary_min,
        resume_skills=resume_skills,
        resume_titles=resume_titles,
    )

    saved = []
    for job_data in jobs:
        existing = Job.query.filter_by(external_id=job_data["external_id"]).first()
        if not existing:
            job = Job(**{k: v for k, v in job_data.items()})
            db.session.add(job)
            db.session.flush()
            saved.append(job.to_dict())
        else:
            existing.match_score = job_data["match_score"]
            saved.append(existing.to_dict())
    db.session.commit()

    return jsonify({"jobs": saved, "count": len(saved)})


@app.route("/api/generate-cover-letter", methods=["POST"])
@api_login_required
def api_generate_cover_letter():
    data = request.get_json() or {}
    job_id = data.get("job_id")
    job_data = data.get("job")

    resume_data = {}
    uid = session["user_id"]
    if "resume_id" in session:
        resume = Resume.query.filter_by(id=session["resume_id"], user_id=uid).first()
        if resume:
            resume_data = resume.to_dict()
            resume_data["raw_text"] = resume.raw_text
            resume_data["experience"] = resume.experience

    if job_id:
        job_obj = Job.query.get(job_id)
        if job_obj:
            job_data = job_obj.to_dict()
            job_data["description"] = job_obj.description

    if not job_data:
        return jsonify({"error": "Job data required"}), 400

    cover = generate_cover_letter(resume_data, job_data)
    return jsonify({"cover_letter": cover})


@app.route("/api/apply", methods=["POST"])
@api_login_required
def api_apply():
    data = request.get_json() or {}
    jobs = data.get("jobs", [])
    if not jobs:
        return jsonify({"error": "No jobs provided"}), 400

    uid = session["user_id"]
    results = []
    for job in jobs[:50]:
        existing = Application.query.filter_by(
            user_id=uid,
            company=job.get("company", ""),
            role=job.get("title", ""),
            date_applied=date.today(),
        ).first()
        if existing:
            results.append({
                "job": job.get("title"),
                "company": job.get("company"),
                "status": "skipped",
                "reason": "Already applied today",
            })
            continue

        app_record = Application(
            user_id=uid,
            company=job.get("company", ""),
            role=job.get("title", ""),
            date_applied=date.today(),
            status="Applied",
            source=job.get("source", ""),
            job_url=job.get("url", ""),
            cover_letter=job.get("cover_letter", ""),
        )
        db.session.add(app_record)
        results.append({
            "job": job.get("title"),
            "company": job.get("company"),
            "status": "applied",
            "url": job.get("url", ""),
        })

    db.session.commit()

    today_count = Application.query.filter_by(user_id=uid).filter(
        Application.date_applied == date.today()
    ).count()

    return jsonify({
        "results": results,
        "applied_count": sum(1 for r in results if r["status"] == "applied"),
        "today_total": today_count,
    })


@app.route("/api/applications", methods=["GET"])
@api_login_required
def api_applications():
    uid = session["user_id"]
    applications = Application.query.filter_by(user_id=uid).order_by(
        Application.date_applied.desc(), Application.created_at.desc()
    ).all()
    today_count = Application.query.filter_by(user_id=uid).filter(
        Application.date_applied == date.today()
    ).count()
    return jsonify({
        "applications": [a.to_dict() for a in applications],
        "today_count": today_count,
        "total": len(applications),
    })


@app.route("/api/applications/<int:app_id>", methods=["PATCH"])
@api_login_required
def api_update_application(app_id):
    uid = session["user_id"]
    app_record = Application.query.filter_by(id=app_id, user_id=uid).first_or_404()
    data = request.get_json() or {}
    allowed = ["status", "notes", "cover_letter"]
    for field in allowed:
        if field in data:
            setattr(app_record, field, data[field])
    db.session.commit()
    return jsonify({"success": True, "application": app_record.to_dict()})


@app.route("/api/applications/<int:app_id>", methods=["DELETE"])
@api_login_required
def api_delete_application(app_id):
    uid = session["user_id"]
    app_record = Application.query.filter_by(id=app_id, user_id=uid).first_or_404()
    db.session.delete(app_record)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/export-csv")
@login_required
def export_csv():
    uid = session["user_id"]
    applications = Application.query.filter_by(user_id=uid).order_by(
        Application.date_applied.desc()
    ).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Company", "Role", "Date Applied", "Status", "Source", "URL", "Notes"])
    for a in applications:
        writer.writerow([
            a.company, a.role,
            a.date_applied.isoformat() if a.date_applied else "",
            a.status, a.source, a.job_url, a.notes or "",
        ])
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"applications_{date.today()}.csv",
    )


@app.route("/api/stats")
@api_login_required
def api_stats():
    uid = session["user_id"]
    today = date.today()
    today_count = Application.query.filter_by(user_id=uid).filter(
        Application.date_applied == today
    ).count()
    total = Application.query.filter_by(user_id=uid).count()
    statuses = db.session.query(
        Application.status, db.func.count(Application.id)
    ).filter_by(user_id=uid).group_by(Application.status).all()
    status_map = {s: c for s, c in statuses}
    interviews = status_map.get("Interview", 0)
    response_rate = round((interviews / total * 100), 1) if total > 0 else 0
    return jsonify({
        "today_count": today_count,
        "total": total,
        "daily_goal": DAILY_GOAL,
        "response_rate": response_rate,
        "status_breakdown": status_map,
    })


@app.route("/api/send-email", methods=["POST"])
@api_login_required
def api_send_email():
    data = request.get_json() or {}
    to_email = data.get("to_email", "").strip()
    job_id = data.get("job_id")
    cover_letter_text = data.get("cover_letter", "")
    job_title = data.get("job_title", "")
    company = data.get("company", "")

    if not to_email:
        return jsonify({"success": False, "error": "Recipient email is required"}), 400

    uid = session["user_id"]
    resume_data = {}
    resume_path = None
    if "resume_id" in session:
        resume = Resume.query.filter_by(id=session["resume_id"], user_id=uid).first()
        if resume:
            resume_data = resume.to_dict()
            resume_data["experience"] = resume.experience
            fp = session.get("resume_filepath", "")
            if fp and os.path.exists(fp):
                resume_path = fp

    if not cover_letter_text and job_id:
        job_obj = Job.query.get(job_id)
        if job_obj:
            jd = job_obj.to_dict()
            jd["description"] = job_obj.description
            cover_letter_text = generate_cover_letter(resume_data, jd)

    result = send_application_email(
        to_email=to_email,
        applicant_name=resume_data.get("name", "Applicant"),
        applicant_email=resume_data.get("email", ""),
        job_title=job_title,
        company=company,
        cover_letter=cover_letter_text,
        resume_path=resume_path,
    )

    if result["success"]:
        app_record = Application(
            user_id=uid,
            company=company,
            role=job_title,
            date_applied=date.today(),
            status="Applied",
            source="Email",
            cover_letter=cover_letter_text,
        )
        db.session.add(app_record)
        db.session.commit()
        today_count = Application.query.filter_by(user_id=uid).filter(
            Application.date_applied == date.today()
        ).count()
        result["today_total"] = today_count

    return jsonify(result)


@app.route("/api/email-status")
@api_login_required
def api_email_status():
    return jsonify({"configured": is_email_configured()})


@app.route("/api/resume/current")
@api_login_required
def api_current_resume():
    uid = session["user_id"]
    if "resume_id" not in session:
        return jsonify({"resume": None})
    resume = Resume.query.filter_by(id=session["resume_id"], user_id=uid).first()
    if not resume:
        return jsonify({"resume": None})
    return jsonify({"resume": resume.to_dict()})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
