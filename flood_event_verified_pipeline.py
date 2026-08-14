import os
import re
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from openai import OpenAI


# ============================================================
# Environment
# ============================================================

load_dotenv()


# ============================================================
# OpenAI config
# ============================================================

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-5.4-mini"
)


# ============================================================
# SOURCE DATABASE
#
# This is your EXISTING database.
# It is only read from.
# ============================================================

SOURCE_DB_CONFIG = {
    "host": os.getenv(
        "SOURCE_DB_HOST",
        "localhost"
    ),
    "port": int(
        os.getenv(
            "SOURCE_DB_PORT",
            "5432"
        )
    ),
    "dbname": os.getenv(
        "SOURCE_DB_NAME",
        "flood_database"
    ),
    "user": os.getenv(
        "SOURCE_DB_USER",
        "postgres"
    ),
    "password": os.getenv(
        "SOURCE_DB_PASSWORD",
        ""
    ),
}


# ============================================================
# TARGET DATABASE
#
# Completely separate new database.
# All new results go here.
# ============================================================

TARGET_DB_CONFIG = {
    "host": os.getenv(
        "TARGET_DB_HOST",
        "localhost"
    ),
    "port": int(
        os.getenv(
            "TARGET_DB_PORT",
            "5432"
        )
    ),
    "dbname": os.getenv(
        "TARGET_DB_NAME",
        "flood_event_intelligence"
    ),
    "user": os.getenv(
        "TARGET_DB_USER",
        "postgres"
    ),
    "password": os.getenv(
        "TARGET_DB_PASSWORD",
        ""
    ),
}


# ============================================================
# File configuration
# ============================================================

EXCEL_PATH = os.getenv(
    "EVENT_EXCEL_PATH",
    "nz_flood_related_events_2017_2026.xlsx"
)

