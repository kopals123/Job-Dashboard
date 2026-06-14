from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

db = SQLAlchemy()


class Resume(db.Model):
    __tablename__ = "resumes"
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255))
    name = db.Column(db.String(255))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(100))
    skills = db.Column(db.Text)
    experience = db.Column(db.Text)
    education = db.Column(db.Text)
    job_titles = db.Column(db.Text)
    raw_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "skills": self.skills.split(",") if self.skills else [],
            "experience": self.experience,
            "education": self.education,
            "job_titles": self.job_titles.split(",") if self.job_titles else [],
        }


class Job(db.Model):
    __tablename__ = "jobs"
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(255), unique=True)
    title = db.Column(db.String(255))
    company = db.Column(db.String(255))
    location = db.Column(db.String(255))
    description = db.Column(db.Text)
    url = db.Column(db.String(1024))
    source = db.Column(db.String(100))
    salary_min = db.Column(db.Integer)
    salary_max = db.Column(db.Integer)
    remote = db.Column(db.Boolean, default=False)
    date_found = db.Column(db.DateTime, default=datetime.utcnow)
    match_score = db.Column(db.Float, default=0.0)
    email_apply = db.Column(db.String(255))

    def to_dict(self):
        return {
            "id": self.id,
            "external_id": self.external_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "description": self.description[:500] if self.description else "",
            "full_description": self.description,
            "url": self.url,
            "source": self.source,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "remote": self.remote,
            "date_found": self.date_found.isoformat() if self.date_found else None,
            "match_score": round(self.match_score, 1),
            "email_apply": self.email_apply,
        }


class Application(db.Model):
    __tablename__ = "applications"
    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(255))
    role = db.Column(db.String(255))
    date_applied = db.Column(db.Date, default=date.today)
    status = db.Column(db.String(50), default="Applied")
    source = db.Column(db.String(100))
    job_url = db.Column(db.String(1024))
    cover_letter = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "company": self.company,
            "role": self.role,
            "date_applied": self.date_applied.isoformat() if self.date_applied else None,
            "status": self.status,
            "source": self.source,
            "job_url": self.job_url,
            "cover_letter": self.cover_letter,
            "notes": self.notes,
        }
