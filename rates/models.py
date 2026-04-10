import uuid

from django.db import models


class RawResponse(models.Model):
    """Stores raw ingestion data for auditability and replay capability."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_url = models.URLField(max_length=500, blank=True, default="")
    payload = models.JSONField(
        help_text="Raw response body from the source, stored for replay/debugging."
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "raw_responses"
        ordering = ["-created_at"]

    def __str__(self):
        return f"RawResponse {self.id} ({self.created_at})"


class Rate(models.Model):
    """Cleaned, normalised interest-rate record."""

    class RateType(models.TextChoices):
        SAVINGS_1YR_FIXED = "savings_1yr_fixed", "Savings 1-Year Fixed"
        SAVINGS_EASY_ACCESS = "savings_easy_access", "Savings Easy Access"
        MORTGAGE_30YR_FIXED = "30yr_fixed_mortgage", "30-Year Fixed Mortgage"
        MORTGAGE_15YR_FIXED = "15yr_fixed_mortgage", "15-Year Fixed Mortgage"
        MORTGAGE_5YR_ARM = "5yr_arm_mortgage", "5-Year ARM Mortgage"

    provider = models.CharField(max_length=100, db_index=True)
    rate_type = models.CharField(max_length=50, choices=RateType.choices, db_index=True)
    rate_value = models.DecimalField(max_digits=7, decimal_places=4)
    effective_date = models.DateField(db_index=True)
    currency = models.CharField(max_length=3, default="USD")
    source_url = models.URLField(max_length=500, blank=True, default="")
    raw_response = models.ForeignKey(
        RawResponse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rates",
    )
    ingested_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "rates"
        ordering = ["-effective_date", "-ingested_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "rate_type", "effective_date"],
                name="uq_provider_type_date",
            ),
        ]
        indexes = [
            models.Index(
                fields=["provider", "rate_type", "-effective_date"],
                name="idx_provider_type_date_desc",
            ),
            models.Index(
                fields=["rate_type", "-effective_date"],
                name="idx_type_date_desc",
            ),
            models.Index(
                fields=["-ingested_at"],
                name="idx_ingested_at_desc",
            ),
        ]

    def __str__(self):
        return f"{self.provider} | {self.rate_type} | {self.rate_value}% ({self.effective_date})"
