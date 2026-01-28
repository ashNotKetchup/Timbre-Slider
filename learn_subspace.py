# %% [markdown]
#  This notebook learns a subspace of a latent space based on examples


# %%

# Refactored: import from new modules
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


# %%
# Model and data setup
model_name: str = 'percussion'
model_location:str = 'generative_models/'+model_name+'.ts'
control_model_location = 'control_models/vae_scripted_model.ts'
# model_type = 'RAVE'
model_type = 'STABLE_AUDIO'
model = Model(model_type=model_type, model_path=[model_location])

feature_type = 'audio_commons'
# feature_type = 'raw_features'
# feature_type = 'audio_commons'
# feature_type = 'PCA'

sr: int =44100
# Get all sound files from the 'sounds' folder
sound_files = [f for f in os.listdir('sounds') if f.endswith(('.wav', '.aif', '.mp3', '.ogg'))]
sound_data = batch_compute_features(sound_files, use_recon=True, model=model, feature_type=feature_type)


latent_data, metadata_vectors, metadata_keys, input_dim, latent_dim = prepare_data(sound_data)

# Instantiate and train VAE
vae = VAE(input_dim=input_dim, latent_dim=latent_dim)
vae, loss_lists, labels = train_vae(vae, latent_data, metadata_vectors, num_epochs=500, batch_size=128, learning_rate=1e-4)

# Plot VAE training losses, all scaled to [0, 1] for comparison
plot_loss(loss_lists, labels)

print(f'Timbre attributes are: {metadata_keys}')

audio_sample = sound_files[1]  # Use the second sound file as an example
y, sr_ = li.load(os.path.join('sounds', audio_sample), sr=None)

# encode with model and vae
encoding = model.encode(y)[0].squeeze(0).T  # shape: (1, latent_dim, time)
encoding_tensor = torch.tensor(encoding, dtype=torch.float32)

with torch.no_grad():
    mu, logvar = vae.encode(encoding_tensor)
    z = vae.reparameterize(mu, logvar)

# %%
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

# Use a dictionary to map slider names to slider widgets
slider_kwargs = {f'slider_{i}': sliders[i] for i in range(len(sliders))}

initial_values = [z[:, i].mean().item() for i in range(len(metadata_keys))]

def shift_timbre(**kwargs):
    # Get slider values in order
    slider_vals = [kwargs[f'slider_{i}'] for i in range(len(sliders))]
    # print(f"Slider values: {slider_vals}")
    z_shifted = z.clone()
    for i, val in enumerate(slider_vals):
        diff = val - initial_values[i]
        z_shifted[:, i] += diff
    with torch.no_grad():
        vae_decoded = vae.decode(z_shifted)
    vae_decoded_np = vae_decoded.numpy().T[np.newaxis, :, :]
    recon_audio = model.decode(vae_decoded_np)
    display(Audio(recon_audio, rate=sr_, normalize=False))
    # plot_spectrograms
    # plot_latent_trajectory
    # plot_features

    ics = audio_features(recon_audio, sr=sr_)
    for key, val in ics.items():
        print(f"  {key}: {val}")


# Use interact with the unpacked slider dictionary
interact(shift_timbre, **slider_kwargs)