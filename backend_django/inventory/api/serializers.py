import logging
from rest_framework import serializers
from ..models import (
    InventorySnapshot, ProductCategory, InventoryItem, InventoryReport,
    ProductRecommendation, AnalyticsReport, CategoryConsumptionTotal,
    ConsumptionDataPoint
)

# Configurar logging
logger = logging.getLogger(__name__)


class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ['id', 'name', 'description', 'ideal_count', 'emergency_priority', 'created_at']
        read_only_fields = ['created_at']


class InventoryItemSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryItem
        fields = ['id', 'snapshot', 'category', 'category_name', 'count']

    def get_category_name(self, obj):
        return obj.category.name


class InventorySnapshotSerializer(serializers.ModelSerializer):
    items = InventoryItemSerializer(many=True, read_only=True)
    product_counts = serializers.JSONField(required=False)
    source_detections = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        write_only=True
    )

    class Meta:
        model = InventorySnapshot
        fields = ['id', 'name', 'description', 'center', 'created_at', 'created_by',
                  'source_detections', 'items', 'product_counts']
        read_only_fields = ['created_at', 'created_by']

    def get_product_counts(self, obj):
        """Returns a dictionary of category_name: count"""
        counts = {}
        for item in obj.items.all():
            counts[item.category.name] = item.count
        return counts

    def create(self, validated_data):
        # Registro para debug
        logger.info(f"Creating snapshot with data: {validated_data}")

        items_data = validated_data.pop('items', [])

        # Extraer product_counts si existe
        product_counts = validated_data.pop('product_counts', {})
        logger.info(f"Product counts: {product_counts}")

        # Extraer source_detections para manejarlos después
        source_detections_ids = validated_data.pop('source_detections', [])
        logger.info(f"Source detections IDs: {source_detections_ids}")

        # Crear el snapshot sin source_detections primero
        snapshot = InventorySnapshot.objects.create(**validated_data)
        logger.info(f"Created snapshot with ID: {snapshot.id}")

        # Ahora manejamos la relación many-to-many correctamente
        if source_detections_ids:
            # Importar aquí para evitar importaciones circulares
            from deteccion_app.models import Deteccion

            # Obtener las detecciones por sus IDs
            detections = Deteccion.objects.filter(id__in=source_detections_ids)
            logger.info(f"Found {detections.count()} detections")

            # Usar set() para asignar las detecciones al snapshot
            snapshot.source_detections.set(detections)

            # Si tenemos detecciones pero no conteos de productos explícitos,
            # intentamos obtener los conteos desde las detecciones
            if not product_counts:
                logger.info("No product counts provided, trying to get from detections")
                product_counts = self._get_product_counts_from_detections(detections)
                logger.info(f"Extracted product counts from detections: {product_counts}")

        # Procesar los conteos de productos
        if product_counts:
            for category_name, count in product_counts.items():
                logger.info(f"Creating item for category {category_name} with count {count}")
                try:
                    category = ProductCategory.objects.get(name=category_name)
                    logger.info(f"Found existing category: {category.name}")
                except ProductCategory.DoesNotExist:
                    # Crear categoría si no existe
                    logger.info(f"Creating new category: {category_name}")
                    category = ProductCategory.objects.create(name=category_name)

                InventoryItem.objects.create(
                    snapshot=snapshot,
                    category=category,
                    count=count
                )

        # Procesar cualquier dato explícito de items
        for item_data in items_data:
            logger.info(f"Creating item from explicit data: {item_data}")
            InventoryItem.objects.create(snapshot=snapshot, **item_data)

        return snapshot

    def _get_product_counts_from_detections(self, detections):
        """
        Extrae conteos de productos desde las detecciones
        """
        product_counts = {}

        for detection in detections:
            # Intentar obtener los resultados de la detección
            try:
                results = detection.get_resultados()

                # Diferentes formatos posibles de resultados
                if 'detections' in results:
                    # Formato usado por las APIs de detección de objetos
                    for det in results.get('detections', []):
                        class_name = det.get('class', '')
                        confidence = det.get('confidence', 0)

                        # Solo considerar detecciones con confianza suficiente
                        if confidence >= 0.5 and class_name:
                            product_counts[class_name] = product_counts.get(class_name, 0) + 1

                # Otro formato posible
                elif 'categories' in results:
                    for category, count in results.get('categories', {}).items():
                        if category:
                            product_counts[category] = product_counts.get(category, 0) + count

                # Algunos sistemas usan un formato diferente
                elif isinstance(results, dict):
                    for category, data in results.items():
                        if isinstance(data, dict) and 'count' in data:
                            product_counts[category] = product_counts.get(category, 0) + data['count']
                        elif isinstance(data, int):
                            product_counts[category] = product_counts.get(category, 0) + data

            except Exception as e:
                logger.error(f"Error extracting product counts from detection {detection.id}: {str(e)}")

        return product_counts


class ProductRecommendationSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()
    replenish_amount = serializers.SerializerMethodField()
    percentage_missing = serializers.SerializerMethodField()

    class Meta:
        model = ProductRecommendation
        fields = ['id', 'report', 'category', 'category_name', 'current_count',
                  'ideal_count', 'priority', 'note', 'replenish_amount', 'percentage_missing']

    def get_category_name(self, obj):
        return obj.category.name

    def get_replenish_amount(self, obj):
        return obj.replenish_amount

    def get_percentage_missing(self, obj):
        return obj.percentage_missing


class InventoryReportSerializer(serializers.ModelSerializer):
    recommendations = ProductRecommendationSerializer(many=True, read_only=True)
    priority_products = serializers.SerializerMethodField()

    class Meta:
        model = InventoryReport
        fields = ['id', 'name', 'center', 'created_at', 'created_by', 'is_emergency',
                  'source_snapshot', 'recommendations', 'priority_products']
        read_only_fields = ['created_at', 'created_by']

    def get_priority_products(self, obj):
        """Returns recommendations with priority > 3"""
        serializer = ProductRecommendationSerializer(
            obj.recommendations.filter(priority__gt=3),
            many=True
        )
        return serializer.data

    def create(self, validated_data):
        recommendations_data = validated_data.pop('recommendations', [])

        # Set the current user as creator
        user = self.context['request'].user
        validated_data['created_by'] = user

        report = InventoryReport.objects.create(**validated_data)

        # Add recommendations
        for rec_data in recommendations_data:
            ProductRecommendation.objects.create(report=report, **rec_data)

        return report


class ConsumptionDataPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsumptionDataPoint
        fields = ['id', 'report', 'category', 'date', 'count', 'note']


class CategoryConsumptionTotalSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()

    class Meta:
        model = CategoryConsumptionTotal
        fields = ['id', 'report', 'category', 'category_name', 'count']

    def get_category_name(self, obj):
        return obj.category.name


class AnalyticsReportSerializer(serializers.ModelSerializer):
    consumption_totals = CategoryConsumptionTotalSerializer(many=True, read_only=True)
    data_points = ConsumptionDataPointSerializer(many=True, read_only=True)
    categories = serializers.SerializerMethodField()
    date_range = serializers.SerializerMethodField()
    most_consumed = serializers.SerializerMethodField()
    least_consumed = serializers.SerializerMethodField()

    class Meta:
        model = AnalyticsReport
        fields = ['id', 'name', 'center', 'created_at', 'created_by', 'period_type',
                  'start_date', 'end_date', 'start_snapshot', 'end_snapshot',
                  'consumption_totals', 'data_points', 'categories', 'date_range',
                  'most_consumed', 'least_consumed']
        read_only_fields = ['created_at', 'created_by']

    def get_categories(self, obj):
        """Returns list of category names included in this report"""
        # First try to get from categories_list field (new approach)
        if hasattr(obj, 'categories_list') and obj.categories_list:
            return obj.get_category_names()

        # Fallback to the old approach
        return [cat.name for cat in obj.get_analyzed_categories()]

    def get_date_range(self, obj):
        """Returns formatted date range"""
        return {
            'startDate': obj.start_date.isoformat(),
            'endDate': obj.end_date.isoformat(),
            'formatted': f"{obj.start_date.strftime('%d/%m/%Y')} - {obj.end_date.strftime('%d/%m/%Y')}"
        }

    def get_most_consumed(self, obj):
        """Returns category with the highest movement (can be consumption or increase)"""
        most_movement = obj.get_most_consumed_category()
        if most_movement:
            return {
                'category': most_movement.category.name,
                'count': most_movement.count,
                'is_increase': obj.is_increase(most_movement.category)
            }
        return {'category': 'N/A', 'count': 0, 'is_increase': False}

    def get_least_consumed(self, obj):
        least_consumed = obj.get_least_consumed_category()
        if least_consumed:
            return {
                'category': least_consumed.category.name,
                'count': least_consumed.count
            }
        return {'category': 'N/A', 'count': 0}

    def create(self, validated_data):
        consumption_totals = validated_data.pop('consumption_totals', [])
        data_points = validated_data.pop('data_points', [])

        # Set the current user as creator
        user = self.context['request'].user
        validated_data['created_by'] = user

        report = AnalyticsReport.objects.create(**validated_data)

        # Add consumption totals
        for total_data in consumption_totals:
            CategoryConsumptionTotal.objects.create(report=report, **total_data)

        # Add data points
        for point_data in data_points:
            ConsumptionDataPoint.objects.create(report=report, **point_data)

        return report

# Serializers for special operations

class GenerateInventoryReportSerializer(serializers.Serializer):
    snapshot_id = serializers.UUIDField(required=True)
    is_emergency = serializers.BooleanField(required=False, default=False)
    custom_ideal_counts = serializers.DictField(
        child=serializers.IntegerField(),
        required=False
    )


class GenerateAnalyticsReportSerializer(serializers.Serializer):
    start_snapshot_id = serializers.UUIDField(required=True)
    end_snapshot_id = serializers.UUIDField(required=True)
    period_type = serializers.ChoiceField(
        choices=AnalyticsReport.PERIOD_CHOICES,
        default='weekly'
    )
    report_name = serializers.CharField(required=False, allow_blank=True)
    selected_categories = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
