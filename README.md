# Lifesaving Championship What-If Simulator

Interactive web app for exploring ""what if"" scenarios at the World Lifesaving Championships.

## Quick start

```bash
pip install -r requirements.txt
pytest tests/                     # verify simulation logic
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## What it does

Toggle candidate athletes (who didn't compete in the real championship) into individual swimming events. The app recomputes:
- Where each candidate would have placed
- Which real finalists/B-finalists they displaced
- How the country medal-table standings change

## Architecture

- `simulator.py` — pure simulation logic, no UI deps
- `data_loader.py` — JSON loading + validation
- `app.py` — Streamlit UI

See `CLAUDE.md` for the full spec.
