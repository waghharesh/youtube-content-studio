import json
import os
from pathlib import Path
from typing import Any, Dict, List
import dotenv
import google.generativeai as genai  # noqa: F401
import requests

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
    "gemini-2.0-flash-lite",
    "gemini-2.5-pro",
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
  "tags": ["flattened list combining all long_tail, mid_tier, and broad tags"],
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


def generate_seo_and_script(topic: str) -> Dict[str, Any]:
    """
    Call Gemini Flash in JSON mode (using REST `x-goog-api-key` for both `AQ.` and `AIza` keys)
    to generate SEO titles, 3-tier tags, a ~230-word spoken script, and stock video search queries.
    Includes automatic model discovery and zero-cost fallback so the pipeline never crashes.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    user_prompt = (
        f"Topic: {topic}\n\n"
        "Generate the complete SEO metadata package, 3-tier tags (long-tail, mid-tier, broad), "
        "a ~230-word high-retention spoken script (for a 1.5-2 minute video), and 6 Pexels stock video search queries."
    )

    if api_key and api_key != "your_gemini_api_key_here":
        for model_name in MODEL_CANDIDATES:
            for base_url in (
                f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent",
                f"https://aiplatform.googleapis.com/v1/publishers/google/models/{model_name}:generateContent",
            ):
                try:
                    resp = requests.post(
                        base_url,
                        headers={
                            "Content-Type": "application/json",
                            "x-goog-api-key": api_key,
                        },
                        params={"key": api_key} if "aiplatform" in base_url else None,
                        json={
                            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                            "generationConfig": {
                                "responseMimeType": "application/json",
                                "temperature": 0.7,
                            },
                        },
                        timeout=20,
                    )
                    if resp.ok:
                        body = resp.json()
                        text = body["candidates"][0]["content"]["parts"][0]["text"]
                        payload = _parse_json_text(text)
                        print(f"[SEO Engine] Generated content using Gemini model: {model_name}")
                        return _normalize_seo_payload(payload, topic)
                except Exception as err:
                    print(f"[SEO Engine] {model_name} attempt notice: {err}")
                    continue

    # Zero-cost fallback if Gemini API key is restricted or unavailable
    try:
        resp = requests.post(
            "https://text.pollinations.ai/openai",
            json={
                "model": "openai",
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=25,
        )
        if resp.ok:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            payload = _parse_json_text(content)
            print("[SEO Engine] Generated content via zero-cost OpenAI JSON fallback.")
            return _normalize_seo_payload(payload, topic)
    except Exception:
        pass

    print("[SEO Engine] Using built-in high-retention script generator.")
    return _build_deterministic_fallback(topic)


def _parse_json_text(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").removeprefix("json").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def _build_deterministic_fallback(topic: str) -> Dict[str, Any]:
    words = [w for w in topic.replace("-", " ").split() if len(w) > 2]
    kw = " ".join(words[:3]) if words else topic
    script = (
        f"Have you noticed how fast {topic} is changing everything around us? "
        f"Most people only see the headlines, but what is happening behind the scenes with {topic} "
        f"is far bigger than almost anyone realizes. First, the speed of adoption has completely "
        f"shattered previous records. Tasks and workflows that used to take entire teams weeks "
        f"to coordinate are now happening in seconds with higher precision and lower cost. "
        f"Second, the barrier to entry has collapsed. You no longer need a massive enterprise budget "
        f"to leverage the core breakthroughs driving {topic}. Independent creators, engineers, and "
        f"small teams are building tools today that rival major tech giants. "
        f"Third, the real advantage goes to those who adapt early. Instead of waiting for the dust to settle, "
        f"focus on mastering the fundamentals and integrating these workflows into your daily routine right now. "
        f"When you look back twelve months from today, this will be the exact turning point where the landscape shifted. "
        f"Follow for more deep dives into the trends shaping our future."
    )
    return _normalize_seo_payload(
        {
            "title": f"{topic[:55]}: What Everyone Is Missing",
            "description": f"Here is the complete breakdown of {topic} and why it matters right now.\n\n#Shorts #TechTrends #Future #Innovation",
            "tags_tiered": {
                "long_tail": [f"{topic.lower()} explained", f"how {kw.lower()} works", f"future of {kw.lower()} 2026"],
                "mid_tier": [kw.lower(), "emerging technology", "tech breakdown", "future trends"],
                "broad": ["technology", "innovation", "shorts"],
            },
            "script": script,
            "pexels_queries": [
                kw,
                "futuristic technology",
                "digital innovation",
                "modern workspace",
                "data network",
                "city skyline night",
            ],
        },
        topic,
    )


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
