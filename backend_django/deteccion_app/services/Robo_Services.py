import io
import requests
import logging
from typing import Dict, Any, Optional
from PIL import Image
from django.conf import settings

from .model_service import ModelService

logger = logging.getLogger(__name__)


class RoboflowService(ModelService):
    """
    Implementación del servicio para la API de Roboflow
    """

    def __init__(self, api_key: Optional[str] = None, model_id: Optional[str] = None):
        """
        Inicializa el servicio de Roboflow

        Args:
            api_key: Clave de API de Roboflow
            model_id: ID del modelo en Roboflow (incluye versión)
        """
        # Valor específico de la API key
        self.api_key = "ByAUZwtbGcbVgbaowa1Q"
        self.model_id = "object-detection-ez3ce/1"

        # No hay modelo local para cargar
        self.model = None
        logger.info(f"Inicializado RoboflowService con model_id: {self.model_id} y api_key: {self.api_key}")

    def load_model(self) -> None:
        """
        No hay modelo para cargar en este caso
        """
        logger.info("No se requiere cargar un modelo para el servicio de Roboflow")
        pass

    def process_image(self, image: Image.Image) -> Dict[str, Any]:
        """
        Envía una imagen a la API de Roboflow para su análisis

        Args:
            image: Imagen a procesar en formato PIL

        Returns:
            Diccionario con los resultados de la detección
        """
        # Convertir la imagen a bytes
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        img_bytes = buffered.getvalue()

        # URL correcta con el modelo incluido
        url = f"https://detect.roboflow.com/{self.model_id}"

        # Parámetros de consulta
        params = {
            "api_key": self.api_key,
            "confidence": 40,
            "overlap": 30,
            "format": "json"
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        try:
            # Loguear la URL y los parámetros para verificar
            logger.info(f"Enviando solicitud a: {url} con params: {params}")

            # Enviar la solicitud POST con la imagen como datos binarios
            response = requests.post(
                url,
                params=params,
                data=img_bytes,
                headers=headers
            )

            # Registrar respuesta antes de evaluar errores
            logger.info(f"Código de estado: {response.status_code}")
            logger.info(f"Respuesta: {response.text[:200]}...")  # Primeros 200 caracteres

            response.raise_for_status()
            result = response.json()

            # Procesar la respuesta
            detections = []
            for prediction in result.get('predictions', []):
                # Convertir de formato Roboflow a nuestro formato estandarizado
                x = prediction.get('x', 0)
                y = prediction.get('y', 0)
                width = prediction.get('width', 0)
                height = prediction.get('height', 0)

                detection = {
                    'class': prediction.get('class', 'unknown'),
                    'confidence': prediction.get('confidence', 0.0),
                    'bbox': {
                        'x1': x - width / 2,
                        'y1': y - height / 2,
                        'x2': x + width / 2,
                        'y2': y + height / 2,
                    }
                }
                detections.append(detection)

            return {
                'detections': detections,
                'count': len(detections),
                'model_type': 'roboflow',
                'api_source': 'Roboflow API'
            }

        except Exception as e:
            logger.error(f"Error al procesar la imagen con Roboflow: {str(e)}", exc_info=True)
            raise RuntimeError(f"Error al procesar la imagen con API externa: {str(e)}")

    def get_model_info(self) -> Dict[str, Any]:
        """
        Devuelve información sobre el servicio de Roboflow

        Returns:
            Diccionario con información sobre el servicio
        """
        return {
            'type': 'Roboflow API',
            'model_id': self.model_id,
            'has_api_key': bool(self.api_key)
        }
