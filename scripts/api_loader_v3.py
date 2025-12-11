"""
Universal API-to-Database Loader
================================

A clean, production-ready template for fetching data from any REST API
and storing it in a database. Designed to be your "Swiss Army Knife"
for data pipelines.

Features:
---------
- Automatic retry on network failures (no more crashed overnight jobs)
- Pagination handling (fetch millions of records without RAM explosion)
- Database upserts (update existing, insert new - no duplicates)
- Generator-based processing (constant memory usage)
- Rate limiting support (be polite to APIs)
- Safe type handling (preserves leading zeros in IDs)
- Works with SQLite, PostgreSQL, MySQL out of the box

Usage:
------
1. Set your environment variables:
   export API_URL="https://api.example.com/items"
   export API_TOKEN="your_token_here"
   export DB_URL="sqlite:///data.db"  # or postgresql://user:pass@host/db

2. Run:
   python api_loader.py

Or import and use programmatically:
   from api_loader import fetch_all, save_to_db
   for batch in fetch_all("https://api.example.com/items"):
       save_to_db(batch, "items")

Author: Your friend who finally stopped vibe coding
Version: 2.0.0 (2025) - Production Hardened
"""

# =============================================================================
# DEVELOPER NOTES (FOR AI ASSISTANTS)
# =============================================================================
# READ THIS BEFORE MAKING CHANGES:
#
# Architecture:
# - This script uses SQLAlchemy Core (not ORM) for performance
# - Generators (yield) are used throughout to prevent memory exhaustion
# - The "temp table" pattern enables portable upserts across DB vendors
#
# DO NOT:
# - Change 'yield' to 'return' in pagination functions (causes OOM on large datasets)
# - Remove the retry logic from create_session() (causes overnight job failures)
# - Hardcode API keys (use environment variables)
# - Let Pandas auto-infer types for ID columns (zip codes become integers)
#
# IF ADDING:
# - New pagination style: add a paginate_xxx() function, register in fetch_all()
# - New database type: add dialect-specific UPSERT SQL in save_to_db()
# - New auth method: extend create_session() parameters
#
# The "Holy Trinity" of data pipelines that this script implements:
# 1. Generators (yield) - constant memory usage
# 2. Retries (HTTPAdapter) - network resilience
# 3. Upserts - idempotent data loading (re-run safe)
#
# PRODUCTION GOTCHAS HANDLED:
# - UUID temp tables (prevents race conditions with parallel runs)
# - ID columns forced to string (preserves leading zeros: "06510" stays "06510")
# - Batched deletes in fallback (prevents SQL query length overflow)
# - Column collision detection (warns if "User Name" and "User-Name" collide)
# =============================================================================

import os
import re
import time
import uuid
import logging
from typing import Iterator, Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass
from datetime import datetime

import requests
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class Config:
    """
    All configuration in one place. Override via environment variables.

    Example .env file:
        API_URL=https://inventory.zoho.com/api/v1/items
        API_TOKEN=your_oauth_token
        DB_URL=postgresql://user:pass@localhost:5432/mydb

    Example with python-dotenv:
        from dotenv import load_dotenv
        load_dotenv()
        config = Config()
    """
    # API Settings
    api_url: str = os.getenv("API_URL", "https://api.example.com/items")
    api_token: str = os.getenv("API_TOKEN", "")
    api_page_size: int = int(os.getenv("API_PAGE_SIZE", "200"))
    api_timeout: int = int(os.getenv("API_TIMEOUT", "30"))

    # Rate Limiting
    # Zoho: 100 requests/minute = 0.6s delay
    # GitHub: 5000 requests/hour = 0.72s delay
    rate_limit_delay: float = float(os.getenv("RATE_LIMIT_DELAY", "0.0"))

    # Database Settings
    db_url: str = os.getenv("DB_URL", "sqlite:///api_data.db")
    db_table: str = os.getenv("DB_TABLE", "items")
    db_primary_key: str = os.getenv("DB_PRIMARY_KEY", "id")

    # Retry Settings
    max_retries: int = 3
    retry_backoff: float = 1.0

    # Batch size for fallback delete operations
    delete_batch_size: int = 500


config = Config()


# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


# =============================================================================
# HTTP SESSION WITH RETRY
# =============================================================================

