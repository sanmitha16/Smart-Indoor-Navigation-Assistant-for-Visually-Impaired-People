from google import genai
from google.genai import types

client = genai.Client(  # still reads GEMINI_API_KEY
    http_options=types.HttpOptions(
        timeout=15000,  # give up after 15 s (ask.py's limit is 20 s)
        retry_options=types.HttpRetryOptions(
            attempts=2,       # one try plus one retry, not a long silent loop
            initial_delay=1.0,
            max_delay=3.0,
        ),
    )
)

def ask(image_path, prompt, max_tokens=150):
    with open(image_path, "rb") as f:
        data = f.read()
    r = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=[types.Part.from_bytes(data=data, mime_type="image/jpeg"), prompt],
        config=types.GenerateContentConfig(temperature=0, max_output_tokens=max_tokens),
    )
    return r.text