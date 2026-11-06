import os
from datetime import datetime
from urllib.parse import urlparse

import psycopg2
from dotenv import load_dotenv
#from dnz.api import Dnz
from api import Dnz



load_dotenv()

DIGITALNZ_API_KEY = os.getenv("DIGITALNZ_API_KEY")
if not DIGITALNZ_API_KEY:
    raise ValueError("Please set DIGITALNZ_API_KEY in your .env file")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}
'''
SEARCH_QUERIES = [
   "flood",
    "flooding",
    "flash flood",
    "storm flood",
    "river flood",
    "New Zealand flood",
]

SEARCH_QUERIES = [
    "Cyclone Gabrielle flooding",
    "Auckland Anniversary floods",
    "Wellington flooding 2026",
    "Cyclone Vaianu flooding",
    "East Coast flooding January 2026",
    "Nelson Tasman flooding 2025",
    "Dunedin flooding October 2024",
    "Edgecumbe flood 2017",
]
'''

SEARCH_QUERIES = [
    # Major 2023 events
    "Cyclone Gabrielle flooding",
    "Cyclone Gabrielle flood damage",
    "Cyclone Gabrielle Hawke's Bay flooding",
    "Cyclone Gabrielle Tairāwhiti flooding",
    "Cyclone Gabrielle Wairoa flooding",
    "Cyclone Gabrielle Esk Valley flooding",
    "Cyclone Gabrielle road bridge damage",
    "Cyclone Gabrielle power outage communication",

    "Auckland Anniversary floods",
    "Auckland flooding January 2023",
    "Auckland flood damage January 2023",
    "Auckland flood evacuation 2023",

    "Ex-Tropical Cyclone Hale flooding",
    "Cyclone Hale Tairāwhiti flooding",
    "Cyclone Hale severe weather New Zealand",

    # 2026 events
    "Wellington flooding 2026",
    "Wellington flood damage 2026",
    "Wellington severe weather flooding 2026",

    "Cyclone Vaianu flooding",
    "Cyclone Vaianu severe weather New Zealand",
    "Cyclone Vaianu flood damage",

    "East Coast flooding January 2026",
    "Tairāwhiti flooding January 2026",
    "Te Araroa flood damage 2026",
    "Tropical Depression 5F New Zealand flooding",

    "Waikato flooding February 2026",
    "Ōtorohanga flooding 2026",
    "Otorohanga flooding 2026",
    "Waipā flooding 2026",

    "Banks Peninsula flooding February 2026",
    "Banks Peninsula slips flooding 2026",
    "Canterbury flooding Banks Peninsula 2026",

    "Ōhura flooding 2026",
    "Ohura flooding 2026",
    "Whanganui flooding April 2026",

    # 2025 events
    "Nelson Tasman flooding 2025",
    "Marlborough flooding 2025",
    "Nelson Tasman severe weather June 2025",
    "Marlborough stopbank flooding 2025",

    "Canterbury flooding May 2025",
    "Selwyn flooding May 2025",
    "Christchurch flooding May 2025",

    # 2024 events
    "Dunedin flooding October 2024",
    "Clutha flooding October 2024",
    "Otago flooding October 2024",

    "Wairoa coastal inundation 2024",
    "Hawke's Bay coastal flooding 2024",
    "Haumoana coastal inundation 2024",

    "East Coast flooding June 2024 New Zealand",
    "Hawke's Bay flooding June 2024",
    "Tairāwhiti flooding June 2024",
    "Wairoa flooding June 2024",

    "Westland flooding January 2024",
    "West Coast flooding January 2024",

    # 2023 other events
    "Southland flooding September 2023",
    "Gore flooding September 2023",
    "Queenstown flooding September 2023",
    "Otago flooding September 2023",

    "Tairāwhiti flooding June 2023",
    "Gisborne flooding June 2023",

    "Auckland flooding May 2023",
    "Auckland severe weather May 2023",

    # 2022 events
    "Nelson Tasman floods August 2022",
    "Marlborough floods August 2022",
    "West Coast floods August 2022",
    "Nelson flooding 2022",

    "South Canterbury flooding July 2022",
    "Temuka flooding July 2022",
    "Pleasant Point flooding July 2022",

    "Tairāwhiti flooding March 2022",
    "Gisborne flooding March 2022",

    "Buller flooding February 2022",
    "Westport flooding February 2022",
    "West Coast flooding February 2022",

    # 2021 events
    "Tairāwhiti flooding November 2021",
    "Gisborne flooding November 2021",

    "West Coast flooding July 2021",
    "Buller flooding July 2021",
    "Marlborough flooding July 2021",
    "Westport flooding July 2021",

    "Canterbury floods May 2021",
    "Canterbury flooding June 2021",
    "Ashburton flooding 2021",
    "Selwyn flooding 2021",
    "Waimakariri flooding 2021",

    # 2020 events
    "Napier flooding November 2020",
    "Hawke's Bay flooding November 2020",

    "Southland flooding February 2020",
    "Gore flooding February 2020",
    "Fiordland flooding February 2020",
    "Clutha flooding February 2020",

    # 2019 events
    "Rangitata flooding December 2019",
    "Timaru flooding December 2019",
    "Canterbury flooding December 2019",

    "Westland flooding March 2019",
    "West Coast flooding March 2019",

    # 2018 events
    "Ngongotahā flooding April 2018",
    "Ngongotaha flooding April 2018",
    "Rotorua flooding April 2018",
    "Bay of Plenty flooding April 2018",

    "Cyclone Gita flooding",
    "Cyclone Gita New Zealand",
    "Cyclone Gita Nelson Tasman",
    "Cyclone Gita Christchurch flooding",
    "Cyclone Gita West Coast",

    "Ex-Tropical Cyclone Fehi flooding",
    "Cyclone Fehi Dunedin flooding",
    "Cyclone Fehi West Coast flooding",

    # 2017 events
    "Canterbury floods July 2017",
    "Otago floods July 2017",
    "Dunedin flooding July 2017",
    "Christchurch flooding July 2017",

    "Cyclone Cook New Zealand flooding",
    "Cyclone Cook Bay of Plenty flooding",
    "Whakatāne flooding Cyclone Cook",
    "Thames Coromandel flooding Cyclone Cook",

    "Edgecumbe flood 2017",
    "Ex-Tropical Cyclone Debbie New Zealand flooding",
    "Rangitāiki River stopbank failure",
    "Whakatāne flooding April 2017",

    "Tasman Tempest flooding",
    "Tasman Tempest New Zealand",
    "Auckland flooding Tasman Tempest",
    "Coromandel flooding Tasman Tempest",
]


