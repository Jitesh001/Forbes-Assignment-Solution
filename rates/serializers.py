from decimal import Decimal

from rest_framework import serializers

from .models import Rate


class RateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rate
        fields = [
            "id",
            "provider",
            "rate_type",
            "rate_value",
            "effective_date",
            "currency",
            "source_url",
            "ingested_at",
        ]
        read_only_fields = fields


class RateHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Rate
        fields = [
            "provider",
            "rate_type",
            "rate_value",
            "effective_date",
            "currency",
            "ingested_at",
        ]
        read_only_fields = fields


class IngestSerializer(serializers.Serializer):
    provider = serializers.CharField(max_length=100)
    rate_type = serializers.ChoiceField(choices=Rate.RateType.choices)
    rate_value = serializers.DecimalField(max_digits=7, decimal_places=4, min_value=Decimal("0"))
    effective_date = serializers.DateField()
    currency = serializers.CharField(max_length=10, default="USD")
    source_url = serializers.URLField(max_length=500, required=False, default="")

    def validate_rate_value(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Rate value must be between 0 and 100.")
        return value
