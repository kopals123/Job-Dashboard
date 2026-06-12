# Job-Dashboard
AI-powered job application automation tool — upload your resume, search jobs from Adzuna, Arbeitnow &amp; RemoteOK, and auto-apply at scale with AI-generated cover letters.

Features

📄 Resume Parsing — Upload your resume (PDF or DOCX) and extract skills, experience, and education automatically
🔍 Multi-board Job Search — Pulls live listings from Adzuna, Arbeitnow, and RemoteOK in one search
🤖 AI Cover Letter Generation — Generates tailored cover letters per job using Claude (Anthropic API)
🎯 Filters — Filter by job title/keywords, location, minimum salary, and remote-only toggle
📊 Progress Tracker — Visual progress bar tracking applications sent per day (target: 50/day)
🖥️ Dashboard — Clean overview of all applications, statuses, and activity

Installation 
# Clone the repo
git clone https://github.com/your-username/jobblitz.git
cd jobblitz

# Backend setup
cd backend
pip install -r requirements.txt
cp .env.example .env
# Add your API keys to .env

# Frontend setup
cd ../frontend
npm install
npm run dev

Running the App
# Start backend (from /backend)
flask run

# Start frontend (from /frontend)
npm run dev

How It Works

Upload your resume — Drop a PDF or DOCX into the resume panel
Search for jobs — Enter a job title, location, salary floor, and remote preference
Review listings — Browse aggregated results from multiple job boards
Auto-apply — JobBlitz generates a tailored cover letter and submits applications on your behalf
Track progress — Monitor your daily application count toward the 50-application goal

Roadmap

LinkedIn and Indeed integration
Application status tracking (applied / interview / rejected)
Email follow-up automation
Resume tailoring per job description
Browser extension for one-click apply on job boards
Analytics dashboard (response rate, interview rate by job type)


Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.
