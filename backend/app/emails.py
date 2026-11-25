"""LLM-written candidate emails + offer letter. Each has an offline fallback template."""
import re

from .config import COMPANY
from .llm import ask

SIGN = f"\n\nBest regards,\nHR Team\n{COMPANY}"


def _write(kind: str, facts: str, fallback: str, words="90-140") -> str:
    prompt = (f"Write a {kind}.\nFacts: {facts}\n"
              f"Rules: plain text only, {words} words, warm and professional, start with 'Dear <name>,', "
              "no subject line, no signature, do not invent salary, dates, links or benefits. "
              "Always include any interview date, time, time zone and link or location given in the facts.")
    body = ask(prompt, fake=lambda: fallback).strip()
    body = re.sub(r"^subject:.*\n+", "", body, flags=re.I)
    body = re.split(r"\n\s*(?:best regards|sincerely|kind regards)", body, flags=re.I)[0].strip()
    return body + SIGN


def interview(name, title, d=None):
    d = d or {}
    when = f"{d.get('date', '')} at {d.get('time', '')} ({d.get('timezone', '')})".strip()
    where = d.get("link", "")
    return _write("interview invitation email", f"candidate {name}; role {title}; shortlisted after resume review; "
                  f"interview date and time: {when}; meeting link or location: {where}",
                  f"Dear {name},\n\nThank you for applying for the {title} role at {COMPANY}. Your profile has been shortlisted.\n\n"
                  f"Interview: {when}\nMeeting link / location: {where}\n\nPlease reply to confirm your availability.")


def offer_email(name, title, deadline):
    return _write("job offer email (the offer letter PDF is attached)",
                  f"candidate {name}; role {title}; passed all interview rounds; reply by {deadline}",
                  f"Dear {name},\n\nCongratulations! You have successfully completed our interview process and we are happy to offer you "
                  f"the position of {title} at {COMPANY}. Please find your offer letter attached and reply to this email by {deadline}.")


def offer_letter(name, title, deadline):
    return _write("formal offer letter", f"candidate {name}; position {title}; company {COMPANY}; acceptance deadline {deadline}; "
                  "compensation and joining date will be shared by HR",
                  f"Dear {name},\n\nWe are pleased to offer you the position of {title} at {COMPANY}. Compensation and your joining "
                  f"date will be shared by our HR team. Please confirm your acceptance by {deadline}.", words="150-220")


def regret(name, title):
    return _write("polite regret email after interviews",
                  f"candidate {name}; role {title}; another candidate was selected; we will keep the profile for future openings",
                  f"Dear {name},\n\nThank you for the time you invested in interviewing for the {title} role. After careful consideration we "
                  "have decided to move forward with another candidate. We will keep your profile for future openings.")


def confirm(name, title):
    return _write("welcome email after offer acceptance", f"candidate {name}; role {title}; HR will share joining details",
                  f"Dear {name},\n\nThank you for accepting our offer for the {title} role at {COMPANY}. We are excited to welcome you "
                  "and our HR team will share your joining details soon.")


def reminder(name, title, deadline):
    return _write("short reminder email about a pending job offer", f"candidate {name}; role {title}; offer expires {deadline}",
                  f"Dear {name},\n\nThis is a friendly reminder that your offer for the {title} role expires on {deadline}. "
                  "Please reply to let us know your decision.", words="50-80")