OUTPUT_DIR = Path(
    os.getenv(
        "BATCH_OUTPUT_DIR",
        "verified_batch_outputs"
    )
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# Verification batch files
# ============================================================

VERIFY_INPUT_JSONL = (
    OUTPUT_DIR /
    "article_event_verification_input.jsonl"
)

VERIFY_MANIFEST_JSON = (
    OUTPUT_DIR /
    "article_event_verification_manifest.json"
)

VERIFY_BATCH_INFO = (
    OUTPUT_DIR /
    "article_event_verification_batch_info.json"
)

VERIFY_OUTPUT_JSONL = (
    OUTPUT_DIR /
    "article_event_verification_output.jsonl"
)

VERIFY_ERROR_JSONL = (
    OUTPUT_DIR /
    "article_event_verification_errors.jsonl"
)


# ============================================================
# Final grouped extraction files
# ============================================================

EXTRACT_INPUT_JSONL = (
    OUTPUT_DIR /
    "verified_event_extraction_input.jsonl"
)

EXTRACT_MANIFEST_JSON = (
    OUTPUT_DIR /
    "verified_event_extraction_manifest.json"
)

EXTRACT_BATCH_INFO = (
    OUTPUT_DIR /
    "verified_event_extraction_batch_info.json"
)

EXTRACT_OUTPUT_JSONL = (
    OUTPUT_DIR /
    "verified_event_extraction_output.jsonl"
)

EXTRACT_ERROR_JSONL = (
    OUTPUT_DIR /
    "verified_event_extraction_errors.jsonl"
)


# ============================================================
# Limits
# ============================================================

MAX_CANDIDATES_PER_EVENT = int(
    os.getenv(
        "MAX_CANDIDATES_PER_EVENT",
        "4000"
    )
)

ARTICLE_CONTENT_MAX_LEN = int(
    os.getenv(
        "ARTICLE_CONTENT_MAX_LEN",
        "7500"
    )
)

VERIFICATION_CONTENT_MAX_LEN = int(
    os.getenv(
        "VERIFICATION_CONTENT_MAX_LEN",
        "2000"
    )
)

VERIFICATION_CONFIDENCE_THRESHOLD = float(
    os.getenv(
        "VERIFICATION_CONFIDENCE_THRESHOLD",
        "0.70"
    )
)


# ============================================================
# Database connections
# ============================================================

def get_source_connection():
    """
    Existing flood_database.

    READ ONLY.
    """

    return psycopg2.connect(
        **SOURCE_DB_CONFIG,
        cursor_factory=RealDictCursor
    )


def get_target_connection():
    """
    New flood_event_intelligence database.

    WRITE results here.
    """

    return psycopg2.connect(
        **TARGET_DB_CONFIG,
        cursor_factory=RealDictCursor
    )


# ============================================================
# Text helpers
# ============================================================

def normalize_text(
    value: Optional[Any]
) -> str:

    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    return re.sub(
        r"\s+",
        " ",
        str(value)
    ).strip()


def slugify(
    value: str
) -> str:

    value = normalize_text(
        value
    ).lower()

    value = re.sub(
        r"[^a-z0-9]+",
        "_",
        value
    )

    value = re.sub(
        r"_+",
        "_",
        value
    ).strip("_")

    return (
        value[:90]
        or "unknown_event"
    )


def truncate_text(
    text: Optional[str],
    max_len: int = 3000
) -> str:

    text = normalize_text(
        text
    )

    if len(text) <= max_len:
        return text

    return (
        text[:max_len]
        + " ..."
    )


# ============================================================
# Date helpers
# ============================================================

def parse_date_safe(
    value: Optional[str]
):

    if not value:
        return None

    value = str(
        value
    ).strip()

    if value.lower() == "null":
        return None

    try:

        return datetime.strptime(
            value,
            "%Y-%m-%d"
        ).date()

    except ValueError:

        return None


# ============================================================
# ID helpers
# ============================================================

def stringify_ids(
    values: Optional[List[Any]]
) -> Optional[str]:

    if not values:
        return None

    return ",".join(
        str(v)
        for v in values
    )


def stringify_urls(
    values: Optional[List[str]]
) -> Optional[str]:

    if not values:
        return None

    return "\n".join(
        v
        for v in values
        if v
    )


# ============================================================
# Event Excel loading
# ============================================================

def infer_event_type(
    event_name: str
) -> str:

    name = event_name.lower()

    if "cyclone" in name:
        return "cyclone_flood_event"

    if "tropical depression" in name:
        return "tropical_depression_flood_event"

    if "severe weather" in name:
        return "severe_weather_flood_event"

    if "coastal inundation" in name:
        return "coastal_inundation_event"

    if (
        "slip" in name
        or "landslide" in name
    ):
        return "flood_and_slip_event"

    return "flood_event"


def load_events_from_excel(
    excel_path: str
) -> List[Dict[str, Any]]:

    df = pd.read_excel(
        excel_path,
        sheet_name="NZ Flood Events"
    )

    required_cols = [
        "Year",
        "Event Name",
        "Main Areas",
        "Source URL",
    ]

    missing = [
        col
        for col in required_cols
        if col not in df.columns
    ]

    if missing:

        raise ValueError(
            f"Missing required Excel columns: {missing}"
        )

    events = []

    for _, row in df.iterrows():

        year = int(
            row["Year"]
        )

        event_name = normalize_text(
            row["Event Name"]
        )

        main_areas = normalize_text(
            row["Main Areas"]
        )

        source_url = normalize_text(
            row["Source URL"]
        )

        event_key = (
            f"{year}_"
            f"{slugify(event_name)}"
        )

        events.append({
            "event_key":
                event_key,

            "event_name":
                event_name,

            "event_type":
                infer_event_type(
                    event_name
                ),

            "year":
                year,

            "main_areas":
                main_areas,

            "source_url":
                source_url,
        })

    return events


# ============================================================
# Candidate retrieval
# ============================================================

STOPWORDS = {
    "the",
    "and",
    "or",
    "of",
    "in",
    "to",
    "for",
    "from",
    "with",

    "new",
    "zealand",
    "nz",

    "event",
    "events",

    "severe",
    "weather",

    "flood",
    "flooding",
    "floods",

    "storm",
    "rain",
    "rainfall",

    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
}


def extract_keywords_from_text(
    text: str
) -> List[str]:

    text = normalize_text(
        text
    ).lower()

    words = re.findall(
        r"[a-zāēīōū]+(?:['’-][a-zāēīōū]+)?|\d{4}",
        text
    )

    result = []

    seen = set()

    for word in words:

        clean = word.strip(
            " -–—'’"
        )

        if not clean:
            continue

        if clean in STOPWORDS:
            continue

        if (
            len(clean) < 3
            and not clean.isdigit()
        ):
            continue

        if clean not in seen:

            result.append(
                clean
            )

            seen.add(
                clean
            )

    return result


def build_event_search_terms(
    event_cfg: Dict[str, Any]
) -> List[str]:

    combined = (
        event_cfg["event_name"]
        + " "
        + event_cfg["main_areas"]
    )

    keywords = (
        extract_keywords_from_text(
            combined
        )
    )

    return keywords[:12]


# ============================================================
# Broad SQL candidate retrieval
# ============================================================

def fetch_candidate_articles_for_event(
    event_cfg: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    IMPORTANT:

    This only finds CANDIDATES.

    It DOES NOT permanently assign them to the event.

    LLM verification happens afterwards.
    """

    year = int(
        event_cfg["year"]
    )

    keyword_terms = (
        build_event_search_terms(
            event_cfg
        )
    )

    if not keyword_terms:

        keyword_terms = [
            event_cfg["event_name"]
        ]

    searchable_cols = [
        #"coalesce(search_query, '')",
        "coalesce(article_title, '')",
        "coalesce(article_description, '')",
        "coalesce(article_content, '')",
    ]


    # --------------------------------------------------------
    # Location / event keyword matching
    # --------------------------------------------------------

    keyword_conditions = []

    keyword_params = []

    for term in keyword_terms:

        pattern = (
            f"%{term}%"
        )

        condition = (
            "("
            +
            " OR ".join(
                f"{col} ILIKE %s"
                for col
                in searchable_cols
            )
            +
            ")"
        )

        keyword_conditions.append(
            condition
        )

        keyword_params.extend(
            [pattern]
            * len(searchable_cols)
        )


    # --------------------------------------------------------
    # Flood-related filtering
    # --------------------------------------------------------

    flood_patterns = [
        "%flood%",
        "%flooding%",
        "%flash flood%",
        "%severe weather%",
        "%heavy rain%",
        "%rainfall%",
        "%storm%",
        "%cyclone%",
        "%slip%",
        "%landslide%",
        "%inundation%",
        "%river%",
    ]

    flood_conditions = []

    flood_params = []

    for pattern in flood_patterns:

        condition = (
            "("
            +
            " OR ".join(
                f"{col} ILIKE %s"
                for col
                in searchable_cols
            )
            +
            ")"
        )

        flood_conditions.append(
            condition
        )

        flood_params.extend(
            [pattern]
            * len(searchable_cols)
        )


    # --------------------------------------------------------
    # IMPORTANT CHANGE
    #
    # Articles with NULL dates are still candidates,
    # but they MUST later pass LLM event verification.
    # --------------------------------------------------------

    query = f"""
        SELECT
            id,
            source_name,
            source_domain,
            article_title,
            article_description,
            article_content,
            article_url,
            published_at,
            search_query

        FROM news_articles

        WHERE

            (
                published_at IS NULL
                OR EXTRACT(
                    YEAR
                    FROM published_at
                ) = %s
            )

            AND
            (
                {" OR ".join(keyword_conditions)}
            )

            AND
            (
                {" OR ".join(flood_conditions)}
            )

        ORDER BY
            published_at ASC NULLS LAST,
            id ASC

        LIMIT %s;
    """

    params = (
        [year]
        +
        keyword_params
        +
        flood_params
        +
        [MAX_CANDIDATES_PER_EVENT]
    )

    conn = get_source_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                query,
                params
            )

            return list(
                cur.fetchall()
            )

    finally:

        conn.close()


# ============================================================
# OpenAI
# ============================================================

def get_openai_client():

    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:

        raise RuntimeError(
            "OPENAI_API_KEY is missing."
        )

    return OpenAI(
        api_key=api_key
    )


# ============================================================
# ARTICLE ↔ EVENT VERIFICATION
# ============================================================

def build_article_verification_prompt(
    event_cfg: Dict[str, Any],
    article: Dict[str, Any]
) -> str:

    article_text = f"""
ARTICLE ID:
{article.get("id")}

TITLE:
{normalize_text(article.get("article_title"))}

PUBLISHED DATE:
{article.get("published_at")}

DESCRIPTION:
{truncate_text(
    article.get("article_description"),
    1500
)}

CONTENT:
{truncate_text(
    article.get("article_content"),
    VERIFICATION_CONTENT_MAX_LEN
)}

SEARCH QUERY:
{normalize_text(article.get("search_query"))}

URL:
{normalize_text(article.get("article_url"))}
""".strip()


    return f"""
You are validating whether ONE news article belongs to ONE predefined New Zealand flood event.

This is a strict event-assignment task.

TARGET EVENT

Event name:
{event_cfg["event_name"]}

Expected year:
{event_cfg["year"]}

Main areas:
{event_cfg["main_areas"]}

Event type:
{event_cfg["event_type"]}


ARTICLE

{article_text}


DECISION RULES

Return belongs_to_event = true ONLY when the article is genuinely describing:

- the same flood / cyclone / severe-weather episode,
- in a compatible time period,
- in a compatible geographic area,
- and in the same disaster context.

Do NOT assign an article merely because:

- it contains the same region,
- it contains the word flood,
- it contains the word cyclone,
- it was retrieved by a related search query,
- it discusses a historical flood,
- it mentions the target event only as background,
- it discusses preparations or future risk only.

TIME IS IMPORTANT.

For example:

A June 2021 article must NOT be assigned to a 2017 flood event merely because both mention Bay of Plenty or Hawke's Bay.

GEOGRAPHY IS IMPORTANT.

Same region does not automatically mean same event.

DISASTER CONTEXT IS IMPORTANT.

Two different storms in the same region and year should not automatically be treated as the same event.

SEARCH_QUERY IS NOT EVIDENCE.

Do not use the search_query field as proof that the article belongs to the event.

Use the actual article title, description, content, publication date, locations and disaster context.


Return ONLY JSON:

{{
    "article_id": {article.get("id")},
    "event_key": "{event_cfg["event_key"]}",
    "belongs_to_event": true,
    "confidence": 0.0,
    "temporal_match": true,
    "location_match": true,
    "disaster_context_match": true,
    "reason": "short explanation"
}}

confidence must be between 0 and 1.
""".strip()


# ============================================================
# Prepare verification batch
# ============================================================

def prepare_verification_batch(
    events: List[Dict[str, Any]]
):

    manifest = {}

    count = 0

    with open(
        VERIFY_INPUT_JSONL,
        "w",
        encoding="utf-8"
    ) as output_file:

        for event_cfg in events:

            candidates = (
                fetch_candidate_articles_for_event(
                    event_cfg
                )
            )

            print(
                f"[candidate] "
                f"{event_cfg['event_name']} "
                f"-> {len(candidates)} candidates"
            )

            for article in candidates:

                custom_id = (
                    f"{event_cfg['event_key']}"
                    f"__article_{article['id']}"
                )

                prompt = (
                    build_article_verification_prompt(
                        event_cfg,
                        article
                    )
                )

                request_body = {
                    "model":
                        OPENAI_MODEL,

                    "input": [
                        {
                            "role":
                                "system",

                            "content":
                                (
                                    "You are a conservative "
                                    "news-event classification "
                                    "system. Avoid false "
                                    "event assignments."
                                ),
                        },
                        {
                            "role":
                                "user",

                            "content":
                                prompt,
                        },
                    ],
                }

                line = {
                    "custom_id":
                        custom_id,

                    "method":
                        "POST",

                    "url":
                        "/v1/responses",

                    "body":
                        request_body,
                }

                output_file.write(
                    json.dumps(
                        line,
                        ensure_ascii=False
                    )
                    + "\n"
                )

                manifest[custom_id] = {
                    "event_cfg":
                        event_cfg,

                    "article":
                        {
                            key:
                                (
                                    str(value)
                                    if isinstance(
                                        value,
                                        (
                                            datetime,
                                        )
                                    )
                                    else value
                                )

                            for key, value
                            in article.items()
                        }
                }

                count += 1


    with open(
        VERIFY_MANIFEST_JSON,
        "w",
        encoding="utf-8"
    ) as manifest_file:

        json.dump(
            manifest,
            manifest_file,
            ensure_ascii=False,
            indent=2,
            default=str
        )

    print(
        f"\nPrepared {count} "
        f"article-event verification requests."
    )

    print(
        f"Input: {VERIFY_INPUT_JSONL}"
    )

    return count


# ============================================================
# Generic Batch submit
# ============================================================

def submit_batch_file(
    jsonl_path: Path,
    batch_info_path: Path,
    description: str
):

    client = get_openai_client()

    uploaded = (
        client.files.create(
            file=open(
                jsonl_path,
                "rb"
            ),
            purpose="batch"
        )
    )

    print(
        f"Uploaded file: {uploaded.id}"
    )

    batch = (
        client.batches.create(
            input_file_id=
                uploaded.id,

            endpoint=
                "/v1/responses",

            completion_window=
                "24h",

            metadata={
                "description":
                    description
            }
        )
    )

    info = {
        "batch_id":
            batch.id,

        "input_file_id":
            uploaded.id,

        "status":
            batch.status,
    }

    with open(
        batch_info_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            info,
            f,
            indent=2
        )

    print(
        f"Batch created: {batch.id}"
    )

    return info


# ============================================================
# Batch status
# ============================================================

def show_batch_status(batch_id: str):

    client = get_openai_client()

    batch = client.batches.retrieve(batch_id)

    print(f"batch_id: {batch.id}")
    print(f"status: {batch.status}")
    print(f"output_file_id: {batch.output_file_id}")
    print(f"error_file_id: {batch.error_file_id}")

    print("\n--- ERROR DETAILS ---")

    print("errors:", getattr(batch, "errors", None))

    if getattr(batch, "errors", None):
        try:
            for error in batch.errors.data:
                print("code:", getattr(error, "code", None))
                print("message:", getattr(error, "message", None))
                print("param:", getattr(error, "param", None))
                print("line:", getattr(error, "line", None))
                print("-" * 60)
        except Exception as e:
            print("Could not parse errors:", e)

    print("\n--- REQUEST COUNTS ---")
    print(getattr(batch, "request_counts", None))

    return batch


def split_jsonl_file(
    input_path: Path,
    output_dir: Path,
    lines_per_file: int = 600
):
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(input_path, "r", encoding="utf-8") as infile:
        lines = [line for line in infile if line.strip()]

    parts = []

    for i in range(0, len(lines), lines_per_file):
        chunk = lines[i:i + lines_per_file]

        part_number = (i // lines_per_file) + 1

        part_path = output_dir / f"verification_part_{part_number:03d}.jsonl"

        with open(part_path, "w", encoding="utf-8") as outfile:
            outfile.writelines(chunk)

        parts.append(part_path)

        print(
            f"Created {part_path} "
            f"with {len(chunk)} requests"
        )

    print(f"\nTotal parts created: {len(parts)}")

    return parts




# ============================================================
# Batch download
# ============================================================

def download_batch(
    batch_id: str,
    output_path: Path,
    error_path: Path
):

    client = get_openai_client()

    batch = (
        client.batches.retrieve(
            batch_id
        )
    )

    if batch.status != "completed":

        print(
            "Batch is not completed."
        )

        print(
            f"Current status: "
            f"{batch.status}"
        )

        return


    if batch.output_file_id:

        content = (
            client.files.content(
                batch.output_file_id
            )
        )

        output_path.write_text(
            content.text,
            encoding="utf-8"
        )

        print(
            f"Saved output: "
            f"{output_path}"
        )


    if batch.error_file_id:

        content = (
            client.files.content(
                batch.error_file_id
            )
        )

        error_path.write_text(
            content.text,
            encoding="utf-8"
        )

        print(
            f"Saved errors: "
            f"{error_path}"
        )


# ============================================================
# Response parsing
# ============================================================

def extract_text_from_response_body(
    body: Dict[str, Any]
) -> str:

    if not body:
        return ""

    if body.get(
        "output_text"
    ):
        return body[
            "output_text"
        ]

    texts = []

    for item in body.get(
        "output",
        []
    ):

        for content in item.get(
            "content",
            []
        ):

            if content.get(
                "type"
            ) in [
                "output_text",
                "text",
            ]:

                text = content.get(
                    "text"
                )

                if text:
                    texts.append(
                        text
                    )

    return "\n".join(
        texts
    ).strip()


def strip_code_fences(
    raw: str
) -> str:

    raw = raw.strip()

    if raw.startswith(
        "```"
    ):

        raw = raw.strip(
            "`"
        ).strip()

        if raw.lower().startswith(
            "json"
        ):

            raw = raw[
                4:
            ].strip()

    return raw


# ============================================================
# Store verification results
# ============================================================

def save_validation_result(
    event_cfg: Dict[str, Any],
    article: Dict[str, Any],
    result: Dict[str, Any]
):

    conn = get_target_connection()

    try:

        with conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    INSERT INTO
                    flood_article_event_validation
                    (
                        event_key,
                        event_name,

                        article_id,
                        article_title,
                        article_url,
                        published_at,

                        belongs_to_event,
                        confidence,

                        temporal_match,
                        location_match,
                        disaster_context_match,

                        verification_reason,

                        is_primary_assignment
                    )

                    VALUES
                    (
                        %s, %s,
                        %s, %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s,
                        FALSE
                    )

                    ON CONFLICT
                    (
                        event_key,
                        article_id
                    )

                    DO UPDATE SET

                        belongs_to_event =
                            EXCLUDED.belongs_to_event,

                        confidence =
                            EXCLUDED.confidence,

                        temporal_match =
                            EXCLUDED.temporal_match,

                        location_match =
                            EXCLUDED.location_match,

                        disaster_context_match =
                            EXCLUDED.disaster_context_match,

                        verification_reason =
                            EXCLUDED.verification_reason,

                        created_at =
                            CURRENT_TIMESTAMP;
                    """,

                    (
                        event_cfg[
                            "event_key"
                        ],

                        event_cfg[
                            "event_name"
                        ],

                        article[
                            "id"
                        ],

                        article.get(
                            "article_title"
                        ),

                        article.get(
                            "article_url"
                        ),

                        article.get(
                            "published_at"
                        ),

                        bool(
                            result.get(
                                "belongs_to_event",
                                False
                            )
                        ),

                        float(
                            result.get(
                                "confidence",
                                0
                            )
                        ),

                        result.get(
                            "temporal_match"
                        ),

                        result.get(
                            "location_match"
                        ),

                        result.get(
                            "disaster_context_match"
                        ),

                        result.get(
                            "reason"
                        ),
                    ),
                )

    finally:

        conn.close()


# ============================================================
# Import verification output
# ============================================================

def import_verification_results():

    with open(
        VERIFY_MANIFEST_JSON,
        "r",
        encoding="utf-8"
    ) as f:

        manifest = json.load(
            f
        )


    with open(
        VERIFY_OUTPUT_JSONL,
        "r",
        encoding="utf-8"
    ) as f:

        for line_number, line in enumerate(
            f,
            start=1
        ):

            if not line.strip():
                continue

            item = json.loads(
                line
            )

            custom_id = item.get(
                "custom_id"
            )

            if custom_id not in manifest:

                print(
                    f"Unknown custom_id: "
                    f"{custom_id}"
                )

                continue


            response = item.get(
                "response",
                {}
            )

            if response.get(
                "status_code"
            ) != 200:

                print(
                    f"Non-200 response: "
                    f"{custom_id}"
                )

                continue


            raw = (
                extract_text_from_response_body(
                    response.get(
                        "body",
                        {}
                    )
                )
            )

            raw = strip_code_fences(
                raw
            )
            raw = re.sub(
                r'"location_confidence"\s*:\s*(low|medium|high)\s*([,}])',
                r'"location_confidence": "\1"\2',
                raw
            )
            # Fix semicolon-separated quoted evidence strings
            raw = re.sub(
                r'"\s*;\s*"',
                '; ',
                raw
            )
            try:

                result = json.loads(
                    raw
                )

            except json.JSONDecodeError:

                print(
                    f"Invalid JSON: "
                    f"{custom_id}"
                )

                continue


            meta = manifest[
                custom_id
            ]

            save_validation_result(
                event_cfg=
                    meta["event_cfg"],

                article=
                    meta["article"],

                result=
                    result
            )


    resolve_primary_article_assignments()

    print(
        "\nVerification results imported."
    )


# ============================================================
# IMPORTANT:
# Resolve same article matching multiple events
# ============================================================

def resolve_primary_article_assignments():
    """
    One article gets ONE primary event.

    Rules:

    1. belongs_to_event must be TRUE.
    2. confidence must be >= threshold.
    3. If multiple events qualify,
       highest confidence wins.
    """

    conn = get_target_connection()

    try:

        with conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    UPDATE
                        flood_article_event_validation
                    SET
                        is_primary_assignment = FALSE;
                    """
                )


                cur.execute(
                    """
                    WITH ranked AS
                    (
                        SELECT
                            validation_id,

                            ROW_NUMBER()
                            OVER
                            (
                                PARTITION BY article_id

                                ORDER BY
                                    confidence DESC,
                                    validation_id ASC
                            )
                            AS rn

                        FROM
                            flood_article_event_validation

                        WHERE
                            belongs_to_event = TRUE

                            AND confidence >= %s
                    )

                    UPDATE
                        flood_article_event_validation v

                    SET
                        is_primary_assignment = TRUE

                    FROM
                        ranked r

                    WHERE
                        v.validation_id =
                            r.validation_id

                        AND r.rn = 1;
                    """,

                    (
                        VERIFICATION_CONFIDENCE_THRESHOLD,
                    )
                )

    finally:

        conn.close()


# ============================================================
# Get verified articles for one event
# ============================================================

def fetch_verified_articles(
    event_key: str
) -> List[Dict[str, Any]]:

    validation_conn = (
        get_target_connection()
    )

    try:

        with validation_conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    article_id,
                    confidence

                FROM
                    flood_article_event_validation

                WHERE
                    event_key = %s

                    AND belongs_to_event = TRUE

                    AND is_primary_assignment = TRUE

                    AND confidence >= %s

                ORDER BY
                    confidence DESC;
                """,

                (
                    event_key,
                    VERIFICATION_CONFIDENCE_THRESHOLD
                )
            )

            verified_rows = list(
                cur.fetchall()
            )

    finally:

        validation_conn.close()


    if not verified_rows:
        return []


    confidence_map = {
        int(row["article_id"]):
            float(row["confidence"])

        for row
        in verified_rows
    }

    article_ids = list(
        confidence_map.keys()
    )


    source_conn = (
        get_source_connection()
    )

    try:

        with source_conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    source_name,
                    source_domain,
                    article_title,
                    article_description,
                    article_content,
                    article_url,
                    published_at,
                    search_query

                FROM
                    news_articles

                WHERE
                    id = ANY(%s)

                ORDER BY
                    published_at ASC NULLS LAST,
                    id ASC;
                """,

                (
                    article_ids,
                )
            )

            articles = list(
                cur.fetchall()
            )

    finally:

        source_conn.close()


    for article in articles:

        article[
            "validation_confidence"
        ] = confidence_map.get(
            int(article["id"])
        )


    return articles


# ============================================================
# Grouped corpus
# ============================================================

def build_event_corpus(
    event_cfg: Dict[str, Any],
    articles: List[Dict[str, Any]]
) -> str:

    parts = [
        (
            "TARGET VERIFIED EVENT: "
            f"{event_cfg['event_name']}"
        ),

        (
            "EVENT YEAR: "
            f"{event_cfg['year']}"
        ),

        (
            "MAIN AREAS: "
            f"{event_cfg['main_areas']}"
        ),

        "",

        (
            "ONLY VERIFIED ARTICLE "
            "EVIDENCE IS INCLUDED BELOW:"
        ),

        "",
    ]


    for index, article in enumerate(
        articles,
        start=1
    ):

        parts.append(
            f"""
