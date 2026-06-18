import os
import re
import hashlib
import requests
from datetime import datetime

ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs"
ARBEITNOW_BASE = "https://arbeitnow.com/api/job-board-api"
REMOTEOK_BASE = "https://remoteok.com/api"


def _make_id(source: str, title: str, company: str) -> str:
    raw = f"{source}:{title}:{company}".lower()
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _extract_email_from_text(text: str) -> str:
    if not text:
        return ""
    match = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
    return match.group(0) if match else ""


def search_adzuna(
    query: str,
    location: str = "",
    remote: bool = False,
    page: int = 1,
    results_per_page: int = 20,
    salary_min: int = None,
    country: str = "us",
) -> list:
    app_id = os.environ.get("ADZUNA_APP_ID", "")
    app_key = os.environ.get("ADZUNA_APP_KEY", "")
    if not app_id or not app_key:
        return []

    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": results_per_page,
        "what": query,
        "content-type": "application/json",
        "page": page,
    }
    if location:
        params["where"] = location
    if salary_min:
        params["salary_min"] = salary_min
    if remote:
        params["what"] = f"{query} remote"

    try:
        url = f"{ADZUNA_BASE}/{country}/search/{page}"
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        jobs = []
        for item in data.get("results", []):
            desc = item.get("description", "")
            jobs.append({
                "external_id": _make_id("adzuna", item.get("title", ""), item.get("company", {}).get("display_name", "")),
                "title": item.get("title", ""),
                "company": item.get("company", {}).get("display_name", ""),
                "location": item.get("location", {}).get("display_name", ""),
                "description": desc,
                "url": item.get("redirect_url", ""),
                "source": "Adzuna",
                "salary_min": int(item.get("salary_min", 0) or 0),
                "salary_max": int(item.get("salary_max", 0) or 0),
                "remote": remote or "remote" in desc.lower(),
                "email_apply": _extract_email_from_text(desc),
            })
        return jobs
    except Exception as e:
        print(f"Adzuna error: {e}")
        return []


def search_arbeitnow(query: str, remote: bool = False) -> list:
    try:
        resp = requests.get(ARBEITNOW_BASE, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        jobs = []
        query_lower = query.lower()
        for item in data.get("data", []):
            title = item.get("title", "")
            tags = " ".join(item.get("tags", []))
            desc = item.get("description", "")
            full_text = f"{title} {tags} {desc}".lower()
            if query_lower not in full_text and not any(
                w in full_text for w in query_lower.split()
            ):
                continue
            if remote and not item.get("remote", False):
                continue
            jobs.append({
                "external_id": _make_id("arbeitnow", title, item.get("company_name", "")),
                "title": title,
                "company": item.get("company_name", ""),
                "location": item.get("location", "Remote"),
                "description": desc,
                "url": item.get("url", ""),
                "source": "Arbeitnow",
                "salary_min": 0,
                "salary_max": 0,
                "remote": item.get("remote", False),
                "email_apply": _extract_email_from_text(desc),
            })
            if len(jobs) >= 25:
                break
        return jobs
    except Exception as e:
        print(f"Arbeitnow error: {e}")
        return []


def search_remoteok(query: str) -> list:
    try:
        headers = {"User-Agent": "JobBot/1.0"}
        resp = requests.get(REMOTEOK_BASE, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        jobs = []
        query_lower = query.lower()
        for item in data:
            if not isinstance(item, dict):
                continue
            position = item.get("position", "")
            tags = " ".join(item.get("tags", []))
            desc = item.get("description", "")
            full_text = f"{position} {tags} {desc}".lower()
            if not any(w in full_text for w in query_lower.split()):
                continue
            company = item.get("company", "")
            jobs.append({
                "external_id": _make_id("remoteok", position, company),
                "title": position,
                "company": company,
                "location": "Remote",
                "description": desc,
                "url": item.get("url", ""),
                "source": "RemoteOK",
                "salary_min": int(item.get("salary_min", 0) or 0),
                "salary_max": int(item.get("salary_max", 0) or 0),
                "remote": True,
                "email_apply": _extract_email_from_text(desc),
            })
            if len(jobs) >= 25:
                break
        return jobs
    except Exception as e:
        print(f"RemoteOK error: {e}")
        return []


def calculate_match_score(job: dict, resume_skills: list, resume_titles: list) -> float:
    if not resume_skills and not resume_titles:
        return 50.0
    text = f"{job.get('title','')} {job.get('description','')}".lower()
    score = 0.0
    matched_skills = sum(1 for s in resume_skills if s.lower() in text)
    if resume_skills:
        score += (matched_skills / len(resume_skills)) * 60
    title_match = any(t.lower() in text for t in resume_titles)
    if title_match:
        score += 30
    if job.get("remote"):
        score += 10
    return min(round(score, 1), 99.0)


def deduplicate(jobs: list) -> list:
    seen = set()
    unique = []
    for job in jobs:
        key = job.get("external_id") or _make_id(
            job.get("source", ""), job.get("title", ""), job.get("company", "")
        )
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique


def search_all(
    query: str,
    location: str = "",
    remote: bool = False,
    salary_min: int = None,
    resume_skills: list = None,
    resume_titles: list = None,
) -> list:
    resume_skills = resume_skills or []
    resume_titles = resume_titles or []
    all_jobs = []

    adzuna = search_adzuna(query, location, remote, salary_min=salary_min)
    all_jobs.extend(adzuna)

    arbeitnow = search_arbeitnow(query, remote)
    all_jobs.extend(arbeitnow)

    if remote or not location:
        remoteok = search_remoteok(query)
        all_jobs.extend(remoteok)

    unique = deduplicate(all_jobs)
    for job in unique:
        job["match_score"] = calculate_match_score(job, resume_skills, resume_titles)

    unique.sort(key=lambda j: j["match_score"], reverse=True)
    return unique
