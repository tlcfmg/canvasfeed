"""Canvas Discussion Assistant
─────────────────────────────────────────────────────────────────────────────
Streamlit app for university instructors. Paste a Canvas discussion URL to:
  - Review an AI-generated analysis of all student submissions (Summary tab).
  - Randomly call on students with instant personalised Socratic follow-up
    questions for in-class discussion (Follow-up tab).

Adapting this app for your course
───────────────────────────────────
1. Copy .env.example to .env and fill in your CANVAS_ACCESS_TOKEN and LLM_API_KEY.
2. Edit COURSE_CONTEXT below with your course description and objectives.
   This text is injected into every LLM prompt so the AI tailors its output
   to your subject matter, student level, and learning goals.
3. Run:  streamlit run app.py

Caching strategy (how the app stays fast)
──────────────────────────────────────────
- fetch_entries()   : Canvas API call, cached per (course_id, discussion_id).
- cached_followup() : one LLM call per student, cached per (course_id, discussion_id, user_id).
- get_summary()     : one LLM call per discussion, cached per (course_id, discussion_id).
- Assembled results : stored in st.session_state per browser tab (never shared between users).

Different teachers courses are automatically isolated by their unique (course_id, discussion_id).
"""
from __future__ import annotations

import html as htmllib
import os
import random
import re
from html.parser import HTMLParser

import pandas as pd
import streamlit as st
from canvasapi import Canvas
from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

# ─── Environment ──────────────────────────────────────────────────────────────
load_dotenv(find_dotenv(raise_error_if_not_found=False))

CANVAS_BASE_URL = os.getenv("CANVAS_BASE_URL", "https://canvas.uva.nl")
CANVAS_ACCESS_TOKEN = os.getenv("CANVAS_ACCESS_TOKEN")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL", "https://ai-research-proxy.azurewebsites.net"
)
LLM_MODEL = os.getenv("LLM_MODEL", "mistral-small-3.2")

# ─── Course context (EDIT THIS FOR YOUR COURSE) ───────────────────────────────
# Paste your course description, objectives, or any context that helps the AI
# understand what students are discussing and what depth of understanding is
# expected. This text is embedded in both the follow-up question prompt and
# the discussion summary prompt, so the output is grounded in your course.
COURSE_CONTEXT = """
Course: Digital Analytics for Communication Science

Objectives
The course develops students knowledge, understanding, skills, and critical
attitudes in digital analytics for communication science and practice. Students will:
- Gain up-to-date knowledge of digital analytics for communication, including
  theoretical and methodological developments in the field.
- Design and execute data analysis plans to address business challenges in communication.
- Evaluate data analysis results, make actionable recommendations, and identify limitations.
- Relate communication theory to digital analytics processes at advanced levels.
- Reflect on ethical and privacy aspects of digital analytics, including GDPR implications.
- Use Python to consolidate communication-related digital data and build basic
  exploratory, predictive, and classification models.

Course topics
How communication professionals use digital analytics to identify and address
communication challenges. Topics include: gathering and understanding digital
data (web behaviour, social media); preparing data for analysis; building
predictive and classification models; evaluating model effectiveness; ethical
machine learning; and relating digital analytics to communication theories.
Tools covered include Google Analytics and Python (pandas, visualisation, ML).

Student background
Masters students in communication science with quantitative research methods
knowledge. The course is not overly technical but requires analytical thinking
and the ability to evaluate data-driven arguments.
""".strip()

