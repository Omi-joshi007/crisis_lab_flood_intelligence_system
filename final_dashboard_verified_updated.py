import os
import pandas as pd
import psycopg2
import plotly.express as px
import plotly.graph_objects as go

from dash import Dash, dcc, html, Input, Output, State, dash_table
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ------------------------------------------------------------
# Config
# ------------------------------------------------------------

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

DB_CONFIG = {
    "host": os.getenv("TARGET_DB_HOST", os.getenv("DB_HOST", "localhost")),
    "port": int(os.getenv("TARGET_DB_PORT", os.getenv("DB_PORT", "5432"))),
    "dbname": os.getenv("TARGET_DB_NAME", os.getenv("DB_NAME", "flood_event_intelligence")),
    "user": os.getenv("TARGET_DB_USER", os.getenv("DB_USER", "postgres")),
    "password": os.getenv("TARGET_DB_PASSWORD", os.getenv("DB_PASSWORD", "")),
}

# ------------------------------------------------------------
# Theme
# ------------------------------------------------------------

THEME = {
    "page_bg": "#05080a",
    "page_bg_alt": "#0a0f12",
    "card_bg": "#0f1417",
    "card_bg_soft": "#151d20",
    "border": "#244136",
    "text_main": "#e8fff2",
    "text_soft": "#9cc9b0",
    "accent": "#7CFFB2",
    "accent_dark": "#33cc7a",
    "accent_soft": "#123426",
    "chip_bg": "#143224",
    "chip_text": "#caffdf",
    "map_paper": "#0f1417",
    "warning": "#fbbf24",
    "danger": "#f87171",
}

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing in .env")
    return OpenAI(api_key=api_key)

def prettify_label(value):
    if value is None:
        return ""
    value = str(value).strip()
    value = value.replace("_", " ")
    return value.title()

def safe_text(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value)

def truncate_text(value, max_chars=2500):
    text = safe_text(value)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + " ..."

def to_python_int(value, default=None):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return int(value)

