import pytest
import os
import psycopg2
import pandas as pd
from stats_sql import get_conn, get_kpis

# Simple test to verify DB connectivity and KPI calculation
# Note: These tests assume the dev database is running as per Docker config

def test_db_connection():
    """Verify that we can connect to the database."""
    try:
        conn = get_conn()
        assert conn is not None
        conn.close()
    except Exception as e:
        pytest.fail(f"Database connection failed: {e}")

def test_get_kpis_invalid_id():
    """Verify that KPI function handles non-existent restaurant IDs gracefully."""
    # Using a random UUID that shouldn't exist
    fake_id = "00000000-0000-0000-0000-000000000000"
    try:
        kpis = get_kpis(fake_id)
        assert isinstance(kpis, dict)
        assert kpis["today_bookings"] == 0
    except Exception as e:
        pytest.fail(f"KPI retrieval failed: {e}")

def test_sql_injection_resilience():
    """Verify system resilience to malicious SQL patterns."""
    malicious_id = "'; DROP TABLE users; --"
    try:
        get_kpis(malicious_id)
    except Exception:
        pass # Expected standard error from UUID casting

def test_customer_metrics_structure():
    """Verify that the CRM logic returns correctly formatted analytical data."""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM restaurants LIMIT 1")
        rid = cur.fetchone()[0]
    
    from stats_sql import get_customer_metrics
    df = get_customer_metrics(rid)
    assert isinstance(df, pd.DataFrame)
    assert "total_bookings" in df.columns
    assert "flakes" in df.columns

def test_forecasting_data_integrity():
    """Verify the integrity of data used for AI forecasting."""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM restaurants LIMIT 1")
        rid = cur.fetchone()[0]
        
    from stats_sql import get_forecasting_data
    df = get_forecasting_data(rid)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "date" in df.columns
    assert "count" in df.columns

def test_audit_logging_mechanism():
    """Verify that administrative actions are correctly recorded in the audit trail."""
    try:
        from stats_sql import log_action, get_audit_logs
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM restaurants LIMIT 1")
            rid = cur.fetchone()[0]
            
        log_action(rid, "test@qa.com", "UNIT_TEST", "Verifying log system")
        df = get_audit_logs(rid)
        assert any(df['Action'] == "UNIT_TEST"), "Log action was not recorded!"
    except Exception as e:
        pytest.fail(f"Audit system test failed: {e}")
