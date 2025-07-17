from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
import datetime

from ..models import (
    InventorySnapshot, ProductCategory, InventoryItem, InventoryReport,
    ProductRecommendation, AnalyticsReport, CategoryConsumptionTotal,
    ConsumptionDataPoint
)
from .serializers import (
    InventorySnapshotSerializer, ProductCategorySerializer, InventoryItemSerializer,
    InventoryReportSerializer, ProductRecommendationSerializer, AnalyticsReportSerializer,
    GenerateInventoryReportSerializer, GenerateAnalyticsReportSerializer, ConsumptionDataPointSerializer
)

class ProductCategoryViewSet(viewsets.ModelViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['GET'])
    def by_center(self, request):
        """Get all active categories with their configurations"""
        center_id = request.query_params.get('center_id')
        if not center_id:
            return Response(
                {'error': 'center_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Obtener solo las categorías activas
            categories = ProductCategory.objects.filter(is_active=True)

            # Si no hay categorías, crear algunas por defecto
            if not categories.exists():
                categories = ProductCategory.objects.filter(is_active=True)

            serializer = self.get_serializer(categories, many=True)
            return Response(serializer.data)

        except Exception as e:
            return Response(
                {'error': f'Error loading categories: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['GET'])
    def categories_stats(self, request):
        """Get statistics for categories in a center"""
        center_id = request.query_params.get('center_id')
        if not center_id:
            return Response(
                {'error': 'center_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        categories = self.get_queryset()
        stats = []

        for category in categories:
            # Obtener el último snapshot del centro
            latest_item = InventoryItem.objects.filter(
                snapshot__center_id=center_id,
                category=category
            ).order_by('-snapshot__created_at').first()

            current_count = latest_item.count if latest_item else 0
            ideal_count = category.ideal_count

            stats.append({
                'id': category.id,
                'name': category.name,
                'current_count': current_count,
                'ideal_count': ideal_count,
                'emergency_priority': category.emergency_priority,
                'status': self._calculate_status(current_count, ideal_count),
                'last_updated': latest_item.snapshot.created_at if latest_item else None
            })

        return Response(stats)

    def _calculate_status(self, current_count, ideal_count):
        """Calculate status based on current and ideal counts"""
        if ideal_count == 0:
            return 'unknown'

        percentage = (current_count / ideal_count) * 100

        if percentage <= 25:
            return 'critical'
        elif percentage <= 50:
            return 'low'
        elif percentage <= 75:
            return 'moderate'
        else:
            return 'good'

    def create(self, request, *args, **kwargs):
        """Override create method to handle category creation/reactivation"""
        try:
            name = request.data.get('name')
            ideal_count = request.data.get('ideal_count', 50)
            emergency_priority = request.data.get('emergency_priority', 3)

            # Check for existing category (including inactive)
            category = ProductCategory.objects.filter(name=name).first()

            if category:
                if not category.is_active:
                    # Reactivate and update existing category
                    category.is_active = True
                    category.ideal_count = ideal_count
                    category.emergency_priority = emergency_priority
                    category.save()
                    serializer = self.get_serializer(category)
                    return Response(serializer.data, status=status.HTTP_200_OK)
                else:
                    return Response(
                        {'error': f'Category {name} already exists and is active'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            category = ProductCategory.objects.create(
                name=name,
                ideal_count=ideal_count,
                emergency_priority=emergency_priority
            )

            serializer = self.get_serializer(category)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get_queryset(self):
        """Only return active categories"""
        return ProductCategory.objects.filter(is_active=True)

    @action(detail=False, methods=['DELETE'], url_path='delete-by-name/(?P<name>[^/.]+)')
    def delete_by_name(self, request, name=None):
        """Soft delete a category by marking it inactive"""
        try:
            category = ProductCategory.objects.get(name=name)
            category.is_active = False  # Soft delete
            category.save()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProductCategory.DoesNotExist:
            return Response(
                {'error': f'Category with name {name} not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['POST'])
    def bulk_update(self, request):
        """Update multiple category configurations at once"""
        try:
            categories_data = request.data
            print(f"Received categories data: {categories_data}")

            updates = []
            errors = []

            for category_data in categories_data:
                try:
                    name = category_data.get('name')
                    ideal_count = category_data.get('ideal_count')
                    emergency_priority = category_data.get('emergency_priority')

                    if not name:
                        errors.append({'error': 'Missing category name'})
                        continue

                    # Solo actualizar categorías existentes
                    try:
                        category = ProductCategory.objects.get(name=name)
                        if ideal_count is not None:
                            category.ideal_count = ideal_count
                        if emergency_priority is not None:
                            category.emergency_priority = emergency_priority
                        category.save()
                        updates.append(self.get_serializer(category).data)
                        print(f"Updated category: {name}")
                    except ProductCategory.DoesNotExist:
                        print(f"Category not found, skipping: {name}")
                        continue

                except Exception as e:
                    print(f"Error updating category {name}: {str(e)}")
                    errors.append({
                        'category': name,
                        'error': str(e)
                    })

            return Response({
                'updated': updates,
                'errors': errors
            })

        except Exception as e:
            print(f"Error in bulk_update: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InventorySnapshotViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Inventory Snapshots
    """
    serializer_class = InventorySnapshotSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['center']
    ordering_fields = ['created_at', 'name']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter snapshots by center if user is not superuser"""
        user = self.request.user
        if not user.is_superuser:
            # Get centers the user belongs to
            centers = user.centers.all()
            return InventorySnapshot.objects.filter(center__in=centers)
        return InventorySnapshot.objects.all()

    def perform_create(self, serializer):
        """Set created_by to current user"""
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['GET'])
    def by_center(self, request):
        """
        Get snapshots for a specific center
        """
        center_id = request.query_params.get('center_id')
        if not center_id:
            return Response(
                {'error': 'center_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        snapshots = self.get_queryset().filter(center_id=center_id)
        serializer = self.get_serializer(snapshots, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['GET'])
    def product_counts(self, request, pk=None):
        """
        Get product counts for a specific snapshot
        """
        snapshot = self.get_object()
        items = snapshot.items.all()

        # Format as a dictionary (category_name: count)
        counts = {}
        for item in items:
            counts[item.category.name] = item.count

        return Response(counts)



class InventoryReportViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Inventory Reports
    """
    serializer_class = InventoryReportSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['center', 'is_emergency']
    ordering_fields = ['created_at', 'name']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter reports by center if user is not superuser"""
        user = self.request.user
        if not user.is_superuser:
            # Get centers the user belongs to
            centers = user.centers.all()
            return InventoryReport.objects.filter(center__in=centers)
        return InventoryReport.objects.all()

    def perform_create(self, serializer):
        """Set created_by to current user"""
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['GET'])
    def by_center(self, request):
        """
        Get reports for a specific center
        """
        center_id = request.query_params.get('center_id')
        if not center_id:
            return Response(
                {'error': 'center_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        reports = self.get_queryset().filter(center_id=center_id)
        serializer = self.get_serializer(reports, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['GET'])
    def latest(self, request):
        """
        Get the latest report for a center
        """
        center_id = request.query_params.get('center_id')
        if not center_id:
            return Response(
                {'error': 'center_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        report = self.get_queryset().filter(center_id=center_id).first()
        if not report:
            return Response(
                {'error': 'No reports found for this center'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(report)
        return Response(serializer.data)

    @action(detail=False, methods=['GET'])
    def priority_products(self, request):
        """
        Get priority products from the latest report
        """
        center_id = request.query_params.get('center_id')
        if not center_id:
            return Response(
                {'error': 'center_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        report = self.get_queryset().filter(center_id=center_id).first()
        if not report:
            return Response(
                {'error': 'No reports found for this center'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get high priority products (priority > 3)
        high_priority = report.recommendations.filter(priority__gt=3)

        # Format as a dictionary (category_name: recommendation)
        priority_products = {}
        for rec in high_priority:
            priority_products[rec.category.name] = ProductRecommendationSerializer(rec).data

        return Response(priority_products)

    @action(detail=False, methods=['GET'])
    def by_category(self, request):
        """
        Get product recommendations by category
        """
        center_id = request.query_params.get('center_id')
        category = request.query_params.get('category')

        if not center_id or not category:
            return Response(
                {'error': 'Both center_id and category parameters are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get latest report
        report = self.get_queryset().filter(center_id=center_id).first()
        if not report:
            return Response(
                {'error': 'No reports found for this center'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Find recommendation for the category
        try:
            category_obj = ProductCategory.objects.get(name=category)
            recommendation = report.recommendations.get(category=category_obj)
            serializer = ProductRecommendationSerializer(recommendation)
            return Response([serializer.data])  # Return as a list for compatibility
        except (ProductCategory.DoesNotExist, ProductRecommendation.DoesNotExist):
            return Response([])  # Empty list for compatibility

    @action(detail=False, methods=['POST'])
    def generate(self, request):
        """
        Generate a new inventory report based on a snapshot
        """
        serializer = GenerateInventoryReportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Get validated data
        snapshot_id = serializer.validated_data['snapshot_id']
        is_emergency = serializer.validated_data.get('is_emergency', False)
        custom_ideal_counts = serializer.validated_data.get('custom_ideal_counts', {})

        try:
            # Get the snapshot
            snapshot = InventorySnapshot.objects.get(id=snapshot_id)

            # Create a name for the report
            now = datetime.datetime.now()
            report_name = f"{'Informe de Emergencia' if is_emergency else 'Informe de Reposicion'} {now.day}/{now.month}/{now.year}"

            # Create the report
            report = InventoryReport.objects.create(
                name=report_name,
                center=snapshot.center,
                created_by=request.user,
                is_emergency=is_emergency,
                source_snapshot=snapshot
            )

            # Get all product categories
            categories = ProductCategory.objects.filter(is_active=True)

            # Create recommendations for each category
            for category in categories:
                # Get current count from snapshot
                try:
                    inventory_item = InventoryItem.objects.get(
                        snapshot=snapshot,
                        category=category
                    )
                    current_count = inventory_item.count
                except InventoryItem.DoesNotExist:
                    current_count = 0

                # Get ideal count (custom or default)
                ideal_count = custom_ideal_counts.get(
                    category.name,
                    category.ideal_count
                )

                # Calculate priority based on percentage missing
                if is_emergency:
                    # In emergency, use predefined emergency_priority
                    priority = category.emergency_priority
                else:
                    # Calculate based on percentage missing
                    if ideal_count <= 0:
                        percentage_missing = 0
                    else:
                        percentage_missing = ((ideal_count - current_count) / ideal_count) * 100

                    if percentage_missing <= 10:
                        priority = 1  # Very Low
                    elif percentage_missing <= 30:
                        priority = 2  # Low
                    elif percentage_missing <= 50:
                        priority = 3  # Medium
                    elif percentage_missing <= 75:
                        priority = 4  # High
                    else:
                        priority = 5  # Very High

                # Create note based on stock level
                note = ''
                if current_count <= 0:
                    note = 'URGENTE: No hay existencias'
                elif current_count < ideal_count * 0.25:
                    note = 'Nivel critico de existencias'
                elif current_count < ideal_count * 0.5:
                    note = 'Nivel bajo de existencias'

                # Create recommendation
                ProductRecommendation.objects.create(
                    report=report,
                    category=category,
                    current_count=current_count,
                    ideal_count=ideal_count,
                    priority=priority,
                    note=note
                )

            serializer = InventoryReportSerializer(report)
            return Response(serializer.data)

        except InventorySnapshot.DoesNotExist:
            return Response(
                {'error': 'Snapshot not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['PATCH'])
    def update_recommendations(self, request, pk=None):
        """
        Actualiza las recomendaciones de un informe existente
        """
        report = self.get_object()
        recommendations_data = request.data.get('recommendations', [])

        if not recommendations_data:
            return Response(
                {'error': 'No recommendations provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        updated_count = 0
        errors = []

        for rec_data in recommendations_data:
            category_id = rec_data.get('category')
            if not category_id:
                errors.append({'error': 'Missing category ID', 'data': rec_data})
                continue

            ideal_count = rec_data.get('ideal_count')
            if ideal_count is None:
                errors.append({'error': 'Missing ideal_count', 'data': rec_data})
                continue

            # Si se proporciona prioridad, usarla; de lo contrario, calcularla
            priority = rec_data.get('priority')
            current_count = rec_data.get('current_count')

            try:
                # Obtener la categoría
                category = ProductCategory.objects.get(id=category_id)

                # Buscar la recomendación existente
                try:
                    recommendation = ProductRecommendation.objects.get(
                        report=report,
                        category=category
                    )

                    # Actualizar la recomendación
                    recommendation.ideal_count = ideal_count

                    if priority is not None:
                        recommendation.priority = priority
                    elif current_count is not None:
                        # Calcular la prioridad basada en porcentaje faltante
                        if ideal_count <= 0:
                            percentage_missing = 0
                        else:
                            percentage_missing = ((ideal_count - current_count) / ideal_count) * 100

                        if percentage_missing <= 10:
                            recommendation.priority = 1  # Very Low
                        elif percentage_missing <= 30:
                            recommendation.priority = 2  # Low
                        elif percentage_missing <= 50:
                            recommendation.priority = 3  # Medium
                        elif percentage_missing <= 75:
                            recommendation.priority = 4  # High
                        else:
                            recommendation.priority = 5  # Very High

                    # Actualizar nota si se proporciona
                    if 'note' in rec_data:
                        recommendation.note = rec_data['note']

                    recommendation.save()
                    updated_count += 1

                except ProductRecommendation.DoesNotExist:
                    # La recomendación no existe, crear una nueva
                    if current_count is None:
                        current_count = 0

                    if priority is None:
                        # Calcular prioridad por defecto
                        if ideal_count <= 0:
                            priority = 1
                        else:
                            percentage_missing = ((ideal_count - current_count) / ideal_count) * 100

                            if percentage_missing <= 10:
                                priority = 1  # Very Low
                            elif percentage_missing <= 30:
                                priority = 2  # Low
                            elif percentage_missing <= 50:
                                priority = 3  # Medium
                            elif percentage_missing <= 75:
                                priority = 4  # High
                            else:
                                priority = 5  # Very High

                    note = rec_data.get('note', '')

                    ProductRecommendation.objects.create(
                        report=report,
                        category=category,
                        current_count=current_count,
                        ideal_count=ideal_count,
                        priority=priority,
                        note=note
                    )
                    updated_count += 1

            except ProductCategory.DoesNotExist:
                errors.append({'error': f'Category not found: {category_id}', 'data': rec_data})
            except Exception as e:
                errors.append({'error': str(e), 'data': rec_data})

        return Response({
            'report_id': str(report.id),
            'updated_count': updated_count,
            'errors': errors
        })


class AnalyticsReportViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Analytics Reports
    """
    serializer_class = AnalyticsReportSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['center', 'period_type']
    ordering_fields = ['created_at', 'name']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter reports by center if user is not superuser"""
        user = self.request.user
        if not user.is_superuser:
            # Get centers the user belongs to
            centers = user.centers.all()
            return AnalyticsReport.objects.filter(center__in=centers)
        return AnalyticsReport.objects.all()

    def perform_create(self, serializer):
        """Set created_by to current user"""
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['GET'])
    def by_center(self, request):
        """
        Get analytics reports for a specific center
        """
        center_id = request.query_params.get('center_id')
        if not center_id:
            return Response(
                {'error': 'center_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        reports = self.get_queryset().filter(center_id=center_id)
        serializer = self.get_serializer(reports, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['GET'])
    def consumption_data(self, request, pk=None):
        """
        Get detailed consumption data for a specific report
        """
        report = self.get_object()

        # Group data by category
        data = {}
        for category in report.get_analyzed_categories():
            # Get consumption data points
            data_points = ConsumptionDataPoint.objects.filter(
                report=report,
                category=category
            ).order_by('date')

            # Serialize data points
            data[category.name] = ConsumptionDataPointSerializer(data_points, many=True).data

        return Response(data)

    @action(detail=False, methods=['POST'])
    def generate(self, request):
        """
        Generate a new analytics report
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Generating analytics report with data: %s", request.data)


        serializer = GenerateAnalyticsReportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Get validated data
        start_snapshot_id = serializer.validated_data['start_snapshot_id']
        end_snapshot_id = serializer.validated_data['end_snapshot_id']
        period_type = serializer.validated_data.get('period_type', 'weekly')
        report_name = serializer.validated_data.get('report_name', '')
        selected_categories = serializer.validated_data.get('selected_categories', [])

        try:
            # Get snapshots
            start_snapshot = InventorySnapshot.objects.get(id=start_snapshot_id)
            end_snapshot = InventorySnapshot.objects.get(id=end_snapshot_id)

            # Check dates
            start_date = start_snapshot.created_at
            end_date = end_snapshot.created_at

            if start_date > end_date:
                return Response(
                    {'error': 'Start date must be earlier than end date'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get or create report name
            if not report_name:
                now = datetime.datetime.now()
                report_name = f"{'Analisis Semanal' if period_type == 'weekly' else 'Analisis Mensual'} {now.day}/{now.month}/{now.year}"

            # Create report
            report = AnalyticsReport.objects.create(
                name=report_name,
                center=start_snapshot.center,
                created_by=request.user,
                period_type=period_type,
                start_date=start_date,
                end_date=end_date,
                start_snapshot=start_snapshot,
                end_snapshot=end_snapshot,
                categories_list=",".join(selected_categories) if selected_categories else ""
            )

            # Get categories to analyze
            categories_to_analyze = []
            if selected_categories:
                # Use selected categories
                logger.info(f"Using {len(selected_categories)} selected categories")
                for cat_name in selected_categories:
                    try:
                        category = ProductCategory.objects.get(name=cat_name)
                        categories_to_analyze.append(category)
                    except ProductCategory.DoesNotExist:
                        # Create category if it doesn't exist
                        category = ProductCategory.objects.create(name=cat_name)
                        categories_to_analyze.append(category)
            else:
                # Use all categories from both snapshots
                start_categories = set(item.category for item in start_snapshot.items.all())
                end_categories = set(item.category for item in end_snapshot.items.all())
                categories_to_analyze = list(start_categories.union(end_categories))

            logger.info(f"Categories for analysis: {[c.name for c in categories_to_analyze]}")

            # Calculate movement for each category
            days = (end_date - start_date).days + 1
            logger.info(f"Analysis period: {days} days")
            import random  # For distributing consumption data

            for category in categories_to_analyze:
                # Get counts from both snapshots
                try:
                    start_count = InventoryItem.objects.get(
                        snapshot=start_snapshot,
                        category=category
                    ).count
                except InventoryItem.DoesNotExist:
                    start_count = 0

                logger.info(f"Start count for {category.name}: {start_count}")

                try:
                    end_count = InventoryItem.objects.get(
                        snapshot=end_snapshot,
                        category=category
                    ).count
                except InventoryItem.DoesNotExist:
                    end_count = 0

                logger.info(f"End count for {category.name}: {end_count}")

                # Calculate movement (positive means increase, negative means consumption)
                movement = end_count - start_count
                is_increase = movement > 0

                # Store absolute value for stats
                movement_value = abs(movement)

                # Log the type of movement
                if is_increase:
                    logger.info(f"Movement for {category.name}: {movement_value} (increase)")
                else:
                    logger.info(f"Movement for {category.name}: {movement_value} (consumption)")

                # Skip if there's no movement
                if movement_value == 0:
                    continue

                # Create total consumption/increase record
                CategoryConsumptionTotal.objects.create(
                    report=report,
                    category=category,
                    count=movement_value
                )

                logger.info(f"Created consumption total for {category.name}: {movement_value}")

                # Generate data points based on period type
                logger.info(f"Generating daily data points for {category.name}")

                # Create a single data point with the appropriate note
                note = "Aumento" if is_increase else "Consumo"

                ConsumptionDataPoint.objects.create(
                    report=report,
                    category=category,
                    date=start_date,
                    count=movement_value,
                    note=note  # Set the appropriate note based on movement direction
                )

                logger.info(f"Created data point: {category.name}, date: {start_date}, count: {movement_value}")

            serializer = AnalyticsReportSerializer(report)
            logger.info(f"Report created successfully. Response data: {serializer.data}")
            return Response(serializer.data)

        except InventorySnapshot.DoesNotExist:
            return Response(
                {'error': 'One or both snapshots not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
