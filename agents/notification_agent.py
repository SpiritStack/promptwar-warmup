"""
VisualLink: Missing Person Reunification Hub
Notification Agent — Gmail, Calendar, and Sheets integration for match alerts
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from google.cloud import firestore
from google.oauth2 import service_account
from googleapiclient.discovery import build
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets",
]


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _get_credentials():
    """Load service-account credentials with required Workspace scopes."""
    return service_account.Credentials.from_service_account_file(
        settings.GOOGLE_SERVICE_ACCOUNT_FILE,
        scopes=SCOPES,
        subject=settings.GOOGLE_WORKSPACE_DELEGATED_USER,
    )


# ---------------------------------------------------------------------------
# Gmail: send alert email
# ---------------------------------------------------------------------------

EMAIL_TEMPLATE = """\
<html>
<body style="font-family: Arial, sans-serif; color: #1a1a2e; background: #f8f9fa; padding: 24px;">
  <div style="max-width: 600px; margin: auto; background: white; border-radius: 12px;
              box-shadow: 0 4px 20px rgba(0,0,0,0.1); overflow: hidden;">

    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 24px; text-align: center;">
      <h1 style="color: white; margin: 0; font-size: 24px;">🔍 VisualLink — Potential Match Found</h1>
    </div>

    <div style="padding: 32px;">
      <div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px;
                  padding: 16px; margin-bottom: 24px;">
        <strong>⚠️ Confidence Score: {confidence:.0%}</strong> — Please review and verify in person.
      </div>

      <h2 style="color: #667eea;">Case Details</h2>
      <table style="width: 100%; border-collapse: collapse;">
        <tr><td style="padding: 8px; color: #666;">Case ID</td>
            <td style="padding: 8px; font-weight: bold;">{case_id}</td></tr>
        <tr style="background: #f8f9fa;">
            <td style="padding: 8px; color: #666;">Missing Person</td>
            <td style="padding: 8px; font-weight: bold;">{name}</td></tr>
        <tr><td style="padding: 8px; color: #666;">Shelter</td>
            <td style="padding: 8px; font-weight: bold;">{shelter_name}</td></tr>
        <tr style="background: #f8f9fa;">
            <td style="padding: 8px; color: #666;">Sighting Time</td>
            <td style="padding: 8px; font-weight: bold;">{timestamp}</td></tr>
        <tr><td style="padding: 8px; color: #666;">Location</td>
            <td style="padding: 8px;">
              <a href="{maps_url}" style="color: #667eea;">View on Google Maps</a>
            </td></tr>
      </table>

      <h2 style="color: #667eea; margin-top: 24px;">Match Analysis</h2>
      <p style="color: #444; line-height: 1.6;">{reasoning}</p>

      <div style="margin-top: 16px;">
        <strong>Matched Features:</strong>
        <ul style="color: #2d8a4e;">
          {matched_features_html}
        </ul>
        <strong>Discrepancies (review carefully):</strong>
        <ul style="color: #c0392b;">
          {discrepancy_html}
        </ul>
      </div>

      <div style="margin-top: 32px; text-align: center;">
        <p style="color: #666; font-size: 14px;">
          This is an automated alert from VisualLink. A case worker has been notified
          and a calendar event has been created for follow-up.
        </p>
      </div>
    </div>
  </div>
