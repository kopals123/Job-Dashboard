import os

TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), "cover_letter_template.txt")
_PLACEHOLDER_MARKER = "[YOUR CUSTOM COVER LETTER TEMPLATE HERE]"


def _load_user_template() -> str:
    """Read the user's custom fallback template, if provided."""
    if not os.path.exists(TEMPLATE_FILE):
        return ""
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        content = f.read().strip()
    # Return empty string if it's still the placeholder
    if _PLACEHOLDER_MARKER in content:
        return ""
    return content


def _apply_template(template: str, resume_data: dict, job: dict) -> str:
    skills = resume_data.get("skills", [])
    top_skills = ", ".join(skills[:3]) if skills else "relevant technologies"
    return (
        template
        .replace("{name}", resume_data.get("name", "Applicant"))
        .replace("{job_title}", job.get("title", "this position"))
        .replace("{company}", job.get("company", "your company"))
        .replace("{top_skills}", top_skills)
    )


def generate_cover_letter(resume_data: dict, job: dict) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "")

    if api_key:
        result = _try_openai(api_key, resume_data, job)
        if result:
            return result

    # Use user template if provided
    user_template = _load_user_template()
    if user_template:
        return _apply_template(user_template, resume_data, job)

    # Built-in fallback
    return _builtin_fallback(resume_data, job)


def _try_openai(api_key: str, resume_data: dict, job: dict) -> str:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        name = resume_data.get("name", "Applicant")
        skills = ", ".join(resume_data.get("skills", [])[:10])
        experience = resume_data.get("experience", "")[:800]
        education = resume_data.get("education", "")[:300]
        job_title = job.get("title", "")
        company = job.get("company", "")
        job_desc = (job.get("full_description") or job.get("description", ""))[:1000]

        prompt = f"""Write a professional, tailored 3-paragraph cover letter for this applicant and job.

Applicant: {name}
Skills: {skills}
Experience: {experience}
Education: {education}

Job Title: {job_title}
Company: {company}
Job Description: {job_desc}

Rules:
- Opening: Enthusiasm for the role and 1-2 specific things about the company/job
- Middle: Connect 2-3 specific skills/experiences to the job requirements
- Closing: Call to action, professional sign-off
- 250-350 words total, no "Dear Hiring Manager" or date
- Do NOT start with "I am writing to apply"
- Return only the 3 paragraphs, nothing else"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI error: {e}")
        return ""


def _builtin_fallback(resume_data: dict, job: dict) -> str:
    name = resume_data.get("name", "Applicant")
    skills = resume_data.get("skills", [])
    top_skills = ", ".join(skills[:3]) if skills else "relevant technologies"
    job_title = job.get("title", "this position")
    company = job.get("company", "your company")

    return (
        f"I am excited to apply for the {job_title} role at {company}. "
        f"Your team's focus on innovation and quality aligns perfectly with my professional goals, "
        f"and I am confident that my background makes me a strong candidate for this opportunity.\n\n"
        f"Throughout my career, I have developed strong expertise in {top_skills}. "
        f"My hands-on experience has equipped me with the technical depth and problem-solving mindset "
        f"needed to contribute meaningfully from day one. I thrive in collaborative environments "
        f"and consistently deliver high-quality work under tight deadlines.\n\n"
        f"I would welcome the opportunity to discuss how my experience aligns with {company}'s needs. "
        f"Thank you for your time and consideration — I look forward to speaking with you soon.\n\n"
        f"Best regards,\n{name}"
    )
