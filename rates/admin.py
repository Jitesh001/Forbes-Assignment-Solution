from django.contrib import admin

from .models import Rate, RawResponse


@admin.register(Rate)
class RateAdmin(admin.ModelAdmin):
    list_display = ("provider", "rate_type", "rate_value", "effective_date", "ingested_at")
    list_filter = ("rate_type", "provider", "effective_date")
    search_fields = ("provider",)
    date_hierarchy = "effective_date"


@admin.register(RawResponse)
class RawResponseAdmin(admin.ModelAdmin):
    list_display = ("id", "source_url", "created_at")
    readonly_fields = ("payload",)