# ─── Page config (must be the very first Streamlit call) ─────────────────────
st.set_page_config(
    page_title="∞ canvasfeed",
    page_icon="∞",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Styling ──────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Lora:ital,wght@0,400;0,600;1,400&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── Hide Streamlit chrome ── */
#MainMenu, footer { visibility: hidden; }
.block-container { padding-top: 1.75rem; max-width: 1100px; }

/* ── App header ── */
.app-header {
    border-bottom: 2px solid #1a1a2e;
    padding-bottom: 0.75rem;
    margin-bottom: 1.75rem;
}
.app-title {
    font-size: 1.9rem;
    font-weight: 700;
    color: #1a1a2e;
    letter-spacing: -0.5px;
    margin: 0;
}
.app-subtitle {
    font-size: 0.88rem;
    color: #6b7280;
    margin-top: 0.25rem;
}

/* ── Discussion title strip ── */
.discussion-title {
    font-family: 'Lora', serif;
    font-size: 1.15rem;
    font-weight: 600;
    color: #374151;
    margin: 0.75rem 0 0.25rem 0;
}

/* ── Section caption (muted intro text) ── */
.section-caption {
    font-size: 0.875rem;
    color: #6b7280;
    line-height: 1.65;
    margin-bottom: 1.25rem;
}

/* ── Student name ── */
.student-name {
    font-family: 'Lora', serif;
    font-size: 1.45rem;
    font-weight: 600;
    color: #111827;
    margin: 0.1rem 0 0.5rem 0;
}

/* ── Follow-up question card ── */
.followup-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-left: 4px solid #1a1a2e;
    border-radius: 0 8px 8px 0;
    padding: 1.1rem 1.4rem;
    font-family: 'Lora', serif;
    font-size: 1.05rem;
    line-height: 1.75;
    color: #1f2937;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    margin-top: 0.5rem;
}

