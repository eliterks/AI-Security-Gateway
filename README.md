# AI Security Gateway — clean starter

## What is included
- FastAPI authentication: registration, password hashing, JWT bearer access tokens, `/auth/me`
- Auth-protected component endpoints:
  - `POST /security/pii/detect`
  - `POST /security/pii/redact`
  - `POST /security/prompt-injection/score`
- Integrated `POST /chat` endpoint
- Regex-based PII redaction
- TF-IDF + Logistic Regression injection classifier loader
- Heuristic SLM/LLM router
- Hugging Face Inference Providers SLM and Gemini LLM adapters

## Important
This is a teaching demo, not production-ready. It includes a small standard-library HS256 token implementation to avoid the OpenSSL/cryptography import conflict seen in some older Python/Anaconda environments. For production, replace `app/security.py` with a maintained authentication library, add rate limiting, TLS, account verification, role-based authorization, security review, and monitoring. Never load untrusted `.joblib` files.

## 1. Use a fresh virtual environment (recommended)
Python 3.11 is recommended. From the extracted project directory:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

If only Python 3.9 is installed, the pinned dependencies are intended to keep the demo compatible, but a newer Python is recommended.

Generate a JWT secret:
```bash
openssl rand -hex 32
```
Paste it into `.env` as `JWT_SECRET`. Add your `HF_TOKEN` and `GEMINI_API_KEY`. Do not share or commit `.env`.

## 2. Add the classifier artifact
Copy the trained `prompt_injection_pipeline.joblib` from Kaggle into this project's `models/` directory.

The app can start without the model artifact, so you can test authentication and PII endpoints first. The prompt-injection endpoint and `/chat` return `503` until a compatible classifier artifact is present.

To train locally, install optional training requirements:
```bash
pip install -r requirements-train.txt
python train_classifier.py
```
Training downloads `deepset/prompt-injections`, so internet access is needed. Check that dataset label `1` means injection before trusting the classifier.

## 3. Configure provider keys
- Hugging Face token: https://huggingface.co/settings/tokens
- Gemini key: https://aistudio.google.com/apikey

The Hugging Face model must be supported by your account's Inference Providers. Change `HF_SLM_MODEL` if needed. Gemini model availability can vary by API account; update `GEMINI_MODEL` to a model available to your key.

## 4. Start
```bash
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs

## 5. Test
1. `POST /auth/register` with username and password (minimum 10 characters).
2. `POST /auth/token` using Swagger's form fields `username` and `password`.
3. Click Swagger's **Authorize** button and authenticate with the access token.
4. Try `GET /auth/me`.
5. Try `POST /security/pii/detect` with `{"prompt":"Email me at student@example.com"}`.
6. Try `POST /security/pii/redact` with the same prompt.
7. Try `POST /security/prompt-injection/score` with an injection-style prompt.
8. Try `POST /chat` with `{"prompt":"Explain TF-IDF simply","model":"auto"}`.

Every security component endpoint and `/chat` requires a valid token. `/health`, registration and login are public by design.

## Security and demo limitations
- Regex is incomplete; it won't reliably detect names/addresses and format matches do not prove a number is valid.
- TF-IDF is lexical and can miss novel/adversarial injection prompts.
- Threshold is a demo policy setting, not a guarantee of security.
- Router uses simple heuristics, not actual quality measurement.
- Redaction changes the prompt before it leaves your server. Check that behavior is appropriate for your task.
- Avoid logging raw prompts or real personal information.
- Public registration is for classroom convenience only; restrict it before deployment.
# AI-Security-Gateway