ARTICLE {index}

article_id:
{article["id"]}

verification_confidence:
{article.get("validation_confidence")}

published_at:
{article.get("published_at")}

title:
{normalize_text(article.get("article_title"))}

description:
{truncate_text(article.get("article_description"), 1200)}

content:
{truncate_text(article.get("article_content"), ARTICLE_CONTENT_MAX_LEN)}

url:
{normalize_text(article.get("article_url"))}
""".strip()
        )

        parts.append(
            "\n"
            + "-" * 80
            + "\n"
        )


    return "\n".join(
        parts
    )


# ============================================================
# Grouped Event → Incident → Impact prompt
# ============================================================

def build_grouped_extraction_prompt(
    event_cfg: Dict[str, Any]
) -> str:

    return f"""
You are extracting structured disaster information from a set of news articles that have already been verified as belonging to ONE New Zealand flood-related event.

TARGET EVENT

event_name:
{event_cfg["event_name"]}

event_type:
{event_cfg["event_type"]}

event_year:
{event_cfg["year"]}

main_areas:
{event_cfg["main_areas"]}


CORE DEFINITIONS

EVENT

The overall real-world disaster episode.


INCIDENT

A physical occurrence that actually happened during the event.

Examples:

- flooding
- flash flooding
- river flooding
- river burst bank
- road flooding
- landslide
- slips
- heavy rain and flooding
- severe rain and flooding