/* ── Submission card ── */
.submission-card {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 1rem 1.25rem;
    font-family: 'Lora', serif;
    font-size: 0.92rem;
    line-height: 1.75;
    color: #374151;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}

/* ── Label chip (e.g. "Follow-up question") ── */
.label-chip {
    display: inline-block;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6b7280;
    margin-bottom: 0.5rem;
}
</style>
""",
    unsafe_allow_html=True,
)


# ─── Utilities ────────────────────────────────────────────────────────────────
# Tags that represent a paragraph/line break in rendered HTML.
_BLOCK_TAGS = frozenset(
    ["p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
     "blockquote", "pre", "hr", "thead", "tbody", "tfoot"]
)


class _Stripper(HTMLParser):
    """HTML → clean plain-text converter.

    Block-level tags are turned into newlines so the LLM receives properly
    structured paragraphs rather than one long space-joined string.
    """

    def __init__(self) -> None:
        super().__init__()
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _BLOCK_TAGS:
            self._buf.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _BLOCK_TAGS:
            self._buf.append("\n")

    def handle_data(self, data: str) -> None:
        self._buf.append(data)

    def handle_entityref(self, name: str) -> None:
        self._buf.append(htmllib.unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        self._buf.append(htmllib.unescape(f"&#{name};"))

    def get_text(self) -> str:
        raw = htmllib.unescape("".join(self._buf))
        # Collapse runs of spaces/tabs on each line, then collapse 3+ newlines to 2.
        lines = [" ".join(ln.split()) for ln in raw.splitlines()]
        text = "\n".join(lines)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def strip_html(html_str: str) -> str:
    """Return clean plain text from an HTML string, preserving paragraph structure."""
    if not html_str:
        return ""
    s = _Stripper()
    s.feed(html_str)
    return s.get_text()


def parse_canvas_url(url: str) -> tuple[int | None, int | None]:
    """Return (course_id, discussion_id) from a Canvas discussion URL, or (None, None)."""
    m = re.search(r"/courses/(\d+)/discussion_topics/(\d+)", url)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


# ─── Cached API clients (singletons, shared across sessions) ─────────────────
@st.cache_resource
def _canvas() -> Canvas:
    return Canvas(CANVAS_BASE_URL, CANVAS_ACCESS_TOKEN)


@st.cache_resource
def _llm() -> OpenAI:
    return OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)


# ─── Cached data functions ────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_entries(course_id: int, discussion_id: int) -> tuple[pd.DataFrame, str]:
    """Fetch all Canvas discussion entries (no LLM calls).

    Cached for 1 hour per (course_id, discussion_id).
    """
    course = _canvas().get_course(course_id)
    topic = course.get_discussion_topic(discussion_id)
    entries = list(topic.get_topic_entries())
    rows = []
    for entry in entries:
        name = getattr(entry, "user_name", None) or f"User {getattr(entry, 'user_id', '?')}"
        raw_html = getattr(entry, "message", "") or ""
        plain = strip_html(raw_html)
        rows.append(
            {
                "Student Name": name,
                "Canvas User ID": getattr(entry, "user_id", None),
                "Submission (HTML)": raw_html,
                "Submission": plain,
            }
        )
    return pd.DataFrame(rows), topic.title


@st.cache_data(ttl=3600, show_spinner=False)
def cached_followup(
    course_id: int, discussion_id: int, user_id: int | None, submission_text: str
) -> str:
    """Generate (and cache) one Socratic follow-up question for a single student.

    Cached per (course_id, discussion_id, user_id) — instant on repeat calls.
    """
    if not submission_text.strip():
        return "(This submission contained no readable text — no follow-up question generated.)"
    resp = _llm().chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an educational assistant helping a university lecturer. "
                    "You will receive course context and a student discussion post. "
                    "Write exactly one concise, open-ended Socratic question to pose "
                    "to the student during in-class discussion. "
                    "The question should challenge their assumptions, prompt deeper "
                    "reflection on their reasoning, and connect to the course topics. "
                    "Output only the question, with no preamble or explanation."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Course context:\n{COURSE_CONTEXT}\n\n"
                    f"Student post:\n\n{submission_text}"
                ),
            },
        ],
        max_tokens=130,
    )
    content = resp.choices[0].message.content
    return content.strip() if content else "(No response returned by the model.)"


@st.cache_data(ttl=3600, show_spinner=False)
def get_summary(course_id: int, discussion_id: int) -> str:
    """Generate (and cache) the structured discussion summary for the instructor.

    Calls fetch_entries internally (cache hit) so it only needs the two IDs.
    """
    df, _ = fetch_entries(course_id, discussion_id)
    block = "\n\n".join(
        f"Student: {r['Student Name']}\nPost: {r['Submission']}"
        for _, r in df.iterrows()
    )
    resp = _llm().chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert educational analyst. "
                    "You will receive course context and a set of student discussion posts. "
                    "Write a well-organised, easy-to-read Markdown report for the instructor. "
                    "Use proper Markdown: ## for section headings, - for bullet points, "
                    "and **bold** for key terms. "
                    "Be concise, coherent, specific, and objective throughout. "
                    "Use exactly these five sections in this order:\n\n"
                    "## Overall Summary\n"
                    "3-5 sentences covering the key themes discussed, the range of student "
                    "perspectives, and the overall quality of engagement with the material.\n\n"
                    "## Common Strengths\n"
                    "Bullet list of concepts or arguments that students generally grasped well, "
                    "with a brief explanation for each point.\n\n"
                    "## Misconceptions and Gaps\n"
                    "Bullet list of recurring misunderstandings or areas lacking depth, "
                    "grounded in the course learning objectives.\n\n"
                    "## Students to Watch\n"
                    "Bullet list naming students who showed exceptional insight OR who may "
                    "benefit from extra support, with a one-sentence rationale each.\n\n"
                    "## Recommended Discussion Points\n"
                    "Numbered list of 2-3 concrete topics to address in the next class, "
                    "directly linked to the misconceptions or gaps identified above."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Course context:\n{COURSE_CONTEXT}\n\n"
                    f"Student posts:\n\n{block}"
                ),
            },
        ],
        max_tokens=1000,
    )
    content = resp.choices[0].message.content
    return content.strip() if content else "(No summary returned by the model.)"


# ─── Per-session state helpers ────────────────────────────────────────────────
def _init_session(disc_key: str) -> None:
    """Reset follow-up tracking when the active discussion changes.

    session_state is per browser tab — never shared between teachers.
    """
    if st.session_state.get("_disc_key") != disc_key:
        st.session_state.update(
            {
                "_disc_key": disc_key,
                "seen_indices": set(),
                "current_idx": None,
            }
        )


def _pick_next(total: int) -> None:
    """Randomly select an unseen student and record them as seen."""
    seen = st.session_state["seen_indices"]
    pool = [i for i in range(total) if i not in seen]
    if pool:
        idx = random.choice(pool)
        st.session_state["seen_indices"] = seen | {idx}
        st.session_state["current_idx"] = idx


# ─── Tab: Discussion Summary ──────────────────────────────────────────────────
def render_summary_tab(summary: str, df: pd.DataFrame) -> None:
    st.markdown(
        "<p class='section-caption'>"
        "Analysis of what students understood, where they struggled, "
        "and what to address in class"
        "</p>",
        unsafe_allow_html=True,
    )

    st.markdown(summary)

    st.divider()

    with st.expander("📊 All Submissions", expanded=False):
        st.dataframe(
            df[["Student Name", "Submission", "Follow-Up Question"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Student Name": st.column_config.TextColumn("Student", width="small"),
                "Submission": st.column_config.TextColumn("Submission", width="large"),
                "Follow-Up Question": st.column_config.TextColumn("Follow-Up Question", width="large"),
            },
        )


# ─── Tab: In-Class Follow-up ──────────────────────────────────────────────────
def render_followup_tab(df: pd.DataFrame) -> None:
    st.markdown(
        "<p class='section-caption'>"
        "Randomly select one student to ask a follow-up question. Each student appears at most once per session."
        "</p>",
        unsafe_allow_html=True,
    )

    total = len(df)
    seen = st.session_state["seen_indices"]
    shown = len(seen)
    remaining = total - shown

    # ── Controls ──────────────────────────────────────────────────────────────
    c_next, c_reset, _ = st.columns([1.3, 1, 4])

    with c_next:
        # Label changes after the first pick so the teacher knows it cycles.
        label = "Pick a Student" if shown == 0 else "Next Student"
        if st.button(
            label, type="primary", disabled=(remaining == 0), use_container_width=True
        ):
            _pick_next(total)
            st.rerun()

    with c_reset:
        # Reset clears seen history so all students can be picked again.
        if st.button("Reset", disabled=(shown == 0), use_container_width=True):
            st.session_state["seen_indices"] = set()
            st.session_state["current_idx"] = None
            st.rerun()

    # ── All done ──────────────────────────────────────────────────────────────
    if remaining == 0 < total:
        st.success(
            f"All {total} students have been called on. "
            "Click **Reset** to begin a new round."
        )
        return

    # ── Idle prompt ───────────────────────────────────────────────────────────
    idx = st.session_state.get("current_idx")
    if idx is None:
        return

    # ── Student card ──────────────────────────────────────────────────────────
    row = df.iloc[idx]
    st.divider()

    st.markdown(
        f"<p class='student-name'>{row['Student Name']}</p>",
        unsafe_allow_html=True,
    )

    with st.expander("📄 View Submission", expanded=False):
        html_content = row["Submission (HTML)"].strip()
        if html_content:
            st.markdown(html_content, unsafe_allow_html=True)
        else:
            st.caption("No text content found in this submission.")

    # ── Follow-up question (pre-generated, instant) ──────────────────────────
    st.markdown("**Follow-up question for in-class discussion:**")
    st.markdown(
        f"<div class='followup-card'>{row['Follow-Up Question']}</div>",
        unsafe_allow_html=True,
    )
    st.write("")


# ─── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div class="app-header">
            <div class="app-title">∞ canvasfeed</div>
            <div class="app-subtitle">
                AI-assisted feedback and follow-up for university teachers using Canvas
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Environment guard ─────────────────────────────────────────────────────
    missing_vars = [
        k
        for k, v in {
            "CANVAS_ACCESS_TOKEN": CANVAS_ACCESS_TOKEN,
            "LLM_API_KEY": LLM_API_KEY,
        }.items()
        if not v
    ]
    if missing_vars:
        st.error(
            f"**Missing configuration:** `{'`, `'.join(missing_vars)}` not set.  \n"
            "Add these variables to a `.env` file in the project root and restart the app."
        )
        return

    # ── URL input ─────────────────────────────────────────────────────────────
    url_input = st.text_input(
        "Paste a Canvas discussion URL to get started",
        placeholder="https://canvas.uva.nl/courses/50503/discussion_topics/933669",
        help=(
            "Navigate to the discussion thread in Canvas and copy the URL "
            "from your browser's address bar."
        ),
    )

    if not url_input.strip():
        with st.expander("How to use this app", expanded=False):
            st.markdown(
                """
**Step 1: Copy the Canvas discussion URL**

Open Canvas in your browser, navigate to the discussion thread you want to review,
and copy the URL from the address bar. It will look like:

`https://canvas.uva.nl/courses/50503/discussion_topics/933669`

**Step 2: Paste the URL and wait for it to load**

Paste the URL into the field above. The app fetches all student posts from Canvas
and uses an AI model to generate a discussion summary and a personalised follow-up
question for every student. This takes about a minute the first time. After that,
results are cached for one hour, so switching between discussions or reopening the
app is instant.

**Step 3: Use the In-Class Follow-up tab**

The app opens on the *In-Class Follow-up* tab. Click **Pick a Student** to randomly
select a student. You will see their submission on the right and a personalised
Socratic follow-up question on the left, ready to pose in class. Click **Next Student**
to pick another student. Each student is picked at most once. Click **Reset** to start
a new round.

**Step 4: Review the Discussion Summary tab**

Switch to the *Discussion Summary* tab for an AI-generated overview of the full
discussion: key themes, what students grasped well, common misconceptions, and
concrete points to address in your next class.
"""
            )
        return

    # ── Parse URL ─────────────────────────────────────────────────────────────
    course_id, discussion_id = parse_canvas_url(url_input.strip())
    if course_id is None:
        st.error(
            "**Could not parse a Canvas discussion URL.**  \n"
            "Make sure the URL contains `/courses/{id}/discussion_topics/{id}`."
        )
        return

    # ── Load discussion ────────────────────────────────────────────────────────
    disc_key = f"{course_id}:{discussion_id}"
    _init_session(disc_key)

    # Use session_state to cache the fully assembled df+summary within a session
    # so that button-click reruns skip the generation loop entirely.
    _loaded_key = f"loaded_{disc_key}"
    if _loaded_key not in st.session_state:
        # ── Step 1: fetch entries from Canvas ─────────────────────────────────
        with st.spinner("Fetching what the students said…"):
            try:
                df_raw, title = fetch_entries(course_id, discussion_id)
            except Exception as exc:
                st.error(f"**Canvas API error:** {exc}")
                return

        if df_raw.empty:
            st.warning(
                "No entries found for this discussion. "
                "Check that the URL is correct and that your Canvas token has access to this course."
            )
            return

        # ── Step 2: generate follow-up questions with a progress bar ──────────
        n = len(df_raw)
        pb = st.progress(0, text=f"Fetching what the students said… (0 / {n})")
        followups: list[str] = []
        for i, (_, row) in enumerate(df_raw.iterrows()):
            pb.progress(
                i / n,
                text=(
                    f"Fetching what the students said… "
                    f"({i + 1} / {n}): {row['Student Name']}"
                ),
            )
            followups.append(
                cached_followup(
                    course_id, discussion_id, row["Canvas User ID"], row["Submission"]
                )
            )

        df_raw["Follow-Up Question"] = followups

        # ── Step 3: generate discussion summary ───────────────────────────────
        pb.progress(1.0, text="Creating discussion summary…")
        try:
            summary = get_summary(course_id, discussion_id)
        except Exception as exc:
            summary = f"*(Summary could not be created: {exc})*"
        pb.empty()

        st.session_state[_loaded_key] = (df_raw, title, summary)

    df, title, summary = st.session_state[_loaded_key]

    if df.empty:
        st.warning(
            "No entries found for this discussion. "
            "Check that the URL is correct and that your Canvas token has access to this course."
        )
        return

    # ── Tabs ──────────────────────────────────────────────────────────────────
    # Follow-up is the first tab so that st.rerun() after picking a student
    # lands back here instead of jumping to the Summary tab.
    tab_fu, tab_sum = st.tabs(["In-Class Follow-up", "Discussion Summary"])

    with tab_fu:
        st.markdown(
            f"<div class='discussion-title'>{title}</div>",
            unsafe_allow_html=True,
        )
        render_followup_tab(df)

    with tab_sum:
        st.markdown(
            f"<div class='discussion-title'>{title}</div>",
            unsafe_allow_html=True,
        )
        render_summary_tab(summary, df)


if __name__ == "__main__":
    main()
