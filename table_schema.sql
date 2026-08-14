CREATE TABLE flood_events (
    event_id SERIAL PRIMARY KEY,
    event_key TEXT UNIQUE NOT NULL,
    event_name TEXT NOT NULL,
    event_type TEXT,
    start_date DATE,
    end_date DATE,
    primary_region TEXT,
    summary TEXT,
    article_count INTEGER DEFAULT 0,
    linked_article_ids TEXT,
    linked_article_urls TEXT,
    event_evidence_text TEXT,
    source_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

SELECT
    COUNT(*) AS total_verification_pairs,
    COUNT(*) FILTER (
        WHERE belongs_to_event = TRUE
    ) AS llm_accepted,
    COUNT(*) FILTER (
        WHERE belongs_to_event = FALSE
    ) AS llm_rejected,
    COUNT(*) FILTER (
        WHERE is_primary_assignment = TRUE
    ) AS final_primary_assignments
FROM flood_article_event_validation;

SELECT
    event_name,
    COUNT(*) AS assigned_articles
FROM flood_article_event_validation
WHERE is_primary_assignment = TRUE
GROUP BY event_name
ORDER BY assigned_articles DESC;

select * from flood_article_event_validation;
select * from flood_event_articles;
select * from flood_events;
select * from flood_impacts;
select * from flood_incidents;

SELECT
    fe.event_name,
    COUNT(fea.article_id) AS article_count
FROM flood_events fe
JOIN flood_event_articles fea
    ON fe.event_id = fea.event_id
WHERE fe.event_name ILIKE '%Debbie%'
GROUP BY fe.event_name;

SELECT COUNT(*) AS article_count
FROM flood_event_articles fea
JOIN flood_events fe
    ON fe.event_id = fea.event_id
WHERE fe.event_name ILIKE '%Debbie%';



CREATE TABLE flood_article_event_validation (
    validation_id SERIAL PRIMARY KEY,

    event_key TEXT NOT NULL,
    event_name TEXT NOT NULL,

    article_id INTEGER NOT NULL,
    article_title TEXT,
    article_url TEXT,
    published_at TIMESTAMP,

    belongs_to_event BOOLEAN NOT NULL,

    confidence NUMERIC(5,4),

    temporal_match BOOLEAN,
    location_match BOOLEAN,
    disaster_context_match BOOLEAN,

    verification_reason TEXT,

    is_primary_assignment BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(event_key, article_id)
);


CREATE TABLE flood_event_articles (
    id SERIAL PRIMARY KEY,

    event_id INTEGER NOT NULL
        REFERENCES flood_events(event_id)
        ON DELETE CASCADE,

    article_id INTEGER NOT NULL,
    article_title TEXT,
    article_url TEXT,
    published_at TIMESTAMP,
    article_content TEXT,

    validation_confidence NUMERIC(5,4),

    UNIQUE(event_id, article_id)
);


CREATE TABLE flood_incidents (
    incident_id SERIAL PRIMARY KEY,

    event_id INTEGER NOT NULL
        REFERENCES flood_events(event_id)
        ON DELETE CASCADE,

    incident_type TEXT,
    incident_title TEXT,
    incident_description TEXT,

    location_name TEXT,
    address TEXT,
    street TEXT,
    suburb TEXT,
    city TEXT,
    district TEXT,
    region TEXT,
    country TEXT,
    river TEXT,

    location_resolution_level TEXT,
    location_confidence TEXT,

    incident_date DATE,

    incident_evidence_text TEXT,

    supporting_article_ids TEXT
);


CREATE TABLE flood_impacts (
    impact_id SERIAL PRIMARY KEY,

    incident_id INTEGER NOT NULL
        REFERENCES flood_incidents(incident_id)
        ON DELETE CASCADE,

    event_id INTEGER NOT NULL
        REFERENCES flood_events(event_id)
        ON DELETE CASCADE,

    impact_category TEXT,
    impact_type TEXT,

    impact_value TEXT,
    impact_unit TEXT,

    impact_description TEXT,
    impact_evidence_text TEXT,

    supporting_article_ids TEXT,

    location_available BOOLEAN,

    impact_location_name TEXT,
    impact_address TEXT,
    impact_street TEXT,
    impact_suburb TEXT,
    impact_city TEXT,
    impact_district TEXT,
    impact_region TEXT,
    impact_country TEXT,
    impact_river TEXT,

    location_resolution_level TEXT,
    location_confidence TEXT,
    location_notes TEXT
);

CREATE TABLE IF NOT EXISTS news_articles (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT,
    source_domain TEXT,
    source_country TEXT,
    article_title TEXT NOT NULL,
    article_url TEXT NOT NULL UNIQUE,
    article_image_url TEXT,
    published_at TIMESTAMP,
    language TEXT,
    search_query TEXT,
    article_description TEXT,
    article_content TEXT,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);