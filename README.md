# LIFEWISE AI — MVP

A local, single-user prototype of a personal AI counselor.

## Requirements
- Python 3.11+
- OpenAI API key for live AI responses

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

Install:
```bash
pip install -r requirements.txt
```

Create a `.env` file by copying `.env.example`, then add your API key.
Never commit `.env` to Git.

Run:
```bash
streamlit run app.py
```

Open the local URL shown by Streamlit, normally http://localhost:8501.

## Tests

```bash
pytest -q
```

## Important limitations
- This is a local, single-user prototype, not production-ready.
- It does not include user authentication or multi-user isolation.
- SQLite stores local profile, goals, approved memories and chat history.
- Memory is explicit: the user chooses what to save. It is not silently inferred.
- Do not deploy this version publicly or enter sensitive personal information.
- For production, add authentication, per-user database ownership, authorization,
  encryption, backups, rate limits, monitoring, deletion/export workflows and
  privacy/legal review.
