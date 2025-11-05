import os
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Analytica Summarizer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SummaryResponse(BaseModel):
    summary: str
    tone: str
    length: str
    language: str
    bullets: bool
    used_input: str


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!", "endpoints": ["/summarize", "/test"]}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Simple environment check. Database is optional for this app."""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Used",
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set",
        "connection_status": "N/A",
        "collections": [],
    }
    try:
        from database import db  # type: ignore

        if db is not None:
            try:
                collections = db.list_collection_names()
                response.update({
                    "database": "✅ Available",
                    "connection_status": "Connected",
                    "collections": collections[:10],
                })
            except Exception:
                response["database"] = "⚠️ Available but not connected"
    except Exception:
        # Database module may not be configured in all environments; that's OK.
        pass
    return response


# --- Core Summarization Endpoint ---
@app.post("/summarize", response_model=SummaryResponse)
async def summarize(
    tone: str = Form("analytical"),
    length: str = Form("short"),
    language: str = Form("en"),
    bullets: bool = Form(False),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    image: Optional[UploadFile] = File(None),
    authorization: Optional[str] = Header(default=None, convert_underscores=False),
    x_api_key: Optional[str] = Header(default=None, convert_underscores=False),
):
    """
    Accepts multipart form-data containing any combination of:
    - text (string)
    - file (UploadFile)
    - image (UploadFile)
    Along with options: tone, length, language, bullets.

    Returns a concise, structured summary. This demo uses a lightweight
    server-side summarizer so you can connect the UI end-to-end immediately.

    You can replace the summarization logic with a call to your preferred LLM.
    """

    # Optional: enforce API key if you want. Currently permissive for quick start.
    api_key = None
    if authorization and authorization.lower().startswith("bearer "):
        api_key = authorization.split(" ", 1)[1].strip()
    if not api_key and x_api_key:
        api_key = x_api_key

    # Read content preference: text > file > image
    used_input = ""
    content = (text or "").strip()

    if not content and file is not None:
        try:
            raw = await file.read()
            content = raw.decode("utf-8", errors="ignore")
            used_input = file.filename or "uploaded file"
        except Exception:
            raise HTTPException(status_code=400, detail="Could not read uploaded file as text.")

    if not content and image is not None:
        # For demo: just acknowledge the image; real OCR may be added later.
        used_input = image.filename or "uploaded image"
        content = f"[Image: {used_input}]"

    if not content:
        raise HTTPException(status_code=400, detail="No input provided. Submit text, a file, or an image.")

    # Simple server-side summarizer (replace with your LLM call as needed)
    base = " ".join(content.split())
    # Determine length caps
    length_caps = {"short": 160, "medium": 320, "detailed": 480}
    cap = length_caps.get(length.lower(), 160)
    truncated = (base[: cap - 1] + "…") if len(base) > cap else base

    # Tone prefix
    tone_map = {
        "analytical": "Analytical summary:",
        "executive": "Executive brief:",
        "neutral": "Summary:",
        "technical": "Technical digest:",
    }
    tone_prefix = tone_map.get(tone.lower(), "Summary:")

    # Bullets or paragraph
    if bullets:
        first_sentence = (truncated.split(".")[0] or truncated).strip()
        body = (
            f"• Key point 1: {first_sentence}\n"
            f"• Key point 2: Impact and implications.\n"
            f"• Next steps: Actions to take."
        )
    else:
        body = truncated

    # Optional very light language tag (doesn't translate; for demo only)
    lang_label = {
        "en": "",
        "es": " (ES)",
        "de": " (DE)",
        "fr": " (FR)",
    }.get(language.lower(), "")

    summary_text = f"{tone_prefix}{lang_label}\n{body}"

    return SummaryResponse(
        summary=summary_text,
        tone=tone,
        length=length,
        language=language,
        bullets=bullets,
        used_input=used_input or ("text" if text else ""),
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
