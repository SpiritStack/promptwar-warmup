"""
VisualLink: Missing Person Reunification Hub
Streamlit Frontend — Single-page multi-tab UI
"""

import io
import json
import os
import tempfile
import time
from datetime import datetime

import streamlit as st

# ── Page config must be FIRST ─────────────────────────────────────────────────
st.set_page_config(
    page_title="VisualLink — Missing Person Reunification Hub",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

  /* Global reset */
  html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
  }

  /* Dark gradient background */
  .stApp {
    background: linear-gradient(135deg, #0f0c29 0%, #1a1a4e 50%, #24243e 100%);
    min-height: 100vh;
  }

  /* Main container */
  .block-container {
    padding: 2rem 3rem !important;
    max-width: 1400px !important;
  }

  /* Hero header */
  .hero {
    text-align: center;
    padding: 2.5rem 1rem 1.5rem;
    background: linear-gradient(135deg, rgba(102,126,234,0.15) 0%, rgba(118,75,162,0.15) 100%);
    border-radius: 20px;
    border: 1px solid rgba(102,126,234,0.3);
    margin-bottom: 2rem;
    backdrop-filter: blur(10px);
  }
  .hero h1 {
    font-size: 2.8rem;
    font-weight: 800;
    background: linear-gradient(135deg, #a78bfa, #60a5fa, #34d399);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0 0 0.5rem;
  }
  .hero p {
    color: #94a3b8;
    font-size: 1.1rem;
    margin: 0;
  }

  /* Stat cards */
  .stat-card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 1.5rem;
    text-align: center;
    backdrop-filter: blur(10px);
    transition: transform 0.2s, border-color 0.2s;
  }
  .stat-card:hover { transform: translateY(-3px); border-color: rgba(167,139,250,0.5); }
  .stat-number { font-size: 2.5rem; font-weight: 800; color: #a78bfa; }
  .stat-label  { color: #94a3b8; font-size: 0.9rem; margin-top: 0.25rem; }

  /* Tab nav overrides */
  .stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background: rgba(255,255,255,0.03);
    border-radius: 12px;
    padding: 6px;
    border: 1px solid rgba(255,255,255,0.08);
  }
  .stTabs [data-baseweb="tab"] {
    border-radius: 10px !important;
    padding: 10px 24px !important;
    color: #94a3b8 !important;
    font-weight: 500 !important;
    background: transparent !important;
    border: none !important;
  }
  .stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #667eea, #764ba2) !important;
    color: white !important;
    font-weight: 600 !important;
  }

  /* Form cards */
  .form-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 20px;
    padding: 2rem;
    backdrop-filter: blur(12px);
  }

  /* Match card */
  .match-card {
    background: rgba(52, 211, 153, 0.08);
    border: 1px solid rgba(52,211,153,0.3);
    border-radius: 16px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    backdrop-filter: blur(8px);
    transition: transform 0.2s;
  }
  .match-card:hover { transform: translateX(4px); }

  .confidence-high   { color: #34d399; font-weight: 700; }
  .confidence-medium { color: #fbbf24; font-weight: 700; }
  .confidence-low    { color: #f87171; font-weight: 700; }

  /* Progress ring placeholder */
  .confidence-badge {
    display: inline-block;
    padding: 4px 14px;
    border-radius: 100px;
    font-size: 0.85rem;
    font-weight: 600;
  }
  .badge-high   { background: rgba(52,211,153,0.2);  color: #34d399; border: 1px solid #34d399; }
  .badge-medium { background: rgba(251,191,36,0.2);  color: #fbbf24; border: 1px solid #fbbf24; }
  .badge-low    { background: rgba(248,113,113,0.2); color: #f87171; border: 1px solid #f87171; }

  /* Input overrides */
  .stTextInput > div > div > input,
  .stNumberInput > div > div > input,
  .stTextArea > div > div > textarea {
    background: rgba(255,255,255,0.06) !important;
    border-color: rgba(255,255,255,0.15) !important;
    color: white !important;
    border-radius: 10px !important;
  }
  .stTextInput > div > div > input:focus,
  .stTextArea > div > div > textarea:focus {
    border-color: #667eea !important;
    box-shadow: 0 0 0 2px rgba(102,126,234,0.25) !important;
  }

  /* Buttons */
  .stButton > button {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.6rem 2rem !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    transition: opacity 0.2s, transform 0.2s !important;
    box-shadow: 0 4px 15px rgba(102,126,234,0.4) !important;
  }
  .stButton > button:hover {
    opacity: 0.9 !important;
    transform: translateY(-2px) !important;
  }

  /* Upload area */
  .stFileUploader > div {
    border: 2px dashed rgba(102,126,234,0.4) !important;
    border-radius: 12px !important;
    background: rgba(102,126,234,0.05) !important;
  }

  /* Success / info / warning boxes */
  .stAlert { border-radius: 12px !important; }

  /* Section headings */
  .section-title {
    font-size: 1.4rem;
    font-weight: 700;
    color: #e2e8f0;
    margin-bottom: 1.2rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid rgba(102,126,234,0.3);
  }

  /* Dividers */
  hr { border-color: rgba(255,255,255,0.08) !important; }

  /* Metrics */
  [data-testid="metric-container"] {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 14px;
    padding: 1rem 1.2rem;
  }
  [data-testid="metric-container"] label { color: #94a3b8 !important; font-size: 0.85rem !important; }
  [data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #a78bfa !important; font-weight: 700 !important;
  }

  /* Sidebar */
  [data-testid="stSidebar"] {
    background: rgba(15, 12, 41, 0.95) !important;
    border-right: 1px solid rgba(255,255,255,0.08) !important;
  }

  /* Spinner */
  .stSpinner > div { border-top-color: #667eea !important; }

  /* Expander */
  .streamlit-expanderHeader {
    background: rgba(255,255,255,0.04) !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
  }

  /* DataFrame */
  .stDataFrame { border-radius: 10px; overflow: hidden; }

  /* Labels */
  .stSelectbox label, .stTextInput label, .stNumberInput label,
  .stTextArea label, .stFileUploader label {
    color: #cbd5e1 !important;
    font-weight: 500 !important;
  }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(102,126,234,0.5); border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

# ── Lazy imports (avoid crashing if env not configured) ───────────────────────
def _get_orchestrator():
    try:
        from agents.orchestrator_agent import OrchestratorAgent
        return OrchestratorAgent()
    except Exception as e:
        return None


def _get_firestore():
    try:
        from google.cloud import firestore
        return firestore.Client()
    except Exception:
        return None


# ── Demo/mock data for development ────────────────────────────────────────────
DEMO_CASES = [
    {
        "case_id": "demo-001",
        "name": "Maria Santos",
        "age": 34,
        "contact_email": "family@example.com",
        "last_known_location": "Downtown Emergency Shelter, NY",
        "status": "active",
        "submitted_at": "2026-03-27T08:15:00Z",
        "features": {
            "face_description": "Oval face, dark brown eyes, small nose",
            "hair": "Dark brown, shoulder-length, wavy",
            "clothing_top": "Blue denim jacket",
            "clothing_bottom": "Dark jeans",
            "approximate_age_range": "30-40",
            "skin_tone": "Medium olive",
            "distinguishing_features": ["Small scar above left eyebrow"],
        },
    },
    {
        "case_id": "demo-002",
        "name": "James Okafor",
        "age": 52,
        "contact_email": "okafor.family@example.com",
        "last_known_location": "Riverside Community Center, CA",
        "status": "active",
        "submitted_at": "2026-03-25T14:30:00Z",
        "features": {
            "face_description": "Round face, dark eyes, broad nose",
            "hair": "Black, short, natural",
            "clothing_top": "Grey hoodie",
            "clothing_bottom": "Black sweatpants",
            "approximate_age_range": "50-60",
            "skin_tone": "Dark brown",
            "distinguishing_features": ["Glasses", "Grey beard"],
        },
    },
]

DEMO_MATCHES = [
    {
        "match_id": "match-alpha-001",
        "case_id": "demo-001",
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
        "matched_at": "2026-03-28T06:00:00Z",
        "notification_status": "sent",
    }
]


# ── Helper functions ───────────────────────────────────────────────────────────

def confidence_badge(score: float) -> str:
    if score >= 0.85:
        return f'<span class="confidence-badge badge-high">✓ {score:.0%} High</span>'
    elif score >= 0.75:
        return f'<span class="confidence-badge badge-medium">~ {score:.0%} Medium</span>'
    else:
        return f'<span class="confidence-badge badge-low">✗ {score:.0%} Low</span>'


def maps_embed_url(location: str) -> str:
    query = location.replace(" ", "+")
    return f"https://maps.google.com/maps?q={query}&output=embed"


# ══════════════════════════════════════════════════════════════════════════════
# HERO HEADER
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="hero">
  <h1>🔍 VisualLink</h1>
  <p>Missing Person Reunification Hub — AI-powered family reconnection using Gemini Vision</p>
</div>
""", unsafe_allow_html=True)

# ── Dashboard KPI row ──────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Active Cases", "2", delta="+1 today")
with col2:
    st.metric("Shelter Feeds", "3", delta="2 new feeds")
with col3:
    st.metric("Confirmed Matches", "1", delta="↑ 1 this week")
with col4:
    st.metric("Avg. Confidence", "89%", delta="+4%")

st.markdown("<div style='margin: 1.5rem 0;'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN TABS
# ══════════════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "📸  Report Missing Person",
    "📹  Shelter Operator Portal",
    "🔎  Case Status Dashboard",
    "⚙️  System Info",
])


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Report Missing Person
# ─────────────────────────────────────────────────────────────────────────────

with tab1:
    st.markdown('<p class="section-title">Report a Missing Person</p>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="form-card">', unsafe_allow_html=True)

        col_form, col_preview = st.columns([1, 1], gap="large")

        with col_form:
            st.markdown("#### 👤 Person Details")

            full_name = st.text_input(
                "Full Name *",
                placeholder="e.g. Maria Santos",
                key="mp_name",
            )
            age = st.number_input(
                "Approximate Age *",
                min_value=1, max_value=120, value=30,
                key="mp_age",
            )
            last_location = st.text_input(
                "Last Known Location *",
                placeholder="e.g. Downtown Emergency Shelter, Chicago IL",
                key="mp_location",
            )
            contact_email = st.text_input(
                "Family Contact Email *",
                placeholder="family@example.com",
                key="mp_email",
            )

            st.markdown("#### 📸 Upload Photo(s)")
            uploaded_files = st.file_uploader(
                "Upload JPEG or PNG (multiple allowed, low-quality OK)",
                type=["jpg", "jpeg", "png"],
                accept_multiple_files=True,
                key="mp_photos",
            )

            run_match_now = st.checkbox(
                "Run matching against existing shelter feeds immediately",
                value=True,
                key="mp_run_match",
            )

            submit_report = st.button(
                "🚀 Submit Report & Start Analysis",
                key="submit_report",
                use_container_width=True,
            )

        with col_preview:
            st.markdown("#### 🖼️ Photo Preview")
            if uploaded_files:
                cols_img = st.columns(min(len(uploaded_files), 3))
                for idx, uf in enumerate(uploaded_files):
                    with cols_img[idx % 3]:
                        st.image(uf, use_container_width=True, caption=uf.name)
            else:
                st.markdown("""
                <div style="height: 220px; display: flex; align-items: center;
                            justify-content: center; border: 2px dashed rgba(102,126,234,0.3);
                            border-radius: 12px; color: #475569;">
                  <div style="text-align: center;">
                    <div style="font-size: 3rem;">📷</div>
                    <div>Photos appear here</div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

            if uploaded_files and full_name:
                st.markdown("#### 📋 Submission Preview")
                st.json({
                    "name": full_name,
                    "age": age,
                    "last_known_location": last_location,
                    "contact_email": contact_email,
                    "photos_count": len(uploaded_files),
                    "run_matching": run_match_now,
                })

        st.markdown('</div>', unsafe_allow_html=True)

    # ── Handle submission ──────────────────────────────────────────────────────
    if submit_report:
        if not all([full_name, last_location, contact_email, uploaded_files]):
            st.error("⚠️ Please fill in all required fields and upload at least one photo.")
        else:
            orchestrator = _get_orchestrator()

            with st.spinner("🔄 Processing — preprocessing image, extracting features, running matching…"):
                image_bytes = uploaded_files[0].read()

                if orchestrator:
                    try:
                        result = orchestrator.report_missing_person(
                            image_bytes=image_bytes,
                            name=full_name,
                            age=int(age),
                            contact_email=contact_email,
                            last_known_location=last_location,
                            run_matching=run_match_now,
                        )
                        case_id = result["ingestion"]["case_id"]

                        st.success(f"✅ Case submitted successfully!")
                        st.balloons()

                        col_r1, col_r2 = st.columns(2)
                        with col_r1:
                            st.metric("Case ID", case_id)
                        with col_r2:
                            matches = result.get("matching", {})
                            if matches:
                                st.metric("Immediate Matches Found",
                                          matches.get("matches_found", 0))

                        with st.expander("📄 Full Response"):
                            st.json(result)

                    except Exception as e:
                        st.error(f"❌ Error: {e}")
                        st.info("💡 Make sure your .env file is configured. Showing demo response:")
                        time.sleep(1.5)
                        st.success("✅ Demo mode — Case submitted!")
                        st.metric("Demo Case ID", "case-" + "x7k2m9")
                else:
                    # Demo mode
                    time.sleep(2)
                    st.success("✅ Demo mode — Case submitted successfully!")
                    st.info("🔧 Configure `.env` to connect to real Gemini + Firestore.")
                    st.metric("Demo Case ID", "demo-003")

                    with st.expander("📄 Extracted Features (Demo)"):
                        st.json({
                            "face_description": "Oval face, hazel eyes, defined cheekbones",
                            "hair": "Brown, medium length, straight",
                            "clothing_top": "Red hoodie with white logo",
                            "clothing_bottom": "Dark grey jeans",
                            "approximate_age_range": f"{age-5}-{age+5}",
                            "skin_tone": "Light medium",
                            "distinguishing_features": ["Small mole on right cheek"],
                        })


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Shelter Operator Portal
# ─────────────────────────────────────────────────────────────────────────────

with tab2:
    st.markdown('<p class="section-title">Shelter Operator Portal</p>', unsafe_allow_html=True)

    st.markdown('<div class="form-card">', unsafe_allow_html=True)

    col_feed_form, col_feed_info = st.columns([1, 1], gap="large")

    with col_feed_form:
        st.markdown("#### 🏠 Shelter Information")

        shelter_name = st.text_input(
            "Shelter Name *",
            placeholder="e.g. Hope Bridge Emergency Shelter",
            key="shelter_name",
        )
        shelter_location = st.text_input(
            "Shelter Address / GPS Coordinates *",
            placeholder="e.g. 123 Hope St, Brooklyn, NY 11201",
            key="shelter_location",
        )

        st.markdown("#### 📹 Security Feed Upload")
        video_file = st.file_uploader(
            "Upload security footage (MP4 / MOV, max 500 MB)",
            type=["mp4", "mov", "avi"],
            key="shelter_video",
        )

        if video_file:
            file_mb = len(video_file.getvalue()) / (1024 * 1024)
            st.info(f"📦 File size: {file_mb:.1f} MB | Format: {video_file.type}")

        submit_feed = st.button(
            "📤 Upload Feed & Run Analysis",
            key="submit_feed",
            use_container_width=True,
        )

    with col_feed_info:
        st.markdown("#### ℹ️ How Video Analysis Works")
        st.markdown("""
        <div style="background: rgba(102,126,234,0.08); border-radius: 12px; padding: 1.5rem;
                    border: 1px solid rgba(102,126,234,0.2);">
          <ol style="color: #cbd5e1; line-height: 2;">
            <li>Video is split into <strong>30-second chunks</strong></li>
            <li>Each chunk is sampled at <strong>1 FPS</strong> to reduce API load</li>
            <li>Gemini Vision analyzes each chunk for persons visible >3 seconds</li>
            <li>Per-person descriptors are extracted and stored in Firestore</li>
            <li>Automatic cross-matching runs against all <strong>active missing cases</strong></li>
            <li>High-confidence matches (≥75%) trigger <strong>instant email alerts</strong></li>
          </ol>
        </div>
        """, unsafe_allow_html=True)

        if shelter_location:
            st.markdown("#### 🗺️ Shelter Location Preview")
            embed_url = maps_embed_url(shelter_location)
            st.components.v1.iframe(embed_url, height=220)

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Handle feed submission ─────────────────────────────────────────────────
    if submit_feed:
        if not all([shelter_name, shelter_location, video_file]):
            st.error("⚠️ Please provide shelter name, location, and a video file.")
        else:
            orchestrator = _get_orchestrator()

            with st.spinner("🔄 Uploading and analysing shelter feed — this may take several minutes…"):
                # Save video to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                    tmp.write(video_file.read())
                    tmp_path = tmp.name

                if orchestrator:
                    try:
                        result = orchestrator.upload_shelter_feed(
                            video_path=tmp_path,
                            shelter_name=shelter_name,
                            shelter_location=shelter_location,
                        )
                        os.unlink(tmp_path)

                        st.success("✅ Feed analysis complete!")
                        col_f1, col_f2, col_f3 = st.columns(3)
                        with col_f1:
                            st.metric("Feed ID", result["feed_analysis"]["feed_id"][:8] + "…")
                        with col_f2:
                            st.metric("Sightings Found", result["feed_analysis"].get("sightings_count", 0))
                        with col_f3:
                            st.metric("Matches Triggered", result.get("total_matches", 0))

                    except Exception as e:
                        os.unlink(tmp_path)
                        st.error(f"❌ Error: {e}")
                else:
                    os.unlink(tmp_path)
                    time.sleep(3)
                    st.success("✅ Demo mode — Feed analysis complete!")
                    st.metric("Demo Sightings", "12")
                    st.metric("Demo Matches", "1")
                    st.info("🔧 Configure `.env` to connect to real Gemini + Firestore.")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Case Status Dashboard
# ─────────────────────────────────────────────────────────────────────────────

with tab3:
    st.markdown('<p class="section-title">Case Status Dashboard</p>', unsafe_allow_html=True)

    col_search, col_list = st.columns([2, 1], gap="large")

    with col_search:
        case_id_input = st.text_input(
            "🔑 Enter Case ID",
            placeholder="e.g. demo-001 or paste full UUID",
            key="case_search",
        )
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            search_btn = st.button("🔍 Look Up Case", key="case_lookup", use_container_width=True)
        with col_btn2:
            if st.button("📋 Load Demo Case", key="load_demo", use_container_width=True):
                case_id_input = "demo-001"
                st.session_state["case_search"] = "demo-001"

    with col_list:
        st.markdown("#### 📂 Recent Active Cases")
        for demo_case in DEMO_CASES:
            st.markdown(f"""
            <div style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.1);
                        border-radius: 10px; padding: 0.8rem 1rem; margin-bottom: 0.5rem;
                        cursor: pointer;">
              <div style="color: #e2e8f0; font-weight: 600;">{demo_case['name']}</div>
              <div style="color: #94a3b8; font-size: 0.8rem;">{demo_case['case_id']} · Age {demo_case['age']}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Case details panel ─────────────────────────────────────────────────────
    search_id = st.session_state.get("case_search", "")
    if search_btn or search_id in ["demo-001", "demo-002"]:
        target_id = st.session_state.get("case_search", "")
        if not target_id:
            st.warning("Please enter a Case ID.")
        else:
            st.markdown("---")

            # Try Firestore first; fall back to demo data
            case_data   = None
            match_list  = []

            db = _get_firestore()
            if db:
                try:
                    doc = db.collection("missing_persons").document(target_id).get()
                    if doc.exists:
                        case_data = doc.to_dict()
                    matches_docs = (
                        db.collection("matches")
                        .where("case_id", "==", target_id)
                        .order_by("matched_at")
                        .stream()
                    )
                    match_list = [m.to_dict() for m in matches_docs]
                except Exception:
                    pass

            # Fall back to demo data
            if not case_data:
                case_data  = next((c for c in DEMO_CASES if c["case_id"] == target_id), None)
                match_list = [m for m in DEMO_MATCHES if m["case_id"] == target_id]

            if not case_data:
                st.error(f"Case `{target_id}` not found.")
            else:
                # ── Case header ────────────────────────────────────────────────
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.metric("Name", case_data.get("name"))
                with c2: st.metric("Age", case_data.get("age"))
                with c3: st.metric("Status", case_data.get("status","active").title())
                with c4: st.metric("Matches Found", len(match_list))

                # ── Feature profile ────────────────────────────────────────────
                features = case_data.get("features", {})
                if features:
                    with st.expander("🧬 Extracted Feature Profile", expanded=True):
                        feat_cols = st.columns(3)
                        feat_items = [
                            ("Face", features.get("face_description")),
                            ("Hair", features.get("hair")),
                            ("Top", features.get("clothing_top")),
                            ("Bottom", features.get("clothing_bottom")),
                            ("Age Range", features.get("approximate_age_range")),
                            ("Skin Tone", features.get("skin_tone")),
                        ]
                        for i, (label, value) in enumerate(feat_items):
                            with feat_cols[i % 3]:
                                st.markdown(f"""
                                <div style="background: rgba(255,255,255,0.04); border-radius: 10px;
                                            padding: 0.8rem; margin-bottom: 0.5rem;
                                            border: 1px solid rgba(255,255,255,0.08);">
                                  <div style="color: #94a3b8; font-size: 0.75rem; font-weight: 600;
                                              text-transform: uppercase; letter-spacing: 0.05em;">
                                    {label}
                                  </div>
                                  <div style="color: #e2e8f0; font-size: 0.9rem; margin-top: 0.3rem;">
                                    {value or '—'}
                                  </div>
                                </div>
                                """, unsafe_allow_html=True)

                        dist = features.get("distinguishing_features", [])
                        if dist:
                            st.markdown(f"**🔖 Distinguishing Features:** {', '.join(dist)}")

                # ── Matches ────────────────────────────────────────────────────
                st.markdown("### 🎯 Match History")

                if not match_list:
                    st.info("No confirmed matches yet. Matching runs automatically when new shelter feeds are uploaded.")
                else:
                    for m in match_list:
                        conf = m.get("match_confidence", 0)
                        badge = confidence_badge(conf)

                        with st.container():
                            st.markdown(f"""
                            <div class="match-card">
                              <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                                <div>
                                  <div style="font-size: 1.1rem; font-weight: 700; color: #e2e8f0;">
                                    🏠 {m.get('shelter_name')}
                                  </div>
                                  <div style="color: #94a3b8; font-size: 0.85rem; margin-top: 0.3rem;">
                                    Sighting at {m.get('timestamp_seconds', 0)}s into feed ·
                                    Match ID: {m.get('match_id', '')[:8]}…
                                  </div>
                                </div>
                                <div>{badge}</div>
                              </div>
                              <p style="color: #cbd5e1; margin-top: 0.8rem; line-height: 1.6; font-size: 0.9rem;">
                                {m.get('match_reasoning', '')}
                              </p>
                            </div>
                            """, unsafe_allow_html=True)

                            # Matched / discrepancy columns
                            mc1, mc2 = st.columns(2)
                            with mc1:
                                st.markdown("**✅ Matched Features**")
                                for f in m.get("key_matched_features", []):
                                    st.markdown(f"- {f}")
                            with mc2:
                                st.markdown("**⚠️ Discrepancies**")
                                for d in m.get("key_discrepancies", []):
                                    st.markdown(f"- {d}")

                            # Map embed
                            loc = m.get("shelter_location") or case_data.get("last_known_location", "")
                            if loc:
                                st.markdown(f"**📍 Shelter Location:** {loc}")
                                st.components.v1.iframe(maps_embed_url(loc), height=300)

                            st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — System Info
# ─────────────────────────────────────────────────────────────────────────────

with tab4:
    st.markdown('<p class="section-title">System Information & Configuration Status</p>', unsafe_allow_html=True)

    col_sys1, col_sys2 = st.columns(2)

    with col_sys1:
        st.markdown("#### 🤖 Agent Status")

        agents_info = [
            ("IngestionAgent",      "Photo preprocessing + Gemini Vision feature extraction"),
            ("FeedAnalysisAgent",   "Video chunking + Gemini Video Understanding"),
            ("MatchingAgent",       "Forensic profile comparison (Gemini)"),
            ("NotificationAgent",   "Gmail + Calendar + Sheets integration"),
            ("OrchestratorAgent",   "Root multi-agent coordinator"),
        ]

        for agent_name, desc in agents_info:
            st.markdown(f"""
            <div style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);
                        border-radius: 10px; padding: 1rem; margin-bottom: 0.5rem; display: flex;
                        align-items: flex-start; gap: 1rem;">
              <div style="background: rgba(52,211,153,0.2); color: #34d399; border-radius: 50%;
                          width: 32px; height: 32px; display: flex; align-items: center;
                          justify-content: center; flex-shrink: 0; font-weight: 700;">✓</div>
              <div>
                <div style="color: #e2e8f0; font-weight: 600;">{agent_name}</div>
                <div style="color: #94a3b8; font-size: 0.85rem;">{desc}</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

    with col_sys2:
        st.markdown("#### 🔧 Configuration Checklist")

        from config import settings

        checks = [
            ("Gemini API Key",           bool(settings.GEMINI_API_KEY)),
            ("Gemini Model",             bool(settings.GEMINI_MODEL)),
            ("GCP Project ID",           bool(settings.GCP_PROJECT_ID)),
            ("GCS Bucket",               bool(settings.GCS_BUCKET_NAME)),
            ("Service Account File",     os.path.exists(settings.GOOGLE_SERVICE_ACCOUNT_FILE)),
            ("Notification Email",       bool(settings.NOTIFICATION_SENDER_EMAIL)),
            ("Case Worker Email",        bool(settings.CASE_WORKER_EMAIL)),
            ("Audit Sheet ID",           bool(settings.AUDIT_SHEET_ID)),
        ]

        for label, ok in checks:
            icon  = "✅" if ok else "❌"
            color = "#34d399" if ok else "#f87171"
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; align-items: center;
                        padding: 0.6rem 1rem; border-radius: 8px; margin-bottom: 0.3rem;
                        background: rgba(255,255,255,0.03);">
              <span style="color: #cbd5e1;">{label}</span>
              <span style="color: {color};">{icon}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("#### 📐 Pipeline Architecture")
        st.markdown("""
        ```
        User Upload ─► IngestionAgent ─► Firestore
                              │
                              ▼
                       MatchingAgent ◄── FeedAnalysisAgent ◄── Shelter Video
                              │
                      (confidence ≥ 0.75)
                              │
                              ▼
                      NotificationAgent
                    ╔═══════╤═══════╤═══════╗
                    ║ Gmail │  Cal  │Sheets ║
                    ╚═══════╧═══════╧═══════╝
        ```
        """)

    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #475569; font-size: 0.85rem; padding: 1rem;">
      VisualLink v1.0 · Powered by Google Gemini Vision · Built with Google ADK<br>
      <em>For humanitarian use only · Handle personal data responsibly</em>
    </div>
    """, unsafe_allow_html=True)
