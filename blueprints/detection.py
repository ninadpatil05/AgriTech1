"""
Crop disease detection — Gemini Vision API (REST, no SDK dependency).
Uses a model fallback chain so the first available model wins.
"""
import base64
import io
import json
import logging
import os
import sqlite3

import requests
from flask import Blueprint, jsonify, request
from PIL import Image

import config
from blueprints.disease_db import DISEASE_DB

logger = logging.getLogger("agritech.detection")
detection_bp = Blueprint("detection", __name__)

# ── Model fallback chain ───────────────────────────────────────────────────────
# Tried in order; first one that returns 200 wins.
# gemini-3.1-flash-lite-preview → confirmed free-tier, replaced deprecated 2.5-flash-lite
# gemini-2.5-flash              → stable GA, may need billing
# gemini-2.5-flash-preview-05-20→ latest preview
# gemini-2.0-flash              → free-tier GA (until Jun 2026)
# gemini-2.0-flash-lite         → lightest free-tier
_MODEL_CANDIDATES = [
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]
_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# ── Disease class list ────────────────────────────────────────────────────────
DISEASE_CLASSES = []
DISEASE_CLASSES_PATH = os.path.join(str(config.MODEL_DIR), "disease_classes.json")

_FALLBACK_CLASSES = [
    "Apple___Apple_scab", "Apple___Black_rot", "Apple___Cedar_apple_rust",
    "Apple___healthy", "Blueberry___healthy",
    "Cherry_(including_sour)___Powdery_mildew", "Cherry_(including_sour)___healthy",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn_(maize)___Common_rust_", "Corn_(maize)___Northern_Leaf_Blight",
    "Corn_(maize)___healthy", "Grape___Black_rot", "Grape___Esca_(Black_Measles)",
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)", "Grape___healthy",
    "Orange___Haunglongbing_(Citrus_greening)", "Peach___Bacterial_spot",
    "Peach___healthy", "Pepper,_bell___Bacterial_spot", "Pepper,_bell___healthy",
    "Potato___Early_blight", "Potato___Late_blight", "Potato___healthy",
    "Raspberry___healthy", "Soybean___healthy", "Squash___Powdery_mildew",
    "Strawberry___Leaf_scorch", "Strawberry___healthy",
    "Tomato___Bacterial_spot", "Tomato___Early_blight", "Tomato___Late_blight",
    "Tomato___Leaf_Mold", "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites Two-spotted_spider_mite", "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus", "Tomato___Tomato_mosaic_virus",
    "Tomato___healthy",
]


def _load_disease_classes():
    global DISEASE_CLASSES
    try:
        if os.path.isfile(DISEASE_CLASSES_PATH):
            with open(DISEASE_CLASSES_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, list) and loaded:
                DISEASE_CLASSES = [str(c) for c in loaded]
                return
    except Exception as e:
        logger.warning(f"Could not load disease_classes.json: {e}")
    DISEASE_CLASSES = _FALLBACK_CLASSES[:]


_load_disease_classes()


def _ensure_db():
    try:
        conn = sqlite3.connect(config.DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                disease_class TEXT,
                confidence REAL,
                timestamp TEXT
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"DB init failed: {e}")


_ensure_db()

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_class_name(class_name: str) -> tuple:
    if "___" in class_name:
        parts = class_name.split("___", 1)
        crop = parts[0].replace("_", " ").replace(",", "").strip()
        disease = parts[1].replace("_", " ").strip().title()
        if "healthy" in disease.lower():
            disease = "Healthy (No Disease)"
        return crop, disease
    return "Unknown", class_name.replace("_", " ").title()


