"""Optional training script. Run in a training environment with requirements-train.txt."""
from pathlib import Path
from datasets import load_dataset
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
import joblib

out = Path("models/prompt_injection_pipeline.joblib")
out.parent.mkdir(parents=True, exist_ok=True)

dataset = load_dataset("deepset/prompt-injections", split="train")
df = dataset.to_pandas()
print("Columns:", list(df.columns))
print(df.head())
print("Label counts:", df["label"].value_counts().to_dict())

X = df["text"].astype(str)
y = df["label"].astype(int)  # verify label 1 means injection in the displayed dataset

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
model = Pipeline([
    ("tfidf", TfidfVectorizer(lowercase=True, ngram_range=(1, 2))),
    ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced")),
])
model.fit(X_train, y_train)
predictions = model.predict(X_test)
print(classification_report(y_test, predictions))
joblib.dump(model, out)
print("Saved:", out)
