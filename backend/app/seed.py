"""Demo data:  python -m app.seed [--applicants N]
Creates demo accounts. With --applicants N it also starts a hiring request, approves the JD and
creates N synthetic candidates who apply with generated resumes (use N<20 and N>=20 to see both outcomes)."""
import io
import random
import sys

import docx

from . import auth, db, portal
from .main import JDDecision, StartReq, jd_decision, start

PASSWORD = "Demo@1234"
FIRST = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Ananya", "Vikram", "Isha", "Arjun", "Sneha", "Rahul", "Pooja",
         "Karan", "Neha", "Aditya", "Riya", "Manav", "Tanvi", "Yash", "Simran", "Dev", "Kriti", "Harsh", "Nisha"]
POOL = ["React", "JavaScript", "HTML", "CSS", "TypeScript", "Git", "Python", "Java"]


def make_user(name, email, role):
    if db.run("SELECT 1 FROM users WHERE email=?", (email,), fetch=True):
        return db.run("SELECT * FROM users WHERE email=?", (email,), fetch=True)[0]
    uid = email.split("@")[0][:10]
    db.run("INSERT INTO users(id,email,name,role,password_hash) VALUES(?,?,?,?,?)", (uid, email, name, role, auth.hash_password(PASSWORD)))
    return db.run("SELECT * FROM users WHERE id=?", (uid,), fetch=True)[0]


def resume_docx(name, email, skills, years):
    d = docx.Document()
    d.add_heading(name, 0)
    d.add_paragraph(f"{email}")
    d.add_paragraph("Education: B.Tech in Computer Science")
    d.add_paragraph(f"Experience: {years} years as a web developer." if years else "Fresher. Completed internships and college projects.")
    d.add_paragraph("Skills: " + ", ".join(skills))
    d.add_paragraph("Projects: Built a portfolio website and a task manager using " + (", ".join(skills[:3]) or "basic web tools") + ".")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def main(n):
    make_user("Demo HR Manager", "hr@demo.com", "hr")
    make_user("Demo Candidate", "candidate@demo.com", "candidate")
    print(f"Demo accounts (password {PASSWORD}):  hr@demo.com  |  candidate@demo.com")
    if not n:
        return
    random.seed(7)
    t = start(StartReq(query="I want to hire a frontend developer in Faridabad with React, JavaScript, HTML and CSS. Freshers can apply."))["thread_id"]
    jd_decision(t, JDDecision(status="approved"))
    for i in range(n):
        name = f"{FIRST[i % len(FIRST)]} {chr(65 + i % 26)}."
        email = f"{FIRST[i % len(FIRST)].lower()}{i}@example.com"
        user = make_user(name, email, "candidate")
        skills = random.sample(POOL, random.randint(3, 7)) if i % 6 else random.sample(POOL, 1)
        portal.apply_to_job(t, user, f"{name}.docx", resume_docx(name, email, skills, random.randint(0, 3)))
    print(f"Created job {t} with {n} applicants. Log in as HR, open 'Hiring chat' and press 'Skip the wait (demo)'.")


if __name__ == "__main__":
    main(int(sys.argv[sys.argv.index("--applicants") + 1]) if "--applicants" in sys.argv else 0)