def create_session(
    token: Optional[str] = None,
    auth_header: str = "Authorization",
    auth_prefix: str = "Bearer",
) -> requests.Session:
    """
    Create a requests Session with automatic retry on failures.

    Args:
        token: API token/key. If None, uses config.api_token
        auth_header: Header name for auth (e.g., "Authorization", "X-API-Key")
        auth_prefix: Prefix before token (e.g., "Bearer", "Zoho-oauthtoken", "")

    Returns:
        Configured Session object
    """
    session = requests.Session()

    retry_strategy = Retry(
        total=config.max_retries,
        backoff_factor=config.retry_backoff,
        status_forcelist=[408, 429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "PUT", "DELETE"],
    )

    # Connection pooling: keeps connections open for reuse (2-5x faster)
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,
        pool_maxsize=10,
    )

    session.mount("http://", adapter)
    session.mount("https://", adapter)

    token = token or config.api_token
    if token:
        auth_value = f"{auth_prefix} {token}".strip() if auth_prefix else token
        session.headers[auth_header] = auth_value

    session.headers["User-Agent"] = "APILoader/2.0"
    session.headers["Accept"] = "application/json"

    return session


# =============================================================================
# PAGINATION HANDLERS
# =============================================================================
# Using generators (yield) for constant memory usage regardless of data size.

def paginate_offset(
    session: requests.Session,
    url: str,
    data_key: str = "items",
    page_param: str = "page",
    size_param: str = "per_page",
    page_size: int = 200,
) -> Iterator[List[Dict[str, Any]]]:
    """Handle page-number pagination (most common)."""
    page = 1

    while True:
        if config.rate_limit_delay > 0:
            time.sleep(config.rate_limit_delay)

        try:
            response = session.get(
                url,
                params={page_param: page, size_param: page_size},
                timeout=config.api_timeout,
            )
            response.raise_for_status()
            data = response.json()

            items = data.get(data_key) or data.get("data", {}).get(data_key) or []

            if not items:
                logger.info(f"No more data at page {page}")
                break

            logger.info(f"Fetched page {page}: {len(items)} records")
            yield items

            if len(items) < page_size:
                break

            page += 1

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed at page {page}: {e}")
            raise


def paginate_cursor(
    session: requests.Session,
    url: str,
    data_key: str = "items",
    cursor_key: str = "next_cursor",
    cursor_param: str = "cursor",
) -> Iterator[List[Dict[str, Any]]]:
    """Handle cursor-based pagination (Slack, Stripe style)."""
    cursor = None
    page = 0

    while True:
        if config.rate_limit_delay > 0:
            time.sleep(config.rate_limit_delay)

        try:
            params = {cursor_param: cursor} if cursor else {}
            response = session.get(url, params=params, timeout=config.api_timeout)
            response.raise_for_status()
            data = response.json()

            items = data.get(data_key) or []

            if not items:
                break

            page += 1
            logger.info(f"Fetched page {page}: {len(items)} records")
            yield items

            cursor = data.get(cursor_key)
            if not cursor:
                break

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise


def paginate_link(
    session: requests.Session,
    url: str,
    data_key: str = "items",
) -> Iterator[List[Dict[str, Any]]]:
    """Handle Link header pagination (GitHub style)."""
    next_url = url
    page = 0

    while next_url:
        if config.rate_limit_delay > 0:
            time.sleep(config.rate_limit_delay)

        try:
            response = session.get(next_url, timeout=config.api_timeout)
            response.raise_for_status()

            items = response.json()
            if isinstance(items, dict):
                items = items.get(data_key) or []

            if not items:
                break

            page += 1
            logger.info(f"Fetched page {page}: {len(items)} records")
            yield items

            links = response.headers.get("Link", "")
            next_url = None
            for link in links.split(","):
                if 'rel="next"' in link:
                    next_url = link.split(";")[0].strip(" <>")
                    break

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise


def fetch_all(
    url: Optional[str] = None,
    data_key: str = "items",
    pagination: str = "offset",
    session: Optional[requests.Session] = None,
    **kwargs,
) -> Iterator[List[Dict[str, Any]]]:
    """
    Universal fetch function - just point it at an API and go.

    Args:
        url: API endpoint. Defaults to config.api_url
        data_key: JSON key containing array (e.g., "items", "data", "results")
        pagination: Pagination style - "offset", "cursor", or "link"
        session: Optional pre-configured session
        **kwargs: Extra args passed to pagination function

    Yields:
        Batches of records
    """
    url = url or config.api_url
    session = session or create_session()

    logger.info(f"Starting fetch from {url}")
    logger.info(f"Pagination: {pagination}, Data key: {data_key}")
    if config.rate_limit_delay > 0:
        logger.info(f"Rate limit delay: {config.rate_limit_delay}s")

    if pagination == "offset":
        yield from paginate_offset(session, url, data_key, **kwargs)
    elif pagination == "cursor":
        yield from paginate_cursor(session, url, data_key, **kwargs)
    elif pagination == "link":
        yield from paginate_link(session, url, data_key, **kwargs)
    else:
        raise ValueError(f"Unknown pagination type: {pagination}")