Warnings and forecasts are NOT incidents.

Power outage is NOT an incident.


IMPACT

A consequence of an incident or the overall event.

Examples:

- fatalities
- injuries
- evacuation
- displacement
- road closure
- bridge damage
- communities cut off
- power outage
- telecommunications outage
- property damage
- economic loss
- agricultural loss
- wastewater failure
- state of emergency


TASK

1. Read all verified articles together.

2. Produce ONE event object.

3. Extract distinct incidents.

4. Deduplicate incidents repeated across articles.

5. For each incident, extract its impacts.

6. Deduplicate impacts repeated across articles.

7. Use only evidence in the supplied articles.

8. Do not invent facts.

9. Evidence snippets must be short.

10. supporting_article_ids must use the article_id values supplied in the evidence.


LOCATION RULES

For each incident and impact:

- Extract the most specific explicitly supported location.
- Prefer address over street.
- Prefer street over suburb.
- Prefer suburb over city.
- Prefer city over district.
- Prefer district over region.
- Never invent a location.

location_resolution_level must be one of:

exact_address
street
suburb
city
district
region
country
unknown

location_confidence must be one of:

high
medium
low


Return ONLY valid JSON:

{{
  "event": {{
    "event_name": "string",
    "event_type": "string",
    "start_date": "YYYY-MM-DD or null",
    "end_date": "YYYY-MM-DD or null",
    "primary_region": "string or null",
    "summary": "string",
    "article_count": 0,
    "linked_article_ids": [],
    "event_evidence_text": "string"
  }},

  "incidents": [
    {{
      "incident_type": "string",

      "incident_title": "string",

      "incident_description": "string",

      "location_name": "string or null",
      "address": "string or null",
      "street": "string or null",
      "suburb": "string or null",
      "city": "string or null",
      "district": "string or null",
      "region": "string or null",
      "country": "string or null",
      "river": "string or null",

      "location_resolution_level":
          "exact_address | street | suburb | city | district | region | country | unknown",

      "location_confidence":
          "high | medium | low",

      "incident_date":
          "YYYY-MM-DD or null",

      "incident_evidence_text":
          "string",

      "supporting_article_ids":
          [],

      "impacts": [
        {{
          "impact_category":
              "human_life | telecom | communication | economic | infrastructure_service | property | transport | evacuation | agriculture | environment | other",

          "impact_type":
              "string",

          "impact_value":
              "string or null",

          "impact_unit":
              "string or null",

          "impact_description":
              "string",

          "impact_evidence_text":
              "string",

          "supporting_article_ids":
              [],

          "location_available":
              true,

          "impact_location_name":
              "string or null",

          "impact_address":
              "string or null",

          "impact_street":
              "string or null",

          "impact_suburb":
              "string or null",

          "impact_city":
              "string or null",

          "impact_district":
              "string or null",

          "impact_region":
              "string or null",

          "impact_country":
              "string or null",

          "impact_river":
              "string or null",

          "location_resolution_level":
              "exact_address | street | suburb | city | district | region | country | unknown",

          "location_confidence":
              "high | medium | low",

          "location_notes":
              "string or null"
        }}
      ]
    }}
  ]
}}
""".strip()


# ============================================================
# Prepare grouped extraction batch
# ============================================================

def prepare_grouped_extraction_batch(
    events: List[Dict[str, Any]]
):

    manifest = {}

    request_count = 0

    with open(
        EXTRACT_INPUT_JSONL,
        "w",
        encoding="utf-8"
    ) as output_file:

        for event_cfg in events:

            articles = (
                fetch_verified_articles(
                    event_cfg[
                        "event_key"
                    ]
                )
            )

            print(
                f"[verified] "
                f"{event_cfg['event_name']} "
                f"-> {len(articles)} articles"
            )

            if not articles:
                continue


            custom_id = (
                event_cfg[
                    "event_key"
                ]
            )


            corpus = (
                build_event_corpus(
                    event_cfg,
                    articles
                )
            )


            prompt = (
                build_grouped_extraction_prompt(
                    event_cfg
                )
            )


            body = {
                "model":
                    OPENAI_MODEL,

                "input": [
                    {
                        "role":
                            "system",

                        "content":
                            prompt,
                    },

                    {
                        "role":
                            "user",

                        "content":
                            corpus,
                    },
                ],
            }


            request = {
                "custom_id":
                    custom_id,

                "method":
                    "POST",

                "url":
                    "/v1/responses",

                "body":
                    body,
            }


            output_file.write(
                json.dumps(
                    request,
                    ensure_ascii=False
                )
                + "\n"
            )


            manifest[
                custom_id
            ] = {

                "event_cfg":
                    event_cfg,

                "articles": [
                    {
                        "id":
                            article[
                                "id"
                            ],

                        "article_title":
                            article.get(
                                "article_title"
                            ),

                        "article_url":
                            article.get(
                                "article_url"
                            ),

                        "published_at":
                            str(
                                article.get(
                                    "published_at"
                                )
                            )
                            if article.get(
                                "published_at"
                            )
                            else None,

                        "article_content":
                            article.get(
                                "article_content"
                            ),

                        "validation_confidence":
                            article.get(
                                "validation_confidence"
                            ),
                    }

                    for article
                    in articles
                ]
            }


            request_count += 1


    with open(
        EXTRACT_MANIFEST_JSON,
        "w",
        encoding="utf-8"
    ) as manifest_file:

        json.dump(
            manifest,
            manifest_file,
            ensure_ascii=False,
            indent=2,
            default=str
        )


    print(
        f"\nPrepared "
        f"{request_count} "
        f"grouped event requests."
    )

    return request_count


# ============================================================
# Event database upsert
# ============================================================

def upsert_flood_event(
    event_key: str,
    event_obj: Dict[str, Any],
    articles: List[Dict[str, Any]],
    source_url: Optional[str]
) -> int:

    linked_urls = [
        normalize_text(
            article.get(
                "article_url"
            )
        )

        for article
        in articles

        if article.get(
            "article_url"
        )
    ]


    conn = get_target_connection()

    try:

        with conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    INSERT INTO
                    flood_events
                    (
                        event_key,
                        event_name,
                        event_type,

                        start_date,
                        end_date,

                        primary_region,

                        summary,

                        article_count,

                        linked_article_ids,
                        linked_article_urls,

                        event_evidence_text,

                        source_url,

                        updated_at
                    )

                    VALUES
                    (
                        %s, %s, %s,
                        %s, %s,
                        %s,
                        %s,
                        %s,
                        %s, %s,
                        %s,
                        %s,
                        CURRENT_TIMESTAMP
                    )

                    ON CONFLICT
                    (
                        event_key
                    )

                    DO UPDATE SET

                        event_name =
                            EXCLUDED.event_name,

                        event_type =
                            EXCLUDED.event_type,

                        start_date =
                            EXCLUDED.start_date,

                        end_date =
                            EXCLUDED.end_date,

                        primary_region =
                            EXCLUDED.primary_region,

                        summary =
                            EXCLUDED.summary,

                        article_count =
                            EXCLUDED.article_count,

                        linked_article_ids =
                            EXCLUDED.linked_article_ids,

                        linked_article_urls =
                            EXCLUDED.linked_article_urls,

                        event_evidence_text =
                            EXCLUDED.event_evidence_text,

                        source_url =
                            EXCLUDED.source_url,

                        updated_at =
                            CURRENT_TIMESTAMP

                    RETURNING
                        event_id;
                    """,

                    (
                        event_key,

                        event_obj.get(
                            "event_name"
                        ),

                        event_obj.get(
                            "event_type"
                        ),

                        parse_date_safe(
                            event_obj.get(
                                "start_date"
                            )
                        ),

                        parse_date_safe(
                            event_obj.get(
                                "end_date"
                            )
                        ),

                        event_obj.get(
                            "primary_region"
                        ),

                        event_obj.get(
                            "summary"
                        ),

                        len(
                            articles
                        ),

                        stringify_ids(
                            [
                                article[
                                    "id"
                                ]
                                for article
                                in articles
                            ]
                        ),

                        stringify_urls(
                            linked_urls
                        ),

                        event_obj.get(
                            "event_evidence_text"
                        ),

                        source_url,
                    ),
                )


                result = (
                    cur.fetchone()
                )

                return result[
                    "event_id"
                ]

    finally:

        conn.close()


