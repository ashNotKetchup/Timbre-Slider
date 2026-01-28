# %% [markdown]
#  This notebook learns a subspace of a latent space based on examples


# %%

# Refactored: import from new modules
from load_generative_model import Model
from features import audio_features, batch_compute_features, get_features
from vae_train import VAE, prepare_data, train_vae
from plotting import plot_loss
from IPython.display import Audio, display
from ipywidgets import interact, FloatSlider
import numpy as np
import os
import torch
import librosa as li
from ipywidgets import FloatSlider, interact
from interface import simple_timbre_slider_interface
import pickle

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

sample_folder = 'sounds'
feature_save_path='features/' + sample_folder + model_type + '_' + feature_type + '_preprocessed_sound_data.pkl'

sr: int =44100
# Get all sound files from the 'sample_folder' folder
sound_files = [f for f in os.listdir(sample_folder) if f.endswith(('.wav', '.aif', '.mp3', '.ogg'))]

# %%
# Preprocess data
sound_data = get_features(sound_files, feature_type, model=model, save_path=feature_save_path, overwrite=False)
latent_data, metadata_vectors, metadata_keys, input_dim, latent_dim = prepare_data(sound_data)
print(f'Timbre attributes are: {metadata_keys}')


# %%
# Add a sample of our choice to the dataset
example_sound_file = 'EX_Noise_120_waterfall_creaks.wav'  # Replace with your desired sound file
example_folder = 'example_sounds'
sound_files.append(batch_compute_features([example_sound_file], root_folder=example_folder, use_recon=True, model=model, feature_type=feature_type))


# %%
# Instantiate and train VAE
vae = VAE(input_dim=input_dim, latent_dim=latent_dim)
vae, loss_lists, loss_labels = train_vae(vae, latent_data, metadata_vectors, num_epochs=500, batch_size=128, learning_rate=1e-4)

# Plot VAE training losses, all scaled to [0, 1] for comparison
plot_loss(loss_lists, loss_labels)

# %%
# Audio example
y, sr = li.load(os.path.join(example_folder, example_sound_file), sr=sr)

# encode with model and vae
encoding = model.encode(y)[0].squeeze(0).T  # shape: (1, latent_dim, time)
encoding_tensor = torch.tensor(encoding, dtype=torch.float32)

with torch.no_grad():
    mu, logvar = vae.encode(encoding_tensor)
    z = vae.reparameterize(mu, logvar)

# %%

# Test VAE performance on the example sound
# For each latent dimension i, intervening on z_i should cause a large, specific change in attribute a_i,
# and minimal change in all other attributes.

# A: Calculate effect size matrix
def calculate_effect_size_matrix(vae, z_init, model, metadata_keys, delta=1.0, sr=44100, feature_type=feature_type):
    """
    For each latent dimension, move z along that axis and measure the change in audio attributes.
    Returns a matrix of shape (num_latent_dims, num_attributes).
    """
    num_dims = z_init.shape[1]
    num_attrs = len(metadata_keys)
    effect_size_matrix = []
    with torch.no_grad():
        for i in range(num_dims):
            # Perturb z along dimension i
            delta_vals = [-1, -0.5, 0, 0.5, 1]
            z_vals = []
            for d in delta_vals:
                z_new = z_init.clone()
                z_new[:, i] += d
                z_vals.append(z_new)
            
            # Decode to attribute space
            recon_audio = [model.decode(vae.decode(z)) for z in z_vals]
            attrs = [audio_features(audio, use_mean=True, feature_type=feature_type) for audio in recon_audio]
            attrs_array = np.array([[attr[key] for key in metadata_keys] for attr in attrs])
            correlations = np.corrcoef(delta_vals, attrs_array.T)
            effect_size_matrix.append(correlations[0, 1:])  # Correlation of delta with each attribute
    return effect_size_matrix

calculate_effect_size_matrix(vae, z, model, metadata_keys, feature_type=feature_type)

# Get initial values for each latent dimension
initial_values = [z[:, i].mean().item() for i in range(len(metadata_keys))]

import matplotlib.pyplot as plt

# For each axis in the latent space, vary it and plot the effect on each attribute
num_steps = 11
axis_range = np.linspace(-3, 3, num_steps)
attribute_impacts = {key: [] for key in metadata_keys}

for axis in range(len(metadata_keys)):
    z_test = z.clone().detach().repeat(num_steps, 1)
    for i, val in enumerate(axis_range):
        z_test[i, axis] = val
    with torch.no_grad():
        recon_mu = vae.decode(z_test)
    # Calculate attributes for each reconstruction
    for i, key in enumerate(metadata_keys):
        attribute_impacts[key].append(recon_mu[:, i].cpu().numpy())
        [i]

# Plot
fig, axs = plt.subplots(len(metadata_keys), 1, figsize=(8, 3 * len(metadata_keys)))
if len(metadata_keys) == 1:
    axs = [axs]
for i, key in enumerate(metadata_keys):
    for axis in range(len(metadata_keys)):
        axs[i].plot(axis_range, [attr[i] for attr in attribute_impacts[key]], label=f'Axis {axis}')
    axs[i].set_title(f'Impact of Latent Axes on Attribute: {key}')
    axs[i].set_xlabel('Latent Value')
    axs[i].set_ylabel('Attribute Value')
    axs[i].legend()
plt.tight_layout()
plt.show()


simple_timbre_slider_interface(metadata_keys, z, initial_values, vae, model, sr)
# Use interact with the unpacked slider dictionary
# interact(shift_timbre, **slider_kwargs)
# %%
