import os
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "")
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))
CLASSIFIER_PATH = os.getenv(
    "CLASSIFIER_PATH", "models/prompt_injection_pipeline.joblib"
)
INJECTION_THRESHOLD = float(os.getenv("INJECTION_THRESHOLD", "0.80"))
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_SLM_MODEL = os.getenv("HF_SLM_MODEL", "HuggingFaceTB/SmolLM2-1.7B-Instruct")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./gateway.db")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "AdminGateway@2026")
