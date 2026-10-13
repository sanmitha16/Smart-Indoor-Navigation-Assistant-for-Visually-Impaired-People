import time
from google import genai
from google.genai import types

client = genai.Client(http_options=types.HttpOptions(timeout=30000))  # 30 s limit
MODEL = "gemini-3.5-flash-lite"
PROMPT = "Name the main object held in front of the camera in 1 to 4 words. If unsure, say 'not sure'."

OPTIONS = {
    "no thinking setting (old version)": None,
    "thinking_level=minimal": types.ThinkingConfig(thinking_level="minimal"),
    "thinking_budget=0": types.ThinkingConfig(thinking_budget=0),
}

data = open("frame.jpg", "rb").read()

for name, th in OPTIONS.items():
    for run in range(3):
        kw = dict(temperature=0, max_output_tokens=40)
        if th is not None:
            kw["thinking_config"] = th
        t = time.time()
        try:
            r = client.models.generate_content(
                model=MODEL,
                contents=[types.Part.from_bytes(data=data, mime_type="image/jpeg"), PROMPT],
                config=types.GenerateContentConfig(**kw),
            )
            print(f"{name} | run {run+1}: {time.time()-t:.1f}s -> {(r.text or '').strip()}")
        except Exception as e:
            print(f"{name} | run {run+1}: ERROR after {time.time()-t:.1f}s -> {str(e)[:150]}")