</body>
</html>
"""


def send_gmail_alert(
    credentials,
    to_email: str,
    case_id: str,
    name: str,
    shelter_name: str,
    shelter_location: str,
    timestamp_seconds: int,
    confidence: float,
    reasoning: str,
    matched_features: list,
    discrepancies: list,
) -> str:
    """Send a rich HTML alert email via Gmail API. Returns message ID."""
    maps_url = (
        f"https://www.google.com/maps/search/?api=1&query="
        f"{shelter_location.replace(' ', '+')}"
    )
    timestamp_str = f"{timestamp_seconds}s into feed"

    matched_html = "".join(f"<li>{f}</li>" for f in (matched_features or []))
    discrep_html = "".join(f"<li>{d}</li>" for d in (discrepancies or []))

    html_body = EMAIL_TEMPLATE.format(
        case_id=case_id,
        name=name,
        shelter_name=shelter_name,
        timestamp=timestamp_str,
        maps_url=maps_url,
        confidence=confidence,
        reasoning=reasoning,
        matched_features_html=matched_html or "<li>See reasoning above</li>",
        discrepancy_html=discrep_html or "<li>None noted</li>",
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[VisualLink] Potential Match for Case {case_id} — Action Required"
    msg["From"]    = settings.NOTIFICATION_SENDER_EMAIL
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    service = build("gmail", "v1", credentials=credentials)
    result  = service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()

    logger.info(f"Gmail sent | message_id={result['id']} | to={to_email}")
    return result["id"]


# ---------------------------------------------------------------------------
# Google Calendar: create case-worker event
# ---------------------------------------------------------------------------

def create_calendar_event(
    credentials,
    case_id: str,
    name: str,
    shelter_name: str,
    case_worker_email: str,
    match_confidence: float,
) -> str:
    """Create a 'Potential Match — Action Required' calendar event."""
    now = datetime.now(timezone.utc)
    start = now + timedelta(hours=1)
    end   = start + timedelta(hours=1)

    event = {
        "summary": f"Potential Match — Action Required | {name}",
        "description": (
            f"VisualLink has found a potential match for missing person: {name}\n"
            f"Case ID: {case_id}\n"
            f"Shelter: {shelter_name}\n"
            f"Match Confidence: {match_confidence:.0%}\n\n"
            "Please verify in person and update the case status in VisualLink."
        ),
        "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
        "end":   {"dateTime": end.isoformat(),   "timeZone": "UTC"},
        "attendees": [{"email": case_worker_email}],
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email",  "minutes": 60},
                {"method": "popup",  "minutes": 10},
            ],
        },
        "colorId": "11",  # red — urgent
    }

    service = build("calendar", "v3", credentials=credentials)
    result  = service.events().insert(
        calendarId="primary", body=event, sendUpdates="all"
    ).execute()

    logger.info(f"Calendar event created | event_id={result['id']}")
    return result["id"]


# ---------------------------------------------------------------------------
# Google Sheets: audit log
# ---------------------------------------------------------------------------

def append_to_audit_sheet(
    credentials,
    case_id: str,
    match_id: str,
    name: str,
    shelter_name: str,
    timestamp_seconds: int,
    confidence: float,
    notified_at: str,
) -> None:
    """Append a row to the VisualLink audit Google Sheet."""
    service     = build("sheets", "v4", credentials=credentials)
    spreadsheet_id = settings.AUDIT_SHEET_ID

    row = [[
        case_id,
        match_id,
        name,
        shelter_name,
        str(timestamp_seconds),
        f"{confidence:.4f}",
        notified_at,
    ]]

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range="Audit!A:G",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": row},
    ).execute()

    logger.info(f"Audit row appended | case_id={case_id} | match_id={match_id}")


# ---------------------------------------------------------------------------
# Update Firestore notification status
# ---------------------------------------------------------------------------

def mark_match_notified(match_id: str, message_id: str, event_id: str) -> None:
    db = firestore.Client()
    db.collection("matches").document(match_id).update({
        "notification_status": "sent",
        "notified_at": datetime.now(timezone.utc).isoformat(),
        "gmail_message_id": message_id,
        "calendar_event_id": event_id,
    })


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

class NotificationAgent:
    """ADK-compatible agent that sends multi-channel alerts on confirmed matches."""

    name        = "NotificationAgent"
    description = (
        "On confirmed match (confidence >= 0.75), sends a rich Gmail alert to "
        "the family contact, creates a Google Calendar event for the case worker, "
        "and logs the event to an audit Google Sheet."
    )

    def run(
        self,
        match_id: str,
        case_doc: dict,
        sighting: dict,
        match_result: dict,
    ) -> dict:
        """
        Send multi-channel notifications for a confirmed match.

        Args:
            match_id:     Firestore match document ID.
            case_doc:     Full missing-person Firestore document.
            sighting:     Shelter sighting document.
            match_result: Gemini match analysis dict.

        Returns:
            dict with keys: gmail_message_id, calendar_event_id, status
        """
        logger.info("NotificationAgent started", extra={"match_id": match_id})

        credentials = _get_credentials()

        case_id            = case_doc.get("case_id", match_id)
        name               = case_doc.get("name", "Unknown")
        contact_email      = case_doc.get("contact_email")
        shelter_name       = sighting.get("shelter_name", "Unknown Shelter")
        shelter_location   = sighting.get("shelter_location", "")
        timestamp_seconds  = sighting.get("timestamp_seconds", 0)
        confidence         = match_result.get("match_confidence", 0.0)
        reasoning          = match_result.get("match_reasoning", "")
        matched_features   = match_result.get("key_matched_features", [])
        discrepancies      = match_result.get("key_discrepancies", [])
        notified_at        = datetime.now(timezone.utc).isoformat()

        # 1. Send Gmail alert to family
        gmail_message_id = None
        if contact_email:
            gmail_message_id = send_gmail_alert(
                credentials=credentials,
                to_email=contact_email,
                case_id=case_id,
                name=name,
                shelter_name=shelter_name,
                shelter_location=shelter_location,
                timestamp_seconds=timestamp_seconds,
                confidence=confidence,
                reasoning=reasoning,
                matched_features=matched_features,
                discrepancies=discrepancies,
            )

        # 2. Create Calendar event for case worker
        calendar_event_id = None
        if settings.CASE_WORKER_EMAIL:
            calendar_event_id = create_calendar_event(
                credentials=credentials,
                case_id=case_id,
                name=name,
                shelter_name=shelter_name,
                case_worker_email=settings.CASE_WORKER_EMAIL,
                match_confidence=confidence,
            )

        # 3. Audit log to Google Sheets
        try:
            append_to_audit_sheet(
                credentials=credentials,
                case_id=case_id,
                match_id=match_id,
                name=name,
                shelter_name=shelter_name,
                timestamp_seconds=timestamp_seconds,
                confidence=confidence,
                notified_at=notified_at,
            )
        except Exception as exc:
            logger.error(f"Sheets audit log failed: {exc}")

        # 4. Update Firestore match status
        mark_match_notified(
            match_id=match_id,
            message_id=gmail_message_id or "",
            event_id=calendar_event_id or "",
        )

        logger.info("NotificationAgent complete", extra={"match_id": match_id})

        return {
            "match_id": match_id,
            "gmail_message_id": gmail_message_id,
            "calendar_event_id": calendar_event_id,
            "notified_at": notified_at,
            "status": "notified",
        }
