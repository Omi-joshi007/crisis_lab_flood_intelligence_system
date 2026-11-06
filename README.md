# Flood Intelligence System

An AI-assisted research prototype that converts unstructured New Zealand flood news into a structured, evidence-linked **Event -> Incident -> Impact** knowledge base, then exposes the results through an interactive Dash dashboard and an event-scoped RAG assistant.

🌐 **Live Dashboard:** [Explore the Flood Intelligence Dashboard](https://crisis-lab-flood-intelligence-syste.vercel.app/)

## What this project does

The project addresses a practical disaster-intelligence problem: flood impacts are reported across many news articles, but the information is fragmented, duplicated and difficult to analyse consistently. The pipeline collects flood-related news, identifies which real-world flood event each article belongs to, extracts incidents and impacts, preserves supporting evidence, and makes the results explorable through a dashboard.

Current repository data contains approximately:

- **4,742** collected news articles
- **9,268** article-event verification records
- **1,029** verified event-linked articles
- **34** structured flood/severe-weather events
- **176** extracted incidents
- **358** extracted impacts

## High-level architecture

```text
DigitalNZ / news sources
        |
        v
news_articles
        |
        v
Broad event candidate retrieval
        |
        v
LLM article <-> event verification
(time + location + disaster context)
        |
        v
Confidence filtering + primary event assignment
        |
        v
Verified articles grouped by event
        |
        v
LLM Event -> Incident -> Impact extraction
        |
        v
PostgreSQL / CSV structured outputs
        |
        +-----------------------+
        |                       |
        v                       v
Dash + Plotly dashboard     Event-scoped RAG assistant
        |
        v
Research / impact intelligence / future impact-based warning work
```

## Core pipeline

The current verified pipeline is implemented in `flood_event_verified_pipeline.py` and separates **retrieval**, **verification**, and **extraction**.

1. Load the predefined New Zealand flood-event catalogue.
2. Retrieve broad candidate articles for each event.
3. Create article-event verification requests.
4. Use an LLM to assess temporal, geographic and disaster-context consistency.
5. Keep high-confidence accepted matches and resolve a primary event per article.
6. Group verified articles by event.
7. Extract structured events, incidents, impacts, locations, evidence and supporting article IDs.
8. Store results in PostgreSQL and/or export them to CSV for dashboard deployment.

## Repository guide

| File | Purpose |
|---|---|
| `digital_nz_api.py` | Collects flood-related records from DigitalNZ and inserts/updates them in `news_articles`. Requires `DIGITALNZ_API_KEY` and PostgreSQL settings. |
| `api.py` | Lightweight DigitalNZ API client used by the collection script. |
| `flood_event_verified_pipeline.py` | Main verified LLM pipeline: candidate retrieval, article-event verification, primary assignment, grouped extraction and database import. |
| `table_schema.sql` | PostgreSQL schema for `news_articles`, event validation, verified event articles, events, incidents and impacts; also includes useful inspection queries. |
| `commands.txt` | Handy command reference for running the verified batch workflow. |
| `final_dashboard_verified_updated.py` | Database-backed Dash dashboard for local/research use with PostgreSQL. |
| `final_dashboard_csv.py` | CSV-backed Dash dashboard used for lightweight deployment without a hosted database. |
| `api/index.py` or `index.py` | Vercel Python adapter that imports the Dash app and exposes its Flask server. |
| `vercel.json` | Routes Vercel requests to the Python entrypoint. If your repository currently names this `versel.json`, rename it to `vercel.json`. |
| `requirements.txt` | Python dependencies for the dashboard/deployment environment. |
| `news_articles.csv` | Collected source-news export. |
| `flood_article_event_validation.csv` | Full audit trail of article-event verification decisions, confidence and matching signals. |
| `flood_event_articles.csv` | Articles accepted and linked to final events. |
| `flood_events.csv` | Event-level structured output and evidence. |
| `flood_incidents.csv` | Incident-level records with dates, locations, evidence and supporting article IDs. |
| `flood_impacts.csv` | Impact-level records linked to incidents/events, including impact type, value, location and evidence. |

## Quick start

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a local `.env` file. Do **not** commit it.

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-5.4-mini

DIGITALNZ_API_KEY=your_digitalnz_key

SOURCE_DB_HOST=localhost
SOURCE_DB_PORT=5432
SOURCE_DB_NAME=flood_database
SOURCE_DB_USER=postgres
SOURCE_DB_PASSWORD=your_password

TARGET_DB_HOST=localhost
TARGET_DB_PORT=5432
TARGET_DB_NAME=flood_event_intelligence
TARGET_DB_USER=postgres
TARGET_DB_PASSWORD=your_password
```

### 3. Create the database schema

Run the required `CREATE TABLE` statements from `table_schema.sql` in PostgreSQL.

### 4. Run the verified pipeline

```bash
python flood_event_verified_pipeline.py prepare-verify
python flood_event_verified_pipeline.py process-all-verify-parts
python flood_event_verified_pipeline.py combine-verify
python flood_event_verified_pipeline.py import-verify
python flood_event_verified_pipeline.py prepare-extract
python flood_event_verified_pipeline.py submit-extract
python flood_event_verified_pipeline.py status --batch-id <BATCH_ID>
python flood_event_verified_pipeline.py download-extract --batch-id <BATCH_ID>
python flood_event_verified_pipeline.py import-extract
```

The pipeline also provides `run-all` and additional batch-management commands. Check:

```bash
python flood_event_verified_pipeline.py --help
```

### 5. Run the dashboard locally

For the CSV version:

```bash
python final_dashboard_csv.py
```

For the PostgreSQL-backed version:

```bash
python final_dashboard_verified_updated.py
```

Then open the local Dash URL shown in the terminal.

## Dashboard capabilities

- National and event-specific flood intelligence views
- Event, year, region and impact-category filters
- Impact hotspot mapping with New Zealand location fallbacks
- Impact-category, regional and yearly visual summaries
- Linked source-article inspection for provenance
- Event-scoped RAG assistant for evidence-grounded questions

## Extending or forking the project

The codebase is deliberately modular. Common extension points are:

- **New sources:** add another collection module that writes into the `news_articles` structure.
- **Better retrieval:** add keyword ranking, embeddings or geospatial/temporal pre-filtering before LLM verification.
- **Model comparison:** keep prompts and evaluation data fixed and swap the model provider/model family.
- **Taxonomy changes:** extend incident/impact categories and update the extraction schema/prompt together.
- **Geospatial improvement:** replace fallback centroids with authoritative geocoding or coordinates extracted during curation.
- **Evaluation:** create independent gold annotations and report precision, recall, F1, false-positive rate and evidence-grounding quality.
- **Operational forecasting:** connect historical impacts with rainfall, river, forecast or hazard-model outputs to support impact-based flood warning research.

## Important notes

- This is a **research prototype**, not an operational emergency-warning system.
- News coverage is incomplete and may contain geographic or reporting bias.
- LLM confidence values are model outputs and should not be treated as calibrated probabilities without validation.
- Keep API keys, database passwords and `.env` files out of GitHub.
- The CSV dashboard is convenient for demonstrations; PostgreSQL remains the better source of truth for pipeline development and auditing.

## Project focus

The long-term research direction is to use the structured historical relationship between **hazard events, local incidents and observed consequences** as an evidence layer for future **impact-based flood warning and forecasting**.