def get_table_columns(table_name):
    query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position;
    """
    with get_connection() as conn:
        df = pd.read_sql(query, conn, params=[table_name])
    return set(df["column_name"].tolist())

def style_plotly(fig, title=None):
    fig.update_layout(
        paper_bgcolor=THEME["card_bg"],
        plot_bgcolor=THEME["card_bg"],
        font={"color": THEME["text_main"]},
        title_font={"color": THEME["accent"], "size": 18},
        legend={
            "bgcolor": "rgba(15,20,23,0.88)",
            "bordercolor": THEME["border"],
            "borderwidth": 1,
            "font": {"color": THEME["text_main"]},
        },
        margin={"l": 30, "r": 20, "t": 50, "b": 30},
    )
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        color=THEME["text_soft"],
    )
    fig.update_yaxes(
        gridcolor="rgba(124,255,178,0.10)",
        zeroline=False,
        color=THEME["text_soft"],
    )
    if title:
        fig.update_layout(title=title)
    return fig

# ------------------------------------------------------------
# NZ fallback centroids for approximate mapping
# ------------------------------------------------------------

NZ_LOCATION_LOOKUP = {
    "northland": (-35.72, 174.32),
    "auckland": (-36.85, 174.76),
    "waikato": (-37.78, 175.28),
    "bay of plenty": (-37.69, 176.17),
    "gisborne": (-38.66, 178.02),
    "hawke's bay": (-39.49, 176.92),
    "hawkes bay": (-39.49, 176.92),
    "taranaki": (-39.06, 174.08),
    "manawatū-whanganui": (-40.35, 175.61),
    "manawatu-whanganui": (-40.35, 175.61),
    "wellington": (-41.28, 174.77),
    "tasman": (-41.30, 173.20),
    "nelson": (-41.27, 173.28),
    "marlborough": (-41.51, 173.96),
    "west coast": (-42.45, 171.21),
    "canterbury": (-43.53, 172.63),
    "otago": (-45.87, 170.50),
    "southland": (-46.41, 168.35),

    "whangārei": (-35.73, 174.32),
    "whangarei": (-35.73, 174.32),
    "auckland city": (-36.85, 174.76),
    "hamilton": (-37.79, 175.28),
    "tauranga": (-37.69, 176.17),
    "gisborne city": (-38.66, 178.02),
    "napier": (-39.49, 176.92),
    "hastings": (-39.64, 176.84),
    "wairoa": (-39.03, 177.37),
    "esk valley": (-39.30, 176.83),
    "new plymouth": (-39.06, 174.08),
    "whanganui": (-39.93, 175.05),
    "ohura": (-38.88, 174.89),
    "palmerston north": (-40.36, 175.61),
    "lower hutt": (-41.21, 174.91),
    "upper hutt": (-41.13, 175.07),
    "porirua": (-41.13, 174.84),
    "nelson city": (-41.27, 173.28),
    "blenheim": (-41.51, 173.96),
    "westport": (-41.75, 171.60),
    "greymouth": (-42.45, 171.21),
    "christchurch": (-43.53, 172.63),
    "selwyn": (-43.64, 172.33),
    "ashburton": (-43.90, 171.75),
    "timaru": (-44.40, 171.25),
    "dunedin": (-45.87, 170.50),
    "clutha": (-46.24, 169.77),
    "gore": (-46.10, 168.94),
    "queenstown": (-45.03, 168.66),
    "invercargill": (-46.41, 168.35),
    "edgecumbe": (-37.98, 176.83),
    "whakatāne": (-37.95, 176.99),
    "whakatane": (-37.95, 176.99),
    "rangitata": (-44.00, 171.20),
    "rotorua": (-38.14, 176.25),
    "ngongotahā": (-38.08, 176.20),
    "ngongotaha": (-38.08, 176.20),
    "banks peninsula": (-43.75, 172.90),
    "otorohanga": (-38.18, 175.21),
    "ōtorohanga": (-38.18, 175.21),
    "tairāwhiti": (-38.66, 178.02),
    "tairawhiti": (-38.66, 178.02),
}

def resolve_fallback_lat_lon(row):
    candidates = [
        safe_text(row.get("impact_location_name")).lower().strip(),
        safe_text(row.get("impact_city")).lower().strip(),
        safe_text(row.get("impact_district")).lower().strip(),
        safe_text(row.get("impact_region")).lower().strip(),
        safe_text(row.get("location_name")).lower().strip(),
        safe_text(row.get("incident_city")).lower().strip(),
        safe_text(row.get("incident_district")).lower().strip(),
        safe_text(row.get("incident_region")).lower().strip(),
        safe_text(row.get("primary_region")).lower().strip(),
    ]
    for candidate in candidates:
        if candidate and candidate in NZ_LOCATION_LOOKUP:
            lat, lon = NZ_LOCATION_LOOKUP[candidate]
            return lat, lon
    return None, None

# ------------------------------------------------------------
# Data loading
# ------------------------------------------------------------

def load_events():
    query = """
        SELECT
            event_id,
            event_name,
            event_type,
            primary_region,
            summary,
            article_count,
            start_date,
            end_date,
            event_evidence_text,
            source_url
        FROM flood_events
        ORDER BY start_date NULLS LAST, event_name;
    """
    with get_connection() as conn:
        return pd.read_sql(query, conn)

def load_articles(event_id):
    event_id = int(event_id)
    query = """
        SELECT
            article_id,
            article_title,
            article_url,
            published_at
        FROM flood_event_articles
        WHERE event_id = %s
        ORDER BY published_at ASC NULLS LAST, article_id ASC;
    """
    with get_connection() as conn:
        return pd.read_sql(query, conn, params=[event_id])

def load_impacts_all():
    """
    Load impact records from the verified pipeline schema.

    The new pipeline stores:
      - impact-specific location fields in flood_impacts
      - parent incident location fields in flood_incidents

    We LEFT JOIN flood_incidents so the dashboard can fall back to the
    incident location when an individual impact has no specific location.
    """

    impact_cols = get_table_columns("flood_impacts")
    incident_cols = get_table_columns("flood_incidents")

    # Core impact columns produced by the verified pipeline.
    requested_impact_cols = [
        "impact_id",
        "incident_id",
        "event_id",
        "impact_category",
        "impact_type",
        "impact_value",
        "impact_unit",
        "impact_description",
        "impact_evidence_text",
        "supporting_article_ids",
        "location_available",
        "impact_location_name",
        "impact_address",
        "impact_street",
        "impact_suburb",
        "impact_city",
        "impact_district",
        "impact_region",
        "impact_country",
        "impact_river",
        "location_resolution_level",
        "location_confidence",
        "location_notes",
        # Kept for forward compatibility if coordinates are added later.
        "impact_lat",
        "impact_lon",
    ]

    actual_impact_cols = [c for c in requested_impact_cols if c in impact_cols]

    if not actual_impact_cols:
        return pd.DataFrame()

    select_parts = [f"i.{c}" for c in actual_impact_cols]

    # Parent-incident location fallback used by the existing map/display code.
    if "location_name" in incident_cols:
        select_parts.append("inc.location_name AS location_name")
    else:
        select_parts.append("NULL::text AS location_name")

    # These incident fields are useful for future expansion and do not change
    # the current dashboard appearance.
    optional_incident_aliases = [
        ("incident_type", "parent_incident_type"),
        ("incident_title", "parent_incident_title"),
        ("incident_description", "parent_incident_description"),
        ("city", "incident_city"),
        ("district", "incident_district"),
        ("region", "incident_region"),
        ("country", "incident_country"),
        ("river", "incident_river"),
        ("location_resolution_level", "incident_location_resolution_level"),
        ("location_confidence", "incident_location_confidence"),
        ("incident_date", "incident_date"),
        ("incident_evidence_text", "incident_evidence_text"),
    ]

    for source_col, alias in optional_incident_aliases:
        if source_col in incident_cols:
            select_parts.append(f"inc.{source_col} AS {alias}")

    query = f"""
        SELECT
            {", ".join(select_parts)}
        FROM flood_impacts i
        LEFT JOIN flood_incidents inc
          ON inc.incident_id = i.incident_id
        ORDER BY i.event_id, i.impact_id;
    """

    with get_connection() as conn:
        return pd.read_sql(query, conn)

def build_master_dataset():
    events_df = load_events()
    impacts_df = load_impacts_all()

    if impacts_df.empty:
        impacts_df = pd.DataFrame(columns=["event_id"])

    for col in [
        "impact_lat", "impact_lon", "impact_location_name", "impact_city",
        "impact_district", "impact_region", "location_name",
        "incident_city", "incident_district", "incident_region",
        "location_available", "location_resolution_level",
        "location_confidence", "location_notes", "impact_category",
        "impact_type", "impact_description", "impact_value", "impact_unit"
    ]:
        if col not in impacts_df.columns:
            impacts_df[col] = None

    merged = impacts_df.merge(
        events_df,
        on="event_id",
        how="left",
        suffixes=("", "_event")
    )

    if "start_date" in merged.columns:
        merged["start_date"] = pd.to_datetime(merged["start_date"], errors="coerce")
        merged["event_year"] = merged["start_date"].dt.year
    else:
        merged["event_year"] = None

    merged["impact_category_pretty"] = merged["impact_category"].apply(prettify_label)
    merged["impact_type_pretty"] = merged["impact_type"].apply(prettify_label)

    merged["display_location"] = merged.apply(
        lambda r: safe_text(r.get("impact_location_name"))
        or safe_text(r.get("impact_city"))
        or safe_text(r.get("impact_district"))
        or safe_text(r.get("impact_region"))
        or safe_text(r.get("location_name"))
        or safe_text(r.get("incident_city"))
        or safe_text(r.get("incident_district"))
        or safe_text(r.get("incident_region"))
        or safe_text(r.get("primary_region"))
        or "Unknown",
        axis=1,
    )

    lat_list = []
    lon_list = []

    for _, row in merged.iterrows():
        lat = row.get("impact_lat")
        lon = row.get("impact_lon")
        if pd.notna(lat) and pd.notna(lon):
            lat_list.append(float(lat))
            lon_list.append(float(lon))
        else:
            fl_lat, fl_lon = resolve_fallback_lat_lon(row)
            lat_list.append(fl_lat)
            lon_list.append(fl_lon)

    merged["plot_lat"] = lat_list
    merged["plot_lon"] = lon_list
    merged["is_mapped"] = merged["plot_lat"].notna() & merged["plot_lon"].notna()

    return events_df, merged

events_df, master_impacts_df = build_master_dataset()

# ------------------------------------------------------------
# Selected-event RAG
# ------------------------------------------------------------

def build_event_rag_context(event_id):
    event_id = int(event_id)
    event_df = events_df[events_df["event_id"] == event_id]
    impacts_df = master_impacts_df[master_impacts_df["event_id"] == event_id].copy()
    articles_df = load_articles(event_id)

    if event_df.empty:
        return "No event data found."

    event = event_df.iloc[0]
    context_parts = []

    context_parts.append("SELECTED FLOOD EVENT")
    context_parts.append(f"Event ID: {event['event_id']}")
    context_parts.append(f"Event name: {safe_text(event['event_name'])}")
    context_parts.append(f"Event type: {safe_text(event['event_type'])}")
    context_parts.append(f"Start date: {safe_text(event['start_date'])}")
    context_parts.append(f"End date: {safe_text(event['end_date'])}")
    context_parts.append(f"Primary region: {safe_text(event['primary_region'])}")
    context_parts.append(f"Article count: {safe_text(event['article_count'])}")
    context_parts.append(f"Summary: {truncate_text(event['summary'], 1800)}")
    context_parts.append(f"Event evidence text: {truncate_text(event.get('event_evidence_text'), 1800)}")

    context_parts.append("\nIMPACTS WITH LOCATION AND EVIDENCE")
    if impacts_df.empty:
        context_parts.append("No impacts were extracted for this selected event.")

    for _, impact in impacts_df.iterrows():
        context_parts.append("\n--- IMPACT ---")
        context_parts.append(f"Impact ID: {safe_text(impact.get('impact_id'))}")
        context_parts.append(f"Category: {safe_text(impact.get('impact_category'))}")
        context_parts.append(f"Type: {safe_text(impact.get('impact_type'))}")
        context_parts.append(f"Value: {safe_text(impact.get('impact_value'))}")
        context_parts.append(f"Unit: {safe_text(impact.get('impact_unit'))}")
        context_parts.append(f"Description: {truncate_text(impact.get('impact_description'), 1200)}")
        context_parts.append(f"Evidence: {truncate_text(impact.get('impact_evidence_text'), 1200)}")
        context_parts.append(f"Supporting article IDs: {safe_text(impact.get('supporting_article_ids'))}")
        context_parts.append(f"Impact location name: {safe_text(impact.get('impact_location_name'))}")
        context_parts.append(f"Impact city: {safe_text(impact.get('impact_city'))}")
        context_parts.append(f"Impact district: {safe_text(impact.get('impact_district'))}")
        context_parts.append(f"Impact region: {safe_text(impact.get('impact_region'))}")
        context_parts.append(f"Location resolution: {safe_text(impact.get('location_resolution_level'))}")
        context_parts.append(f"Location confidence: {safe_text(impact.get('location_confidence'))}")
        context_parts.append(f"Location notes: {safe_text(impact.get('location_notes'))}")

    context_parts.append("\nLINKED ARTICLES")
    if articles_df.empty:
        context_parts.append("No linked articles found for this selected event.")

    for _, article in articles_df.head(25).iterrows():
        context_parts.append(
            f"- Article ID {safe_text(article['article_id'])}: "
            f"{safe_text(article['article_title'])} | "
            f"Published: {safe_text(article['published_at'])} | "
            f"URL: {safe_text(article['article_url'])}"
        )

    return "\n".join(context_parts)

def answer_question_with_rag(event_id, user_question):
    event_id = int(event_id)
    context = build_event_rag_context(event_id)
    client = get_openai_client()

    system_prompt = """
