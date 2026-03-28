"""
VisualLink: Missing Person Reunification Hub
Orchestrator Agent — Root coordinator for all specialized agents
"""

import logging
from typing import Optional

from agents.ingestion_agent   import IngestionAgent
from agents.feed_analysis_agent import FeedAnalysisAgent
from agents.matching_agent    import MatchingAgent
from agents.notification_agent import NotificationAgent

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """
    Root ADK agent that coordinates the VisualLink multi-agent pipeline.

    Workflow A — New Missing Person Report:
        IngestionAgent → MatchingAgent (against ALL feeds) → NotificationAgent

    Workflow B — New Shelter Feed Upload:
        FeedAnalysisAgent → MatchingAgent (new sightings vs ALL active cases)
        → NotificationAgent (per confirmed match)

    Workflow C — Manual re-match:
        MatchingAgent → NotificationAgent
    """

    name        = "OrchestratorAgent"
    description = "Root coordinator for the VisualLink multi-agent pipeline."

    def __init__(self):
        self.ingestion_agent     = IngestionAgent()
        self.feed_analysis_agent = FeedAnalysisAgent()
        self.matching_agent      = MatchingAgent()
        self.notification_agent  = NotificationAgent()

    # -----------------------------------------------------------------------
    # Notification callback — passed into MatchingAgent
    # -----------------------------------------------------------------------

    def _notify(self, match_id: str, case_doc: dict, sighting: dict, match_result: dict):
        try:
            self.notification_agent.run(
                match_id=match_id,
                case_doc=case_doc,
                sighting=sighting,
                match_result=match_result,
            )
        except Exception as exc:
            logger.error(f"NotificationAgent failed for match {match_id}: {exc}")

    # -----------------------------------------------------------------------
    # Workflow A: Report a missing person
    # -----------------------------------------------------------------------

    def report_missing_person(
        self,
        image_bytes: bytes,
        name: str,
        age: int,
        contact_email: str,
        last_known_location: str,
        run_matching: bool = True,
    ) -> dict:
        """
        End-to-end flow for a new missing-person report.

        Returns combined result dict with ingestion + match summary.
        """
        logger.info(f"[Orchestrator] Workflow A started: report_missing_person | name={name}")

        # Step 1 — Ingest
        ingestion_result = self.ingestion_agent.run(
            image_bytes=image_bytes,
            name=name,
            age=age,
            contact_email=contact_email,
            last_known_location=last_known_location,
        )

        case_id = ingestion_result["case_id"]
        logger.info(f"[Orchestrator] Ingestion complete | case_id={case_id}")

        match_summary = None
        if run_matching:
            # Step 2 — Match against existing sightings
            match_summary = self.matching_agent.run(
                case_id=case_id,
                notification_callback=self._notify,
            )
            logger.info(
                f"[Orchestrator] Matching complete | "
                f"matches={match_summary.get('matches_found', 0)}"
            )

        return {
            "workflow": "report_missing_person",
            "ingestion": ingestion_result,
            "matching":  match_summary,
        }

    # -----------------------------------------------------------------------
    # Workflow B: Upload shelter feed
    # -----------------------------------------------------------------------

    def upload_shelter_feed(
        self,
        video_path: str,
        shelter_name: str,
        shelter_location: str,
        run_matching: bool = True,
    ) -> dict:
        """
        End-to-end flow for a new shelter security feed upload.

        Returns combined result dict with feed analysis + matching per case.
        """
        logger.info(f"[Orchestrator] Workflow B started: upload_shelter_feed | shelter={shelter_name}")

        # Step 1 — Analyze feed
        feed_result = self.feed_analysis_agent.run(
            video_path=video_path,
            shelter_name=shelter_name,
            shelter_location=shelter_location,
        )

        feed_id = feed_result["feed_id"]
        logger.info(
            f"[Orchestrator] Feed analysis complete | feed_id={feed_id} | "
            f"sightings={feed_result.get('sightings_count', 0)}"
        )

        match_summaries = []
        if run_matching and feed_result.get("sightings_count", 0) > 0:
            # Match ALL active missing persons against the new feed's sightings
            from google.cloud import firestore
            db = firestore.Client()
            active_cases = db.collection("missing_persons").where(
                "status", "==", "active"
            ).stream()

            for case_doc in active_cases:
                case_data = case_doc.to_dict()
                case_id   = case_data.get("case_id", case_doc.id)

                try:
                    result = self.matching_agent.run(
                        case_id=case_id,
                        feed_id=feed_id,
                        notification_callback=self._notify,
                    )
                    match_summaries.append(result)
                    logger.info(
                        f"[Orchestrator] Matched case {case_id}: "
                        f"{result.get('matches_found', 0)} match(es)"
                    )
                except Exception as exc:
                    logger.error(f"Matching failed for case {case_id}: {exc}")

        return {
            "workflow":       "upload_shelter_feed",
            "feed_analysis":  feed_result,
            "match_summaries": match_summaries,
            "total_matches":   sum(r.get("matches_found", 0) for r in match_summaries),
        }

    # -----------------------------------------------------------------------
    # Workflow C: Manual re-match
    # -----------------------------------------------------------------------

    def run_matching(
        self,
        case_id: str,
        feed_id: Optional[str] = None,
    ) -> dict:
        """Trigger matching for an existing case (optionally against one feed)."""
        logger.info(f"[Orchestrator] Workflow C: re-match | case_id={case_id}")

        result = self.matching_agent.run(
            case_id=case_id,
            feed_id=feed_id,
            notification_callback=self._notify,
        )

        return {
            "workflow": "run_matching",
            "matching": result,
        }
