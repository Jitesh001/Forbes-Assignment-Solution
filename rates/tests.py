"""
Tests for the rates application.
Covers: ingestion service, management command, API endpoints, authentication.
"""

import json
import uuid
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from rates.models import Rate, RawResponse
from rates.services import (
    ingest_from_parquet,
    ingest_single_record,
    normalize_currency,
    normalize_provider,
    validate_rate_value,
)


# ---- Unit tests: normalization helpers ----


class TestNormalization(TestCase):
    def test_normalize_provider_lowercase(self):
        assert normalize_provider("hsbc") == "HSBC"

    def test_normalize_provider_mixed_case(self):
        assert normalize_provider("Hsbc") == "HSBC"

    def test_normalize_provider_uppercase(self):
        assert normalize_provider("HSBC") == "HSBC"

    def test_normalize_provider_with_spaces(self):
        assert normalize_provider("  chase  ") == "Chase"

    def test_normalize_provider_unknown_defaults_to_title(self):
        assert normalize_provider("new bank") == "New Bank"

    def test_normalize_currency_lowercase(self):
        assert normalize_currency("usd") == "USD"

    def test_normalize_currency_mixed_label(self):
        assert normalize_currency("US Dollar") == "USD"

    def test_normalize_currency_uppercase(self):
        assert normalize_currency("USD") == "USD"

    def test_validate_rate_value_valid(self):
        assert validate_rate_value(3.5) == Decimal("3.5000")

    def test_validate_rate_value_null(self):
        assert validate_rate_value(float("nan")) is None

    def test_validate_rate_value_negative(self):
        assert validate_rate_value(-1.5) is None

    def test_validate_rate_value_over_100(self):
        assert validate_rate_value(101.0) is None


# ---- Integration test: seed_data management command with mocked HTTP ----


class TestSeedDataCommand(TestCase):
    """
    Tests the ingestion pipeline with a small fixture DataFrame,
    mocking the parquet file read to simulate an HTTP-fetched dataset.
    """

    def _build_fixture_df(self):
        """Build a small DataFrame matching the parquet schema."""
        rows = [
            {
                "provider": "hsbc",
                "rate_type": "30yr_fixed_mortgage",
                "rate_value": 6.75,
                "effective_date": date(2025, 3, 1),
                "ingestion_ts": pd.Timestamp("2025-03-01 10:00:00"),
                "source_url": "https://www.hsbc.com/rates/30yr_fixed_mortgage",
                "raw_response_id": str(uuid.uuid4()),
                "currency": "usd",
            },
            {
                "provider": "Chase",
                "rate_type": "savings_1yr_fixed",
                "rate_value": 4.25,
                "effective_date": date(2025, 3, 1),
                "ingestion_ts": pd.Timestamp("2025-03-01 10:00:00"),
                "source_url": "https://www.chase.com/rates/savings_1yr_fixed",
                "raw_response_id": str(uuid.uuid4()),
                "currency": "USD",
            },
            # Duplicate of HSBC with later timestamp — should win
            {
                "provider": "Hsbc",
                "rate_type": "30yr_fixed_mortgage",
                "rate_value": 6.80,
                "effective_date": date(2025, 3, 1),
                "ingestion_ts": pd.Timestamp("2025-03-01 12:00:00"),
                "source_url": "https://www.hsbc.com/rates/30yr_fixed_mortgage",
                "raw_response_id": str(uuid.uuid4()),
                "currency": "US Dollar",
            },
            # Invalid: null rate
            {
                "provider": "Chase",
                "rate_type": "savings_1yr_fixed",
                "rate_value": None,
                "effective_date": date(2025, 3, 2),
                "ingestion_ts": pd.Timestamp("2025-03-02 10:00:00"),
                "source_url": "https://www.chase.com/rates/savings_1yr_fixed",
                "raw_response_id": str(uuid.uuid4()),
                "currency": "USD",
            },
            # Invalid: negative rate
            {
                "provider": "Chase",
                "rate_type": "savings_easy_access",
                "rate_value": -1.5,
                "effective_date": date(2025, 3, 3),
                "ingestion_ts": pd.Timestamp("2025-03-03 10:00:00"),
                "source_url": "https://www.chase.com/rates/savings_easy_access",
                "raw_response_id": str(uuid.uuid4()),
                "currency": "USD",
            },
        ]
        return pd.DataFrame(rows)

    @patch("rates.services.pd.read_parquet")
    def test_ingestion_with_fixture(self, mock_read):
        """Mock the HTTP/file call and assert parsed output matches known fixture."""
        mock_read.return_value = self._build_fixture_df()

        stats = ingest_from_parquet("/fake/path.parquet")

        # 5 total, 2 invalid (null + negative), 1 duplicate
        assert stats["total"] == 5
        assert stats["skipped_invalid"] == 2
        assert stats["skipped_duplicate"] == 1
        assert stats["inserted"] == 2  # HSBC 30yr + Chase savings_1yr

        # HSBC should have the later rate (6.80, from the duplicate with later ts)
        hsbc_rate = Rate.objects.get(provider="HSBC", rate_type="30yr_fixed_mortgage")
        assert hsbc_rate.rate_value == Decimal("6.8000")
        assert hsbc_rate.currency == "USD"

        # Chase should exist
        chase_rate = Rate.objects.get(provider="Chase", rate_type="savings_1yr_fixed")
        assert chase_rate.rate_value == Decimal("4.2500")

        # RawResponses should be created
        assert RawResponse.objects.count() == 2

    @patch("rates.services.pd.read_parquet")
    def test_idempotent_rerun(self, mock_read):
        """Running ingestion twice with the same data should not create duplicates."""
        mock_read.return_value = self._build_fixture_df()

        ingest_from_parquet("/fake/path.parquet")
        ingest_from_parquet("/fake/path.parquet")

        # Should still be 2 rates, not 4
        assert Rate.objects.count() == 2

    @patch("rates.services.pd.read_parquet")
    def test_management_command(self, mock_read):
        """Test the management command runs without errors."""
        mock_read.return_value = self._build_fixture_df()
        call_command("seed_data", "--file", "/fake/path.parquet")
        assert Rate.objects.count() == 2