You are Aegis, a Crisis Lab flood event assistant.

You answer questions using only the provided database context about the selected New Zealand flood event.

Rules:
- Use only the provided context.
- Do not invent facts, locations, dates, numbers, incidents, impacts, or article references.
- If the answer is not available in the context, say: "I could not find that information in the selected event data."
- Be clear and practical.
- Mention impact types, affected locations, and evidence when useful.
- If evidence is available, include a short "Evidence" section.
- Do not mention that you are using RAG unless asked.
- Do not use Markdown formatting.
""".strip()

    user_prompt = f"""
DATABASE CONTEXT:
{context}

USER QUESTION:
{user_question}
""".strip()

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    return response.output_text

# ------------------------------------------------------------
# Filtering
# ------------------------------------------------------------

ALL_EVENTS_VALUE = "ALL_EVENTS"

def filter_impacts(df, selected_event, selected_years, selected_regions, selected_categories, mapped_only):
    filtered = df.copy()

    if selected_event and selected_event != ALL_EVENTS_VALUE:
        filtered = filtered[filtered["event_id"] == int(selected_event)]

    if selected_years:
        years = [int(y) for y in selected_years]
        filtered = filtered[filtered["event_year"].isin(years)]

    if selected_regions:
        region_series = filtered["primary_region"].fillna("")
        filtered = filtered[region_series.isin(selected_regions)]

    if selected_categories:
        cat_series = filtered["impact_category_pretty"].fillna("")
        filtered = filtered[cat_series.isin(selected_categories)]

    if mapped_only and "mapped_only" in mapped_only:
        filtered = filtered[filtered["is_mapped"] == True]

    return filtered

# ------------------------------------------------------------
# Figures
# ------------------------------------------------------------

def build_map(filtered_df):
    if filtered_df.empty:
        fig = px.scatter_mapbox(lat=[], lon=[], zoom=4)
        fig.update_layout(
            mapbox_style="carto-darkmatter",
            mapbox_center={"lat": -41.0, "lon": 173.0},
            mapbox_zoom=4.3,
            margin={"l": 0, "r": 0, "t": 0, "b": 0},
            paper_bgcolor=THEME["map_paper"],
            plot_bgcolor=THEME["map_paper"],
            font={"color": THEME["text_main"]},
        )
        fig.add_annotation(
            text="No impacts match the selected filters.",
            x=0.5, y=0.5, xref="paper", yref="paper",
            showarrow=False, font={"size": 16, "color": THEME["text_main"]}
        )
        return fig

    map_df = filtered_df[filtered_df["is_mapped"] == True].copy()

    if map_df.empty:
        fig = px.scatter_mapbox(lat=[], lon=[], zoom=4)
        fig.update_layout(
            mapbox_style="carto-darkmatter",
            mapbox_center={"lat": -41.0, "lon": 173.0},
            mapbox_zoom=4.3,
            margin={"l": 0, "r": 0, "t": 0, "b": 0},
            paper_bgcolor=THEME["map_paper"],
            plot_bgcolor=THEME["map_paper"],
            font={"color": THEME["text_main"]},
        )
        fig.add_annotation(
            text="No mappable impacts available for the selected filters.",
            x=0.5, y=0.5, xref="paper", yref="paper",
            showarrow=False, font={"size": 16, "color": THEME["text_main"]}
        )
        return fig

    map_df["hover_text"] = map_df.apply(
        lambda r: (
            f"Event: {safe_text(r.get('event_name'))}<br>"
            f"Impact: {safe_text(r.get('impact_type_pretty'))}<br>"
            f"Category: {safe_text(r.get('impact_category_pretty'))}<br>"
            f"Location: {safe_text(r.get('display_location'))}<br>"
            f"Region: {safe_text(r.get('primary_region'))}<br>"
            f"Resolution: {safe_text(r.get('location_resolution_level'))}<br>"
            f"Description: {truncate_text(r.get('impact_description'), 220)}"
        ),
        axis=1,
    )

    fig = px.scatter_mapbox(
        map_df,
        lat="plot_lat",
        lon="plot_lon",
        color="impact_category_pretty",
        hover_name="impact_type_pretty",
        custom_data=["hover_text"],
        zoom=4.3,
        height=640,
        color_discrete_sequence=[
            "#7CFFB2", "#57e389", "#33cc7a", "#1faa59", "#9cffc1",
            "#6ee7a8", "#4ade80", "#22c55e", "#86efac", "#bbf7d0"
        ],
    )
    fig.update_traces(
        marker={"size": 13, "opacity": 0.92},
        hovertemplate="%{customdata[0]}<extra></extra>"
    )
    fig.update_layout(
        mapbox_style="carto-darkmatter",
        mapbox_center={"lat": -41.0, "lon": 173.0},
        mapbox_zoom=4.3,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor=THEME["map_paper"],
        plot_bgcolor=THEME["map_paper"],
        font={"color": THEME["text_main"]},
        legend_title_text="Impact Category",
        legend={
            "bgcolor": "rgba(15,20,23,0.90)",
            "bordercolor": THEME["border"],
            "borderwidth": 1,
            "font": {"color": THEME["text_main"]},
        },
    )
    return fig

def build_category_chart(filtered_df):
    if filtered_df.empty:
        return style_plotly(go.Figure(), "Impacts by Category")

    cat_df = (
        filtered_df.groupby("impact_category_pretty", dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .head(10)
    )
    fig = px.bar(
        cat_df,
        x="impact_category_pretty",
        y="count",
        text="count",
        color="impact_category_pretty",
        color_discrete_sequence=["#7CFFB2"] * len(cat_df),
    )
    fig.update_traces(marker_line_color=THEME["accent_dark"], marker_line_width=1)
    return style_plotly(fig, "Impacts by Category")

def build_region_chart(filtered_df):
    if filtered_df.empty:
        return style_plotly(go.Figure(), "Top Affected Regions")

    region_df = (
        filtered_df.assign(region_display=filtered_df["primary_region"].fillna("Unknown"))
        .groupby("region_display", dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .head(10)
    )
    fig = px.bar(
        region_df,
        x="count",
        y="region_display",
        orientation="h",
        text="count",
        color_discrete_sequence=["#57e389"],
    )
    fig.update_traces(marker_line_color=THEME["accent_dark"], marker_line_width=1)
    return style_plotly(fig, "Top Affected Regions")

def build_year_chart(filtered_df):
    if filtered_df.empty:
        return style_plotly(go.Figure(), "Impacts by Year")

    year_df = (
        filtered_df.dropna(subset=["event_year"])
        .groupby("event_year")
        .size()
        .reset_index(name="count")
        .sort_values("event_year")
    )
    fig = px.line(
        year_df,
        x="event_year",
        y="count",
        markers=True,
    )
    fig.update_traces(line_color="#7CFFB2", marker_color="#33cc7a")
    return style_plotly(fig, "Impacts by Year")

# ------------------------------------------------------------
# UI builders
# ------------------------------------------------------------

def kpi_card(title, value, subtitle=""):
    return html.Div(
        style={
            "backgroundColor": THEME["card_bg_soft"],
            "padding": "16px",
            "borderRadius": "12px",
            "border": f"1px solid {THEME['border']}",
        },
        children=[
            html.Div(title, style={"fontSize": "12px", "color": THEME["text_soft"], "fontWeight": "700"}),
            html.Div(str(value), style={"fontSize": "28px", "fontWeight": "800", "color": THEME["accent"], "marginTop": "6px"}),
            html.Div(subtitle, style={"fontSize": "12px", "color": THEME["text_soft"], "marginTop": "4px"}) if subtitle else html.Div(),
        ],
    )

def build_articles_panel(selected_event):
    if not selected_event or selected_event == ALL_EVENTS_VALUE:
        return html.Div(
            "Select a specific event to view linked source articles.",
            style={"color": THEME["text_soft"], "fontStyle": "italic"}
        )

    articles_df = load_articles(int(selected_event))
    if articles_df.empty:
        return html.Div(
            "No linked articles found for this event.",
            style={"color": THEME["text_soft"], "fontStyle": "italic"}
        )

    article_cards = []
    for _, row in articles_df.head(5).iterrows():
        article_cards.append(
            html.Div(
                style={
                    "padding": "12px",
                    "borderRadius": "12px",
                    "backgroundColor": THEME["card_bg_soft"],
                    "border": f"1px solid {THEME['border']}",
                    "marginBottom": "10px",
                },
                children=[
                    html.Div(
                        safe_text(row["article_title"]),
                        style={"fontWeight": "700", "color": THEME["text_main"], "marginBottom": "6px"},
                    ),
                    html.Div(
                        f"Article ID: {safe_text(row['article_id'])} | Published: {safe_text(row['published_at'])}",
                        style={"fontSize": "12px", "color": THEME["text_soft"], "marginBottom": "6px"},
                    ),
                    html.A(
                        safe_text(row["article_url"]),
                        href=safe_text(row["article_url"]),
                        target="_blank",
                        style={"color": THEME["accent"], "fontSize": "13px", "wordBreak": "break-all"},
                    ),
                ],
            )
        )

    return html.Div(article_cards)

def build_summary_card(selected_event, filtered_df):
    if selected_event and selected_event != ALL_EVENTS_VALUE:
        event_id = int(selected_event)
        event_row = events_df[events_df["event_id"] == event_id].iloc[0]
        impacts_count = len(filtered_df)
        mapped_count = int(filtered_df["is_mapped"].sum()) if not filtered_df.empty else 0

        return html.Div([
            html.Div(
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "flexWrap": "wrap",
                    "gap": "12px",
                    "marginBottom": "14px",
                },
                children=[
                    html.H2(
                        safe_text(event_row["event_name"]),
                        style={
                            "margin": "0",
                            "fontSize": "30px",
                            "fontWeight": "800",
                            "color": THEME["text_main"],
                        },
                    ),
                    html.Div(
                        style={
                            "backgroundColor": THEME["chip_bg"],
                            "color": THEME["chip_text"],
                            "padding": "8px 14px",
                            "borderRadius": "999px",
                            "fontWeight": "700",
                            "fontSize": "13px",
                            "border": f"1px solid {THEME['accent_dark']}",
                        },
                        children=prettify_label(event_row["event_type"]),
                    ),
                ],
            ),
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fit, minmax(180px, 1fr))",
                    "gap": "14px",
                    "marginBottom": "18px",
                },
                children=[
                    kpi_card("Primary Region", safe_text(event_row["primary_region"])),
                    kpi_card("Articles Linked", safe_text(event_row["article_count"])),
                    kpi_card("Impacts Found", impacts_count),
                    kpi_card("Mapped Impacts", mapped_count, "Location-enabled"),
                ],
            ),
            html.Div(
                style={
                    "backgroundColor": THEME["card_bg_soft"],
                    "padding": "16px",
                    "borderRadius": "12px",
                    "border": f"1px solid {THEME['border']}",
                },
                children=[
                    html.Div("Event Summary", style={"fontSize": "13px", "color": THEME["text_soft"], "fontWeight": "700", "marginBottom": "8px"}),
                    html.P(
                        safe_text(event_row["summary"]),
                        style={
                            "margin": "0",
                            "fontSize": "15px",
                            "lineHeight": "1.7",
                            "color": THEME["text_main"],
                        },
                    ),
                ],
            ),
        ])

    total_events = events_df["event_id"].nunique()
    total_impacts = len(filtered_df)
    mapped_impacts = int(filtered_df["is_mapped"].sum()) if not filtered_df.empty else 0

    top_region = "N/A"
    if not filtered_df.empty and "primary_region" in filtered_df.columns:
        vc = filtered_df["primary_region"].fillna("Unknown").value_counts()
        if not vc.empty:
            top_region = vc.index[0]

    return html.Div([
        html.Div(
            style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "flexWrap": "wrap",
                "gap": "12px",
                "marginBottom": "14px",
            },
            children=[
                html.H2(
                    "National Flood Intelligence Overview",
                    style={
                        "margin": "0",
                        "fontSize": "30px",
                        "fontWeight": "800",
                        "color": THEME["text_main"],
                    },
                ),
                html.Div(
                    style={
                        "backgroundColor": THEME["chip_bg"],
                        "color": THEME["chip_text"],
                        "padding": "8px 14px",
                        "borderRadius": "999px",
                        "fontWeight": "700",
                        "fontSize": "13px",
                        "border": f"1px solid {THEME['accent_dark']}",
                    },
                    children="Policy View",
                ),
            ],
        ),
        html.Div(
            style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fit, minmax(180px, 1fr))",
                "gap": "14px",
                "marginBottom": "18px",
            },
            children=[
                kpi_card("Total Events", total_events, "Events in database"),
                kpi_card("Filtered Impacts", total_impacts, "Current filter result"),
                kpi_card("Mapped Impacts", mapped_impacts, "Ready for map analysis"),
                kpi_card("Top Affected Region", top_region),
            ],
        ),
        html.Div(
            style={
                "backgroundColor": THEME["card_bg_soft"],
                "padding": "16px",
                "borderRadius": "12px",
                "border": f"1px solid {THEME['border']}",
            },
            children=[
                html.Div("Policy Insight", style={"fontSize": "13px", "color": THEME["text_soft"], "fontWeight": "700", "marginBottom": "8px"}),
                html.P(
                    "This view aggregates all selected flood events and impacts to support national-level disaster policy planning. Use the filters to compare years, regions, and impact categories, then use the map and charts to identify hotspots, repeated disruptions, and where intervention planning may be needed.",
                    style={
                        "margin": "0",
                        "fontSize": "15px",
                        "lineHeight": "1.7",
                        "color": THEME["text_main"],
                    },
                ),
            ],
        ),
    ])

# ------------------------------------------------------------
# Dash app
# ------------------------------------------------------------

app = Dash(__name__)
app.title = "Flood Intelligence Dashboard"
app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            html, body {
                margin: 0;
                padding: 0;
                background: #05080a;
                overflow-x: hidden;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""

CARD_STYLE = {
    "backgroundColor": THEME["card_bg"],
    "borderRadius": "16px",
    "padding": "20px",
    "boxShadow": "0 6px 22px rgba(0,0,0,0.28)",
    "border": f"1px solid {THEME['border']}",
}

SECTION_TITLE_STYLE = {
    "fontSize": "22px",
    "fontWeight": "700",
    "color": THEME["accent"],
    "marginBottom": "12px",
}

years_options = sorted([int(y) for y in master_impacts_df["event_year"].dropna().unique().tolist()])
region_options = sorted([r for r in master_impacts_df["primary_region"].dropna().astype(str).unique().tolist() if r.strip()])
category_options = sorted([c for c in master_impacts_df["impact_category_pretty"].dropna().astype(str).unique().tolist() if c.strip()])

app.layout = html.Div(
    style={
        "background": f"linear-gradient(180deg, {THEME['page_bg']} 0%, {THEME['page_bg_alt']} 100%)",
        "minHeight": "100vh",
        "padding": "24px",
        "fontFamily": "Arial, sans-serif",
        "overflowX": "hidden",
        "position": "relative",
        "color": THEME["text_main"],
    },
    children=[
        dcc.Store(id="chat-open-store", data=False),

        html.Div(
            style={
                "maxWidth": "1450px",
                "margin": "0 auto",
                "overflowX": "hidden",
            },
            children=[
                html.Div(
                    style={
                        "marginBottom": "24px",
                        "padding": "24px",
                        "borderRadius": "18px",
                        "background": "linear-gradient(135deg, #05080a 0%, #0f1417 55%, #33cc7a 100%)",
                        "color": "white",
                        "boxShadow": "0 10px 28px rgba(0,0,0,0.35)",
                        "border": f"1px solid {THEME['border']}",
                    },
                    children=[
                        html.H1(
                            "Flood Intelligence Dashboard",
                            style={"margin": "0", "fontSize": "38px", "fontWeight": "800"},
                        ),
                        html.P(
                            "Policy-ready flood intelligence for national situational awareness, hotspot mapping, evidence review, and intervention planning.",
                            style={"marginTop": "10px", "marginBottom": "0", "fontSize": "16px", "opacity": "0.96"},
                        ),
                    ],
                ),

                html.Div(
                    style={**CARD_STYLE, "marginBottom": "24px"},
                    children=[
                        html.Div("Policy Filters", style=SECTION_TITLE_STYLE),
                        html.Div(
                            style={
                                "display": "grid",
                                "gridTemplateColumns": "repeat(auto-fit, minmax(220px, 1fr))",
                                "gap": "14px",
                            },
                            children=[
                                html.Div([
                                    html.Label("Event", style={"display": "block", "fontWeight": "700", "marginBottom": "8px", "color": THEME["text_main"]}),
                                    dcc.Dropdown(
                                        id="event-dropdown",
                                        options=[{"label": "All Events", "value": ALL_EVENTS_VALUE}] + [
                                            {"label": row["event_name"], "value": int(row["event_id"])}
                                            for _, row in events_df.iterrows()
                                        ],
                                        value=ALL_EVENTS_VALUE,
                                        clearable=False,
                                        style={"fontSize": "14px", "color": "#0f172a"},
                                    ),
                                ]),
                                html.Div([
                                    html.Label("Year", style={"display": "block", "fontWeight": "700", "marginBottom": "8px", "color": THEME["text_main"]}),
                                    dcc.Dropdown(
                                        id="year-filter",
                                        options=[{"label": str(y), "value": int(y)} for y in years_options],
                                        multi=True,
                                        placeholder="All years",
                                        style={"fontSize": "14px", "color": "#0f172a"},
                                    ),
                                ]),
                                html.Div([
                                    html.Label("Region", style={"display": "block", "fontWeight": "700", "marginBottom": "8px", "color": THEME["text_main"]}),
                                    dcc.Dropdown(
                                        id="region-filter",
                                        options=[{"label": r, "value": r} for r in region_options],
                                        multi=True,
                                        placeholder="All regions",
                                        style={"fontSize": "14px", "color": "#0f172a"},
                                    ),
                                ]),
                                html.Div([
                                    html.Label("Impact Category", style={"display": "block", "fontWeight": "700", "marginBottom": "8px", "color": THEME["text_main"]}),
                                    dcc.Dropdown(
                                        id="category-filter",
                                        options=[{"label": c, "value": c} for c in category_options],
                                        multi=True,
                                        placeholder="All categories",
                                        style={"fontSize": "14px", "color": "#0f172a"},
                                    ),
                                ]),
                                html.Div([
                                    html.Label("Map Readiness", style={"display": "block", "fontWeight": "700", "marginBottom": "8px", "color": THEME["text_main"]}),
                                    dcc.Checklist(
                                        id="mapped-only-filter",
                                        options=[{"label": " Show only mapped impacts", "value": "mapped_only"}],
                                        value=[],
                                        style={"color": THEME["text_main"], "paddingTop": "8px"},
                                        inputStyle={"marginRight": "8px"},
                                    ),
                                ]),
                            ],
                        ),
                    ],
                ),

                html.Div(id="summary-card", style={**CARD_STYLE, "marginBottom": "24px"}),

                html.Div(
                    style={**CARD_STYLE, "marginBottom": "24px"},
                    children=[
                        html.Div("Impact Hotspot Map", style=SECTION_TITLE_STYLE),
                        html.P(
                            "Map shows filtered impact locations. It uses extracted coordinates when available and falls back to approximate New Zealand city or region centroids.",
                            style={"marginTop": "0", "marginBottom": "16px", "color": THEME["text_soft"], "fontSize": "14px"},
                        ),
                        dcc.Graph(
                            id="impact-map",
                            config={"displayModeBar": False, "scrollZoom": True},
                            style={"height": "680px"},
                        )
                    ],
                ),

                html.Div(
                    style={
                        "display": "grid",
                        "gridTemplateColumns": "repeat(auto-fit, minmax(420px, 1fr))",
                        "gap": "24px",
                        "marginBottom": "24px",
                    },
                    children=[
                        html.Div(style=CARD_STYLE, children=[dcc.Graph(id="category-chart", config={"displayModeBar": False})]),
                        html.Div(style=CARD_STYLE, children=[dcc.Graph(id="region-chart", config={"displayModeBar": False})]),
                        html.Div(style=CARD_STYLE, children=[dcc.Graph(id="year-chart", config={"displayModeBar": False})]),
                    ],
                ),

                html.Div(
                    style={**CARD_STYLE, "marginBottom": "24px"},
                    children=[
                        html.Div("Filtered Impact Records", style=SECTION_TITLE_STYLE),
                        html.P(
                            "Detailed impact view for evidence-led review and policy analysis. Showing 5 records at a time.",
                            style={"marginTop": "0", "marginBottom": "12px", "color": THEME["text_soft"], "fontSize": "14px"},
                        ),
                        dash_table.DataTable(
                            id="impact-table",
                            page_size=5,
                            style_table={"overflowX": "auto"},
                            style_header={
                                "backgroundColor": THEME["accent_soft"],
                                "color": THEME["text_main"],
                                "fontWeight": "700",
                                "border": f"1px solid {THEME['border']}",
                            },
                            style_cell={
                                "backgroundColor": THEME["card_bg_soft"],
                                "color": THEME["text_main"],
                                "border": f"1px solid {THEME['border']}",
                                "padding": "10px",
                                "textAlign": "left",
                                "whiteSpace": "normal",
                                "height": "auto",
                                "fontSize": "13px",
                                "minWidth": "120px",
                                "maxWidth": "280px",
                            },
                            style_data_conditional=[
                                {
                                    "if": {"row_index": "odd"},
                                    "backgroundColor": THEME["card_bg"],
                                }
                            ],
                        ),
                    ],
                ),

                html.Div(
                    style={**CARD_STYLE, "marginBottom": "24px"},
                    children=[
                        html.Div("Linked Source Articles", style=SECTION_TITLE_STYLE),
                        html.P(
                            "Available when a specific event is selected. Showing 5 linked articles at a time.",
                            style={"marginTop": "0", "marginBottom": "12px", "color": THEME["text_soft"], "fontSize": "14px"},
                        ),
                        html.Div(id="articles-panel"),
                    ],
                ),
            ],
        ),

        html.Button(
            "💬",
            id="chat-toggle-button",
            n_clicks=0,
            title="Open policy assistant",
            style={
                "position": "fixed",
                "right": "24px",
                "bottom": "24px",
                "width": "64px",
                "height": "64px",
                "borderRadius": "50%",
                "border": f"1px solid {THEME['accent_dark']}",
                "background": "linear-gradient(135deg, #0f1417 0%, #33cc7a 100%)",
                "color": "white",
                "fontSize": "28px",
                "cursor": "pointer",
                "boxShadow": "0 10px 24px rgba(51,204,122,0.25)",
                "zIndex": 1000,
            },
        ),

        html.Div(
            id="chat-panel",
            style={
                "position": "fixed",
                "top": "0",
                "right": "-430px",
                "width": "400px",
                "height": "100vh",
                "backgroundColor": THEME["card_bg"],
                "boxShadow": "-8px 0 24px rgba(0,0,0,0.30)",
                "borderLeft": f"1px solid {THEME['border']}",
                "padding": "18px",
                "zIndex": 999,
                "transition": "right 0.3s ease",
                "display": "flex",
                "flexDirection": "column",
            },
            children=[
                html.Div(
                    style={
                        "display": "flex",
                        "justifyContent": "space-between",
                        "alignItems": "center",
                        "marginBottom": "12px",
                    },
                    children=[
                        html.Div(
                            "Aegis Policy Assistant",
                            style={"fontSize": "22px", "fontWeight": "800", "color": THEME["text_main"]},
                        ),
                        html.Button(
                            "✕",
                            id="chat-close-button",
                            n_clicks=0,
                            style={
                                "border": "none",
                                "backgroundColor": "transparent",
                                "fontSize": "22px",
                                "cursor": "pointer",
                                "color": THEME["text_soft"],
                            },
                        ),
                    ],
                ),
                html.P(
                    "Select a specific event, then ask about impacts, locations, evidence, linked articles, or summary.",
                    style={"marginTop": "0", "color": THEME["text_soft"], "fontSize": "14px"},
                ),
                dcc.Textarea(
                    id="chat-input",
                    placeholder="Ask something like: Which locations had transport-related impacts and what evidence supports them?",
                    style={
                        "width": "100%",
                        "height": "110px",
                        "padding": "12px",
                        "borderRadius": "12px",
                        "border": f"1px solid {THEME['border']}",
                        "fontSize": "14px",
                        "resize": "vertical",
                        "boxSizing": "border-box",
                        "backgroundColor": THEME["card_bg_soft"],
                        "color": THEME["text_main"],
                    },
                ),
                html.Button(
                    "Send",
                    id="chat-button",
                    n_clicks=0,
                    style={
                        "marginTop": "12px",
                        "backgroundColor": THEME["accent_dark"],
                        "color": "white",
                        "border": "none",
                        "padding": "10px 18px",
                        "borderRadius": "10px",
                        "fontWeight": "700",
                        "cursor": "pointer",
                        "alignSelf": "flex-start",
                        "boxShadow": "0 6px 18px rgba(51,204,122,0.22)",
                    },
                ),
                html.Div(
                    id="chat-output",
                    style={
                        "marginTop": "15px",
                        "padding": "14px",
                        "border": f"1px solid {THEME['border']}",
                        "borderRadius": "12px",
                        "backgroundColor": THEME["card_bg_soft"],
                        "color": THEME["text_main"],
                        "minHeight": "120px",
                        "whiteSpace": "pre-wrap",
                        "overflowY": "auto",
                        "flex": "1 1 auto",
                    },
                    children="Assistant ready. Select a specific event and ask a question.",
                ),
            ],
        ),
    ],
)

# ------------------------------------------------------------
# Main dashboard callback
# ------------------------------------------------------------

@app.callback(
    Output("summary-card", "children"),
    Output("impact-map", "figure"),
    Output("category-chart", "figure"),
    Output("region-chart", "figure"),
    Output("year-chart", "figure"),
    Output("impact-table", "data"),
    Output("impact-table", "columns"),
    Output("articles-panel", "children"),
    Input("event-dropdown", "value"),
    Input("year-filter", "value"),
    Input("region-filter", "value"),
    Input("category-filter", "value"),
    Input("mapped-only-filter", "value"),
)
def update_dashboard(selected_event, selected_years, selected_regions, selected_categories, mapped_only):
    filtered_df = filter_impacts(
        master_impacts_df,
        selected_event,
        selected_years,
        selected_regions,
        selected_categories,
        mapped_only,
    )

    summary_card = build_summary_card(selected_event, filtered_df)
    map_fig = build_map(filtered_df)
    cat_fig = build_category_chart(filtered_df)
    region_fig = build_region_chart(filtered_df)
    year_fig = build_year_chart(filtered_df)

    table_df = filtered_df.copy()

    desired_cols = [
        "event_name",
        "event_year",
        "primary_region",
        "impact_category_pretty",
        "impact_type_pretty",
        "display_location",
        "location_resolution_level",
        "impact_value",
        "impact_unit",
        "impact_description",
    ]
    actual_cols = [c for c in desired_cols if c in table_df.columns]
    table_df = table_df[actual_cols].copy()

    rename_map = {
        "event_name": "Event",
        "event_year": "Year",
        "primary_region": "Primary Region",
        "impact_category_pretty": "Impact Category",
        "impact_type_pretty": "Impact Type",
        "display_location": "Location",
        "location_resolution_level": "Resolution",
        "impact_value": "Value",
        "impact_unit": "Unit",
        "impact_description": "Description",
    }
    table_df = table_df.rename(columns=rename_map)
    table_df = table_df.fillna("")

    impact_columns = [{"name": c, "id": c} for c in table_df.columns]
    impact_data = table_df.to_dict("records")

    articles_panel = build_articles_panel(selected_event)

    return (
        summary_card,
        map_fig,
        cat_fig,
        region_fig,
        year_fig,
        impact_data,
        impact_columns,
        articles_panel,
    )

# ------------------------------------------------------------
# Floating chat panel toggle
# ------------------------------------------------------------

@app.callback(
    Output("chat-open-store", "data"),
    Input("chat-toggle-button", "n_clicks"),
    Input("chat-close-button", "n_clicks"),
    State("chat-open-store", "data"),
    prevent_initial_call=True,
)
def toggle_chat_panel(open_clicks, close_clicks, is_open):
    from dash import ctx
    trigger = ctx.triggered_id
    if trigger == "chat-toggle-button":
        return True
    if trigger == "chat-close-button":
        return False
    return is_open

@app.callback(
    Output("chat-panel", "style"),
    Input("chat-open-store", "data"),
)
def update_chat_panel_style(is_open):
    base_style = {
        "position": "fixed",
        "top": "0",
        "width": "400px",
        "height": "100vh",
        "backgroundColor": THEME["card_bg"],
        "boxShadow": "-8px 0 24px rgba(0,0,0,0.30)",
        "borderLeft": f"1px solid {THEME['border']}",
        "padding": "18px",
        "zIndex": 999,
        "transition": "right 0.3s ease",
        "display": "flex",
        "flexDirection": "column",
    }
    base_style["right"] = "0" if is_open else "-430px"
    return base_style

# ------------------------------------------------------------
# Chatbot callback
# ------------------------------------------------------------

@app.callback(
    Output("chat-output", "children"),
    Input("chat-button", "n_clicks"),
    State("chat-input", "value"),
    State("event-dropdown", "value"),
)
def event_chatbot(n_clicks, user_text, selected_event):
    if not n_clicks or not user_text:
        return "Assistant ready. Select a specific event and ask a question."

    if selected_event in [None, ALL_EVENTS_VALUE]:
        return "Please select a specific event first. The assistant currently answers at selected-event level."

    try:
        answer = answer_question_with_rag(int(selected_event), user_text)
        return f"Question: {user_text}\n\n{answer}"
    except Exception as e:
        return f"Error while generating chatbot answer.\n\n{str(e)}"

# ------------------------------------------------------------
# Run app
# ------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=False)

