"""
VisualLink: Missing Person Reunification Hub
Ingestion Agent — Processes uploaded photos of missing persons
"""

import base64
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2
import google.generativeai as genai
import numpy as np
from google.cloud import firestore, storage
from PIL import Image, ImageEnhance, ImageFilter
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Image preprocessing helpers
# ---------------------------------------------------------------------------

def preprocess_image(image_bytes: bytes) -> bytes:
    """
    Auto-enhance a potentially blurry or low-quality image.
    Steps: denoise → contrast/sharpness boost → upscale (if small).
    Returns JPEG bytes of the processed image.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # 1. Denoise
    img_cv = cv2.fastNlMeansDenoisingColored(img_cv, None, 10, 10, 7, 21)

    # 2. CLAHE contrast on luminance channel
    lab = cv2.cvtColor(img_cv, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l_ch = clahe.apply(l_ch)
    img_cv = cv2.cvtColor(cv2.merge([l_ch, a_ch, b_ch]), cv2.COLOR_LAB2BGR)

    # 3. Upscale if either dimension < 256 px
    h, w = img_cv.shape[:2]
    if min(h, w) < 256:
        scale = 256 / min(h, w)
        img_cv = cv2.resize(img_cv, None, fx=scale, fy=scale,
                            interpolation=cv2.INTER_LANCZOS4)

    # 4. Sharpness boost via PIL
    pil_img = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
    pil_img = ImageEnhance.Sharpness(pil_img).enhance(1.8)
    pil_img = ImageEnhance.Contrast(pil_img).enhance(1.2)

    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Gemini extraction
# ---------------------------------------------------------------------------

INGESTION_PROMPT = """
Analyze this image of a potentially missing person. Extract and return a JSON
object with these fields:
- face_description: detailed facial features (shape, eye color, nose, lips,
  distinguishing marks)
- hair: color, length, style
- clothing_top: color, type, visible patterns or logos
- clothing_bottom: color, type
- approximate_age_range: string (e.g., "30-40")
- skin_tone: general descriptor
- distinguishing_features: list of notable marks, tattoos, accessories
Return ONLY valid JSON. If any field is uncertain, use null.
""".strip()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def extract_features_from_image(image_bytes: bytes) -> dict:
    """Call Gemini Vision to extract structured person descriptors."""
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    image_part = {
        "mime_type": "image/jpeg",
        "data": base64.b64encode(image_bytes).decode("utf-8"),
    }

    response = model.generate_content(
        [INGESTION_PROMPT, image_part],
        generation_config=genai.types.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )

    raw = response.text.strip()
    # Strip possible markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


# ---------------------------------------------------------------------------
# GCS upload
# ---------------------------------------------------------------------------

def upload_image_to_gcs(image_bytes: bytes, case_id: str) -> str:
    """Upload image to GCS and return a public-ish GCS URI."""
    client = storage.Client()
    bucket = client.bucket(settings.GCS_BUCKET_NAME)
    blob_name = f"missing_persons/{case_id}/photo.jpg"
    blob = bucket.blob(blob_name)
    blob.upload_from_string(image_bytes, content_type="image/jpeg")
    return f"gs://{settings.GCS_BUCKET_NAME}/{blob_name}"


# ---------------------------------------------------------------------------
# Firestore persistence
# ---------------------------------------------------------------------------

def save_case_to_firestore(
    case_id: str,
    name: str,
    age: int,
    contact_email: str,
    last_known_location: str,
    photo_gcs_url: str,
    features: dict,
) -> None:
    db = firestore.Client()
    doc_ref = db.collection("missing_persons").document(case_id)
    doc_ref.set({
        "case_id": case_id,
        "name": name,
        "age": age,
        "contact_email": contact_email,
        "last_known_location": last_known_location,
        "photo_gcs_url": photo_gcs_url,
        "features": features,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    })


# ---------------------------------------------------------------------------
# Main agent entry-point (called by OrchestratorAgent)
# ---------------------------------------------------------------------------

class IngestionAgent:
    """ADK-compatible agent for processing missing-person photos."""

    name = "IngestionAgent"
    description = (
        "Accepts uploaded images of missing persons, preprocesses them, "
        "extracts visual descriptors via Gemini Vision, and stores results "
        "in Firestore."
    )

    def run(
        self,
        image_bytes: bytes,
        name: str,
        age: int,
        contact_email: str,
        last_known_location: str,
    ) -> dict:
        """
        Process a missing-person photo end-to-end.

        Returns:
            dict with keys: case_id, features, photo_gcs_url, status
        """
        case_id = str(uuid.uuid4())
        logger.info("IngestionAgent started", extra={"case_id": case_id})

        # --- Step 1: Preprocess ---
        try:
            processed_bytes = preprocess_image(image_bytes)
            logger.info("Image preprocessing complete", extra={"case_id": case_id})
        except Exception as exc:
            logger.warning(f"Preprocessing failed, using raw image: {exc}")
            processed_bytes = image_bytes

        # --- Step 2: Extract features via Gemini ---
        features = extract_features_from_image(processed_bytes)
        logger.info("Feature extraction complete", extra={
            "case_id": case_id, "features_keys": list(features.keys())
        })

        # --- Step 3: Upload to GCS ---
        try:
            photo_gcs_url = upload_image_to_gcs(processed_bytes, case_id)
        except Exception as exc:
            logger.error(f"GCS upload failed: {exc}")
            photo_gcs_url = None

        # --- Step 4: Persist to Firestore ---
        save_case_to_firestore(
            case_id=case_id,
            name=name,
            age=age,
            contact_email=contact_email,
            last_known_location=last_known_location,
            photo_gcs_url=photo_gcs_url,
            features=features,
        )

        return {
            "case_id": case_id,
            "features": features,
            "photo_gcs_url": photo_gcs_url,
            "status": "ingested",
        }
