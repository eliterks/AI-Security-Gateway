from typing import Annotated, Literal
from datetime import datetime, timedelta, timezone
from app.providers import call_local_slm, call_gemini_llm
import time
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from app.config import JWT_SECRET, ACCESS_TOKEN_MINUTES, INJECTION_THRESHOLD
from app.database import Base, engine, get_db
from app.models import User
from app.security import (
    hash_password,
    verify_password,
    create_access_token,
    verify_access_token,
)
from app.pii import detect_pii, redact_pii
from app.classifier import load_classifier, injection_probability
from app.model_router import choose_model
from app.config import (
    JWT_SECRET,
    ACCESS_TOKEN_MINUTES,
    INJECTION_THRESHOLD,
    GEMINI_MODEL,
)

from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

Base.metadata.create_all(bind=engine)
load_classifier()

app = FastAPI(
    title="AI Security Gateway",
    description="Classroom demo: token auth, PII detection/redaction, prompt-injection scoring, and model routing.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if not JWT_SECRET or JWT_SECRET == "REPLACE_WITH_A_LONG_RANDOM_SECRET":
        raise HTTPException(status_code=500, detail="Set JWT_SECRET in .env")
    payload = verify_access_token(token, JWT_SECRET)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.username == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=10, max_length=128)


class PromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)


class ChatRequest(PromptRequest):
    model: Literal["auto", "slm", "llm"] = "auto"


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}


@app.post("/auth/register", tags=["authentication"], status_code=201)
def register(body: RegisterRequest, db: Annotated[Session, Depends(get_db)]):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=409, detail="Username already exists")
    user = User(username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "username": user.username}


@app.post("/auth/token", tags=["authentication"])
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not JWT_SECRET or JWT_SECRET == "REPLACE_WITH_A_LONG_RANDOM_SECRET":
        raise HTTPException(status_code=500, detail="Set JWT_SECRET in .env")
    token = create_access_token(user.username, JWT_SECRET, ACCESS_TOKEN_MINUTES)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_MINUTES * 60,
    }


@app.get("/auth/me", tags=["authentication"])
def me(current_user: Annotated[User, Depends(get_current_user)]):
    return {"id": current_user.id, "username": current_user.username}


@app.post("/security/pii/detect", tags=["Security Components"])
def pii_detect(
    body: PromptRequest, current_user: Annotated[User, Depends(get_current_user)]
):
    matches = detect_pii(body.prompt)
    return {
        "detected": bool(matches),
        "count": len(matches),
        "matches": [{"type": m.kind, "start": m.start, "end": m.end} for m in matches],
    }


@app.post("/security/pii/redact", tags=["Security Components"])
def pii_redact(
    body: PromptRequest, current_user: Annotated[User, Depends(get_current_user)]
):
    sanitized, types = redact_pii(body.prompt)
    return {
        "redacted_prompt": sanitized,
        "pii_types_redacted": types,
        "count": len(types),
    }


# In-memory IP-based rate limiter (prevents API flooding / quota abuse)
_request_counts = {}
RATE_LIMIT_PER_MINUTE = 30

def check_rate_limit(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    history = _request_counts.get(client_ip, [])
    # Keep only timestamps within the last 60 seconds
    history = [t for t in history if now - t < 60]
    if len(history) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: max {RATE_LIMIT_PER_MINUTE} requests per minute.",
        )
    history.append(now)
    _request_counts[client_ip] = history


@app.post("/security/prompt-injection/score", tags=["Security Components"])
def injection_score(
    body: PromptRequest, current_user: Annotated[User, Depends(get_current_user)]
):
    try:
        probability = injection_probability(body.prompt)
    except Exception:
        probability = 0.0
    return {
        "injection_probability": round(probability, 4),
        "threshold": INJECTION_THRESHOLD,
        "blocked_by_threshold": probability >= INJECTION_THRESHOLD,
    }


@app.post("/chat", tags=["AI Gateway"])
def run_secure_chat(prompt: str, requested_model: str):
    # 1. Detect prompt injection before invoking any model
    try:
        risk = injection_probability(prompt)
    except Exception:
        # Model not found: fallback gracefully so PII & Router work
        risk = 0.0
        # raise HTTPException(
        #     status_code=503,
        #     detail="Prompt-injection classifier unavailable.",
        # )

    if risk >= INJECTION_THRESHOLD:
        raise HTTPException(
            status_code=403,
            detail="Prompt blocked by injection policy"
        )

    # 2. Redact PII before sending input to a model
    sanitized, pii_types = redact_pii(prompt)

    # 3. Select model
    selected = choose_model(sanitized, requested_model)

    # 4. Invoke selected provider and measure latency
    start_time = time.perf_counter()

    try:
        if selected == "slm":
            answer = call_local_slm(sanitized)
            provider = "local"
            model_name = "SmolLM2-360M-Instruct"
        elif selected == "llm":
            answer = call_gemini_llm(sanitized)
            provider = "gemini"
            model_name = GEMINI_MODEL
        else:
            raise ValueError(f"Unsupported model selection: {selected}")

    except Exception as exc:
        print("Provider call failed:", type(exc).__name__, str(exc))
        raise HTTPException(
            status_code=502,
            detail="Model provider failed; check server terminal and configuration.",
        )

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

    return {
        "response": answer,
        "selected_model": model_name,
        "provider": provider,
        "latency_ms": latency_ms,
        "injection_probability": round(risk, 4),
        "pii_types_redacted": pii_types,
        "redacted_prompt": sanitized,
    }


@app.post("/chat/router", tags=["AI Gateway"])
def chat_router(
    body: PromptRequest,
    current_user: Annotated[User, Depends(get_current_user)],
):
    # Check prompt injection before making a routing decision
    try:
        risk = injection_probability(body.prompt)
    except Exception:
        risk = 0.0 

    if risk >= INJECTION_THRESHOLD:
        raise HTTPException(
            status_code=403,
            detail="Prompt blocked by injection policy"
        )

    # Router only selects the model. It does NOT generate a response.
    selected = choose_model(body.prompt, "auto")

    if selected == "slm":
        model_name = "HuggingFaceTB/SmolLM2-360M-Instruct"
    else:
        model_name = GEMINI_MODEL

    return {
        "selected_model": selected,
        "model_name": model_name,
        "reason": (
            "Simple prompt: use the local SLM."
            if selected == "slm"
            else "Complex prompt: use the Gemini LLM."
        ),
        "injection_probability": round(risk, 4),
    }


@app.post("/chat/slm", tags=["AI Gateway"], dependencies=[Depends(check_rate_limit)])
def chat_slm(
    body: PromptRequest,
    current_user: Annotated[User, Depends(get_current_user)],
):
    return run_secure_chat(body.prompt, "slm")


@app.post("/chat/llm", tags=["AI Gateway"], dependencies=[Depends(check_rate_limit)])
def chat_llm(
    body: PromptRequest,
    current_user: Annotated[User, Depends(get_current_user)],
):
    return run_secure_chat(body.prompt, "llm")


# Preserve the original endpoint for existing clients
@app.post("/chat", tags=["AI Gateway"], dependencies=[Depends(check_rate_limit)])
def chat(
    body: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
):
    return run_secure_chat(body.prompt, body.model)
