import json
import os
from pathlib import Path
from typing import Any, Dict, List
import dotenv
import google.generativeai as genai

_orig_load_dotenv = dotenv.load_dotenv


def _safe_load_dotenv(*args, **kwargs):
    try:
        return _orig_load_dotenv(*args, **kwargs)
    except PermissionError:
        fallback = Path(__file__).parent / "config.env"
        if fallback.exists():
            return _orig_load_dotenv(dotenv_path=str(fallback))
        return False


dotenv.load_dotenv = _safe_load_dotenv
_safe_load_dotenv()
if (Path(__file__).parent / "config.env").exists():
    _orig_load_dotenv(dotenv_path=str(Path(__file__).parent / "config.env"))

MODEL_CANDIDATES = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-flash-latest",
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash",
]

SYSTEM_PROMPT = """
You are an expert YouTube growth strategist and scriptwriter specializing in high-retention 1.5 to 2-minute vertical videos (1080x1920).
Given a topic, return a strictly valid JSON object with the following structure:
{
  "title": "High-CTR SEO-optimized primary title (under 70 characters)",
  "title_variants": [
    "Alternative catchy title 1",
    "Alternative catchy title 2",
    "Alternative catchy title 3"
  ],
  "description": "SEO-optimized YouTube description including a strong hook in the first 2 lines, key takeaways, and relevant hashtags.",
  "tags_tiered": {
    "long_tail": ["specific multi-word search phrase 1", "specific phrase 2", "specific phrase 3", "specific phrase 4"],
    "mid_tier": ["moderately competitive keyword 1", "keyword 2", "keyword 3", "keyword 4"],
    "broad": ["broad category tag 1", "broad tag 2", "broad tag 3"]
  },
  "tags": ["flattened list combining all long_tail, mid-tier, and broad tags"],
  "script": "Engaging spoken voiceover script of approximately 230 words (1.5 to 2 minutes at natural speaking pace). Do NOT include stage directions, speaker labels, or timestamps—only the exact words to be spoken.",
  "pexels_queries": [
    "vertical cinematic search query 1",
    "vertical cinematic search query 2",
    "vertical cinematic search query 3",
    "vertical cinematic search query 4",
    "vertical cinematic search query 5",
    "vertical cinematic search query 6"
  ]
}
""".strip()


def configure_gemini() -> None:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_gemini_api_key_here":
        raise ValueError(
            "GEMINI_API_KEY is missing or still set to the placeholder in .env"
        )
    genai.configure(api_key=api_key)


def _get_working_model_names() -> List[str]:
    """Return candidate model names, appending any available models from ListModels."""
    candidates = list(MODEL_CANDIDATES)
    try:
        for m in genai.list_models():
            methods = getattr(m, "supported_generation_methods", []) or []
            if "generateContent" in methods:
                name = m.name.replace("models/", "")
                if name not in candidates:
                    candidates.append(name)
    except Exception:
        pass
    return candidates


def generate_seo_and_script(topic: str) -> Dict[str, Any]:
    """
    Call Gemini Flash in JSON mode to generate SEO titles, 3-tier tags,
    a ~230-word spoken script, and stock video search queries for a given topic.
    """
    configure_gemini()

    user_prompt = (
        f"Topic: {topic}\n\n"
        "Generate the complete SEO metadata package, 3-tier tags (long-tail, mid-tier, broad), "
        "a ~230-word high-retention spoken script (for a 1.5-2 minute video), and 6 Pexels stock video search queries."
    )

    last_err = None
    response = None
    for model_name in _get_working_model_names():
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=SYSTEM_PROMPT,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.7,
                },
            )
            response = model.generate_content(user_prompt)
            print(f"[SEO Engine] Generated content using model: {model_name}")
            break
        except Exception as err:
            last_err = err
            continue

    if response is None:
        raise RuntimeError(f"All Gemini models failed. Last error: {last_err}")

    text = response.text.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    payload = json.loads(text)
    return _normalize_seo_payload(payload, topic)


def _normalize_seo_payload(payload: Dict[str, Any], topic: str) -> Dict[str, Any]:
    title = str(payload.get("title") or f"{topic}: What You Need to Know").strip()
    description = str(payload.get("description") or f"Deep dive into {topic}.").strip()
    script = str(payload.get("script") or "").strip()

    tags_tiered = payload.get("tags_tiered") or {}
    long_tail: List[str] = [str(t) for t in tags_tiered.get("long_tail", [])]
    mid_tier: List[str] = [str(t) for t in tags_tiered.get("mid_tier", [])]
    broad: List[str] = [str(t) for t in tags_tiered.get("broad", [])]

    flat_tags: List[str] = [str(t) for t in payload.get("tags", [])]
    if not flat_tags:
        flat_tags = long_tail + mid_tier + broad

    queries: List[str] = [
        str(q).strip() for q in payload.get("pexels_queries", []) if str(q).strip()
    ]
    if not queries:
        queries = [topic, "technology abstract", "future innovation"]

    return {
        "title": title,
        "title_variants": payload.get("title_variants", [title]),
        "description": description,
        "tags_tiered": {
            "long_tail": long_tail,
            "mid_tier": mid_tier,
            "broad": broad,
        },
        "tags": flat_tags,
        "script": script,
        "pexels_queries": queries,
    }
