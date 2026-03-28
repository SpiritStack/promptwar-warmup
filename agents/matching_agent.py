"""
VisualLink: Missing Person Reunification Hub
Matching Agent — Compares missing-person profiles against shelter sightings
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import google.generativeai as genai
from google.cloud import firestore
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

logger = logging.getLogger(__name__)

MATCH_CONFIDENCE_THRESHOLD = 0.75


# ---------------------------------------------------------------------------
# Gemini matching prompt
# ---------------------------------------------------------------------------

MATCHING_PROMPT_TEMPLATE = """
You are a forensic visual matching assistant. Given Person A's profile (from a
family-uploaded photo) and Person B's profile (from a shelter security feed),
determine how likely they are the same individual.

Person A (Missing Person):
{person_a_json}

Person B (Shelter Sighting):
{person_b_json}

Return JSON with:
- match_confidence: float 0.0-1.0
- match_reasoning: 2-3 sentence explanation of key matching or mismatching features
- key_matched_features: list of features that aligned
- key_discrepancies: list of features that did not align
Return ONLY valid JSON.
""".strip()


# ---------------------------------------------------------------------------
# Core matching call
# ---------------------------------------------------------------------------

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def compare_profiles(person_a: dict, person_b: dict) -> dict:
    """
    Ask Gemini to compare two person feature profiles.
    Returns a dict with: match_confidence, match_reasoning,
    key_matched_features, key_discrepancies.
    """
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    prompt = MATCHING_PROMPT_TEMPLATE.format(
        person_a_json=json.dumps(person_a, indent=2),
        person_b_json=json.dumps(person_b, indent=2),
    )

    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.05,
        ),
    )

    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    return json.loads(raw)


# ---------------------------------------------------------------------------
# Firestore helpers
# ---------------------------------------------------------------------------

def get_missing_person(case_id: str) -> Optional[dict]:
    db = firestore.Client()
    doc = db.collection("missing_persons").document(case_id).get()
    return doc.to_dict() if doc.exists else None


def iter_all_sightings(limit: int = 500) -> list[dict]:
    """Fetch recent shelter sightings across all feeds."""
    db = firestore.Client()
    sightings = []

    feeds = db.collection("shelter_sightings").stream()
    for feed_doc in feeds:
        feed_id = feed_doc.id
        sub = (
            db.collection("shelter_sightings")
            .document(feed_id)
            .collection("sightings")
            .order_by("analyzed_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        for s in sub:
            d = s.to_dict()
            d["_sighting_id"] = s.id
            d["_feed_id"] = feed_id
            sightings.append(d)

    return sightings


def iter_sightings_for_feed(feed_id: str) -> list[dict]:
    """Fetch all sightings for a specific feed."""
    db = firestore.Client()
    sightings = []
    docs = (
        db.collection("shelter_sightings")
        .document(feed_id)
        .collection("sightings")
        .stream()
    )
    for doc in docs:
        d = doc.to_dict()
        d["_sighting_id"] = doc.id
        d["_feed_id"] = feed_id
        sightings.append(d)
    return sightings


def save_match(
    case_id: str,
    sighting: dict,
    match_result: dict,
) -> str:
    """Persist a confirmed match to Firestore."""
    db = firestore.Client()
    match_id = str(uuid.uuid4())

    db.collection("matches").document(match_id).set({
        "match_id": match_id,
        "case_id": case_id,
        "sighting_id": sighting.get("_sighting_id"),
        "feed_id": sighting.get("_feed_id"),
        "shelter_name": sighting.get("shelter_name"),
        "shelter_location": sighting.get("shelter_location"),
        "timestamp_seconds": sighting.get("timestamp_seconds"),
        "match_confidence": match_result.get("match_confidence"),
        "match_reasoning": match_result.get("match_reasoning"),
        "key_matched_features": match_result.get("key_matched_features", []),
        "key_discrepancies": match_result.get("key_discrepancies", []),
        "matched_at": datetime.now(timezone.utc).isoformat(),
        "notification_status": "pending",
    })

    return match_id


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

class MatchingAgent:
    """ADK-compatible agent that cross-matches person profiles to sightings."""

    name        = "MatchingAgent"
    description = (
        "Compares extracted missing-person features against all stored shelter "
        "sightings using Gemini forensic matching. Triggers NotificationAgent "
        "for high-confidence matches (>= 0.75)."
    )

    def run(
        self,
        case_id: str,
        feed_id: Optional[str] = None,
        notification_callback=None,
    ) -> dict:
        """
        Run matching for a given case_id against shelter sightings.

        Args:
            case_id:               The missing-person case to match.
            feed_id:               Optional — limit matching to a specific feed.
            notification_callback: Callable(match_id, case_doc, sighting, match_result)
                                   invoked when match_confidence >= threshold.

        Returns:
            dict with keys: matches_found, match_ids, comparisons_run
        """
        logger.info("MatchingAgent started", extra={"case_id": case_id})

        person_doc = get_missing_person(case_id)
        if not person_doc:
            raise ValueError(f"Case {case_id} not found in Firestore")

        person_features = person_doc.get("features", {})

        # Retrieve sightings
        sightings = (
            iter_sightings_for_feed(feed_id)
            if feed_id
            else iter_all_sightings()
        )

        logger.info(f"Comparing against {len(sightings)} sightings")

        confirmed_matches: list[str] = []
        comparisons_run = 0

        for sighting in sightings:
            sighting_features = sighting.get("features", {})
            confidence_of_extraction = sighting.get("confidence_of_extraction", 0)

            # Skip very unclear sightings
            if confidence_of_extraction < 0.3:
                continue

            try:
                match_result = compare_profiles(person_features, sighting_features)
                comparisons_run += 1
            except Exception as exc:
                logger.error(f"Comparison failed for sighting {sighting.get('_sighting_id')}: {exc}")
                continue

            mc = match_result.get("match_confidence", 0.0)
            logger.info(
                f"Match confidence: {mc:.2f} | sighting: {sighting.get('_sighting_id')}",
                extra={"case_id": case_id},
            )

            if mc >= MATCH_CONFIDENCE_THRESHOLD:
                match_id = save_match(case_id, sighting, match_result)
                confirmed_matches.append(match_id)
                logger.info(
                    f"HIGH CONFIDENCE MATCH → match_id={match_id} | confidence={mc:.2f}",
                    extra={"case_id": case_id},
                )

                # Trigger notification downstream
                if notification_callback:
                    try:
                        notification_callback(
                            match_id=match_id,
                            case_doc=person_doc,
                            sighting=sighting,
                            match_result=match_result,
                        )
                    except Exception as exc:
                        logger.error(f"Notification callback failed: {exc}")

        return {
            "case_id": case_id,
            "comparisons_run": comparisons_run,
            "matches_found": len(confirmed_matches),
            "match_ids": confirmed_matches,
            "status": "complete",
        }
