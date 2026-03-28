"""
VisualLink: Missing Person Reunification Hub
Feed Analysis Agent — Processes shelter security camera video feeds
"""

import base64
import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

import cv2
import google.generativeai as genai
import numpy as np
from google.cloud import firestore, storage
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

logger = logging.getLogger(__name__)

FRAMES_PER_SECOND_TARGET = 1        # Sample 1 frame/sec from video
CHUNK_DURATION_SECONDS   = 30       # Feed Gemini 30-second video chunks
MAX_VIDEO_SIZE_MB        = 500


# ---------------------------------------------------------------------------
# Gemini prompt
# ---------------------------------------------------------------------------

FEED_ANALYSIS_PROMPT = """
Analyze this video segment from a shelter security camera. For each person
visible for more than 3 seconds, return a JSON array. Each element must contain:
- timestamp_seconds: first frame they appear (integer)
- face_description: detailed facial features (shape, eye color, nose, lips, marks)
- hair: color, length, style
- clothing_top: color, type, visible patterns or logos
- clothing_bottom: color, type
- approximate_age_range: string (e.g., "30-40")
- skin_tone: general descriptor
- distinguishing_features: list of notable marks, tattoos, accessories
- confidence_of_extraction: float 0.0-1.0 (how clearly the person was visible)
Return ONLY a valid JSON array. If no persons are clearly visible, return [].
""".strip()


# ---------------------------------------------------------------------------
# Video chunking helpers
# ---------------------------------------------------------------------------

def iter_video_chunks(
    video_path: str,
    chunk_seconds: int = CHUNK_DURATION_SECONDS,
    fps_target: int = FRAMES_PER_SECOND_TARGET,
) -> Generator[tuple[int, bytes], None, None]:
    """
    Yield (start_second, chunk_bytes) tuples for each 30-second window.
    The chunk is re-encoded as a lightweight MP4 containing sampled frames.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Cannot open video: {video_path}")

    native_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    total_seconds = int(total_frames / native_fps)

    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    chunk_start = 0

    while chunk_start < total_seconds:
        chunk_end = min(chunk_start + chunk_seconds, total_seconds)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name

        writer = cv2.VideoWriter(tmp_path, fourcc, float(fps_target), (width, height))

        for sec in range(chunk_start, chunk_end, max(1, int(native_fps // fps_target))):
            cap.set(cv2.CAP_PROP_POS_MSEC, sec * 1000)
            ret, frame = cap.read()
            if ret:
                writer.write(frame)

        writer.release()

        with open(tmp_path, "rb") as f:
            chunk_bytes = f.read()
        os.unlink(tmp_path)

        yield chunk_start, chunk_bytes
        chunk_start = chunk_end

    cap.release()


# ---------------------------------------------------------------------------
# Gemini Vision call
# ---------------------------------------------------------------------------

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
def analyze_video_chunk(chunk_bytes: bytes) -> list[dict]:
    """Send a video chunk to Gemini and parse the returned JSON array."""
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    video_part = {
        "mime_type": "video/mp4",
        "data": base64.b64encode(chunk_bytes).decode("utf-8"),
    }

    response = model.generate_content(
        [FEED_ANALYSIS_PROMPT, video_part],
        generation_config=genai.types.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )

    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    data = json.loads(raw)
    return data if isinstance(data, list) else []


# ---------------------------------------------------------------------------
# GCS upload for video
# ---------------------------------------------------------------------------

def upload_video_to_gcs(video_path: str, feed_id: str) -> str:
    client  = storage.Client()
    bucket  = client.bucket(settings.GCS_BUCKET_NAME)
    suffix  = Path(video_path).suffix
    blob    = bucket.blob(f"shelter_feeds/{feed_id}/feed{suffix}")
    blob.upload_from_filename(video_path)
    return f"gs://{settings.GCS_BUCKET_NAME}/shelter_feeds/{feed_id}/feed{suffix}"


# ---------------------------------------------------------------------------
# Firestore persistence
# ---------------------------------------------------------------------------

def save_sightings_to_firestore(
    feed_id: str,
    shelter_name: str,
    shelter_location: str,
    feed_gcs_url: str,
    sightings: list[dict],
) -> list[str]:
    db = firestore.Client()
    saved_ids = []

    for s in sightings:
        sighting_id = str(uuid.uuid4())
        doc_ref = (
            db.collection("shelter_sightings")
            .document(feed_id)
            .collection("sightings")
            .document(sighting_id)
        )
        doc_ref.set({
            "sighting_id": sighting_id,
            "feed_id": feed_id,
            "shelter_name": shelter_name,
            "shelter_location": shelter_location,
            "feed_gcs_url": feed_gcs_url,
            "timestamp_seconds": s.get("timestamp_seconds"),
            "features": {k: v for k, v in s.items()
                         if k not in ("timestamp_seconds", "confidence_of_extraction")},
            "confidence_of_extraction": s.get("confidence_of_extraction", 0.0),
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        })
        saved_ids.append(sighting_id)

    return saved_ids


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

class FeedAnalysisAgent:
    """ADK-compatible agent for processing shelter security feeds."""

    name        = "FeedAnalysisAgent"
    description = (
        "Accepts shelter security video feeds, chunks them, runs Gemini Video "
        "Understanding on each chunk, and stores per-person sightings in Firestore."
    )

    def run(
        self,
        video_path: str,
        shelter_name: str,
        shelter_location: str,
    ) -> dict:
        """
        Process a video feed end-to-end.

        Args:
            video_path:       Local path to the uploaded video file.
            shelter_name:     Human-readable shelter name.
            shelter_location: Address / GPS coordinates of the shelter.

        Returns:
            dict with keys: feed_id, sightings_count, sighting_ids, feed_gcs_url
        """
        feed_id = str(uuid.uuid4())
        logger.info("FeedAnalysisAgent started", extra={"feed_id": feed_id})

        # Upload original video to GCS
        try:
            feed_gcs_url = upload_video_to_gcs(video_path, feed_id)
        except Exception as exc:
            logger.error(f"GCS upload failed: {exc}")
            feed_gcs_url = None

        all_sightings: list[dict] = []

        for chunk_start, chunk_bytes in iter_video_chunks(video_path):
            logger.info(f"Analyzing chunk starting at {chunk_start}s …",
                        extra={"feed_id": feed_id})
            try:
                sightings = analyze_video_chunk(chunk_bytes)
                # Offset timestamps by chunk start
                for s in sightings:
                    s["timestamp_seconds"] = (
                        (s.get("timestamp_seconds") or 0) + chunk_start
                    )
                all_sightings.extend(sightings)
                logger.info(f"Chunk {chunk_start}s → {len(sightings)} sightings")
            except Exception as exc:
                logger.error(f"Chunk analysis failed at {chunk_start}s: {exc}")

        # Persist sightings
        sighting_ids = save_sightings_to_firestore(
            feed_id=feed_id,
            shelter_name=shelter_name,
            shelter_location=shelter_location,
            feed_gcs_url=feed_gcs_url,
            sightings=all_sightings,
        )

        logger.info(
            f"FeedAnalysisAgent complete: {len(sighting_ids)} sightings stored",
            extra={"feed_id": feed_id},
        )

        return {
            "feed_id": feed_id,
            "sightings_count": len(sighting_ids),
            "sighting_ids": sighting_ids,
            "feed_gcs_url": feed_gcs_url,
            "status": "analyzed",
        }