# ---- API integration tests ----


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}})
class TestLatestRatesAPI(TestCase):
    def setUp(self):
        self.client = APIClient()
        self._create_sample_data()

    def _create_sample_data(self):
        today = date.today()
        yesterday = today - timedelta(days=1)

        # Chase: two dates, latest should win
        Rate.objects.create(
            provider="Chase",
            rate_type="30yr_fixed_mortgage",
            rate_value=Decimal("6.50"),
            effective_date=yesterday,
        )
        Rate.objects.create(
            provider="Chase",
            rate_type="30yr_fixed_mortgage",
            rate_value=Decimal("6.75"),
            effective_date=today,
        )
        Rate.objects.create(
            provider="HSBC",
            rate_type="savings_1yr_fixed",
            rate_value=Decimal("4.25"),
            effective_date=today,
        )

    def test_latest_rates_returns_200(self):
        response = self.client.get("/api/rates/latest/")
        assert response.status_code == status.HTTP_200_OK

    def test_latest_rates_returns_most_recent_per_provider(self):
        response = self.client.get("/api/rates/latest/")
        data = response.json()
        # Should get latest for Chase (6.75) and HSBC (4.25)
        assert len(data) == 2
        providers = {r["provider"] for r in data}
        assert providers == {"Chase", "HSBC"}

        chase = next(r for r in data if r["provider"] == "Chase")
        assert chase["rate_value"] == "6.7500"

    def test_latest_rates_type_filter(self):
        response = self.client.get("/api/rates/latest/?type=savings_1yr_fixed")
        data = response.json()
        assert len(data) == 1
        assert data[0]["provider"] == "HSBC"

    def test_latest_rates_no_auth_required(self):
        """GET endpoints must work without auth."""
        response = self.client.get("/api/rates/latest/")
        assert response.status_code == status.HTTP_200_OK


class TestRateHistoryAPI(TestCase):
    def setUp(self):
        self.client = APIClient()
        base_date = date(2025, 3, 1)
        for i in range(10):
            Rate.objects.create(
                provider="Chase",
                rate_type="30yr_fixed_mortgage",
                rate_value=Decimal("6.50") + Decimal(str(i * 0.01)),
                effective_date=base_date + timedelta(days=i),
            )

    def test_history_requires_params(self):
        response = self.client.get("/api/rates/history/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_history_returns_paginated(self):
        response = self.client.get(
            "/api/rates/history/?provider=Chase&type=30yr_fixed_mortgage"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "results" in data
        assert "count" in data
        assert data["count"] == 10

    def test_history_date_filter(self):
        response = self.client.get(
            "/api/rates/history/?provider=Chase&type=30yr_fixed_mortgage"
            "&from=2025-03-03&to=2025-03-07"
        )
        data = response.json()
        assert data["count"] == 5

    def test_history_no_auth_required(self):
        response = self.client.get(
            "/api/rates/history/?provider=Chase&type=30yr_fixed_mortgage"
        )
        assert response.status_code == status.HTTP_200_OK


@override_settings(INGEST_BEARER_TOKEN="test-token-123")
class TestIngestAPI(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.valid_payload = {
            "provider": "Chase",
            "rate_type": "30yr_fixed_mortgage",
            "rate_value": "6.75",
            "effective_date": "2025-03-15",
            "currency": "USD",
            "source_url": "https://www.chase.com/rates",
        }

    def test_ingest_requires_auth(self):
        response = self.client.post(
            "/api/rates/ingest/",
            data=self.valid_payload,
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_ingest_rejects_bad_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer wrong-token")
        response = self.client.post(
            "/api/rates/ingest/",
            data=self.valid_payload,
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_ingest_accepts_valid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer test-token-123")
        response = self.client.post(
            "/api/rates/ingest/",
            data=self.valid_payload,
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Rate.objects.count() == 1
        assert RawResponse.objects.count() == 1

    def test_ingest_validates_payload(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer test-token-123")
        bad_payload = {**self.valid_payload, "rate_value": "-5.0"}
        response = self.client.post(
            "/api/rates/ingest/",
            data=bad_payload,
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "errors" in response.json()

    def test_ingest_rejects_invalid_rate_type(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer test-token-123")
        bad_payload = {**self.valid_payload, "rate_type": "invalid_type"}
        response = self.client.post(
            "/api/rates/ingest/",
            data=bad_payload,
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_ingest_creates_raw_response(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer test-token-123")
        self.client.post(
            "/api/rates/ingest/",
            data=self.valid_payload,
            format="json",
        )
        raw = RawResponse.objects.first()
        assert raw is not None
        assert raw.payload["provider"] == "Chase"

    def test_ingest_idempotent_same_key(self):
        """Ingesting the same provider+type+date should update, not duplicate."""
        self.client.credentials(HTTP_AUTHORIZATION="Bearer test-token-123")

        self.client.post("/api/rates/ingest/", data=self.valid_payload, format="json")

        updated_payload = {**self.valid_payload, "rate_value": "7.00"}
        self.client.post("/api/rates/ingest/", data=updated_payload, format="json")

        assert Rate.objects.count() == 1
        rate = Rate.objects.first()
        assert rate.rate_value == Decimal("7.0000")
