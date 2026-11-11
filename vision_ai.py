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

MODEL = "gemini-3.5-flash-lite"


def _contents(image_path, prompt):
    with open(image_path, "rb") as f:
        data = f.read()
    return [types.Part.from_bytes(data=data, mime_type="image/jpeg"), prompt]


def _config(max_tokens):
    return types.GenerateContentConfig(temperature=0, max_output_tokens=max_tokens)


def ask(image_path, prompt, max_tokens=150):
    r = client.models.generate_content(
        model=MODEL, contents=_contents(image_path, prompt), config=_config(max_tokens))
    return r.text


def ask_stream(image_path, prompt, max_tokens=150):
    """Like ask(), but yields the answer in pieces as Gemini writes it, so speech can start sooner."""
    for chunk in client.models.generate_content_stream(
            model=MODEL, contents=_contents(image_path, prompt), config=_config(max_tokens)):
        if chunk.text:
            yield chunk.text