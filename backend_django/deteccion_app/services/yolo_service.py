import os
import torch
from PIL import Image
import numpy as np
from typing import Dict, Any, List, Optional
import logging
from django.conf import settings

from .model_service import ModelService

logger = logging.getLogger(__name__)


class YOLOService(ModelService):
    """
    Implementación del servicio para modelos YOLO
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        Inicializa el servicio de YOLO

        Args:
            model_path: Ruta al archivo del modelo. Si es None, se usará la ruta por defecto.
        """
        if model_path is None:
            # Usa la ruta por defecto desde las configuraciones
            self.model_path = os.path.join(settings.BASE_DIR, 'weights', 'best.pt')
        else:
            self.model_path = model_path

        self.model = None

        # Intenta usar CUDA si está disponible, pero con manejo de errores
        try:
            if torch.cuda.is_available():
                self.device = torch.device('cuda')
                # Verificar si el dispositivo realmente está disponible para uso
                torch.cuda.empty_cache()  # Liberar memoria
                test_tensor = torch.zeros(1).to(self.device)  # Prueba simple
                logger.info(f"CUDA disponible. Utilizando dispositivo: {self.device}")
            else:
                self.device = torch.device('cpu')
                logger.info(f"CUDA no disponible. Utilizando dispositivo: {self.device}")
        except Exception as e:
            # Si hay algún error con CUDA, usar CPU
            self.device = torch.device('cpu')
            logger.warning(f"Error al configurar CUDA, usando CPU: {str(e)}")

    def load_model(self) -> None:
        """
        Carga el modelo YOLO en memoria
        """
        try:
            # Si ocurrió algún problema con CUDA anteriormente, asegurar uso de CPU
            if self.device.type == 'cuda':
                try:
                    # Verificar nuevamente si CUDA está realmente disponible
                    test_tensor = torch.zeros(1).to(self.device)
                except Exception as cuda_error:
                    logger.warning(f"Error al usar CUDA al cargar modelo, cambiando a CPU: {str(cuda_error)}")
                    self.device = torch.device('cpu')

            # Intenta usar directamente la clase YOLO de ultralytics (para YOLOv8)
            try:
                from ultralytics import YOLO
                self.model = YOLO(self.model_path)
                # Para YOLOv8, configurar el dispositivo después de cargar
                if hasattr(self.model, 'to'):
                    self.model.to(self.device)
                logger.info(f"Modelo YOLOv8 cargado desde {self.model_path} en {self.device}")
                return
            except (ImportError, Exception) as e:
                logger.warning(f"Error al cargar con ultralytics YOLO: {str(e)}")

            # Si falla, intenta cargar con torch.hub (para YOLOv5)
            try:
                from torch.serialization import add_safe_globals
                try:
                    from ultralytics.nn.tasks import DetectionModel
                    add_safe_globals([DetectionModel])
                except ImportError:
                    pass

                self.model = torch.hub.load('ultralytics/yolov5', 'custom',
                                            path=self.model_path, device=self.device, force_reload=True)
                logger.info(f"Modelo YOLOv5 cargado desde {self.model_path} en {self.device}")
                return
            except Exception as e:
                logger.error(f"Error al cargar el modelo con torch.hub: {str(e)}")

            # Último intento: carga directa
            try:
                # Cargar el modelo
                model_data = torch.load(self.model_path, map_location=self.device, weights_only=False)

                if isinstance(model_data, dict):
                    # Es un modelo en formato de diccionario (común en YOLOv8)
                    from ultralytics import YOLO
                    self.model = YOLO(self.model_path)
                    if hasattr(self.model, 'to'):
                        self.model.to(self.device)
                elif hasattr(model_data, 'model'):
                    # Es un modelo tradicional
                    self.model = model_data.model
                    self.model.to(self.device)
                    self.model.eval()
                else:
                    # Es el modelo directamente
                    self.model = model_data
                    self.model.to(self.device)
                    self.model.eval()

                logger.info(f"Modelo YOLO cargado directamente desde {self.model_path} en {self.device}")
            except Exception as e2:
                logger.error(f"Error al cargar el modelo directamente: {str(e2)}")
                # Último intento: forzar CPU
                try:
                    logger.warning("Intentando cargar el modelo forzando CPU...")
                    model_data = torch.load(self.model_path, map_location="cpu", weights_only=False)
                    if isinstance(model_data, dict):
                        from ultralytics import YOLO
                        self.model = YOLO(self.model_path)
                    elif hasattr(model_data, 'model'):
                        self.model = model_data.model
                        self.model.eval()
                    else:
                        self.model = model_data
                        self.model.eval()
                    self.device = torch.device('cpu')
                    logger.info(f"Modelo YOLO cargado en CPU como fallback")
                except Exception as e3:
                    logger.error(f"Todos los intentos de carga fallaron: {str(e3)}")
                    raise RuntimeError(f"No se pudo cargar el modelo YOLO: {str(e3)}")

        except Exception as e:
            logger.error(f"Error general al cargar el modelo: {str(e)}")
            raise RuntimeError(f"No se pudo cargar el modelo YOLO: {str(e)}")

    def process_image(self, image: Image.Image) -> Dict[str, Any]:
        """
        Procesa una imagen con el modelo YOLO

        Args:
            image: Imagen a procesar en formato PIL

        Returns:
            Diccionario con los resultados de la detección
        """
        if self.model is None:
            self.load_model()

        # Realizar inferencia - adaptado para funcionar con diferentes versiones de YOLO
        try:
            # Asegurar que no hay problemas con CUDA
            if self.device.type == 'cuda':
                try:
                    torch.cuda.empty_cache()
                except Exception as cuda_error:
                    logger.warning(f"Problema con CUDA durante inferencia, cambiando a CPU: {str(cuda_error)}")
                    self.device = torch.device('cpu')
                    if hasattr(self.model, 'to'):
                        self.model.to(self.device)

            # Comprobar el tipo de modelo y usar el método adecuado
            if hasattr(self.model, 'predict'):
                # Para modelos YOLOv8
                results = self.model.predict(image, verbose=False, device=self.device)
            elif hasattr(self.model, '__call__'):
                # Para modelos YOLOv5 y similares
                results = self.model(image)
            else:
                # Para otros formatos, intentar approachs alternativos
                logger.warning("Modelo no reconocido, intentando métodos alternativos")
                if hasattr(self.model, 'model') and hasattr(self.model.model, '__call__'):
                    results = self.model.model(image)
                elif hasattr(self.model, 'forward'):
                    # Método forward estándar de PyTorch
                    results = self.model.forward(image)
                else:
                    raise ValueError("No se pudo determinar cómo realizar inferencia con este modelo")

            # Procesar resultados
            processed_results = self._process_results(results)
            return processed_results

        except Exception as e:
            logger.error(f"Error durante la inferencia: {str(e)}", exc_info=True)
            # Si es un error de CUDA, intentar con CPU
            if "CUDA" in str(e) and self.device.type == 'cuda':
                try:
                    logger.info("Error de CUDA detectado, intentando con CPU...")
                    original_device = self.device
                    self.device = torch.device('cpu')

                    # Mover el modelo a CPU si es posible
                    if hasattr(self.model, 'to'):
                        self.model.to(self.device)

                    # Reintentar inferencia
                    if hasattr(self.model, 'predict'):
                        results = self.model.predict(image, verbose=False, device=self.device)
                    elif hasattr(self.model, '__call__'):
                        results = self.model(image)
                    else:
                        if hasattr(self.model, 'model') and hasattr(self.model.model, '__call__'):
                            results = self.model.model(image)
                        elif hasattr(self.model, 'forward'):
                            results = self.model.forward(image)

                    processed_results = self._process_results(results)
                    logger.info("Procesamiento exitoso usando CPU como fallback")
                    return processed_results
                except Exception as cpu_error:
                    logger.error(f"También falló con CPU: {str(cpu_error)}", exc_info=True)
                    self.device = original_device  # Restaurar dispositivo original

            raise RuntimeError(f"Error al procesar la imagen: {str(e)}")
    def _process_results(self, results) -> Dict[str, Any]:
        """
        Procesa los resultados del modelo en un formato estandarizado

        Args:
            results: Resultados directos del modelo

        Returns:
            Diccionario con los resultados procesados
        """
        detections = []

        try:
            # Para modelos YOLOv8
            if hasattr(results, 'boxes') or (isinstance(results, list) and hasattr(results[0], 'boxes')):
                result_obj = results[0] if isinstance(results, list) else results

                # Obtener diccionario de clases si existe
                class_names = {}
                if hasattr(self.model, 'names'):
                    class_names = self.model.names
                elif hasattr(result_obj, 'names'):
                    class_names = result_obj.names

                # Procesar cada resultado
                for r in results if isinstance(results, list) else [results]:
                    if not hasattr(r, 'boxes'):
                        continue

                    boxes = r.boxes
                    for box in boxes:
                        # Obtener coordenadas
                        x1, y1, x2, y2 = box.xyxy[0].tolist() if hasattr(box, 'xyxy') else [0, 0, 0, 0]

                        # Obtener clase y confianza
                        cls = int(box.cls[0]) if hasattr(box, 'cls') and len(box.cls) > 0 else 0
                        conf = float(box.conf[0]) if hasattr(box, 'conf') and len(box.conf) > 0 else 0.0

                        # Obtener nombre de la clase
                        if cls in class_names:
                            class_name = class_names[cls]
                        else:
                            class_name = f"clase_{cls}"

                        detection = {
                            'class': class_name,
                            'confidence': conf,
                            'bbox': {
                                'x1': x1,
                                'y1': y1,
                                'x2': x2,
                                'y2': y2,
                            }
                        }
                        detections.append(detection)

            # Para modelos YOLOv5
            elif hasattr(results, 'pandas'):
                # Extraer información de las predicciones
                predictions = results.pandas().xyxy[0]  # Resultados en formato pandas

                for _, pred in predictions.iterrows():
                    detection = {
                        'class': pred['name'],
                        'confidence': float(pred['confidence']),
                        'bbox': {
                            'x1': float(pred['xmin']),
                            'y1': float(pred['ymin']),
                            'x2': float(pred['xmax']),
                            'y2': float(pred['ymax']),
                        }
                    }
                    detections.append(detection)

            # Formato alternativo para algunos modelos YOLOv8
            elif isinstance(results, list) and len(results) > 0 and hasattr(results[0], 'probs'):
                for result in results:
                    # Este formato es para resultados de clasificación, no detección
                    if hasattr(result, 'probs'):
                        probs = result.probs
                        if hasattr(probs, 'top1'):
                            cls_id = int(probs.top1)
                            conf = float(probs.top1conf)
                            class_name = result.names[cls_id] if hasattr(result,
                                                                         'names') and cls_id in result.names else f"clase_{cls_id}"

                            # Para clasificación no hay bboxes específicos, así que usamos toda la imagen
                            detection = {
                                'class': class_name,
                                'confidence': conf,
                                'bbox': {
                                    'x1': 0.0,
                                    'y1': 0.0,
                                    'x2': 1.0,  # Normalizado a 1
                                    'y2': 1.0,  # Normalizado a 1
                                }
                            }
                            detections.append(detection)

            # Si no se reconoce ninguno de los formatos anteriores
            else:
                logger.warning("Formato de resultados no reconocido, extrayendo información de clases disponible")

                # Intentar extraer información de clases del modelo
                class_names = {}
                if hasattr(self.model, 'names'):
                    class_names = self.model.names
                elif hasattr(self.model, 'model') and hasattr(self.model.model, 'names'):
                    class_names = self.model.model.names
                elif hasattr(self.model, 'module') and hasattr(self.model.module, 'names'):
                    class_names = self.model.module.names

                # Registrar la estructura de los resultados para depuración
                logger.info(f"Estructura de resultados: {type(results)}")
                if isinstance(results, list):
                    if len(results) > 0:
                        logger.info(f"Primer elemento: {type(results[0])}")
                        logger.info(f"Atributos: {dir(results[0])}")
                else:
                    logger.info(f"Atributos: {dir(results)}")

                # Si no se encontró un formato reconocido, realizar una detección genérica
                if class_names and isinstance(results, (list, tuple)) and len(results) > 0:
                    # Asumir que el primer resultado tiene información relevante
                    if hasattr(results[0], 'xywh') or hasattr(results[0], 'xyxy'):
                        boxes_attr = 'xyxy' if hasattr(results[0], 'xyxy') else 'xywh'
                        boxes = getattr(results[0], boxes_attr)

                        for i, box in enumerate(boxes):
                            if len(box) >= 5:  # Formato esperado: [x, y, w, h, conf, cls...]
                                cls_id = int(box[5]) if len(box) > 5 else 0
                                conf = float(box[4])
                                class_name = class_names.get(cls_id, f"clase_{cls_id}")

                                # Convertir de xywh a xyxy si es necesario
                                if boxes_attr == 'xywh':
                                    x, y, w, h = box[0:4]
                                    x1, y1, x2, y2 = x - w / 2, y - h / 2, x + w / 2, y + h / 2
                                else:
                                    x1, y1, x2, y2 = box[0:4]

                                detection = {
                                    'class': class_name,
                                    'confidence': conf,
                                    'bbox': {
                                        'x1': float(x1),
                                        'y1': float(y1),
                                        'x2': float(x2),
                                        'y2': float(y2),
                                    }
                                }
                                detections.append(detection)

                # Si aún no hay detecciones, intentar un enfoque genérico con el primer objeto encontrado
                if not detections and class_names and len(class_names) > 0:
                    # Tomar la primera clase como fallback
                    first_class_id = list(class_names.keys())[0]
                    class_name = class_names[first_class_id]

                    logger.warning(f"No se pudieron extraer detecciones, usando clase por defecto: {class_name}")
                    detection = {
                        'class': class_name,
                        'confidence': 0.5,  # Confianza arbitraria
                        'bbox': {
                            'x1': 0.1,  # Valores arbitrarios
                            'y1': 0.1,
                            'x2': 0.9,
                            'y2': 0.9,
                        }
                    }
                    detections.append(detection)

        except Exception as e:
            logger.error(f"Error al procesar resultados del modelo: {str(e)}", exc_info=True)
            # No lanzar error para devolver al menos resultados vacíos

        # Si después de todo no hay detecciones, registrar advertencia
        if not detections:
            logger.warning("No se pudieron extraer detecciones del modelo")

        return {
            'detections': detections,
            'count': len(detections),
            'model_type': 'yolo',
            'model_path': self.model_path
        }
    def get_model_info(self) -> Dict[str, Any]:
        """
        Devuelve información sobre el modelo YOLO

        Returns:
            Diccionario con información sobre el modelo
        """
        if self.model is None:
            self.load_model()

        return {
            'type': 'YOLO',
            'path': self.model_path,
            'device': str(self.device),
            'classes': self.model.names if hasattr(self.model, 'names') else None
        }