# =============================================================================
# DATA CLEANING
# =============================================================================

# Columns that should ALWAYS be treated as strings to preserve leading zeros
ID_COLUMN_HINTS = frozenset({
    'id', 'sku', 'code', 'zip', 'postal', 'phone', 'fax', 'ssn', 'ein',
    'account', 'routing', 'barcode', 'upc', 'ean', 'isbn', 'asin'
})


def normalize_id(text: Optional[str]) -> str:
    """Clean ID for matching: 'OS/123-A' -> 'OS123A'"""
    if not text:
        return ""
    return re.sub(r'[^A-Z0-9]', '', str(text).upper())


def _sanitize_column_name(col: str) -> str:
    """Convert column name to database-safe format."""
    clean = re.sub(r'[^a-z0-9]', '_', str(col).lower().strip())
    clean = re.sub(r'_+', '_', clean).strip('_')
    return clean or 'column'


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and normalize a DataFrame before saving.

    PRODUCTION SAFETY:
    - Forces ID-like columns to string FIRST (preserves leading zeros)
    - Detects column name collisions
    - Uses vectorized operations for speed

    Args:
        df: Raw DataFrame from API

    Returns:
        Cleaned DataFrame
    """
    if df.empty:
        return df

    # STEP 1: Force ID-like columns to STRING before any other processing
    # This prevents Pandas from converting "06510" -> 6510
    for col in df.columns:
        col_lower = str(col).lower()
        if any(hint in col_lower for hint in ID_COLUMN_HINTS):
            df[col] = df[col].astype(str)

    # STEP 2: Sanitize column names
    original_cols = list(df.columns)
    new_cols = [_sanitize_column_name(c) for c in original_cols]

    # Detect collisions: "User Name" and "User-Name" both become "user_name"
    seen = {}
    final_cols = []
    for orig, new in zip(original_cols, new_cols):
        if new in seen:
            logger.warning(
                f"Column collision: '{orig}' and '{seen[new]}' both become '{new}'. "
                f"Renaming to '{new}_2'"
            )
            new = f"{new}_2"
        seen[new] = orig
        final_cols.append(new)

    df.columns = final_cols

    # STEP 3: Convert date columns (after column rename)
    for col in df.columns:
        if any(hint in col for hint in ('date', 'time', 'created', 'updated', '_at')):
            # Skip if already datetime
            if not pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = pd.to_datetime(df[col], errors='coerce')

    # STEP 4: Clean string columns
    for col in df.select_dtypes(include=['object']).columns:
        # Vectorized strip (faster than apply)
        df[col] = df[col].astype(str).str.strip()

    # STEP 5: Handle NaN/None for SQL compatibility
    # pd.where is faster than replace for large DataFrames
    df = df.where(pd.notnull(df), None)

    # STEP 6: Add normalized ID columns
    if 'sku' in df.columns:
        df['sku_normalized'] = df['sku'].apply(normalize_id)
    if 'os_no' in df.columns:
        df['os_normalized'] = df['os_no'].apply(normalize_id)

    # STEP 7: Add metadata
    df['_loaded_at'] = datetime.utcnow()

    return df


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

_engine_cache: Dict[str, Engine] = {}


def get_engine(db_url: Optional[str] = None) -> Engine:
    """Get or create a database engine (cached for reuse)."""
    db_url = db_url or config.db_url

    if db_url not in _engine_cache:
        # Hide credentials in log
        safe_url = db_url.split('@')[-1] if '@' in db_url else db_url
        logger.info(f"Creating database connection: {safe_url}")
        _engine_cache[db_url] = create_engine(db_url, echo=False)

    return _engine_cache[db_url]


def _batched_delete(conn, table: str, primary_key: str, values: List, batch_size: int = 500):
    """
    Delete records in batches to avoid SQL query length limits.

    Some databases have max query lengths (64KB-1MB). If you try to delete
    10,000 IDs in one query, it will fail. This batches the deletes.
    """
    for i in range(0, len(values), batch_size):
        batch = values[i:i + batch_size]
        # Escape single quotes in values (O'Reilly -> O''Reilly)
        safe_values = [str(v).replace("'", "''") for v in batch]
        placeholders = ", ".join([f"'{v}'" for v in safe_values])
        conn.execute(text(f"DELETE FROM {table} WHERE {primary_key} IN ({placeholders})"))


def save_to_db(
    data: Union[pd.DataFrame, List[Dict]],
    table: Optional[str] = None,
    primary_key: Optional[str] = None,
    engine: Optional[Engine] = None,
    if_exists: str = "upsert",
) -> int:
    """
    Save data to database with upsert support.

    Args:
        data: DataFrame or list of dicts to save
        table: Target table name. Defaults to config.db_table
        primary_key: Column for upsert matching. Defaults to config.db_primary_key
        engine: SQLAlchemy engine. Creates one if not provided
        if_exists: "upsert" (update/insert), "replace" (drop & recreate), "append"

    Returns:
        Number of records processed
    """
    if isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        df = data.copy()

    if df.empty:
        logger.warning("No data to save")
        return 0

    table = table or config.db_table
    primary_key = primary_key or config.db_primary_key
    engine = engine or get_engine()

    df = clean_dataframe(df)

    logger.info(f"Saving {len(df)} records to {table}")

    if if_exists == "append":
        df.to_sql(table, engine, if_exists="append", index=False)
        return len(df)

    if if_exists == "replace":
        df.to_sql(table, engine, if_exists="replace", index=False)
        return len(df)

    # Upsert logic
    inspector = inspect(engine)
    table_exists = table in inspector.get_table_names()

    if not table_exists:
        logger.info(f"Creating table: {table}")
        df.to_sql(table, engine, if_exists="replace", index=False)
        return len(df)

    # UUID prevents race conditions if running multiple instances
    temp_table = f"_temp_{table}_{uuid.uuid4().hex[:8]}"
    df.to_sql(temp_table, engine, if_exists="replace", index=False)

    try:
        columns = ", ".join(df.columns)

        with engine.begin() as conn:
            dialect = engine.dialect.name

            if dialect == "sqlite":
                sql = f"""
                    INSERT OR REPLACE INTO {table} ({columns})
                    SELECT {columns} FROM {temp_table}
                """
            elif dialect == "postgresql":
                update_cols = ", ".join([
                    f"{c} = EXCLUDED.{c}" for c in df.columns if c != primary_key
                ])
                sql = f"""
                    INSERT INTO {table} ({columns})
                    SELECT {columns} FROM {temp_table}
                    ON CONFLICT ({primary_key}) DO UPDATE SET {update_cols}
                """
            elif dialect == "mysql":
                update_cols = ", ".join([
                    f"{c} = VALUES({c})" for c in df.columns if c != primary_key
                ])
                sql = f"""
                    INSERT INTO {table} ({columns})
                    SELECT {columns} FROM {temp_table}
                    ON DUPLICATE KEY UPDATE {update_cols}
                """
            else:
                # Fallback: batched delete + insert
                logger.warning(f"Unknown dialect {dialect}, using batched delete+insert")
                pk_values = df[primary_key].tolist()
                _batched_delete(conn, table, primary_key, pk_values, config.delete_batch_size)
                sql = f"INSERT INTO {table} ({columns}) SELECT {columns} FROM {temp_table}"

            conn.execute(text(sql))
            conn.execute(text(f"DROP TABLE {temp_table}"))

    except Exception:
        # Cleanup temp table on error
        try:
            with engine.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {temp_table}"))
        except Exception:
            pass
        raise

    logger.info(f"Saved {len(df)} records")
    return len(df)


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def run_pipeline(
    url: Optional[str] = None,
    table: Optional[str] = None,
    data_key: str = "items",
    pagination: str = "offset",
    transform: Optional[Callable[[pd.DataFrame], pd.DataFrame]] = None,
) -> int:
    """
    Complete ETL pipeline: Fetch -> Transform -> Load.

    Args:
        url: API endpoint
        table: Database table
        data_key: JSON key for data array
        pagination: Pagination style
        transform: Optional custom transform function

    Returns:
        Total records processed
    """
    url = url or config.api_url
    table = table or config.db_table
    total = 0

    logger.info("=" * 60)
    logger.info("STARTING PIPELINE")
    logger.info(f"Source: {url}")
    logger.info(f"Target: {table}")
    logger.info("=" * 60)

    start = datetime.utcnow()

    for batch in fetch_all(url, data_key=data_key, pagination=pagination):
        df = pd.DataFrame(batch)

        if transform:
            df = transform(df)

        count = save_to_db(df, table)
        total += count

    elapsed = (datetime.utcnow() - start).total_seconds()

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info(f"Total records: {total}")
    logger.info(f"Elapsed time: {elapsed:.1f}s")
    if elapsed > 0:
        logger.info(f"Rate: {total/elapsed:.1f} records/sec")
    logger.info("=" * 60)

    return total


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    if not config.api_token:
        logger.warning("No API_TOKEN set. export API_TOKEN='your_token'")

    if config.api_url == "https://api.example.com/items":
        logger.warning("Using default API_URL. export API_URL='https://...'")

    run_pipeline()