def _to_jpeg(img: Image.Image, max_px: int = 1024) -> bytes:
    img = img.convert("RGB")
    if max(img.size) > max_px:
        img.thumbnail((max_px, max_px), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    return buf.getvalue()


# ── Gemini REST call with model fallback ──────────────────────────────────────

_PROMPT = """\
You are an expert agricultural plant disease detection AI (PlantVillage dataset).

Examine the crop/plant image carefully.

AVAILABLE DISEASE CLASSES — pick the single closest match:
{classes}

Respond with VALID JSON ONLY (no markdown, no preamble):
{{
  "is_plant": <true|false>,
  "raw_class": "<exact class string from the list>",
  "crop_type": "<human-readable crop name>",
  "disease_name": "<human-readable disease, or 'Healthy (No Disease)'>",
  "confidence": <0.0-1.0>,
  "description": "<2-3 sentences: visible symptoms and reasoning>"
}}"""


def _call_gemini(jpeg_bytes: bytes, api_key: str) -> tuple:
    """
    Try each model in _MODEL_CANDIDATES until one succeeds.
    Returns (analysis_dict, model_used) or raises the last exception.
    """
    classes_str = "\n".join(f"  - {c}" for c in DISEASE_CLASSES)
    prompt = _PROMPT.format(classes=classes_str)

    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {
                    "mime_type": "image/jpeg",
                    "data": base64.b64encode(jpeg_bytes).decode(),
                }},
                {"text": prompt},
            ]
        }],
        "generationConfig": {
            "temperature": 0.05,
            "maxOutputTokens": 600,
        },
    }

    last_err = None
    for model in _MODEL_CANDIDATES:
        url = f"{_API_BASE}/{model}:generateContent"
        try:
            resp = requests.post(
                url,
                params={"key": api_key},
                json=payload,
                timeout=45,
            )

            if resp.status_code == 404:
                logger.warning(f"Model {model} returned 404 — trying next.")
                last_err = Exception(f"Model {model}: 404 Not Found")
                continue

            if resp.status_code == 403:
                body = resp.text[:300]
                if "allowlist" in body.lower() or "not allowed" in body.lower():
                    raise PermissionError(
                        "API key has host/IP restrictions. "
                        "Go to https://aistudio.google.com/app/apikey, "
                        "create a new key with NO restrictions, "
                        "and replace GEMINI_API_KEY in your .env file."
                    )
                raise PermissionError(f"403 Forbidden: {body}")

            resp.raise_for_status()

            raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            # Strip markdown fences Gemini sometimes adds despite instructions
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            analysis = json.loads(raw)
            logger.info(f"Used model: {model}")
            return analysis, model

        except (PermissionError, json.JSONDecodeError, KeyError) as e:
            raise   # don't retry on auth or parse errors
        except requests.exceptions.RequestException as e:
            last_err = e
            logger.warning(f"Network error on {model}: {e}")
            continue

    raise last_err or RuntimeError("All Gemini models failed.")


# ── Routes ────────────────────────────────────────────────────────────────────

@detection_bp.route("/detect", methods=["POST"])
def detect():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400
    file = request.files["image"]
    if not file or file.filename == "":
        return jsonify({"error": "No image selected"}), 400

    api_key = config.GEMINI_API_KEY
    if not api_key:
        return jsonify({
            "status": "error",
            "error": "GEMINI_API_KEY not set.",
            "message": "Add GEMINI_API_KEY=<your-key> to .env and restart.",
        }), 503

    # Open + convert image
    try:
        img = Image.open(file.stream)
        jpeg_bytes = _to_jpeg(img)
    except Exception as e:
        logger.warning(f"Bad image upload: {e}")
        return jsonify({"error": "Invalid image. Please upload a JPEG or PNG."}), 400

    # Call Gemini
    try:
        analysis, model_used = _call_gemini(jpeg_bytes, api_key)
        logger.info(f"Gemini response ({model_used}): {analysis}")

    except PermissionError as e:
        logger.error(f"Gemini auth error: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
        }), 403

    except requests.exceptions.HTTPError as e:
        logger.error(f"Gemini HTTP error: {e}")
        return jsonify({"error": f"Gemini API HTTP error: {e}"}), 502

    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Cannot reach Gemini API. Check internet connection."}), 502

    except json.JSONDecodeError:
        return jsonify({"error": "Gemini returned unexpected output. Please retry."}), 500

    except Exception as e:
        logger.error(f"Gemini call failed: {e}", exc_info=True)
        return jsonify({"error": f"Detection failed: {e}"}), 500

    # Plant check
    if not analysis.get("is_plant", True):
        return jsonify({
            "status": "error",
            "message": "No plant detected. Please upload a clear photo of a crop leaf.",
        })

    raw_class  = analysis.get("raw_class", "").strip()
    crop_name  = analysis.get("crop_type", "Unknown")
    disease_name = analysis.get("disease_name", "Unknown")
    confidence = min(max(float(analysis.get("confidence", 0.5)), 0.0), 1.0)
    gemini_desc = analysis.get("description", "")

    # Enrich from disease DB (exact, then loose match)
    report_data = DISEASE_DB.get(raw_class, {})
    if not report_data:
        for key in DISEASE_DB:
            if key.lower().replace("_", "") == raw_class.lower().replace("_", ""):
                report_data = DISEASE_DB[key]
                break

    if not report_data:
        report_data = {
            "crop_type": crop_name,
            "disease": disease_name,
            "description": gemini_desc or f"{disease_name} detected on {crop_name}.",
            "pesticide_treatments": "Use AI Advice for treatment recommendations.",
            "preventive_measures": "Use AI Advice for prevention tips.",
        }

    if "___" in raw_class:
        crop_name, disease_name = parse_class_name(raw_class)

    # Log to DB
    try:
        conn = sqlite3.connect(config.DB_PATH)
        conn.execute(
            "INSERT INTO detections (disease_class, confidence, timestamp) "
            "VALUES (?, ?, datetime('now'))",
            (raw_class, confidence),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"DB log failed: {e}")

    logger.info(f"Detection OK: {raw_class} ({confidence:.1%}) via {model_used}")
    return jsonify({
        "status": "success",
        "crop_type": crop_name,
        "disease_detected": disease_name,
        "raw_class": raw_class,
        "confidence": confidence,
        "model_used": model_used,
        "report": {
            "disease":                    report_data.get("disease"),
            "description":                report_data.get("description"),
            "causes":                     report_data.get("causes"),
            "soil_requirements":          report_data.get("soil_requirements"),
            "recommended_fertilizers":    report_data.get("recommended_fertilizers"),
            "pesticide_treatments":       report_data.get("pesticide_treatments"),
            "soil_moisture":              report_data.get("soil_moisture"),
            "preventive_measures":        report_data.get("preventive_measures"),
            "additional_recommendations": report_data.get("additional_recommendations"),
        },
    })


