import re
import os

SKILL_KEYWORDS = [
    "python", "javascript", "typescript", "java", "c++", "c#", "go", "rust", "swift", "kotlin",
    "react", "vue", "angular", "node", "django", "flask", "fastapi", "spring", "rails",
    "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ci/cd",
    "machine learning", "deep learning", "nlp", "tensorflow", "pytorch", "scikit-learn",
    "rest api", "graphql", "microservices", "agile", "scrum", "git",
    "html", "css", "tailwind", "sass", "webpack", "vite",
    "data analysis", "tableau", "power bi", "excel", "spark", "hadoop",
    "linux", "bash", "powershell", "devops", "sre", "security",
    "product management", "project management", "leadership", "communication",
]

JOB_TITLE_PATTERNS = [
    r"(?:senior|sr\.?|junior|jr\.?|lead|principal|staff|chief|head of)?\s*"
    r"(?:software|frontend|backend|full[ -]?stack|web|mobile|ios|android|data|ml|ai|devops|cloud|security|platform|infrastructure|site reliability|qa|test)?\s*"
    r"(?:engineer|developer|architect|scientist|analyst|manager|director|designer|specialist|consultant|lead)",
]


def parse_pdf(file_path: str) -> str:
    try:
        import fitz
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        return f"Error parsing PDF: {e}"


def parse_docx(file_path: str) -> str:
    try:
        from docx import Document
        doc = Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception as e:
        return f"Error parsing DOCX: {e}"


def extract_email(text: str) -> str:
    match = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
    return match.group(0) if match else ""


def extract_phone(text: str) -> str:
    match = re.search(
        r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text
    )
    return match.group(0).strip() if match else ""


def extract_name(text: str) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines[:5]:
        if (
            len(line.split()) in (2, 3)
            and not re.search(r"[@\d|/\\]", line)
            and line[0].isupper()
        ):
            return line
    return lines[0] if lines else ""


def extract_skills(text: str) -> list:
    text_lower = text.lower()
    found = []
    for skill in SKILL_KEYWORDS:
        if re.search(r"\b" + re.escape(skill) + r"\b", text_lower):
            found.append(skill)
    return found


def extract_job_titles(text: str) -> list:
    text_lower = text.lower()
    titles = set()
    for pattern in JOB_TITLE_PATTERNS:
        for match in re.finditer(pattern, text_lower):
            t = match.group(0).strip()
            if len(t) > 4:
                titles.add(t.title())
    return list(titles)[:8]


def extract_section(text: str, headers: list) -> str:
    lines = text.splitlines()
    capturing = False
    section_lines = []
    stop_headers = [
        "education", "experience", "skills", "summary", "objective",
        "certifications", "projects", "awards", "references", "languages",
        "contact", "profile",
    ]

    for line in lines:
        line_lower = line.lower().strip()
        is_header = any(h in line_lower for h in headers)
        is_stop = any(h in line_lower for h in stop_headers if h not in headers)

        if is_header:
            capturing = True
            continue
        if capturing and is_stop and len(line_lower) < 40:
            break
        if capturing and line.strip():
            section_lines.append(line.strip())

    return "\n".join(section_lines[:20])


def parse_resume(file_path: str) -> dict:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        text = parse_pdf(file_path)
    elif ext in (".docx", ".doc"):
        text = parse_docx(file_path)
    else:
        with open(file_path, "r", errors="ignore") as f:
            text = f.read()

    name = extract_name(text)
    email = extract_email(text)
    phone = extract_phone(text)
    skills = extract_skills(text)
    job_titles = extract_job_titles(text)
    experience = extract_section(text, ["experience", "work history", "employment"])
    education = extract_section(text, ["education", "academic", "degree"])

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "skills": skills,
        "job_titles": job_titles,
        "experience": experience,
        "education": education,
        "raw_text": text,
    }
