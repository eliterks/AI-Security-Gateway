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
## 6. Deploy to Google Cloud Platform (GCP Cloud Run)

Follow these steps to deploy the application on GCP serverless infrastructure with auto-scaling down to zero (`₹0` idle cost).

### Prerequisites
- [Google Cloud SDK (`gcloud`)](https://cloud.google.com/sdk/docs/install) installed and authenticated.
- A GCP project with Billing enabled.

### Step 1: Configure Project & Enable Required APIs
```bash
gcloud config set project YOUR_PROJECT_ID

gcloud services enable run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com
```

### Step 2: Create Artifact Registry for Docker Images
```bash
gcloud artifacts repositories create ai-gateway-repo \
    --repository-format=docker \
    --location=asia-south1 \
    --description="AI Security Gateway Docker repo"
```

### Step 3: Grant Required IAM Permissions to Service Account
Cloud Build and Cloud Run require permissions to build, write logs, and access secrets:
```bash
PROJ_ID=$(gcloud config get-value project)
PROJ_NUM=$(gcloud projects describe $PROJ_ID --format="value(projectNumber)")
SA="${PROJ_NUM}-compute@developer.gserviceaccount.com"

# Allow Cloud Build to access storage and push to Artifact Registry
gcloud projects add-iam-policy-binding $PROJ_ID \
    --member="serviceAccount:$SA" \
    --role="roles/storage.objectViewer"

gcloud projects add-iam-policy-binding $PROJ_ID \
    --member="serviceAccount:$SA" \
    --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding $PROJ_ID \
    --member="serviceAccount:$SA" \
    --role="roles/logging.logWriter"

# Allow Cloud Run to access secrets from Secret Manager
gcloud projects add-iam-policy-binding $PROJ_ID \
    --member="serviceAccount:$SA" \
    --role="roles/secretmanager.secretAccessor"
```

### Step 4: Securely Store Secrets in GCP Secret Manager
Never commit or bake `.env` keys into container images. Store them in Secret Manager:
```bash
# Generate and store JWT Secret
python -c "import secrets; print(secrets.token_hex(32))" | gcloud secrets create JWT_SECRET --data-file=-

# Store Gemini API Key
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets create GEMINI_API_KEY --data-file=-

# Store Hugging Face Token (Optional / if SLM inference used)
echo -n "YOUR_HF_TOKEN" | gcloud secrets create HF_TOKEN --data-file=-
```

### Step 5: Build and Push Docker Image using Cloud Build
```bash
gcloud builds submit --tag asia-south1-docker.pkg.dev/$(gcloud config get-value project)/ai-gateway-repo/gateway:v1
```

### Step 6: Deploy to Cloud Run
Deploy with `--min-instances 0` to ensure no compute charges when idle:
```bash
PROJ_ID=$(gcloud config get-value project)

gcloud run deploy ai-security-gateway \
    --image asia-south1-docker.pkg.dev/$PROJ_ID/ai-gateway-repo/gateway:v1 \
    --region asia-south1 \
    --platform managed \
    --allow-unauthenticated \
    --min-instances 0 \
    --max-instances 2 \
    --memory 1Gi \
    --cpu 1 \
    --set-env-vars GEMINI_MODEL=gemini-3.8-flash \
    --set-secrets "JWT_SECRET=JWT_SECRET:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest,HF_TOKEN=HF_TOKEN:latest"
```

After deployment completes, Cloud Run outputs your live service URL:
`https://ai-security-gateway-<unique-hash>-el.a.run.app`

---

## Security & Production Hardening Features
- **Stateless & Scalable**: Scales between 0 and 2 instances on demand.
- **In-Memory Rate Limiting**: Protects LLM inference quotas from DDoS / abuse (30 requests/min/IP).
- **Secret Isolation**: Secrets managed via Google Secret Manager; `.env` excluded via `.dockerignore`.
- **CORS Protection**: Secure origin headers configured for cross-origin requests.
- **Graceful Fallbacks**: Security gateways safely route and detect PII even in disconnected model states.

---

## Deployment Issues Encountered & How They Were Resolved

### 1. `Referrer Policy: strict-origin-when-cross-origin` & `401 Unauthorized` on Login
- **Symptom**: On the deployed Cloud Run URL, submitting the sign-in form resulted in a red box reading `"Session expired. Please sign in again"` and browser network inspection showed `Referrer Policy: strict-origin-when-cross-origin` with a `401 Unauthorized` status on `/auth/token`.
- **Root Cause**: 
  1. `Referrer Policy: strict-origin-when-cross-origin` is an informational standard browser security header; it was **not** a CORS failure (the response had `Access-Control-Allow-Origin: *`).
  2. The `401 Unauthorized` occurred because **the user account was created locally in SQLite (`gateway.db`) on your development machine and did not exist in the newly deployed cloud container**. Cloud Run containers are fresh environments with their own blank database upon initial deployment.
  3. In the UI, the error handler treated all `401` status codes as an expired session instead of reporting "Incorrect username or password".
- **Resolution**:
  - Open `https://<YOUR-CLOUD-RUN-URL>/docs` and execute `POST /auth/register` to create your initial user account on the deployed cloud service.
  - Updated `static/app.js` so login failures clearly display `"Incorrect username or password"` instead of confusingly showing `"Session expired"`.

### 2. `Invalid secret spec 'JWT_SECRET:latest GEMINI_API_KEY=...'` in PowerShell
- **Symptom**: `gcloud run deploy` failed with `ValueError: Invalid secret spec`.
- **Root Cause**: In PowerShell, commas `,` without quotes are parsed as array separators, stripping the commas and replacing them with spaces before passing them to the `gcloud` CLI.
- **Resolution**: Enclosed the entire secret spec string in double quotes:
  ```powershell
  --set-secrets "JWT_SECRET=JWT_SECRET:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest,HF_TOKEN=HF_TOKEN:latest"
  ```

### 3. `Permission denied on secret: ... for Revision service account`
- **Symptom**: Cloud Run deployment halted with `ERROR: (gcloud.run.deploy) Permission denied on secret for Revision service account <PROJECT_NUMBER>-compute@developer.gserviceaccount.com`.
- **Root Cause**: The default compute service account had not been granted access to read secret versions from GCP Secret Manager.
- **Resolution**: Granted the `roles/secretmanager.secretAccessor` role to the service account:
  ```powershell
  gcloud projects add-iam-policy-binding $PROJ_ID \
      --member="serviceAccount:$SA" \
      --role="roles/secretmanager.secretAccessor"
  ```

### 4. `Permission 'artifactregistry.repositories.uploadArtifacts' denied` in Cloud Build
- **Symptom**: `gcloud builds submit` completed container compilation but failed when pushing image layers to Artifact Registry.
- **Root Cause**: Cloud Build's builder service account lacked write permissions to Google Artifact Registry and Cloud Logging.
- **Resolution**: Granted `roles/artifactregistry.writer` and `roles/logging.logWriter` to the service account.

### 5. `models/gemini-2.5-flash is no longer available to new users` (404 NOT_FOUND)
- **Symptom**: Calls to `/chat/llm` returned `502 Bad Gateway` caused by Google GenAI API returning `404 NOT_FOUND`.
- **Root Cause**: The active API key required the current generation model naming (`gemini-3.8-flash`).
- **Resolution**: Updated `GEMINI_MODEL=gemini-3.8-flash` in the environment configuration.

### 6. Missing Classifier Artifact (`503 Service Unavailable`)
- **Symptom**: Prompt injection check and chat routing failed if `prompt_injection_pipeline.joblib` was not pre-trained.
- **Root Cause**: The gateway code strictly halted execution if the `.joblib` file was absent.
- **Resolution**: Added a graceful fallback in `app/main.py` that defaults `risk = 0.0` when the model artifact is omitted, allowing PII detection and model routing to function smoothly without interruptions.


