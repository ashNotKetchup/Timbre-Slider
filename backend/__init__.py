"""
Backend module for Timbre-Slider.
Exposes core audio processing and ML components.
"""

from .timbre_VAE.load_audio import BufferManager
from .timbre_VAE.load_generative_model import Model, LatentRepresentation, ControlModel
from .timbre_VAE.logger import RequestLogger
from .timbre_VAE.vae_train import prepare_data, VAE, train_vae
from .timbre_VAE.features import batch_compute_features, get_features

__all__ = [
    "BufferManager",
    "Model",
    "LatentRepresentation",
    "ControlModel",
    "RequestLogger",
    "prepare_data",
    "VAE",
    "train_vae",
    "batch_compute_features",
    "get_features",
]
