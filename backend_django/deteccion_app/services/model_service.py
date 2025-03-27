from abc import ABC, abstractmethod
from typing import Dict, Any, List
import numpy as np
from PIL import Image


class ModelService(ABC):
    """
    Clase abstracta que define la interfaz para los servicios de modelos de detección
    """

    @abstractmethod
    def load_model(self) -> None:
        """
        Carga el modelo en memoria
        """
        pass

    @abstractmethod
    def process_image(self, image: Image.Image) -> Dict[str, Any]:
        """
        Procesa una imagen y devuelve los resultados de la detección

        Args:
            image: Imagen a procesar en formato PIL

        Returns:
            Diccionario con los resultados de la detección
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        Devuelve información sobre el modelo

        Returns:
            Diccionario con información sobre el modelo
        """
        pass