INSERT_SQL = """
INSERT INTO news_articles (
    source_name,
    source_domain,
    source_country,
    article_title,
    article_url,
    article_image_url,
    published_at,
    language,
    search_query,
    article_description,
    article_content
)
VALUES (
    %(source_name)s,
    %(source_domain)s,
    %(source_country)s,
    %(article_title)s,
    %(article_url)s,
    %(article_image_url)s,
    %(published_at)s,
    %(language)s,
    %(search_query)s,
    %(article_description)s,
    %(article_content)s
)
ON CONFLICT (article_url) DO UPDATE SET
    source_name = EXCLUDED.source_name,
    source_domain = EXCLUDED.source_domain,
    source_country = EXCLUDED.source_country,
    article_title = EXCLUDED.article_title,
    article_image_url = EXCLUDED.article_image_url,
    published_at = EXCLUDED.published_at,
    language = EXCLUDED.language,
    search_query = EXCLUDED.search_query,
    article_description = EXCLUDED.article_description,
    article_content = EXCLUDED.article_content;
"""


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def parse_datetime(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    value = str(value).strip()

    # Common ISO-style formats seen in APIs
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    return None


def extract_domain(url):
    if not url:
        return None
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return None


def safe_get(record, key, default=None):
    """
    Handles both dict-like records and objects with attributes.
    """
    if isinstance(record, dict):
        return record.get(key, default)
    return getattr(record, key, default)


def normalize_text(value):
    if value is None:
        return None

    if isinstance(value, list):
        joined = " ".join(str(v).strip() for v in value if v is not None)
        return joined.strip() or None

    value = str(value).strip()
    return value or None


def get_best_article_url(record):
    """
    Prefer source_url when available, otherwise fall back to landing_url.
    """
    source_url = normalize_text(safe_get(record, "source_url"))
    landing_url = normalize_text(safe_get(record, "landing_url"))
    return source_url or landing_url


def map_record_to_row(record, search_query):
    article_url = get_best_article_url(record)
    if not article_url:
        return None

    title = normalize_text(safe_get(record, "title"))
    if not title:
        return None

    description = normalize_text(safe_get(record, "description"))
    additional_description = normalize_text(safe_get(record, "additional_description"))
    thumbnail_url = normalize_text(safe_get(record, "thumbnail_url"))
    content_partner = normalize_text(safe_get(record, "content_partner"))
    language = normalize_text(safe_get(record, "language"))
    date_value = normalize_text(safe_get(record, "date"))

    article_description = description or additional_description
    article_content = description or additional_description  # metadata only, not full page text

    return {
        "source_name": content_partner or "DigitalNZ",
        "source_domain": extract_domain(article_url),
        "source_country": "New Zealand",
        "article_title": title,
        "article_url": article_url,
        "article_image_url": thumbnail_url,
        "published_at": parse_datetime(date_value),
        "language": language,
        "search_query": search_query,
        "article_description": article_description,
        "article_content": article_content,
    }


def save_rows(rows):
    if not rows:
        return 0

    conn = get_db_connection()
    inserted = 0

    try:
        with conn:
            with conn.cursor() as cur:
                for row in rows:
                    cur.execute(INSERT_SQL, row)
                    inserted += 1
    finally:
        conn.close()

    return inserted


def fetch_and_store_from_digitalnz(
    search_query,
    per_page=100,
    max_pages=5,
    category_filter="Articles"
):
    dnz = Dnz(DIGITALNZ_API_KEY)

    total_saved = 0

    for page in range(1, max_pages + 1):
        print(f"Fetching query='{search_query}', page={page}")

        result = dnz.search(
            search_query,
            per_page=per_page,
            page=page,
            sort="date",
            direction="desc",
            fields=[
                "title",
                "description",
                "additional_description",
                "source_url",
                "landing_url",
                "thumbnail_url",
                "date",
                "language",
                "content_partner",
                "category",
            ],
            _and={"category": [category_filter]},
        )

        records = getattr(result, "records", None) or []

        if not records:
            print("No more records found.")
            break

        rows = []
        for record in records:
            row = map_record_to_row(record, search_query)
            if row:
                rows.append(row)

        saved_now = save_rows(rows)
        total_saved += saved_now

        print(f"Saved/updated {saved_now} rows from page {page}")

        if len(records) < per_page:
            break

    print(f"Finished query='{search_query}'. Total saved/updated: {total_saved}")
    return total_saved


def main():
    grand_total = 0

    for query in SEARCH_QUERIES:
        grand_total += fetch_and_store_from_digitalnz(
            search_query=query,
            per_page=100,
            max_pages=5,
            category_filter="Articles",
        )

    print(f"All queries finished. Total rows saved/updated: {grand_total}")


if __name__ == "__main__":
    main()