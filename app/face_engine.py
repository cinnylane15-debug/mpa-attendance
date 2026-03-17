import logging
import threading
from typing import Optional

import cv2
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


class FaceEngine:
    """InsightFace wrapper for face detection and embedding extraction."""

    def __init__(self):
        self._model = None
        self._lock = threading.Lock()

    def _load_model(self):
        """Lazily load the InsightFace model on first use."""
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            try:
                from insightface.app import FaceAnalysis

                logger.info("Loading InsightFace model: %s", settings.INSIGHTFACE_MODEL)
                self._model = FaceAnalysis(
                    name=settings.INSIGHTFACE_MODEL,
                    providers=["CPUExecutionProvider"],
                )
                self._model.prepare(ctx_id=-1, det_size=(640, 640))
                logger.info("InsightFace model loaded successfully")
            except Exception as e:
                logger.error("Failed to load InsightFace model: %s", e)
                raise

    def extract_embedding(self, image_path: str) -> Optional[np.ndarray]:
        """Extract a 512-dim face embedding from an image file.

        Returns the embedding of the largest detected face, or None if no face found.
        """
        self._load_model()
        img = cv2.imread(image_path)
        if img is None:
            logger.warning("Could not read image: %s", image_path)
            return None

        faces = self._model.get(img)
        if not faces:
            logger.warning("No face detected in image: %s", image_path)
            return None

        # Pick the largest face by bounding box area
        largest = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        embedding = largest.embedding  # 512-dim numpy array
        # Normalize to unit vector for cosine similarity
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding

    def extract_embedding_from_frame(self, frame: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
        """Extract face embeddings from a video frame.

        Returns list of (bbox, embedding) tuples.
        """
        self._load_model()
        faces = self._model.get(frame)
        results = []
        for face in faces:
            embedding = face.embedding
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            results.append((face.bbox, embedding))
        return results

    @staticmethod
    def compare_embeddings(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings.

        Both embeddings should already be normalized. Returns value in [-1, 1].
        """
        return float(np.dot(emb1, emb2))


# Global singleton
face_engine = FaceEngine()
