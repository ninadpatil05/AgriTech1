"""Gemini-powered crop disease advice — English & Hindi.
Uses the Gemini REST API directly (no SDK) to avoid protobuf conflicts with TensorFlow.
"""
import hashlib
import json
import logging
import time

import requests
from flask import Blueprint, jsonify, request

import config

logger = logging.getLogger("agritech.advice")

advice_bp = Blueprint("advice", __name__)

GEMINI_MODELS = [
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

_PROMPT_TEMPLATE = """You are an expert agricultural scientist and crop doctor.
Detected disease: {disease}
Crop type: {crop_type}

Respond ONLY with this exact JSON structure (no markdown, no code fences):
{{
  "english": {{
    "treatment": ["step 1", "step 2", "step 3", "step 4"],
    "prevention": ["tip 1", "tip 2", "tip 3"],
    "urgency": "high"
  }},
  "hindi": {{
    "treatment": ["\u091a\u0930\u0923 1", "\u091a\u0930\u0923 2", "\u091a\u0930\u0923 3", "\u091a\u0930\u0923 4"],
    "prevention": ["\u0938\u0941\u091d\u093e\u0935 1", "\u0938\u0941\u091d\u093e\u0935 2", "\u0938\u0941\u091d\u093e\u0935 3"],
    "urgency": "\u0909\u091a\u094d\u091a"
  }}
}}

Rules:
- urgency must be one of: low/medium/high (English) and \u0915\u092e/\u092e\u0927\u094d\u092f\u092e/\u0909\u091a\u094d\u091a (Hindi)
- treatment: 3-5 actionable steps in simple farmer-friendly language
- prevention: 3-4 preventive tips
- If disease contains 'healthy', provide general care tips instead
- Keep language simple and practical for Indian farmers
"""


def _extract_json(text: str) -> dict:
    """Robustly parse a JSON object from Gemini output.

    Handles:
    - Markdown code fences (```json ... ``` or ``` ... ```)
    - Extra prose before/after the JSON object
    - Direct valid JSON
    """
    text = text.strip()
    # Strip markdown code fences (triple backtick blocks)
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])  # drop opening fence line
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fall back: find outermost { ... } and parse that
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
        raise


def _call_gemini(disease: str, crop_type: str) -> dict:
    api_key = config.GEMINI_API_KEY
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")

    # Sanitise raw PlantVillage class names so the model sees clean text
    disease_clean = disease.replace("___", " ").replace("_", " ").strip()
    prompt = _PROMPT_TEMPLATE.format(disease=disease_clean, crop_type=crop_type)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024},
    }

    for model in GEMINI_MODELS:
        url = GEMINI_API_BASE.format(model=model)
        logger.info(f"Calling Gemini ({model}) for disease: '{disease_clean}'")
        # Retry up to 3 times on 429 (free tier rate limit)
        for attempt in range(3):
            resp = requests.post(url, params={"key": api_key}, json=payload, timeout=30)
            if resp.status_code != 429:
                break
            wait = 5 * (attempt + 1)  # 5s, 10s, 15s
            logger.warning(f"Gemini 429 rate-limit on {model}, attempt {attempt + 1}/3, waiting {wait}s")
            time.sleep(wait)

        if resp.status_code == 429:
            logger.warning(f"Gemini {model} exhausted after 3 retries, trying next model.")
            continue  # try next model
        resp.raise_for_status()
        result = resp.json()
        raw = result["candidates"][0]["content"]["parts"][0]["text"]
        logger.info(f"Gemini ({model}) responded successfully for '{disease_clean}'")
        return _extract_json(raw)

    logger.error("Gemini rate limit hit on all models for disease: '%s'", disease_clean)
    raise Exception(
        "Gemini rate limit hit on all models. "
        "The free tier allows 15 requests/min. Please wait ~1 minute and try again."
    )


# ── In-memory advice cache ────────────────────────────────────────────────────
_advice_cache: dict = {}
CACHE_MAX_SIZE = 100  # max unique disease+crop combinations to cache


def _cache_key(disease: str, crop_type: str) -> str:
    return hashlib.md5(f"{disease.lower()}|{crop_type.lower()}".encode()).hexdigest()


def get_cached_advice(disease: str, crop_type: str) -> dict:
    key = _cache_key(disease, crop_type)
    if key in _advice_cache:
        logger.info(f"Cache hit for: '{disease}' / '{crop_type}'")
        return _advice_cache[key]
    try:
        result = _call_gemini(disease, crop_type)
    except Exception as e:
        logger.error(f"Gemini failed for '{disease}': {e}", exc_info=True)
        raise
    if len(_advice_cache) < CACHE_MAX_SIZE:
        _advice_cache[key] = result
        logger.info(f"Cached advice for '{disease}' / '{crop_type}' (cache size: {len(_advice_cache)})")
    return result


@advice_bp.route("/advice", methods=["POST"])
def get_advice():
    body = request.get_json(silent=True) or {}
    disease = str(body.get("disease", "")).strip()
    crop_type = str(body.get("crop_type", "Unknown")).strip()

    if not disease:
        return jsonify({"error": "disease field is required"}), 400

    if not config.GEMINI_API_KEY:
        return jsonify({
            "error": "Gemini API key not configured.",
            "message": (
                "Open the .env file and set GEMINI_API_KEY=your_key_here, "
                "then restart the server."
            ),
        }), 503

    try:
        advice = get_cached_advice(disease, crop_type)
        return jsonify({"status": "success", "advice": advice})
    except requests.HTTPError as e:
        return jsonify({"error": f"Gemini API error: {e.response.status_code}", "detail": e.response.text}), 502
    except json.JSONDecodeError as e:
        return jsonify({"error": "Failed to parse Gemini response as JSON", "detail": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@advice_bp.route("/advice/clear-cache", methods=["POST"])
def clear_cache():
    _advice_cache.clear()
    return jsonify({"status": "cache cleared"})
