from pathlib import Path
import joblib
from app.config import CLASSIFIER_PATH

_model = None
_error = None

def load_classifier():
    global _model, _error
    path = Path(CLASSIFIER_PATH)
    if not path.exists():
        _model = None
        _error = f"Classifier artifact not found: {path}"
        return
    try:
        _model = joblib.load(path)
        _error = None
    except Exception as exc:
        _model = None
        _error = f"Could not load classifier: {type(exc).__name__}"

def injection_probability(prompt: str) -> float:
    if _model is None:
        raise RuntimeError(_error or "Classifier is not loaded")
    probabilities = _model.predict_proba([prompt])[0]
    classes = list(_model.classes_)
    if 1 not in classes:
        raise RuntimeError("Expected label 1 to mean prompt injection.")
    return float(probabilities[classes.index(1)])
