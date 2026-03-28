"""
VisualLink: Missing Person Reunification Hub
Firestore Schema Setup & Index Configuration Script
Run once: python firestore_setup.py
"""

import logging
from datetime import datetime, timezone

from google.cloud import firestore

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ── Seed schema with sample documents ─────────────────────────────────────────

SAMPLE_MISSING_PERSON = {
    "case_id": "demo-001",
    "name": "Maria Santos",
    "age": 34,
    "contact_email": "family@example.com",
    "last_known_location": "Downtown Emergency Shelter, NY",
    "photo_gcs_url": None,
    "features": {
        "face_description": "Oval face, dark brown eyes, small nose, thin lips",
        "hair": "Dark brown, shoulder-length, wavy",
        "clothing_top": "Blue denim jacket",
        "clothing_bottom": "Dark blue jeans",
        "approximate_age_range": "30-40",
        "skin_tone": "Medium olive",
        "distinguishing_features": ["Small scar above left eyebrow"],
    },
    "submitted_at": datetime.now(timezone.utc).isoformat(),
    "status": "active",
}

SAMPLE_SIGHTING = {
    "sighting_id": "sighting-demo-001",
    "feed_id": "feed-demo-001",
    "shelter_name": "Hope Bridge Shelter",
    "shelter_location": "123 Hope Street, Brooklyn, NY 11201",
    "feed_gcs_url": None,
    "timestamp_seconds": 127,
    "features": {
        "face_description": "Oval face, dark brown eyes, small nose",
        "hair": "Dark brown, shoulder-length",
        "clothing_top": "Blue jacket",
        "clothing_bottom": "Dark jeans",
        "approximate_age_range": "30-40",
        "skin_tone": "Olive",
        "distinguishing_features": ["Small mark above left eye"],
    },
    "confidence_of_extraction": 0.82,
    "analyzed_at": datetime.now(timezone.utc).isoformat(),
}

SAMPLE_MATCH = {
    "match_id": "match-alpha-001",
    "case_id": "demo-001",
    "sighting_id": "sighting-demo-001",
    "feed_id": "feed-demo-001",
    "shelter_name": "Hope Bridge Shelter",
    "shelter_location": "123 Hope Street, Brooklyn, NY 11201",
    "timestamp_seconds": 127,
    "match_confidence": 0.89,
    "match_reasoning": (
        "Strong facial feature alignment including eye shape and skin tone. "
        "Clothing description closely matches the blue denim jacket. "
        "Hair color and length are consistent with the uploaded photo."
    ),
    "key_matched_features": ["eye color", "skin tone", "hair color", "jacket color"],
    "key_discrepancies": ["partial face occlusion in feed"],
    "matched_at": datetime.now(timezone.utc).isoformat(),
    "notification_status": "pending",
}


def setup_firestore():
    db = firestore.Client()

    # missing_persons
    logger.info("Creating missing_persons/demo-001 …")
    db.collection("missing_persons").document("demo-001").set(
        SAMPLE_MISSING_PERSON, merge=True
    )

    # shelter_sightings (nested sub-collection)
    logger.info("Creating shelter_sightings/feed-demo-001/sightings/sighting-demo-001 …")
    (
        db.collection("shelter_sightings")
        .document("feed-demo-001")
        .collection("sightings")
        .document("sighting-demo-001")
        .set(SAMPLE_SIGHTING, merge=True)
    )

    # matches
    logger.info("Creating matches/match-alpha-001 …")
    db.collection("matches").document("match-alpha-001").set(
        SAMPLE_MATCH, merge=True
    )

    logger.info("✅ Firestore schema seeded successfully.")


# ── Composite index configuration (deploy via Firebase CLI) ───────────────────

FIRESTORE_INDEXES = {
    "indexes": [
        {
            "collectionGroup": "missing_persons",
            "queryScope": "COLLECTION",
            "fields": [
                {"fieldPath": "status",       "order": "ASCENDING"},
                {"fieldPath": "submitted_at", "order": "DESCENDING"},
            ],
        },
        {
            "collectionGroup": "sightings",
            "queryScope": "COLLECTION_GROUP",
            "fields": [
                {"fieldPath": "feed_id",      "order": "ASCENDING"},
                {"fieldPath": "analyzed_at",  "order": "DESCENDING"},
            ],
        },
        {
            "collectionGroup": "matches",
            "queryScope": "COLLECTION",
            "fields": [
                {"fieldPath": "case_id",         "order": "ASCENDING"},
                {"fieldPath": "match_confidence", "order": "DESCENDING"},
            ],
        },
    ],
    "fieldOverrides": [],
}


def write_index_config():
    import json
    with open("firestore.indexes.json", "w") as f:
        json.dump(FIRESTORE_INDEXES, f, indent=2)
    logger.info("✅ firestore.indexes.json written.")


if __name__ == "__main__":
    write_index_config()
    try:
        setup_firestore()
    except Exception as exc:
        logger.warning(f"Firestore seed skipped (no credentials?): {exc}")
        logger.info("Run with GOOGLE_APPLICATION_CREDENTIALS set to seed Firestore.")