# ============================================================
# Clear old children only from NEW DB
# ============================================================

def clear_event_children(
    event_id: int
):

    conn = get_target_connection()

    try:

        with conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    DELETE FROM
                        flood_impacts

                    WHERE
                        event_id = %s;
                    """,

                    (
                        event_id,
                    )
                )


                cur.execute(
                    """
                    DELETE FROM
                        flood_incidents

                    WHERE
                        event_id = %s;
                    """,

                    (
                        event_id,
                    )
                )


                cur.execute(
                    """
                    DELETE FROM
                        flood_event_articles

                    WHERE
                        event_id = %s;
                    """,

                    (
                        event_id,
                    )
                )

    finally:

        conn.close()


# ============================================================
# Insert verified event articles
# ============================================================

def insert_flood_event_articles(
    event_id: int,
    articles: List[Dict[str, Any]]
):

    conn = get_target_connection()

    try:

        with conn:

            with conn.cursor() as cur:

                for article in articles:

                    cur.execute(
                        """
                        INSERT INTO
                        flood_event_articles
                        (
                            event_id,

                            article_id,
                            article_title,
                            article_url,
                            published_at,
                            article_content,

                            validation_confidence
                        )

                        VALUES
                        (
                            %s,
                            %s, %s, %s,
                            %s, %s,
                            %s
                        )

                        ON CONFLICT
                        (
                            event_id,
                            article_id
                        )

                        DO NOTHING;
                        """,

                        (
                            event_id,

                            article[
                                "id"
                            ],

                            article.get(
                                "article_title"
                            ),

                            article.get(
                                "article_url"
                            ),

                            article.get(
                                "published_at"
                            ),

                            article.get(
                                "article_content"
                            ),

                            article.get(
                                "validation_confidence"
                            ),
                        ),
                    )

    finally:

        conn.close()


# ============================================================
# Insert incidents + impacts
# ============================================================

def insert_incidents_and_impacts(
    event_id: int,
    incidents: List[Dict[str, Any]]
):

    conn = get_target_connection()

    try:

        with conn:

            with conn.cursor() as cur:

                for incident in incidents:

                    cur.execute(
                        """
                        INSERT INTO
                        flood_incidents
                        (
                            event_id,

                            incident_type,
                            incident_title,
                            incident_description,

                            location_name,

                            address,
                            street,
                            suburb,
                            city,
                            district,
                            region,
                            country,
                            river,

                            location_resolution_level,
                            location_confidence,

                            incident_date,

                            incident_evidence_text,

                            supporting_article_ids
                        )

                        VALUES
                        (
                            %s,

                            %s, %s, %s,

                            %s,

                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s,

                            %s, %s,

                            %s,

                            %s,

                            %s
                        )

                        RETURNING
                            incident_id;
                        """,

                        (
                            event_id,

                            incident.get(
                                "incident_type"
                            ),

                            incident.get(
                                "incident_title"
                            ),

                            incident.get(
                                "incident_description"
                            ),

                            incident.get(
                                "location_name"
                            ),

                            incident.get(
                                "address"
                            ),

                            incident.get(
                                "street"
                            ),

                            incident.get(
                                "suburb"
                            ),

                            incident.get(
                                "city"
                            ),

                            incident.get(
                                "district"
                            ),

                            incident.get(
                                "region"
                            ),

                            incident.get(
                                "country"
                            ),

                            incident.get(
                                "river"
                            ),

                            incident.get(
                                "location_resolution_level"
                            ),

                            incident.get(
                                "location_confidence"
                            ),

                            parse_date_safe(
                                incident.get(
                                    "incident_date"
                                )
                            ),

                            incident.get(
                                "incident_evidence_text"
                            ),

                            stringify_ids(
                                incident.get(
                                    "supporting_article_ids"
                                )
                            ),
                        )
                    )


                    incident_id = (
                        cur.fetchone()[
                            "incident_id"
                        ]
                    )


                    for impact in incident.get(
                        "impacts",
                        []
                    ):

                        cur.execute(
                            """
                            INSERT INTO
                            flood_impacts
                            (
                                incident_id,
                                event_id,

                                impact_category,
                                impact_type,

                                impact_value,
                                impact_unit,

                                impact_description,
                                impact_evidence_text,

                                supporting_article_ids,

                                location_available,

                                impact_location_name,
                                impact_address,
                                impact_street,
                                impact_suburb,
                                impact_city,
                                impact_district,
                                impact_region,
                                impact_country,
                                impact_river,

                                location_resolution_level,
                                location_confidence,

                                location_notes
                            )

                            VALUES
                            (
                                %s, %s,

                                %s, %s,

                                %s, %s,

                                %s, %s,

                                %s,

                                %s,

                                %s, %s, %s,
                                %s, %s, %s,
                                %s, %s, %s,

                                %s, %s,

                                %s
                            );
                            """,

                            (
                                incident_id,
                                event_id,

                                impact.get(
                                    "impact_category"
                                ),

                                impact.get(
                                    "impact_type"
                                ),

                                impact.get(
                                    "impact_value"
                                ),

                                impact.get(
                                    "impact_unit"
                                ),

                                impact.get(
                                    "impact_description"
                                ),

                                impact.get(
                                    "impact_evidence_text"
                                ),

                                stringify_ids(
                                    impact.get(
                                        "supporting_article_ids"
                                    )
                                ),

                                impact.get(
                                    "location_available"
                                ),

                                impact.get(
                                    "impact_location_name"
                                ),

                                impact.get(
                                    "impact_address"
                                ),

                                impact.get(
                                    "impact_street"
                                ),

                                impact.get(
                                    "impact_suburb"
                                ),

                                impact.get(
                                    "impact_city"
                                ),

                                impact.get(
                                    "impact_district"
                                ),

                                impact.get(
                                    "impact_region"
                                ),

                                impact.get(
                                    "impact_country"
                                ),

                                impact.get(
                                    "impact_river"
                                ),

                                impact.get(
                                    "location_resolution_level"
                                ),

                                impact.get(
                                    "location_confidence"
                                ),

                                impact.get(
                                    "location_notes"
                                ),
                            )
                        )

    finally:

        conn.close()


# ============================================================
# Import grouped extraction
# ============================================================

def import_grouped_extraction():

    with open(
        EXTRACT_MANIFEST_JSON,
        "r",
        encoding="utf-8"
    ) as f:

        manifest = json.load(
            f
        )


    with open(
        EXTRACT_OUTPUT_JSONL,
        "r",
        encoding="utf-8"
    ) as f:

        for line_number, line in enumerate(
            f,
            start=1
        ):

            if not line.strip():
                continue


            result_line = json.loads(
                line
            )

            custom_id = (
                result_line.get(
                    "custom_id"
                )
            )


            if custom_id not in manifest:

                print(
                    f"Unknown event: "
                    f"{custom_id}"
                )

                continue


            response = (
                result_line.get(
                    "response",
                    {}
                )
            )


            if response.get(
                "status_code"
            ) != 200:

                print(
                    f"Non-200: "
                    f"{custom_id}"
                )

                continue


            raw = (
                extract_text_from_response_body(
                    response.get(
                        "body",
                        {}
                    )
                )
            )


            raw = strip_code_fences(
                raw
            )
            raw = re.sub(
                r'"location_confidence"\s*:\s*(low|medium|high)\s*([,}])',
                r'"location_confidence": "\1"\2',
                raw
            )

            # Fix semicolon-separated quoted evidence strings
            raw = re.sub(
                r'"\s*;\s*"',
                '; ',
                raw
            )

            try:
                extracted = json.loads(raw)

            except json.JSONDecodeError as e:

                print(f"\nInvalid JSON for {custom_id}")
                print(f"JSON error: {e}")

                repaired = try_repair_json(raw)

                if repaired is not None:
                    print(f"[repair] Successfully repaired JSON for {custom_id}")
                    extracted = repaired

                else:
                    bad_dir = OUTPUT_DIR / "invalid_extraction_json"
                    bad_dir.mkdir(
                        parents=True,
                        exist_ok=True
                    )

                    bad_file = (
                        bad_dir /
                        f"{custom_id}.txt"
                    )

                    bad_file.write_text(
                        raw,
                        encoding="utf-8"
                    )

                    print(
                        f"Saved invalid response to: "
                        f"{bad_file}"
                    )

                    continue

            meta = manifest[
                custom_id
            ]

            event_cfg = (
                meta[
                    "event_cfg"
                ]
            )

            articles = (
                meta[
                    "articles"
                ]
            )


            if "event" not in extracted:

                print(
                    f"No event object: "
                    f"{custom_id}"
                )

                continue


            event_obj = (
                extracted[
                    "event"
                ]
            )


            event_obj[
                "article_count"
            ] = len(
                articles
            )


            event_obj[
                "linked_article_ids"
            ] = [
                str(
                    article[
                        "id"
                    ]
                )

                for article
                in articles
            ]


            event_id = (
                upsert_flood_event(
                    event_key=
                        custom_id,

                    event_obj=
                        event_obj,

                    articles=
                        articles,

                    source_url=
                        event_cfg.get(
                            "source_url"
                        )
                )
            )


            clear_event_children(
                event_id
            )


            insert_flood_event_articles(
                event_id,
                articles
            )


            insert_incidents_and_impacts(
                event_id,

                extracted.get(
                    "incidents",
                    []
                )
            )


            print(
                f"[saved] "
                f"{event_cfg['event_name']} "
                f"event_id={event_id} "
                f"articles={len(articles)} "
                f"incidents="
                f"{len(extracted.get('incidents', []))}"
            )


# ============================================================
# Poll
# ============================================================

def poll_until_complete(
    batch_id: str,
    sleep_seconds: int = 60
):

    while True:

        batch = (
            show_batch_status(
                batch_id
            )
        )

        if batch.status in [
            "completed",
            "failed",
            "cancelled",
            "expired",
        ]:

            return batch.status

        print(
            f"Waiting "
            f"{sleep_seconds}s..."
        )

        time.sleep(
            sleep_seconds
        )


def split_verification_jsonl(
    input_path: Path = VERIFY_INPUT_JSONL,
    lines_per_file: int = 500
) -> List[Path]:
    """
    Split the large verification JSONL into smaller files
    so that each OpenAI Batch submission stays below
    the organisation's enqueued-token limit.
    """

    split_dir = OUTPUT_DIR / "verification_parts"

    split_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # Remove old split files so we do not mix runs.
    for old_file in split_dir.glob("verification_part_*.jsonl"):
        old_file.unlink()

    with open(
        input_path,
        "r",
        encoding="utf-8"
    ) as infile:

        lines = [
            line
            for line in infile
            if line.strip()
        ]

    part_files = []

    for start in range(
        0,
        len(lines),
        lines_per_file
    ):

        chunk = lines[
            start:
            start + lines_per_file
        ]

        part_number = (
            start // lines_per_file
        ) + 1

        part_path = (
            split_dir /
            f"verification_part_{part_number:03d}.jsonl"
        )

        with open(
            part_path,
            "w",
            encoding="utf-8"
        ) as outfile:

            outfile.writelines(
                chunk
            )

        part_files.append(
            part_path
        )

        print(
            f"[split] {part_path} "
            f"-> {len(chunk)} requests"
        )

    print(
        f"\nCreated {len(part_files)} "
        f"verification batch parts."
    )

    return part_files


# ============================================================
# Commands
# ============================================================

def try_repair_json(raw: str):
    """
    Attempts a few safe repairs for common LLM JSON formatting issues.
    Returns parsed dict if successful, otherwise None.
    """

    raw = strip_code_fences(raw).strip()

    # Try normal JSON first
    raw = re.sub(
        r'"location_confidence"\s*:\s*(low|medium|high)\s*([,}])',
        r'"location_confidence": "\1"\2',
        raw
    )

    # Fix semicolon-separated quoted evidence strings
    raw = re.sub(
        r'"\s*;\s*"',
        '; ',
        raw
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Extract only the outermost JSON object
    first = raw.find("{")
    last = raw.rfind("}")

    if first != -1 and last != -1 and last > first:
        candidate = raw[first:last + 1]

        candidate = re.sub(
            r'"location_confidence"\s*:\s*(low|medium|high)\s*([,}])',
            r'"location_confidence": "\1"\2',
            candidate
        )

        # Fix semicolon-separated quoted evidence strings
        candidate = re.sub(
            r'"\s*;\s*"',
            '; ',
            candidate
        )
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    return None

def combine_verification_outputs():

    parts = sorted(
        OUTPUT_DIR.glob(
            "verification_part_*_output.jsonl"
        )
    )

    if not parts:
        raise FileNotFoundError(
            "No verification output parts found."
        )

    total_lines = 0

    with open(
        VERIFY_OUTPUT_JSONL,
        "w",
        encoding="utf-8"
    ) as outfile:

        for part in parts:

            print(
                f"[combine] {part.name}"
            )

            with open(
                part,
                "r",
                encoding="utf-8"
            ) as infile:

                for line in infile:

                    if line.strip():

                        outfile.write(line)

                        total_lines += 1

    print("\n" + "=" * 80)

    print(
        f"Combined {len(parts)} files"
    )

    print(
        f"Total verification results: "
        f"{total_lines}"
    )

    print(
        f"Combined output: "
        f"{VERIFY_OUTPUT_JSONL}"
    )

    print("=" * 80)

def command_combine_verify(args):

    combine_verification_outputs()

def command_prepare_verify(
    args
):

    events = (
        load_events_from_excel(
            args.excel
        )
    )

    print(
        f"Loaded "
        f"{len(events)} events."
    )

    prepare_verification_batch(
        events
    )

    split_verification_jsonl(
        VERIFY_INPUT_JSONL,
        lines_per_file=500
    )

def command_submit_verify(
    args
):

    submit_batch_file(
        VERIFY_INPUT_JSONL,
        VERIFY_BATCH_INFO,
        (
            "NZ flood article-event "
            "verification"
        )
    )


def command_import_verify(
    args
):

    import_verification_results()


def command_prepare_extract(
    args
):

    events = (
        load_events_from_excel(
            args.excel
        )
    )

    prepare_grouped_extraction_batch(
        events
    )


def command_submit_extract(
    args
):

    submit_batch_file(
        EXTRACT_INPUT_JSONL,
        EXTRACT_BATCH_INFO,
        (
            "Verified NZ flood "
            "Event Incident Impact extraction"
        )
    )


def command_import_extract(
    args
):

    import_grouped_extraction()


def command_status(
    args
):

    show_batch_status(
        args.batch_id
    )


def command_download_verify(
    args
):

    download_batch(
        args.batch_id,
        VERIFY_OUTPUT_JSONL,
        VERIFY_ERROR_JSONL
    )


def command_download_extract(
    args
):

    download_batch(
        args.batch_id,
        EXTRACT_OUTPUT_JSONL,
        EXTRACT_ERROR_JSONL
    )

def process_all_verification_parts(
    sleep_seconds: int = 60
):
    """
    Sequentially processes all split verification parts:

    Part 001
        -> submit
        -> wait until complete
        -> download

    Part 002
        -> submit
        -> wait until complete
        -> download

    ...until all parts are finished.
    """

    parts_dir = OUTPUT_DIR / "verification_parts"

    part_files = sorted(
        parts_dir.glob("verification_part_*.jsonl")
    )

    if not part_files:
        raise FileNotFoundError(
            f"No verification part files found in {parts_dir}"
        )

    print(f"Found {len(part_files)} verification parts.")

    for index, part_path in enumerate(part_files, start=1):

        print("\n" + "=" * 80)
        print(
            f"PROCESSING PART {index}/{len(part_files)}"
        )
        print(f"File: {part_path}")
        print("=" * 80)

        # ----------------------------------------------------
        # Output filenames unique to this part
        # ----------------------------------------------------

        output_path = (
            OUTPUT_DIR /
            f"{part_path.stem}_output.jsonl"
        )

        error_path = (
            OUTPUT_DIR /
            f"{part_path.stem}_errors.jsonl"
        )

        batch_info_path = (
            OUTPUT_DIR /
            f"{part_path.stem}_batch_info.json"
        )

        # ----------------------------------------------------
        # Skip already completed/downloaded parts
        # ----------------------------------------------------

        if output_path.exists():

            print(
                f"[skip] Output already exists: "
                f"{output_path}"
            )

            continue

        # ----------------------------------------------------
        # Submit this part
        # ----------------------------------------------------

        batch_info = submit_batch_file(
            part_path,
            batch_info_path,
            (
                "NZ flood article-event "
                f"verification {part_path.stem}"
            )
        )

        batch_id = batch_info["batch_id"]

        print(
            f"\nSubmitted {part_path.name}"
        )

        print(
            f"Batch ID: {batch_id}"
        )

        # ----------------------------------------------------
        # Wait until this batch finishes
        # ----------------------------------------------------

        final_status = poll_until_complete(
            batch_id,
            sleep_seconds=sleep_seconds
        )

        # ----------------------------------------------------
        # Stop if this part failed
        # ----------------------------------------------------

        if final_status != "completed":

            print(
                f"\nSTOPPING."
            )

            print(
                f"{part_path.name} ended with "
                f"status: {final_status}"
            )

            print(
                "Fix the issue before continuing "
                "to the remaining parts."
            )

            return

        # ----------------------------------------------------
        # Download this part
        # ----------------------------------------------------

        download_batch(
            batch_id,
            output_path,
            error_path
        )

        print(
            f"\nCompleted part {index}/"
            f"{len(part_files)}"
        )

    print("\n" + "=" * 80)
    print("ALL VERIFICATION PARTS COMPLETED")
    print("=" * 80)

def command_process_all_verify_parts(args):

        process_all_verification_parts(
            sleep_seconds=args.sleep_seconds
        )
# ============================================================
# Full pipeline
# ============================================================

def command_run_all(
    args
):

    events = (
        load_events_from_excel(
            args.excel
        )
    )


    # --------------------------------------------------------
    # PHASE 1
    # Candidate → verification
    # --------------------------------------------------------

    print(
        "\n"
        "PHASE 1: "
        "ARTICLE ↔ EVENT VERIFICATION"
    )

    count = (
        prepare_verification_batch(
            events
        )
    )

    if count == 0:

        print(
            "No candidate articles."
        )

        return


    verify_batch = (
        submit_batch_file(
            VERIFY_INPUT_JSONL,

            VERIFY_BATCH_INFO,

            (
                "NZ flood "
                "article-event verification"
            )
        )
    )


    if not args.poll:

        print(
            "\nVerification batch submitted."
        )

        print(
            f"Batch ID: "
            f"{verify_batch['batch_id']}"
        )

        return


    verify_status = (
        poll_until_complete(
            verify_batch[
                "batch_id"
            ],

            args.sleep_seconds
        )
    )


    if verify_status != "completed":

        print(
            "Verification batch "
            "did not complete."
        )

        return


    download_batch(
        verify_batch[
            "batch_id"
        ],

        VERIFY_OUTPUT_JSONL,
        VERIFY_ERROR_JSONL
    )


    import_verification_results()


    # --------------------------------------------------------
    # PHASE 2
    # Verified articles → grouped extraction
    # --------------------------------------------------------

    print(
        "\n"
        "PHASE 2: "
        "EVENT → INCIDENT → IMPACT"
    )


    extract_count = (
        prepare_grouped_extraction_batch(
            events
        )
    )


    if extract_count == 0:

        print(
            "No verified articles "
            "available for extraction."
        )

        return


    extraction_batch = (
        submit_batch_file(
            EXTRACT_INPUT_JSONL,

            EXTRACT_BATCH_INFO,

            (
                "Verified NZ flood "
                "event extraction"
            )
        )
    )


    extraction_status = (
        poll_until_complete(
            extraction_batch[
                "batch_id"
            ],

            args.sleep_seconds
        )
    )


    if extraction_status != "completed":

        print(
            "Extraction batch "
            "did not complete."
        )

        return


    download_batch(
        extraction_batch[
            "batch_id"
        ],

        EXTRACT_OUTPUT_JSONL,
        EXTRACT_ERROR_JSONL
    )


    import_grouped_extraction()


    print(
        "\n"
        "FULL VERIFIED PIPELINE COMPLETE."
    )


# ============================================================
# CLI
# ============================================================

def build_arg_parser():

    parser = (
        argparse.ArgumentParser(
            description=(
                "Verified NZ flood event "
                "classification and "
                "Event-Incident-Impact extraction"
            )
        )
    )


    subparsers = (
        parser.add_subparsers(
            dest="command",
            required=True
        )
    )


    prepare_verify = (
        subparsers.add_parser(
            "prepare-verify"
        )
    )

    prepare_verify.add_argument(
        "--excel",
        default=EXCEL_PATH
    )

    process_verify_parts = (
    subparsers.add_parser(
        "process-all-verify-parts"
    )
    )

    process_verify_parts.add_argument(
        "--sleep-seconds",
        type=int,
        default=60
    )

    process_verify_parts.set_defaults(
        func=command_process_all_verify_parts
    )

    prepare_verify.set_defaults(
        func=command_prepare_verify
    )


    submit_verify = (
        subparsers.add_parser(
            "submit-verify"
        )
    )

    submit_verify.set_defaults(
        func=command_submit_verify
    )


    download_verify = (
        subparsers.add_parser(
            "download-verify"
        )
    )

    download_verify.add_argument(
        "--batch-id",
        required=True
    )

    download_verify.set_defaults(
        func=command_download_verify
    )


    import_verify = (
        subparsers.add_parser(
            "import-verify"
        )
    )

    import_verify.set_defaults(
        func=command_import_verify
    )


    prepare_extract = (
        subparsers.add_parser(
            "prepare-extract"
        )
    )

    prepare_extract.add_argument(
        "--excel",
        default=EXCEL_PATH
    )

    prepare_extract.set_defaults(
        func=command_prepare_extract
    )


    submit_extract = (
        subparsers.add_parser(
            "submit-extract"
        )
    )

    submit_extract.set_defaults(
        func=command_submit_extract
    )


    download_extract = (
        subparsers.add_parser(
            "download-extract"
        )
    )

    download_extract.add_argument(
        "--batch-id",
        required=True
    )

    download_extract.set_defaults(
        func=command_download_extract
    )


    import_extract = (
        subparsers.add_parser(
            "import-extract"
        )
    )

    import_extract.set_defaults(
        func=command_import_extract
    )


    status = (
        subparsers.add_parser(
            "status"
        )
    )

    status.add_argument(
        "--batch-id",
        required=True
    )

    status.set_defaults(
        func=command_status
    )


    run_all = (
        subparsers.add_parser(
            "run-all"
        )
    )

    run_all.add_argument(
        "--excel",
        default=EXCEL_PATH
    )

    run_all.add_argument(
        "--poll",
        action="store_true"
    )

    run_all.add_argument(
        "--sleep-seconds",
        type=int,
        default=60
    )

    run_all.set_defaults(
        func=command_run_all
    )

    combine_verify = (
    subparsers.add_parser(
        "combine-verify"
    )
    )

    combine_verify.set_defaults(
        func=command_combine_verify
    )


    return parser


# ============================================================
# Main
# ============================================================

def main():

    parser = (
        build_arg_parser()
    )

    args = (
        parser.parse_args()
    )

    args.func(
        args
    )


if __name__ == "__main__":
    main()