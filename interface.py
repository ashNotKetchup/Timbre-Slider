
from load_generative_model import Model
from features import audio_features, batch_compute_features
from vae_train import VAE, prepare_data, train_vae
from plotting import plot_loss
from IPython.display import Audio, display
from ipywidgets import interact, FloatSlider
import numpy as np
import os
import torch
import librosa as li
from ipywidgets import FloatSlider, interact

def simple_timbre_slider_interface(metadata_keys, z, initial_values, vae, model, sr):
    """
    Creates interactive sliders for timbre manipulation and displays audio output.

    Args:
        metadata_keys (list): List of timbre attribute names.
        z (torch.Tensor): Latent vector.
        initial_values (list): Initial slider values.
        vae (VAE): Trained VAE model.
        model (Model): Generative model.
        sr (int): Sample rate for audio playback and feature extraction.
    """
    sliders = [FloatSlider(
            value=z[:, i].mean().item(),
            min=-5,
            max=5,
            step=0.01,
            description=f'{key}:',
            orientation='horizontal',
            readout=True,
            readout_format='.2f',
            continuous_update=False
        )
    for i, key in enumerate(metadata_keys)]

    slider_kwargs = {f'slider_{i}': sliders[i] for i in range(len(sliders))}

    def shift_timbre(**kwargs):
        slider_vals = [kwargs[f'slider_{i}'] for i in range(len(sliders))]
        z_shifted = z.clone()
        for i, val in enumerate(slider_vals):
            diff = val - initial_values[i]
            z_shifted[:, i] += diff
        with torch.no_grad():
            vae_decoded = vae.decode(z_shifted)
        vae_decoded_np = vae_decoded.numpy().T[np.newaxis, :, :]
        recon_audio = model.decode(vae_decoded_np)
        display(Audio(recon_audio, rate=sr, normalize=True))
        ics = audio_features(recon_audio, sr=sr)
        for key, val in ics.items():
            print(f"  {key}: {val}")

    interact(shift_timbre, **slider_kwargs)