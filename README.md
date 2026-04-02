# ∞ canvasfeed

A local Streamlit app that helps university instructors get more out of Canvas discussion boards. Paste a discussion URL, and the app:

- Generates a structured analysis of all student submissions (themes, strengths, misconceptions, students to watch, recommended discussion points).
- Lets you randomly pick students during class and instantly shows a personalised Socratic follow-up question for each one.

Designed to run **locally on the instructor's laptop** and be shared on-screen during class. You can preview how the user interface looks in [this demo](https://canvasfeed.streamlit.app).

---

## Requirements

- Python 3.10 or newer
- A Canvas LMS account with access to the course
- An LLM API key (UvA AI Research Proxy or OpenAI-compatible endpoint)

---

## Setup (one time)

### 1. Clone the repository

```bash
git clone https://github.com/tlcfmg/canvasfeed.git
cd canvasfeed
```

### 2. Create and activate a Python environment

Using conda (recommended):

```bash
conda create -n canvasfeed python=3.10
conda activate canvasfeed
```

Or using venv:

```bash
python3 -m venv .venv
source .venv/bin/activate   # on Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install streamlit canvasapi openai python-dotenv pandas
```

### 4. Create your `.env` file

Copy the template and fill in your credentials:

```bash
cp .env.example .env
```

Open `.env` in any text editor and set:

| Variable | What to put here |
|---|---|
| `CANVAS_ACCESS_TOKEN` | Your personal Canvas API token (see below) |
| `CANVAS_BASE_URL` | Your institution's Canvas URL, e.g. `https://canvas.uva.nl` |
| `LLM_API_KEY` | Your LLM API key |
| `LLM_BASE_URL` | Leave as-is if using the UvA AI Research Proxy |
| `LLM_MODEL` | Leave as-is, or change to a model available on your endpoint |

**How to get a Canvas access token:**

1. Log in to Canvas and click your profile picture (top left).
2. Go to **Account > Settings**.
3. Scroll to **Approved Integrations** and click **New Access Token**.
4. Give it a name (e.g. "canvasfeed") and click **Generate Token**.
5. Copy the token immediately — Canvas only shows it once.

> **Security note:** `.env` is listed in `.gitignore` and will never be committed to Git. Never share your tokens publicly.

### 5. Customise the course context (optional but recommended)

Open `app.py` and find the `COURSE_CONTEXT` block near the top of the file. Replace it with a description of your course — the learning objectives, topics, and student background. This text is sent to the AI model with every prompt, so the generated questions and summaries will be grounded in your specific course.

---

## Running the app

```bash
streamlit run app.py
```

The app opens automatically at `http://localhost:8501`. You can share your screen during class and use it directly from the browser.

---

## How to use the app

### Step 1: Copy the Canvas discussion URL

Open Canvas, navigate to the discussion thread you want to review, and copy the URL from your browser's address bar. It will look like:

```
https://canvas.uva.nl/courses/50503/discussion_topics/933669
```

You do not need to know the course ID or discussion ID — the app reads them from the URL automatically.

### Step 2: Paste the URL and wait for it to load

Paste the URL into the field at the top of the app. The app will:

1. Fetch all student posts from Canvas.
2. Generate a personalised Socratic follow-up question for each student.
3. Generate an overall discussion summary.

This takes about one minute the first time. Results are cached for one hour, so switching discussions or reopening the app is instant.

### Step 3: Run the in-class follow-up session

The app opens on the **In-Class Follow-up** tab. Click **Pick a Student** to randomly select a student. You will see:

- Their original submission.
- A personalised Socratic follow-up question to pose during class discussion.

Click **Next Student** to pick another student. Each student appears at most once per session. Click **Reset** to start a new round.

### Step 4: Review the Discussion Summary tab

Switch to the **Discussion Summary** tab. The AI-generated summary is organised into five sections:

- **Overall Summary** — key themes and quality of engagement
- **Common Strengths** — what students understood well
- **Misconceptions and Gaps** — recurring errors or shallow reasoning
- **Students to Watch** — outstanding students and those who may need support
- **Recommended Discussion Points** — concrete topics to address in class

---

## Adapting this app for your course

All course-specific configuration is at the top of `app.py`:

| What to change | Where |
|---|---|
| Course description and learning objectives | `COURSE_CONTEXT` constant |
| Language model or endpoint | `.env` — `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY` |
| Canvas institution URL | `.env` — `CANVAS_BASE_URL` |
| Cache duration (default: 1 hour) | `ttl=3600` in `@st.cache_data` decorators |

---

## Project structure

```
canvasfeed/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
├── .env                # Your local secrets (never committed to Git)
├── .env.example        # Template — copy this to .env to get started
├── .gitignore          # Excludes .env, notebooks, and other sensitive files
└── README.md           # This file
```

> The `code/` folder (Jupyter notebooks) is excluded from Git as notebook outputs may contain real student data.

---

## Troubleshooting

**The app shows "Missing configuration" on startup**
Make sure your `.env` file exists in the project root and contains valid values for `CANVAS_ACCESS_TOKEN` and `LLM_API_KEY`.

**Canvas API error: Unauthorized**
Your Canvas access token may have expired or been revoked. Generate a new one and update `.env`.

**Canvas API error: Not Found**
The URL you pasted may point to a discussion you do not have access to, or the discussion may have been deleted. Check the URL and your Canvas permissions.

**The summary or follow-up questions look generic**
Fill in the `COURSE_CONTEXT` block in `app.py` with your actual course description and learning objectives. The more specific you are, the more relevant the AI output will be.

**Results are stale after students post new entries**
Results are cached for one hour. To force a refresh, restart the app (`Ctrl+C` in the terminal, then `streamlit run app.py`).

---

## Contact

For questions about this app, reach out to [tlc-fmg@uva.nl](mailto:tlc-fmg@uva.nl).
