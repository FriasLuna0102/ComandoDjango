from django.db import models
import uuid
from center.models import Center
from backend_django.users.models import User


class InventorySnapshot(models.Model):
    """Model to represent a snapshot of inventory at a specific point in time"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    center = models.ForeignKey(Center, on_delete=models.CASCADE, related_name='inventory_snapshots')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='inventory_snapshots')

    source_detections = models.ManyToManyField(
        'deteccion_app.Deteccion',
        related_name='inventory_snapshots',
        blank=True
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Instantánea de Inventario"
        verbose_name_plural = "Instantáneas de Inventario"

    def __str__(self):
        return f"{self.name} - {self.created_at.strftime('%d/%m/%Y %H:%M')}"


class ProductCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    ideal_count = models.PositiveIntegerField(default=0, help_text="Recommended inventory level")
    emergency_priority = models.PositiveSmallIntegerField(
        default=3,
        choices=[(1, 'Muy Baja'), (2, 'Baja'), (3, 'Media'), (4, 'Alta'), (5, 'Muy Alta')],
        help_text="Priority level during emergency situations"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Categoría de Producto"
        verbose_name_plural = "Categorías de Productos"

    def __str__(self):
        return self.name


class InventoryItem(models.Model):
    """Model to represent inventory items in a snapshot"""
    snapshot = models.ForeignKey(InventorySnapshot, on_delete=models.CASCADE, related_name='items')
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE, related_name='inventory_items')
    count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('snapshot', 'category')

    def __str__(self):
        return f"{self.category.name}: {self.count} (in {self.snapshot.name})"


class InventoryReport(models.Model):
    """Model for inventory replenishment reports"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    center = models.ForeignKey(Center, on_delete=models.CASCADE, related_name='inventory_reports')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='inventory_reports')
    is_emergency = models.BooleanField(default=False)

    source_snapshot = models.ForeignKey(
        InventorySnapshot,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generated_reports'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Informe de Inventario"
        verbose_name_plural = "Informes de Inventario"

    def __str__(self):
        emergency_tag = "[EMERGENCIA] " if self.is_emergency else ""
        return f"{emergency_tag}{self.name} - {self.created_at.strftime('%d/%m/%Y')}"


class ProductRecommendation(models.Model):
    """Model for product replenishment recommendations in reports"""
    report = models.ForeignKey(InventoryReport, on_delete=models.CASCADE, related_name='recommendations')
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE, related_name='recommendations')
    current_count = models.PositiveIntegerField(default=0)
    ideal_count = models.PositiveIntegerField(default=0)
    priority = models.PositiveSmallIntegerField(
        choices=[(1, 'Muy Baja'), (2, 'Baja'), (3, 'Media'), (4, 'Alta'), (5, 'Muy Alta')],
    )
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ('report', 'category')

    def __str__(self):
        return f"{self.category.name} (Priority: {self.priority})"

    @property
    def replenish_amount(self):
        """Calculate how many items to replenish"""
        return max(0, self.ideal_count - self.current_count)

    @property
    def percentage_missing(self):
        """Calculate percentage missing from ideal count"""
        if self.ideal_count == 0:
            return 0
        return (self.replenish_amount / self.ideal_count) * 100


class AnalyticsReport(models.Model):
    """Model for consumption analytics reports"""
    PERIOD_CHOICES = [
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    center = models.ForeignKey(Center, on_delete=models.CASCADE, related_name='analytics_reports')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='analytics_reports')

    period_type = models.CharField(max_length=20, choices=PERIOD_CHOICES, default='weekly')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    categories_list = models.TextField(blank=True, help_text="Comma-separated list of category names")

    start_snapshot = models.ForeignKey(
        InventorySnapshot,
        on_delete=models.SET_NULL,
        null=True,
        related_name='analytics_start'
    )
    end_snapshot = models.ForeignKey(
        InventorySnapshot,
        on_delete=models.SET_NULL,
        null=True,
        related_name='analytics_end'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Reporte Analítico"
        verbose_name_plural = "Reportes Analíticos"

    def is_increase(self, category):
        """Check if a category's movement represents an increase rather than consumption"""
        try:
            data_point = ConsumptionDataPoint.objects.filter(
                report=self,
                category=category
            ).first()

            if data_point and data_point.note:
                return 'aumento' in data_point.note.lower()
            return False
        except:
            return False

    def __str__(self):
        return f"{self.name} ({self.get_period_type_display()}) - {self.created_at.strftime('%d/%m/%Y')}"

    def get_analyzed_categories(self):
        """Get all categories included in this report"""
        return ProductCategory.objects.filter(consumption_totals__report=self).distinct()

    def get_most_consumed_category(self):
        """Get the category with highest consumption"""
        return self.consumption_totals.order_by('-count').first()

    def get_least_consumed_category(self):
        """Get the category with lowest consumption"""
        return self.consumption_totals.order_by('count').first()

    def get_days_count(self):
        """Calculate number of days in the analysis period"""
        return (self.end_date - self.start_date).days + 1

    def get_category_names(self):
        """Get all category names from the categories_list field"""
        if self.categories_list:
            return [name.strip() for name in self.categories_list.split(',')]
        return []


class CategoryConsumptionTotal(models.Model):
    """Model for total consumption of a category in an analytics report"""
    report = models.ForeignKey(AnalyticsReport, on_delete=models.CASCADE, related_name='consumption_totals')
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE, related_name='consumption_totals')
    count = models.PositiveIntegerField(default=0, help_text="Total consumption for this category")

    class Meta:
        unique_together = ('report', 'category')

    def __str__(self):
        return f"{self.category.name}: {self.count} units"


class ConsumptionDataPoint(models.Model):
    """Model for detailed consumption data points in an analytics report"""
    report = models.ForeignKey(AnalyticsReport, on_delete=models.CASCADE, related_name='data_points')
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE, related_name='consumption_data')
    date = models.DateTimeField()
    count = models.PositiveIntegerField(default=0, help_text="Consumption on this date")
    # Cambiar el campo para permitir NULL
    note = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['date']
        indexes = [
            models.Index(fields=['report', 'category', 'date'])
        ]

    def __str__(self):
        return f"{self.category.name}: {self.count} on {self.date.strftime('%d/%m/%Y')}"
