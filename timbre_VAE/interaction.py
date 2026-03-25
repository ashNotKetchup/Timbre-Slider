from ipywidgets import interact, FloatSlider, Dropdown, VBox, jslink, interactive_output, IntSlider, Label, fixed
from IPython.display import Audio, display
import numpy as np

def slider_to_audio(position, audio_sample, sorted_corpus, latent_model, control_model=None):
    left_index = int(np.floor(position))
    right_index = min(left_index + 1, len(sorted_corpus) - 1)
    alpha = position - left_index
    encoding = audio_sample['encoding']
    if control_model is not None:
        encoding = control_model.model.encode_z(torch.tensor(encoding, dtype=torch.float32))
    interp_latent = encoding + position
    if control_model is not None:
        import torch
        with torch.no_grad():
            decoded_latent = control_model.decode(interp_latent)
        from scipy.ndimage import gaussian_filter1d
        dl_np = decoded_latent.cpu().numpy() if hasattr(decoded_latent, 'cpu') else np.array(decoded_latent)
        dl_np = gaussian_filter1d(dl_np, sigma=2.0, axis=0) # Smooth latent frames
        interp_latent = torch.tensor(dl_np) if hasattr(decoded_latent, 'cpu') else dl_np
    recon_audio = latent_model.decode(interp_latent)
    return recon_audio, interp_latent

def make_slider(max_val, min_val=0, step=0.01, default=0, description='Interpolation'):
    return FloatSlider(min=min_val, max=max_val, step=step, value=default, description=description)
