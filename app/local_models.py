import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

SMALL_MODEL = "HuggingFaceTB/SmolLM2-360M-Instruct"
LARGE_MODEL = "HuggingFaceTB/SmolLM2-1.7B-Instruct"

# Select the best available device on your Mac
if torch.backends.mps.is_available():
    DEVICE = "mps"  # Apple Silicon GPU
elif torch.cuda.is_available():
    DEVICE = "cuda"
else:
    DEVICE = "cpu"

print(f"Using device: {DEVICE}")

models = {}


def load_model(model_name):
    if model_name in models:
        return models[model_name]

    print(f"Loading {model_name}...")

    tokenizer = AutoTokenizer.from_pretrained(model_name)

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float32,
    ).to(DEVICE)

    model.eval()
    models[model_name] = (tokenizer, model)

    print(f"Loaded {model_name}")
    return tokenizer, model


def generate_response(prompt, model_name, max_new_tokens=150):
    tokenizer, model = load_model(model_name)

    messages = [{"role": "user", "content": prompt}]

    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )

    generated_tokens = outputs[0][inputs["input_ids"].shape[1] :]

    return tokenizer.decode(
        generated_tokens,
        skip_special_tokens=True,
    )


if __name__ == "__main__":
    prompt = "Explain JWT authentication in simple terms."

    print("\n--- Small model ---")
    print(generate_response(prompt, SMALL_MODEL))

    print("\n--- Large model ---")
    print(generate_response(prompt, LARGE_MODEL))
