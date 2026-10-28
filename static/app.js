const API = {
  token: "/auth/token",
  router: "/chat/router",
  slm: "/chat/slm",
  llm: "/chat/llm",
};

let accessToken = null;
let selectedMode = "router";
let lastResponse = "";

const $ = (id) => document.getElementById(id);

function show(element, visible = true) {
  element.classList.toggle("hidden", !visible);
}

function setMessage(id, message) {
  const element = $(id);
  element.textContent = message || "";
  show(element, Boolean(message));
}

function showToast(message) {
  const toast = $("toast");
  toast.textContent = message;
  show(toast);

  clearTimeout(showToast.timeout);
  showToast.timeout = setTimeout(() => show(toast, false), 2800);
}

async function readJson(response) {
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = data.detail;
    let message = "Request failed (" + response.status + ").";

    if (typeof detail === "string") {
      message = detail;
    } else if (detail && typeof detail === "object") {
      message = detail.message || JSON.stringify(detail);
    }

    if (response.status === 401) {
      if (response.url.includes("/auth/token")) {
        throw new Error(message || "Incorrect username or password.");
      }
      logout();
      throw new Error("Session expired. Please sign in again.");
    }

    throw new Error(message);
  }

  return data;
}

function setConnectionStatus(text, connected = false) {
  $("connection-status").textContent = text;
  const dot = document.querySelector(".status-dot");
  dot.style.background = connected ? "var(--green)" : "var(--muted)";
}

function setBusy(busy) {
  $("send-button").disabled = busy;
  $("login-button").disabled = busy;
  $("send-button").innerHTML = busy
    ? "Processing request…"
    : "Run request <span>→</span>";
}

function logout() {
  accessToken = null;
  $("password").value = "";
  show($("login-section"));
  show($("workspace"), false);
  show($("logout-button"), false);
  show($("result-section"), false);
  setConnectionStatus("Signed out");
}

async function login(event) {
  event.preventDefault();
  setMessage("login-error", "");

  const username = $("username").value.trim();
  const password = $("password").value;

  $("login-button").disabled = true;
  $("login-button").textContent = "Signing in…";

  try {
    // FastAPI OAuth2PasswordRequestForm expects form-encoded data,
    // not a JSON body.
    const form = new URLSearchParams();
    form.set("username", username);
    form.set("password", password);

    const response = await fetch(API.token, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: form.toString(),
    });

    const data = await readJson(response);

    if (!data.access_token) {
      throw new Error("Login succeeded but no access token was returned.");
    }

    accessToken = data.access_token;

    show($("login-section"), false);
    show($("workspace"));
    show($("logout-button"));
    setConnectionStatus("Authenticated", true);
    showToast("Successfully signed in.");
  } catch (error) {
    setMessage("login-error", error.message);
  } finally {
    $("login-button").disabled = false;
    $("login-button").innerHTML = "Sign in <span>→</span>";
  }
}

function selectMode(mode) {
  selectedMode = mode;

  document.querySelectorAll(".model-card").forEach((card) => {
    const selected = card.dataset.mode === mode;
    card.classList.toggle("selected", selected);
    card.setAttribute("aria-pressed", String(selected));
  });
}

async function apiPost(path, payload) {
  if (!accessToken) {
    throw new Error("Please sign in before sending a request.");
  }

  const response = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(payload),
  });

  return readJson(response);
}

function getModelLabel(model, provider) {
  if (model && model.includes("SmolLM2")) {
    return "SmolLM2-360M";
  }

  if (provider === "gemini") {
    return model || "Gemini";
  }

  return model || "Unknown";
}

async function runPrompt() {
  setMessage("request-error", "");

  const prompt = $("prompt").value.trim();

  if (!prompt) {
    setMessage("request-error", "Please enter a prompt.");
    $("prompt").focus();
    return;
  }

  if (!accessToken) {
    setMessage("request-error", "Please sign in first.");
    return;
  }

  show($("result-section"), false);
  setBusy(true);

  try {
    let routing = null;
    let endpoint;

    if (selectedMode === "router") {
      // The router only chooses the model; it does not generate text.
      routing = await apiPost(API.router, { prompt });

      if (routing.selected_model === "slm") {
        endpoint = API.slm;
      } else if (routing.selected_model === "llm") {
        endpoint = API.llm;
      } else {
        throw new Error(
          "Router returned an unexpected model: " +
            String(routing.selected_model)
        );
      }
    } else {
      endpoint = API[selectedMode];
    }

    // Generate the response using the chosen model endpoint.
    const result = await apiPost(endpoint, { prompt });

    renderResult(result, routing);
    setConnectionStatus("API request successful", true);
  } catch (error) {
    setMessage("request-error", error.message);
    setConnectionStatus("Request failed");
  } finally {
    setBusy(false);
  }
}

function renderResult(result, routing) {
  lastResponse = result.response || "";

  $("response-text").textContent =
    lastResponse || "(The model returned an empty response.)";

  $("metric-model").textContent = getModelLabel(
    result.selected_model,
    result.provider
  );

  $("metric-provider").textContent = result.provider || "—";

  $("metric-latency").textContent =
    result.latency_ms != null ? `${result.latency_ms} ms` : "—";

  const score = result.injection_probability;
  $("metric-injection").textContent =
    score != null ? `${(Number(score) * 100).toFixed(1)}%` : "—";

  $("security-injection").textContent =
    score != null
      ? `Passed · ${(Number(score) * 100).toFixed(1)}% risk`
      : "Not reported";

  const piiTypes = result.pii_types_redacted || [];
  $("security-pii").textContent = piiTypes.length
    ? `Redacted: ${piiTypes.join(", ")}`
    : "No PII types reported";

  show($("routing-card"), Boolean(routing));

  if (routing) {
    $("routing-model").textContent = getModelLabel(
      routing.model_name,
      routing.selected_model
    );

    $("routing-reason").textContent = routing.reason || "";
  }

  const sanitized = result.redacted_prompt;
  show($("sanitized-details"), typeof sanitized === "string");

  if (typeof sanitized === "string") {
    $("sanitized-prompt").textContent = sanitized;
  }

  $("result-title").textContent = "Model response";
  $("result-status").textContent = "Completed";

  show($("result-section"));
  $("result-section").scrollIntoView({
    behavior: "smooth",
    block: "start",
  });
}

async function copyResponse() {
  if (!lastResponse) {
    showToast("There is no response to copy.");
    return;
  }

  try {
    await navigator.clipboard.writeText(lastResponse);
    showToast("Response copied.");
  } catch {
    showToast("Clipboard unavailable in this browser.");
  }
}

$("login-form").addEventListener("submit", login);
$("send-button").addEventListener("click", runPrompt);
$("logout-button").addEventListener("click", logout);
$("copy-button").addEventListener("click", copyResponse);

$("prompt").addEventListener("input", () => {
  $("character-count").textContent = `${$("prompt").value.length} characters`;
});

document.querySelectorAll(".model-card").forEach((card) => {
  card.addEventListener("click", () => selectMode(card.dataset.mode));
});

$("prompt").addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    runPrompt();
  }
});

// Check whether the UI is being served by the backend.
fetch("/health")
  .then((response) => {
    setConnectionStatus(
      response.ok ? "API available" : "API health check failed",
      response.ok
    );
  })
  .catch(() => setConnectionStatus("API unavailable"));
