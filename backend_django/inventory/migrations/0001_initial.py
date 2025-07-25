# Generated by Django 5.0.11 on 2025-05-11 06:59

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('center', '0002_alter_center_options'),
        ('deteccion_app', '0005_deteccion_confirmed'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('ideal_count', models.PositiveIntegerField(default=0, help_text='Recommended inventory level')),
                ('emergency_priority', models.PositiveSmallIntegerField(choices=[(1, 'Muy Baja'), (2, 'Baja'), (3, 'Media'), (4, 'Alta'), (5, 'Muy Alta')], default=3, help_text='Priority level during emergency situations')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Categoría de Producto',
                'verbose_name_plural': 'Categorías de Productos',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='InventorySnapshot',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('center', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inventory_snapshots', to='center.center')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inventory_snapshots', to=settings.AUTH_USER_MODEL)),
                ('source_detections', models.ManyToManyField(blank=True, related_name='inventory_snapshots', to='deteccion_app.deteccion')),
            ],
            options={
                'verbose_name': 'Instantánea de Inventario',
                'verbose_name_plural': 'Instantáneas de Inventario',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='InventoryReport',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_emergency', models.BooleanField(default=False)),
                ('center', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inventory_reports', to='center.center')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inventory_reports', to=settings.AUTH_USER_MODEL)),
                ('source_snapshot', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='generated_reports', to='inventory.inventorysnapshot')),
            ],
            options={
                'verbose_name': 'Informe de Inventario',
                'verbose_name_plural': 'Informes de Inventario',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AnalyticsReport',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('period_type', models.CharField(choices=[('weekly', 'Weekly'), ('monthly', 'Monthly')], default='weekly', max_length=20)),
                ('start_date', models.DateTimeField()),
                ('end_date', models.DateTimeField()),
                ('center', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='analytics_reports', to='center.center')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='analytics_reports', to=settings.AUTH_USER_MODEL)),
                ('end_snapshot', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='analytics_end', to='inventory.inventorysnapshot')),
                ('start_snapshot', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='analytics_start', to='inventory.inventorysnapshot')),
            ],
            options={
                'verbose_name': 'Reporte Analítico',
                'verbose_name_plural': 'Reportes Analíticos',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='InventoryItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('count', models.PositiveIntegerField(default=0)),
                ('snapshot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='inventory.inventorysnapshot')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inventory_items', to='inventory.productcategory')),
            ],
            options={
                'unique_together': {('snapshot', 'category')},
            },
        ),
        migrations.CreateModel(
            name='ConsumptionDataPoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateTimeField()),
                ('count', models.PositiveIntegerField(default=0, help_text='Consumption on this date')),
                ('note', models.CharField(blank=True, max_length=255)),
                ('report', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='data_points', to='inventory.analyticsreport')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='consumption_data', to='inventory.productcategory')),
            ],
            options={
                'ordering': ['date'],
                'indexes': [models.Index(fields=['report', 'category', 'date'], name='inventory_c_report__4d9285_idx')],
            },
        ),
        migrations.CreateModel(
            name='CategoryConsumptionTotal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('count', models.PositiveIntegerField(default=0, help_text='Total consumption for this category')),
                ('report', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='consumption_totals', to='inventory.analyticsreport')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='consumption_totals', to='inventory.productcategory')),
            ],
            options={
                'unique_together': {('report', 'category')},
            },
        ),
        migrations.CreateModel(
            name='ProductRecommendation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('current_count', models.PositiveIntegerField(default=0)),
                ('ideal_count', models.PositiveIntegerField(default=0)),
                ('priority', models.PositiveSmallIntegerField(choices=[(1, 'Muy Baja'), (2, 'Baja'), (3, 'Media'), (4, 'Alta'), (5, 'Muy Alta')])),
                ('note', models.CharField(blank=True, max_length=255)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recommendations', to='inventory.productcategory')),
                ('report', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recommendations', to='inventory.inventoryreport')),
            ],
            options={
                'unique_together': {('report', 'category')},
            },
        ),
    ]