@detection_bp.route("/test-gemini", methods=["GET"])
def test_gemini():
    """
    Diagnostic endpoint — hit /api/test-gemini in your browser to see
    exactly which models work with your API key.
    """
    api_key = config.GEMINI_API_KEY
    if not api_key:
        return jsonify({"ok": False, "error": "GEMINI_API_KEY not set in .env"}), 503

    results = {}
    for model in _MODEL_CANDIDATES:
        url = f"{_API_BASE}/{model}:generateContent"
        try:
            resp = requests.post(
                url,
                params={"key": api_key},
                json={"contents": [{"parts": [{"text": "Reply with: ok"}]}],
                      "generationConfig": {"maxOutputTokens": 5}},
                timeout=15,
            )
            if resp.status_code == 200:
                results[model] = "✅ working"
            elif resp.status_code == 404:
                results[model] = "❌ 404 — model not available for your key/plan"
            elif resp.status_code == 403:
                body = resp.text[:200]
                if "allowlist" in body.lower():
                    results[model] = (
                        "❌ 403 — API key has host/IP restrictions. "
                        "Go to https://aistudio.google.com/app/apikey and create "
                        "a new key with NO restrictions."
                    )
                else:
                    results[model] = f"❌ 403 Forbidden: {body}"
            else:
                results[model] = f"❌ {resp.status_code}: {resp.text[:100]}"
        except Exception as e:
            results[model] = f"❌ Exception: {e}"

    working = [m for m, s in results.items() if "✅" in s]
    return jsonify({
        "ok": len(working) > 0,
        "working_models": working,
        "all_results": results,
        "fix_if_all_fail": (
            "Your API key likely has restrictions. "
            "Visit https://aistudio.google.com/app/apikey → Create a new API key "
            "→ choose 'No restriction' → copy the new key → paste it into "
            "your .env as GEMINI_API_KEY=<new_key> → restart Flask."
        ),
    })


@detection_bp.route("/stats", methods=["GET"])
def get_stats():
    try:
        conn = sqlite3.connect(config.DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM detections")
        total = cur.fetchone()[0]
        cur.execute("""SELECT disease_class, COUNT(*) c FROM detections
                       GROUP BY disease_class ORDER BY c DESC LIMIT 1""")
        top = cur.fetchone()
        cur.execute("""SELECT disease_class, COUNT(*) c FROM detections
                       GROUP BY disease_class ORDER BY c DESC LIMIT 5""")
        breakdown = [{"disease_class": r[0], "count": r[1]} for r in cur.fetchall()]
        conn.close()
        return jsonify({"total_detections": total,
                        "top_disease": top[0] if top else "N/A",
                        "breakdown": breakdown})
    except Exception as e:
        return jsonify({"total_detections": 0, "top_disease": "N/A",
                        "breakdown": [], "error": str(e)})


@detection_bp.route("/health", methods=["GET"])
def health():
    gemini_ok = bool(config.GEMINI_API_KEY)
    return jsonify({
        "status": "ok" if gemini_ok else "degraded",
        "engine": "gemini-vision (REST fallback chain)",
        "models_tried": _MODEL_CANDIDATES,
        "gemini_configured": gemini_ok,
        "disease_classes_loaded": len(DISEASE_CLASSES),
        "validator_model": True,   # legacy key for frontend banner compat
        "disease_model": True,
        "detail": [] if gemini_ok else ["GEMINI_API_KEY missing in .env"],
    })
