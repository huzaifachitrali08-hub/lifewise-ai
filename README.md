# LIFEWISE AI V15 — Intelligent Goal-to-Action Workspace

A local Streamlit prototype for personal guidance, goal-aware roadmaps, editable action plans and goal coaching.

## What's new in V15

- **Two planning modes:** AI Smart Plan and Manual Plan.
- **Goal-aware roadmap generation:** identifies common goal types (medical career, data science, software career, business, skill learning and general goals) and creates different staged plans rather than the same generic 12 actions for every goal.
- **Long-term planning:** medical-career roadmaps use a multi-year horizon and include eligibility, admission preparation, medical education, supervised practice/registration and early-career milestones. The suggested seven-year horizon is an estimate, not a promise or official rule.
- **Personal context:** Smart Plan asks for country, current education/qualification and the user's current situation. This context is saved with the goal and supplied to its private Goal Coach.
- **Manual planning:** users can create an empty goal workspace, then add their own actions and name their own stages/milestones.
- Existing dashboards, progress tracking, action statuses, custom actions and private Goal Coach are retained.
- Existing SQLite databases are migrated by adding the new goal metadata columns; existing goals and actions are preserved.

## Requirements
- Python 3.10+
- Google Gemini API key for live counselor chat (the goal-aware template planner also works without an API key)

## Setup

```bash
python -m venv venv
```

Windows:
```bash
venv\Scripts\activate
```

macOS/Linux:
```bash
source venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your Google AI API key:
```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

Never commit `.env` to Git or share your API key.

Run:
```bash
streamlit run app.py
```

Open the local URL shown by Streamlit, normally http://localhost:8501.

## Important planning limitations

- Smart Plan uses goal-type-specific planning templates and the context supplied by the user. It is a planning assistant, not a guarantee of admission, employment, business success or professional qualification.
- Medical education, admission, internship/house-job, licensing and registration requirements vary by country and change over time. Users must verify the current rules with official regulators and institutions. The suggested duration is only a planning estimate.
- Users can edit or delete generated actions and add their own stages and actions.
- Daily/weekly tasks should be generated progressively from the next milestone, not treated as a fixed schedule for every day over several years.

## Production limitations

This is a development prototype. Before public deployment, complete security, privacy, authorization, encryption, backup, rate-limit, monitoring, deletion/export and legal reviews. Do not enter highly sensitive personal information.
