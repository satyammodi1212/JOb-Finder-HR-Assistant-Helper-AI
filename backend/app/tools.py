"""External actions: job portals, e-mail, offer-letter PDF."""
import os
import smtplib
import uuid
from email.message import EmailMessage

from . import db
from .config import COMPANY, DATA, MAIL_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER

def count_applications(thread_id: str) -> int:
    rows = db.run("SELECT COUNT(*) n FROM candidates WHERE thread_id=?", (thread_id,), fetch=True)
    return rows[0]["n"]


# ---------- E-mail ----------
def send_email(thread_id, to, subject, body, kind, attachment=None):
    if kind != "hr_alert" and db.run(
            "SELECT 1 FROM email_logs WHERE thread_id=? AND to_email=? AND type=? AND subject=? AND status IN ('sent','logged')",
            (thread_id, to, kind, subject), fetch=True):
        print(f"[EMAIL:{kind}] duplicate skipped to={to}")   # retries never send the same email twice
        return
    status = "logged"
    if SMTP_HOST and SMTP_PASSWORD and to:
        try:
            msg = EmailMessage()
            msg["From"], msg["To"], msg["Subject"] = MAIL_FROM, to, subject
            msg.set_content(body)
            if attachment:
                msg.add_attachment(open(attachment, "rb").read(), maintype="application",
                                   subtype="pdf", filename=os.path.basename(attachment))
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
                s.starttls()
                if SMTP_USER:
                    s.login(SMTP_USER, SMTP_PASSWORD)
                s.send_message(msg)
            status = "sent"
        except Exception as e:  # never crash the workflow because of mail
            status = f"failed: {e}"
    print(f"[EMAIL:{kind}] to={to} subject={subject} status={status}")
    db.run("INSERT INTO email_logs(thread_id,to_email,type,subject,status) VALUES(?,?,?,?,?)",
           (thread_id, to, kind, subject, status))


def offer_letter_pdf(name: str, title: str, body: str) -> str:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    path = os.path.join(DATA, "letters", f"offer_{uuid.uuid4().hex[:8]}.pdf")
    st = getSampleStyleSheet()
    flow = [Paragraph(COMPANY, st["Title"]), Paragraph(f"Offer of Employment - {title}", st["Heading2"]), Spacer(1, 12)]
    for para in body.split("\n\n"):
        safe = para.replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br/>")
        flow += [Paragraph(safe, st["BodyText"]), Spacer(1, 8)]
    SimpleDocTemplate(path, pagesize=A4).build(flow)
    return path
