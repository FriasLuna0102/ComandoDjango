from django.contrib import admin
from .models import (
    InventorySnapshot, ProductCategory, InventoryItem, InventoryReport,
    ProductRecommendation, AnalyticsReport, CategoryConsumptionTotal,
    ConsumptionDataPoint
)

class InventoryItemInline(admin.TabularInline):
    model = InventoryItem
    extra = 1

@admin.register(InventorySnapshot)
class InventorySnapshotAdmin(admin.ModelAdmin):
    list_display = ('name', 'center', 'created_at', 'created_by')
    list_filter = ('center', 'created_at')
    search_fields = ('name', 'description')
    date_hierarchy = 'created_at'
    inlines = [InventoryItemInline]

@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'ideal_count', 'emergency_priority', 'created_at')
    list_filter = ('emergency_priority', 'created_at')
    search_fields = ('name', 'description')

class ProductRecommendationInline(admin.TabularInline):
    model = ProductRecommendation
    extra = 1
    readonly_fields = ('replenish_amount', 'percentage_missing')

@admin.register(InventoryReport)
class InventoryReportAdmin(admin.ModelAdmin):
    list_display = ('name', 'center', 'created_at', 'is_emergency', 'created_by')
    list_filter = ('center', 'created_at', 'is_emergency')
    search_fields = ('name',)
    date_hierarchy = 'created_at'
    inlines = [ProductRecommendationInline]

class CategoryConsumptionTotalInline(admin.TabularInline):
    model = CategoryConsumptionTotal
    extra = 1

class ConsumptionDataPointInline(admin.TabularInline):
    model = ConsumptionDataPoint
    extra = 1

@admin.register(AnalyticsReport)
class AnalyticsReportAdmin(admin.ModelAdmin):
    list_display = ('name', 'center', 'period_type', 'start_date', 'end_date', 'created_at')
    list_filter = ('center', 'period_type', 'created_at')
    search_fields = ('name',)
    date_hierarchy = 'created_at'
    inlines = [CategoryConsumptionTotalInline, ConsumptionDataPointInline]
