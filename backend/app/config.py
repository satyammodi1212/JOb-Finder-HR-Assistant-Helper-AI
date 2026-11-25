import os
from dotenv import load_dotenv

load_dotenv()
g = os.getenv
LLM_PROVIDER = g("LLM_PROVIDER", "fake").lower()   # local | huggingface | openai | fake
HF_TOKEN = g("HF_TOKEN", "")
HF_MODEL = g("HF_MODEL", "Qwen/Qwen2.5-7B-Instruct")
LOCAL_URL = g("LOCAL_URL", "http://localhost:11434/v1")   # Ollama
LOCAL_MODEL = g("LOCAL_MODEL", "qwen2.5:7b")
LLM_API_KEY = g("LLM_API_KEY", "")   # only for LLM_PROVIDER=openai
LLM_MODEL = g("LLM_MODEL", "")
SMTP_HOST, SMTP_PORT = g("SMTP_HOST", "smtp.gmail.com"), int(g("SMTP_PORT", "587"))
SMTP_USER, SMTP_PASSWORD = g("SMTP_USER", "ankitmodi117@gmail.com"), g("SMTP_PASSWORD", "")
MAIL_FROM, HR_EMAIL = g("MAIL_FROM", "ankitmodi117@gmail.com"), g("HR_EMAIL", "ankitmodi117@gmail.com")
COMPANY = g("COMPANY_NAME", "S.K A.I Development")
MIN_APPLICATIONS = int(g("MIN_APPLICATIONS", "20"))
SHORTLIST_N = int(g("SHORTLIST_N", "20"))
OFFER_DEADLINE_DAYS = int(g("OFFER_DEADLINE_DAYS", "5"))
WAIT_SCALE = float(g("WAIT_SCALE", "1.0"))
EMBEDDINGS = g("EMBEDDINGS", "hash")
DATA = os.path.join(os.path.dirname(__file__), "..", "storage")
os.makedirs(os.path.join(DATA, "resumes"), exist_ok=True)
os.makedirs(os.path.join(DATA, "letters"), exist_ok=True)
DB_PATH = os.path.join(DATA, "hr_app.db")
CHECKPOINT_DB = os.path.join(DATA, "hr_checkpoints.db")
CHROMA_DIR = os.path.join(DATA, "chroma")
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "templates")
# Scoring weights (HR can change these)
WEIGHTS = {"skill": 0.50, "experience": 0.20, "education": 0.15, "semantic": 0.15}

PROFILE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "company_profile.txt")
SECRET_KEY = g("SECRET_KEY", "dev-secret-change-me")      # signs login tokens: CHANGE in production
TOKEN_HOURS = int(g("TOKEN_HOURS", "12"))
HR_INVITE_CODE = g("HR_INVITE_CODE", "SKAI-HR-2026")     # needed to register an HR account
APPLY_DEADLINE_DAYS = int(g("APPLY_DEADLINE_DAYS", "30"))
MAX_RESUME_MB = int(g("MAX_RESUME_MB", "5"))
