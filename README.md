# H.R Assistant A.I - S.K A.I Development

Agentic recruitment assistant: LangGraph + RAG (ChromaDB) + FastAPI + React + a free open LLM (Qwen2.5 via Ollama).

Two dashboards, one login page:
* **HR Dashboard** (`/hr`): Hiring chat (JD, approvals, shortlist, offers), Jobs and applicants (live tracking), Live activity feed.
* **Candidate Dashboard** (`/candidate`): search jobs, apply with a resume, track the application, accept or decline offers.

Jobs are published on the built-in **Candidate Portal**, so no LinkedIn / Naukri / JobIndia API key is needed.
Those three are optional: post by hand with the copy-ready text, then paste the link under *Jobs and applicants*.

## Run (Linux / Pop!_OS)
```
# Terminal 1 - LLM (see below for the portable Ollama copy)      -> ollama serve
# Terminal 2 - backend
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # set SMTP_PASSWORD (Gmail app password), SECRET_KEY, HR_INVITE_CODE
python -m app.seed              # demo accounts   (or: python -m app.seed --applicants 22)
uvicorn app.main:app --reload --port 8000
# Terminal 3 - frontend
cd frontend && npm install && npm run dev      # http://localhost:5173
```
Demo logins (password `Demo@1234`): `hr@demo.com`, `candidate@demo.com`.
`LLM_PROVIDER=fake` in `.env` runs everything without a model.

## Accounts and security
* Candidates register themselves. **HR registration needs the invitation code** (`HR_INVITE_CODE` in `.env`).
* Every HR endpoint checks the HR role; candidates only reach their own applications, resumes and offers.
* Passwords use scrypt; login tokens are signed (change `SECRET_KEY`). Resumes are stored in a private folder and only downloadable by the owner or HR. Only PDF/DOCX up to 5 MB are accepted. Resume text is treated as untrusted data.

## Demo flow
1. HR > Hiring chat: type a request, **Reject** the first draft with feedback, then **Approve**. The job goes live on the Candidate Dashboard.
2. Candidate (another browser/profile): register, filter jobs (location, skill, Fresher), upload a resume, **Apply**. HR sees the applicant instantly under *Jobs and applicants*.
3. HR > Hiring chat > **Skip the wait (demo)** (or set `WAIT_SCALE=0.0001`).
   * fewer than 20 applicants: AI revises the JD, HR approves it, 48-hour check, then HR chooses *review* or *extend*.
   * 20 or more: AI shortlist (up to 20, never padded) for HR to review, change and approve with interview details.
4. HR sends invitations, selects a candidate (offer letter + email are written by the LLM), the candidate accepts on their dashboard, both dashboards update and the confirmation email is logged.
5. Retrying a publish or an email never creates a duplicate.
