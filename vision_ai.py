from google import genai
from google.genai import types

client = genai.Client()  # reads GEMINI_API_KEY

def ask(image_path, prompt, max_tokens=150):
    with open(image_path, "rb") as f:
        data = f.read()
    r = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=[types.Part.from_bytes(data=data, mime_type="image/jpeg"), prompt],
        config=types.GenerateContentConfig(temperature=0, max_output_tokens=max_tokens),
    )
    return r.text