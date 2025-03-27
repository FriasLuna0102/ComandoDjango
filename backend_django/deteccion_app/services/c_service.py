import os
import base64
import io
import logging
import requests
import json
import re
import traceback
from PIL import Image, ImageOps
from typing import Dict, Any, Optional, List

from django.conf import settings
from .model_service import ModelService

logger = logging.getLogger(__name__)


class ClaudeService(ModelService):
    """
    Implementación del servicio para la API de Claude
    especializada en la clasificación de productos alimenticios,
    con formato de respuesta compatible con YOLOService
    """

    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
        """
        Inicializa el servicio de Claude

        Args:
            api_key: Clave de API de Claude. Si es None, se usará la clave de las configuraciones.
            api_url: URL base de la API de Claude. Si es None, se usará la URL por defecto.
        """
        self.api_key = api_key or getattr(settings, 'CE_API_KEY', '')
        self.api_url = api_url or getattr(settings, 'CE_API_URL', 'https://api.anthropic.com/v1/messages')

        # Probar con el modelo más reciente si el error persiste
        # self.model = getattr(settings, 'CE_MODEL', 'claude-3-sonnet-20240229')
        self.model = 'claude-3-7-sonnet-20250219'  # Modelo más estable para pruebas

        # Configurar el mapeo de clases similar a YOLO
        self.class_names = {
            0: "beverage",  # Bebidas
            1: "dairy",  # Leches en polvo y derivados lácteos
            2: "cereal",  # Cereales
            3: "canned_food",  # Alimentos enlatados
            4: "crackers_cookies",  # Galletas
            5: "pasta_noodles",  # Espaguetis y similares
            6: "condiments"  # Condimentos y salsas
        }

        # Mapeo inverso para buscar IDs por nombre
        self.class_ids = {name: id for id, name in self.class_names.items()}

        if not self.api_key:
            logger.warning("No se ha configurado la clave de API de Claude.")

        logger.info(f"ClaudeService inicializado con el modelo: {self.model}")

    def load_model(self) -> None:
        """
        No hay modelo para cargar en este caso, pero implementamos el método para
        mantener la consistencia con la interfaz
        """
        logger.info("No se requiere cargar un modelo para el servicio de Claude.")
        pass

    def process_image(self, image: Image.Image) -> Dict[str, Any]:
        """
        Envía una imagen a la API de Claude para clasificar los productos alimenticios
        con formato de respuesta compatible con YOLOService

        Args:
            image: Imagen a procesar en formato PIL

        Returns:
            Diccionario con los resultados de la clasificación
        """
        try:
            if not self.api_key:
                logger.error("No se ha configurado una clave API para Claude")
                raise ValueError("Se requiere una clave de API para usar el servicio de Claude.")

            # Obtener dimensiones de la imagen para los bboxes
            img_width, img_height = image.size
            logger.info(f"Procesando imagen con dimensiones: {img_width}x{img_height}")

            # Abordaje simplificado para el procesamiento de la imagen
            try:
                # Asegurar que la imagen es RGB y redimensionarla a un tamaño más pequeño
                if image.mode != 'RGB':
                    image = image.convert('RGB')

                # Redimensionar a un tamaño más manejable
                max_dimension = 512  # Usar un tamaño más pequeño para evitar problemas

                if img_width > max_dimension or img_height > max_dimension:
                    image.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
                    img_width, img_height = image.size
                    logger.info(f"Imagen redimensionada a: {img_width}x{img_height}")

                # Guardar como JPEG con calidad reducida
                buffered = io.BytesIO()
                image.save(buffered, format="JPEG", quality=70)
                buffered.seek(0)

                # Leer bytes y codificar en base64
                image_bytes = buffered.read()
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')

                logger.info(f"Imagen convertida a base64, tamaño: {len(image_base64) / 1024:.2f} KB")

            except Exception as img_error:
                logger.error(f"Error al procesar la imagen: {str(img_error)}")
                logger.error(traceback.format_exc())
                return self._create_fallback_response(f"Error al procesar la imagen: {str(img_error)}")

            # Preparar la solicitud a la API
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }

            # Prompt específico para clasificación de alimentos
            prompt = """
            Analiza detalladamente la imagen e identifica TODOS los objetos o productos alimenticios que puedas ver.

            Para cada objeto identificado, clasifícalo en UNA de estas categorías:

            1. beverage (Para las bebidas)
            2. dairy (Leches en polvos, y demás)
            3. cereal (Cereales)
            4. canned_food (Alimentos enlatados)
            5. crackers_cookies (Galletas)
            6. pasta_noodles (Espaguetis, y demás)
            7. condiments (Condimentos, salsas)

            Proporciona tu respuesta con el siguiente formato estructurado:

            OBJETOS IDENTIFICADOS:
            1. [Nombre del objeto 1]: [Descripción breve] - Categoría: [categoría asignada] - Confianza: [alta/media/baja]
            2. [Nombre del objeto 2]: [Descripción breve] - Categoría: [categoría asignada] - Confianza: [alta/media/baja]
            (y así sucesivamente para todos los objetos)

            RESUMEN:
            Total de objetos: [número]
            Distribución por categorías:
            - beverage: [número]
            - dairy: [número]
            - cereal: [número]
            - canned_food: [número]
            - crackers_cookies: [número]
            - pasta_noodles: [número]
            - condiments: [número]

            Categoría predominante: [categoría con más objetos]

            IMPORTANTE: Asegúrate de identificar y clasificar TODOS los objetos visibles, incluso si están parcialmente ocultos.
            """

            # Construir el payload para la API
            payload = {
                "model": self.model,
                "max_tokens": 1000,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_base64
                                }
                            }
                        ]
                    }
                ]
            }

            # Log de debug (sin exponer datos sensibles)
            debug_info = {
                "model": self.model,
                "image_size_kb": len(image_base64) / 1024,
                "api_url": self.api_url
            }
            logger.info(f"Enviando solicitud a Claude API con: {json.dumps(debug_info)}")

            # Enviar solicitud
            try:
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=30
                )

                logger.info(f"Respuesta de Claude API. Status: {response.status_code}")

                # Si hay error, devolver un resultado de fallback
                if response.status_code != 200:
                    error_info = str(response.text)
                    logger.error(f"Error en API de Claude: {response.status_code}, Respuesta: {error_info}")

                    # Si el problema es con la imagen, devolver un mensaje más específico
                    if "invalid base64 data" in error_info:
                        logger.error("Error específico: Datos base64 inválidos")
                        # Intentar con un enfoque de detección genérica
                        return self._generate_generic_detection(img_width, img_height)

                    return self._create_fallback_response(f"Error en API: {response.status_code}")

                # Procesar la respuesta
                result = response.json()

                # Extraer el texto de la respuesta
                claude_text = ""
                for content_item in result.get('content', []):
                    if content_item.get('type') == 'text':
                        claude_text = content_item.get('text', '')
                        break

                # logger.info(f"Respuesta exitosa de Claude, longitud: {len(claude_text)} caracteres")

                # Procesar y devolver los resultados
                processed_result = self._parse_food_classification(claude_text, img_width, img_height)
                processed_result['model_type'] = 'yolo_2.0'
                processed_result['model_path'] = "yolo2.0"
                # processed_result['raw_response'] = claude_text

                return processed_result

            except requests.exceptions.RequestException as req_error:
                logger.error(f"Error de conexión: {str(req_error)}")
                return self._create_fallback_response(f"Error de conexión: {str(req_error)}")

        except Exception as e:
            # logger.error(f"Error general en process_image: {str(e)}")
            # logger.error(traceback.format_exc())
            return self._create_fallback_response(f"Error inesperado: {str(e)}")

    def _generate_generic_detection(self, img_width: int, img_height: int) -> Dict[str, Any]:
        """
        Genera una detección genérica cuando no se puede usar la API pero queremos
        devolver algo útil al usuario

        Args:
            img_width: Ancho de la imagen
            img_height: Alto de la imagen

        Returns:
            Diccionario con detección genérica compatible con el resto del sistema
        """
        # logger.info("Generando detección genérica debido a error de API")

        # Elegir una categoría aleatoria
        import random
        categories = list(self.class_names.values())
        random_category = random.choice(categories)

        return {
            'detections': [
                {
                    'class': random_category,
                    'confidence': 0.6,
                    'bbox': {
                        'x1': float(img_width * 0.1),
                        'y1': float(img_height * 0.1),
                        'x2': float(img_width * 0.9),
                        'y2': float(img_height * 0.9),
                    },
                    # 'object_name': "Alimento detectado",
                    # 'description': "Detección genérica (la API no pudo procesar la imagen)"
                }
            ],
            'count': 1,
            'model_type': 'yolo2.0',
            'model_path': self.model,
            'category_distribution': {category: 1 if category == random_category else 0
                                      for category in self.class_names.values()},
            'predominant_category': random_category,
            'raw_response': "Respuesta generada localmente debido a error en la API.",
            'is_fallback': True
        }

    def _create_fallback_response(self, error_message: str) -> Dict[str, Any]:
        """
        Crea una respuesta de fallback que pueda ser procesada por el sistema
        cuando ocurre un error en la API de Claude.

        Args:
            error_message: Mensaje de error para incluir en el resultado

        Returns:
            Dict con estructura compatible con el resto del sistema
        """
        return {
            'detections': [],
            'count': 0,
            'model_type': 'yolo2.0',
            'model_path': "yolo2.0",
            'category_distribution': {category: 0 for category in self.class_names.values()},
            'predominant_category': None,
            'error': error_message,
            # 'raw_response': f"Error en la API de Claude: {error_message}",
            'is_fallback': True
        }

    def _parse_food_classification(self, response_text: str, img_width: int, img_height: int) -> Dict[str, Any]:
        """
        Parsea la respuesta de Claude para extraer la información estructurada
        sobre la clasificación de alimentos y la convierte a formato compatible con YOLO

        Args:
            response_text: Texto de respuesta de la API de Claude
            img_width: Ancho de la imagen original
            img_height: Alto de la imagen original

        Returns:
            Diccionario con la información estructurada en formato compatible con YOLO
        """
        # Inicializamos el resultado con la estructura similar a YOLO
        result = {
            'detections': [],
            'count': 0,
            'category_distribution': {},  # Mantenemos esta información adicional
            'predominant_category': None  # Mantenemos esta información adicional
        }

        # Inicializar distribución de categorías
        for category in self.class_names.values():
            result['category_distribution'][category] = 0

        # Verificar si tenemos una respuesta válida
        if not response_text or len(response_text.strip()) < 10:
            logger.warning("Respuesta de Claude vacía o demasiado corta")
            return result

        try:
            # Extraer la lista de objetos identificados
            objects_section_match = re.search(r'OBJETOS IDENTIFICADOS:(.*?)(?:RESUMEN:|$)',
                                              response_text, re.DOTALL)

            if objects_section_match:
                objects_text = objects_section_match.group(1).strip()
                # Busca patrones numerados como "1. Objeto:" o líneas que comienzan con números
                object_entries = re.findall(r'^\d+\.\s+(.*?)(?=^\d+\.|\Z)', objects_text, re.MULTILINE | re.DOTALL)

                for i, entry in enumerate(object_entries):
                    entry = entry.strip()
                    if not entry:
                        continue

                    # Extraer nombre, descripción, categoría y confianza
                    name_match = re.match(r'([^:]+):', entry)
                    name = name_match.group(1).strip() if name_match else "Objeto no identificado"

                    category_match = re.search(r'Categoría:\s*(\w+)', entry)
                    category = category_match.group(1).strip() if category_match else None

                    confidence_match = re.search(r'Confianza:\s*(alta|media|baja)', entry, re.IGNORECASE)
                    confidence_text = confidence_match.group(1).lower() if confidence_match else "media"

                    # Convertir texto de confianza a valor numérico
                    confidence_value = {
                        'alta': 0.9,
                        'media': 0.7,
                        'baja': 0.5
                    }.get(confidence_text, 0.5)

                    # Extraer descripción (todo lo que está entre el nombre y "Categoría:")
                    description = entry
                    if name_match and category_match:
                        name_end = name_match.end()
                        category_start = entry.find("Categoría:")
                        if category_start > name_end:
                            description = entry[name_end:category_start].strip()
                            # Eliminar el carácter ":" que podría quedar al principio
                            if description.startswith(':'):
                                description = description[1:].strip()

                    # Solo agregar si tenemos una categoría válida
                    if category and category in self.class_names.values():
                        # Generar bbox artificial para ser compatible con YOLO
                        # Como Claude no proporciona ubicaciones, creamos boxes distribuidos en la imagen
                        # Calculamos posiciones relativas basadas en el número de objetos
                        num_objects = len(object_entries)

                        # Calculamos filas y columnas para distribuir los objetos en una cuadrícula
                        import math
                        cols = math.ceil(math.sqrt(num_objects))
                        rows = math.ceil(num_objects / cols)

                        # Calculamos la posición en la cuadrícula
                        col = i % cols
                        row = i // cols

                        # Calculamos las coordenadas del bbox
                        box_width = img_width / cols * 0.8  # 80% del ancho de la celda
                        box_height = img_height / rows * 0.8  # 80% del alto de la celda

                        x1 = (col * img_width / cols) + (img_width / cols * 0.1)  # 10% de margen
                        y1 = (row * img_height / rows) + (img_height / rows * 0.1)  # 10% de margen
                        x2 = x1 + box_width
                        y2 = y1 + box_height

                        # Crear detección en formato compatible con YOLO
                        detection = {
                            'class': category,
                            'confidence': confidence_value,
                            'bbox': {
                                'x1': float(x1),
                                'y1': float(y1),
                                'x2': float(x2),
                                'y2': float(y2),
                            },
                            # Información adicional de Claude
                            # 'object_name': name,
                            # 'description': description
                        }
                        result['detections'].append(detection)

                        # Actualizar distribución de categorías
                        result['category_distribution'][category] += 1

            # Extraer información del resumen
            total_match = re.search(r'Total de objetos:\s*(\d+)', response_text)
            if total_match:
                result['count'] = int(total_match.group(1))
            else:
                result['count'] = len(result['detections'])

            # Extraer categoría predominante
            predominant_match = re.search(r'Categoría predominante:\s*(\w+)', response_text)
            if predominant_match:
                result['predominant_category'] = predominant_match.group(1).strip()
            else:
                # Determinar la categoría predominante por conteo
                max_count = 0
                for category, count in result['category_distribution'].items():
                    if count > max_count:
                        max_count = count
                        result['predominant_category'] = category

            # Si no hay detecciones pero debería haberlas según el resumen
            if not result['detections'] and result['count'] > 0:
                logger.warning("No se pudieron extraer detecciones aunque el resumen indica que hay objetos")
                # Crear al menos una detección genérica
                result['detections'] = [{
                    'class': result['predominant_category'] or 'unknown',
                    'confidence': 0.5,
                    'bbox': {
                        'x1': float(img_width * 0.1),
                        'y1': float(img_height * 0.1),
                        'x2': float(img_width * 0.9),
                        'y2': float(img_height * 0.9),
                    },
                    # 'object_name': "Objeto detectado",
                    # 'description': "No se pudo extraer información detallada"
                }]

            return result

        except Exception as e:
            logger.error(f"Error al parsear la respuesta de Claude: {str(e)}")
            logger.error(traceback.format_exc())
            # Devolver un resultado vacío pero válido
            return {
                'detections': [],
                'count': 0,
                'category_distribution': {category: 0 for category in self.class_names.values()},
                'predominant_category': None
            }

    def get_model_info(self) -> Dict[str, Any]:
        """
        Devuelve información sobre el servicio de Claude,
        con formato similar a YOLO para mantener consistencia

        Returns:
            Diccionario con información sobre el servicio
        """
        return {
            'type': 'Yolo 2.0',
            'path': self.api_url,
            'device': 'cloud',
            'classes': self.class_names,
            'model': self.model,
            'has_api_key': bool(self.api_key)
        }
