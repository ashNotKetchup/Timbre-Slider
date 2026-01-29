# %% [markdown]
#  This notebook learns a subspace of a latent space based on examples


# %%

# Refactored: import from new modules
from load_generative_model import Model
from features import audio_features, batch_compute_features, get_features, calculate_effect_size_matrix
from vae_train import VAE, prepare_data, train_vae
from plotting import plot_loss, plot_effect_size_correlations
from IPython.display import Audio, display
from ipywidgets import interact, FloatSlider
import numpy as np
import os
import torch
import librosa as li
from ipywidgets import FloatSlider, interact
from interface import simple_timbre_slider_interface
import pickle
import pandas as pd

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
effect_size_matrix = calculate_effect_size_matrix(vae, z, model, metadata_keys, feature_type=feature_type)

# Visualize effect sizes using the plotting utility
correlation_df, fig = plot_effect_size_correlations(effect_size_matrix, metadata_keys)
print("Correlations between x and attributes for each dimension:")
print(correlation_df)

# %%

# plot a dimension against all attributes
import matplotlib.pyplot as plt

def plot_dimension_effects(dimension_to_plot=0):
    plt.figure(figsize=(10, 6))
    df_dim = effect_size_matrix[effect_size_matrix['dim'] == dimension_to_plot]
    for attr in metadata_keys:
        plt.plot(df_dim['x'], df_dim[attr], label=attr)
    plt.xlabel('Delta')
    plt.ylabel('Attribute Change')
    plt.title(f'Effect of Latent Dimension {dimension_to_plot} on Attributes')
    plt.legend()
    plt.grid(True)
    plt.show()

interact(plot_dimension_effects, dimension_to_plot=(0, latent_dim-1, 1))
# plot_dimension_effects(dimension_to_plot=0)

# %%

# Get initial values for each latent dimension
initial_values = [z[:, i].mean().item() for i in range(len(metadata_keys))]

# Interactive timbre slider interface
simple_timbre_slider_interface(metadata_keys, z, initial_values, vae, model, sr)

