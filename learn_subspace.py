
# %% [markdown]
#  This notebook learns a subspace of a latent space based on examples


# %%
# Import necessary libraries
from load_generative_model import Model
from IPython.display import Audio, display
# from gui import interface
import librosa as li
import torch

import numpy as np
import os
from pathlib import Path
import IPython.display as ipd
from ipywidgets import interact, IntSlider
import matplotlib.pyplot as plt
import os
import random
import numpy as np
from ipywidgets import FloatSlider, IntSlider, interact, VBox, Label, fixed
from ipywidgets import Dropdown
import matplotlib.pyplot as plt
from ipywidgets import Dropdown, interact, FloatSlider, IntSlider, fixed, VBox
from scipy.signal import resample
import librosa as li
import numpy as np
import os
import torch
from itertools import product
from ipywidgets import VBox
from ipywidgets import FloatSlider, interact
from ipywidgets import VBox, FloatSlider, interact



# %%
# Model and data setup
model_name: str = 'percussion'
model_location:str = 'generative_models/'+model_name+'.ts'
control_model_location = 'control_models/vae_scripted_model.ts'
audio_sample = 'UMRU_chord_loop_atmosphere_140_Abmin.wav'
# model_type = 'RAVE'
model_type = 'STABLE_AUDIO'


# Options:  'RAVE', 'STABLE_AUDIO'
model = Model(model_type=model_type, model_path=[model_location])
# model = Model(model_type='STABLE_AUDIO', model_path=[model_location, control_model_location])
sr: int =44100
# Get all sound files from the 'sounds' folder
sound_files = [f for f in os.listdir('sounds') if f.endswith(('.wav', '.aif', '.mp3', '.ogg'))]


# %%
# Loading and analysing samples – First, we load our sample library. Then we compute the audio features and encodings for the sounds.
def audio_features(audio_y, sr=44100):
            '''Compute timbre features for each audio file and its encoding'''
                
            # Compute spectral centroid
            spectral_centroid = li.feature.spectral_centroid(y=audio_y, sr=sr)[0]
            
            # Take the mean spectral centroid across time
            mean_centroid = np.mean(spectral_centroid)
            
            # Compute spectral flatness
            spectral_flatness = li.feature.spectral_flatness(y=audio_y)[0]
            mean_flatness = np.mean(spectral_flatness)

            # Compute zero crossing rate as another timbre feature
            zero_crossings = li.feature.zero_crossing_rate(y=audio_y)[0]
            mean_zero_crossings = np.mean(zero_crossings)

            
            audio_features = {
                'spectral_centroid': mean_centroid,
                'spectral_flatness': mean_flatness,
                'zero_crossing_rate': mean_zero_crossings,
            }
            return audio_features

def get_pitch(y, sr):
    pitches, mags = li.piptrack(y=y, sr=sr)
    pitch_values = pitches[mags.argmax(axis=0), np.arange(mags.shape[1])]
    return pitch_values.reshape(1, -1)

def batch_compute_features(sound_files, use_recon:bool=True, model=None, use_mean:bool=False):
    audio_features = []
    for sound_file in sound_files:
        if use_recon and model is None:
                raise ValueError("Model must be provided if use_recon is True.")
        
        try:
            audio_features.append(
                 {
                'filename': sound_file,
                'focus': False,
                'raw_audio': (y := li.load(os.path.join('sounds', sound_file), sr=None)[0]),
                'recon_audio': (y_recon := model.decode(model.encode(y)[0]) if use_recon else None),
                'sr': (sr_ := li.get_samplerate(os.path.join('sounds', sound_file)) if hasattr(li, 'get_samplerate') else li.load(os.path.join('sounds', sound_file), sr=None)[1]),
                'encoding': (enc := model.encode(y)[0]),
                'encoding_mean': enc.mean(axis=-1),
                'encoding_std': enc.std(axis=-1),
                'features_raw': {
                    'spectral_centroid': (centroid := li.feature.spectral_centroid(y=y, sr=sr_).mean()),
                    'spectral_flatness': (flatness := li.feature.spectral_flatness(y=y).mean()),
                    'zero_crossing_rate': (zcr := li.feature.zero_crossing_rate(y).mean()),
                    'loudness': (loudness := li.feature.rms(y=y).mean()),
                    # 'pitch': (pitch := li.feature.pitch.yin(y, fmin=li.note_to_hz('C2'), fmax=li.note_to_hz('C7')).mean())
                },
                'features_recon': {
                    'spectral_centroid': (centroid_recon := li.feature.spectral_centroid(y=y_recon, sr=sr_).mean() if use_mean else li.feature.spectral_centroid(y=y_recon, sr=sr_)),
                    'spectral_flatness': (flatness_recon := li.feature.spectral_flatness(y=y_recon).mean() if use_mean else li.feature.spectral_flatness(y=y_recon)),
                    'zero_crossing_rate': (zcr_recon := li.feature.zero_crossing_rate(y_recon).mean() if use_mean else li.feature.zero_crossing_rate(y_recon)),
                    'loudness': (loudness_recon := li.feature.rms(y=y_recon).mean() if use_mean else li.feature.rms(y=y_recon)),
                    # Compute features on reconstruction
                    'pitch': get_pitch(y_recon, sr_),
                    # 'pitch': (pitch_recon := li.feature.pitch.yin(y_recon, fmin=li.note_to_hz('C2'), fmax=li.note_to_hz('C7')).mean())
                    }
                }
                 
            )
            # print(f"Processed: {Path(sound_file).name} - Centroid: {centroid_recon:.2f} Hz, Flatness: {flatness_recon:.4f}, Zero Crossings: {zcr_recon:.4f}")
        except Exception as e:
            print(f"Error processing {sound_file}: {e}")
    print(f"\nSuccessfully processed {len(audio_features)} files.")
    print('shapes of features_recon:', [ {k: v.shape if isinstance(v, np.ndarray) else 'scalar' for k, v in item['features_recon'].items()} for item in audio_features])
    return audio_features
        
# Plotting
def plot_sound_features(
    dataset,
    x_feature,
    y_feature,
    splits=None,
    labels=None,
    figsize=(12, 6),
    colors=None,
    markers=None,
    special_filename=None
):
    """
    Plot features from a sound_data-like dataset, optionally split by keys in `splits`.
    - dataset: list of dicts (sound_data_sorted).
    - x_feature: feature name (str) or 'filename' for x-axis.
    - y_feature: feature name (str) for y-axis.
    - splits: list of keys to split features (e.g. ['features_recon', 'features_raw']).
    - labels: list of labels for each point (optional).
    - colors: list of colors for each split (optional).
    - markers: list of marker styles for each split (optional).
    """
    # Highlight a special filename if provided
    
    special_color = '#e41a1c'  # red
    special_marker = '*'
    # You can set special_filename to a string, e.g. 'Kick C78.aif'
    # special_filename = 'Kick C78.aif'

    # Prepare to collect special points
    special_points = []

    # Remove special filename from normal plotting if present
    if special_filename is not None:
        dataset_normal = [d for d in dataset if d['filename'] != special_filename]
        special_points = [d for d in dataset if d['filename'] == special_filename]
    else:
        dataset_normal = dataset

    # Use dataset_normal for the main plotting loop below
    dataset = dataset_normal

    if splits is None:
        splits = [None]
    if labels is None:
        labels = [d['filename'] for d in dataset]
    if colors is None:
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']  # default matplotlib colors
    if markers is None:
        markers = ['o', 's', '^', 'D']

        
    plt.figure(figsize=figsize)
    for i, split in enumerate(splits):
        color = colors[i % len(colors)]
        marker = markers[i % len(markers)]
        if split is None:
            x_vals = [d[x_feature] if x_feature != 'filename' else d['filename'] for d in dataset]
            y_vals = [d[y_feature] for d in dataset]
            label = y_feature
        else:
            x_vals = [d[x_feature] if x_feature != 'filename' else d['filename'] for d in dataset]
            y_vals = [d[split][y_feature] for d in dataset]
            label = split.replace('features_', '').capitalize()
        plt.plot(x_vals, y_vals, marker=marker, color=color, linestyle='-', label=label)
        for x, y, lbl in zip(x_vals, y_vals, labels):
            plt.annotate(lbl, (x, y), fontsize=9, alpha=0.8, xytext=(5, 5), textcoords='offset points')
    
    # Plot special points with red stars if any
    if special_points:
        x_vals_special = [d[x_feature] if x_feature != 'filename' else d['filename'] for d in special_points]
        y_vals_special = [d[y_feature] for d in special_points]
        plt.plot(x_vals_special, y_vals_special, marker=special_marker, color=special_color, linestyle='None', markersize=14, label='Special')
    plt.xlabel(x_feature.replace('_', ' ').capitalize(), fontsize=13)
    plt.ylabel(y_feature.replace('_', ' ').capitalize(), fontsize=13)
    plt.xticks(rotation=45, ha='right')
    plt.legend(fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.tight_layout()
    plt.show()


def plot_raw_vs_recon(audio_features_recon, audio_features_raw, features, labels):
    plt.figure(figsize=(15, 4 * len(features)))
    for idx, feature in enumerate(features):
        plt.subplot(len(features), 1, idx + 1)
        recon_vals = [audio[feature] for audio in audio_features_recon]
        raw_vals = [audio[feature] for audio in audio_features_raw]
        plt.plot(labels, recon_vals, 'o-', label='Reconstructed')
        plt.plot(labels, raw_vals, 's--', label='Raw')
        plt.ylabel(feature.replace('_', ' ').capitalize())
        plt.xticks(rotation=45, ha='right')
        plt.legend()
        plt.title(f"{feature.replace('_', ' ').capitalize()} (Raw vs. Reconstructed)")
    plt.tight_layout()
    plt.show()


def plot_latent(dim, encodings, labels):
    plt.figure(figsize=(10, 4))
    # print(len(encodings))
    # Assume 'dim' is the latent dimension to plot
    for index, latent in enumerate(encodings):
        # latent shape: (batch, dim, time)
        # Plot the selected dimension over time for the first batch
        plt.plot(latent[0, dim], label=str(labels[index]), color=plt.cm.tab10(index % 10), linewidth=2, alpha=0.7)
    # plt.plot(encodings['interp'][0, dim], label='Interpolated', color='black', linewidth=2)
    # plt.plot(encodings['left'][0, dim], label=f'Left ({labels[encodings["left_index"]]})', color='blue', linestyle='--')
    # plt.plot(encodings['right'][0, dim], label=f'Right ({labels[encodings["right_index"]]})', color='red', linestyle='--')
    plt.xlabel('Time')
    plt.ylabel('Value')
    plt.title(f'Latent Dimension {dim}')
    plt.legend()
    plt.tight_layout()
    plt.show()

def plot_timbre_vs_encoding(sound_data_sorted, quality_dropdown, dimension=0):
        """
        Plots the selected timbre quality against encoding mean and std for each sound in the corpus.
        """
        encoding_means = [item['encoding_mean'][-1][dimension] for item in sound_data_sorted]
        encoding_stds = [item['encoding_std'][-1][dimension] for item in sound_data_sorted]
        timbre_qualities = [item['features_recon'][quality_dropdown.value] for item in sound_data_sorted]
        filenames = [item['filename'] for item in sound_data_sorted]

        plt.figure(figsize=(14, 6))
        plt.subplot(1, 2, 1)
        plt.scatter(encoding_means, timbre_qualities, c='b')
        for i, label in enumerate(filenames):
            plt.annotate(label, (encoding_means[i], timbre_qualities[i]), fontsize=8, alpha=0.7)
        plt.xlabel(f'Encoding Mean (dimension {dimension})')
        plt.ylabel(quality_dropdown.label)
        plt.title(f"{quality_dropdown.label} vs Encoding Mean")

        plt.subplot(1, 2, 2)
        plt.scatter(encoding_stds, timbre_qualities, c='g')
        for i, label in enumerate(filenames):
            plt.annotate(label, (encoding_stds[i], timbre_qualities[i]), fontsize=8, alpha=0.7)
        plt.xlabel(f'Encoding Std (dimension {dimension})')
        plt.ylabel(quality_dropdown.label)
        plt.title(f"{quality_dropdown.label} vs Encoding Std (Variance)")

        plt.tight_layout()
        plt.show()

# Plot spectrograms for left, right, and interpolated audio
def plot_spectrograms(encodings, left_index, right_index, interpolated_audio, labels):
        fig, axs = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
        titles = [
            f"Left: {labels[left_index]}",
            f"Right: {labels[right_index]}",
            "Interpolated"
        ]
        audios = [
            model.decode(encodings[left_index]),
            model.decode(encodings[right_index]),
            interpolated_audio
        ]
        for i, (audio_data, ax, title) in enumerate(zip(audios, axs, titles)):
            S = np.abs(np.fft.rfft(audio_data))
            ax.plot(S)
            ax.set_title(title)
            ax.set_ylabel("Magnitude")
        axs[-1].set_xlabel("Frequency Bin")
        plt.tight_layout()
        plt.show()



# Latent operations
def interpolate_latents(enc_left, enc_right, alpha, latent_length:int=10):
    # Linearly interpolates between two latent encodings enc_left and enc_right
    # based on the interpolation factor alpha (0 <= alpha <= 1).
    # Resamples both encodings to the same length before interpolation

    # Interpolate the latent length between left and right encodings
    left_len = enc_left.shape[-1]
    right_len = enc_right.shape[-1]
    latent_length = int(round((1 - alpha) * left_len + alpha * right_len))

    if latent_length is not None:
        enc_left_resampled = torch.nn.functional.interpolate(torch.from_numpy(enc_left), size=latent_length).numpy()
        enc_right_resampled = torch.nn.functional.interpolate(torch.from_numpy(enc_right), size=latent_length).numpy()
        enc_right_resampled = torch.nn.functional.interpolate(torch.from_numpy(enc_right), size=latent_length).numpy()
    else:
        target_len = min(enc_left.shape[-1], enc_right.shape[-1])
        enc_left_resampled = torch.nn.functional.interpolate(torch.from_numpy(enc_left), size=target_len).numpy()
        enc_right_resampled = torch.nn.functional.interpolate(torch.from_numpy(enc_right), size=target_len).numpy()
    enc_left = enc_left_resampled
    enc_right = enc_right_resampled
    return (1-alpha)*enc_left + alpha*enc_right


def apply_attribute_vector(z1, z2, input, alpha, match_input_length:bool=True):
    ''' 
    Applies an attribute vector between z1 and z2 to the input latent encoding

    'output is to input what z2 is to z1'

    '''
    if match_input_length:
        latent_length = input.shape[-1]
    else:
        # Interpolate the latent length between left and right encodings
        left_len = z1.shape[-1]
        right_len = z2.shape[-1]
        latent_length = int(round((1 - alpha) * left_len + alpha * right_len))
        

    z1_resampled = torch.nn.functional.interpolate(torch.from_numpy(z1), size=latent_length).numpy()
    z2_resampled = torch.nn.functional.interpolate(torch.from_numpy(z2), size=latent_length).numpy()
    input_resampled = torch.nn.functional.interpolate(torch.from_numpy(input), size=latent_length).numpy()

    z1 = z1_resampled
    z2 = z2_resampled
    input = input_resampled

    return alpha*(z2 - z1) + input

# Interactive bits
def slider_to_audio(position:float, audio_sample:dict, sorted_corpus:list[dict],latent_model=model, control_model=None):
    left_index = int(np.floor(position))
    right_index = min(left_index + 1, len(sorted_corpus) - 1)
    alpha = position - left_index
    encoding = audio_sample['encoding']
    if control_model is not None:
        encoding = control_model.encode(encoding)
    # interp_latent = apply_attribute_vector(sorted_corpus[left_index]['encoding'], sorted_corpus[right_index]['encoding'], audio_sample['encoding'], alpha)
    interp_latent = encoding + position
    # interpolate_latents(sorted_corpus[left_index]['encoding'], sorted_corpus[right_index]['encoding'], alpha)
    if control_model is not None:
        interp_latent = control_model.decode(interp_latent)

    recon_audio = latent_model.decode(interp_latent)
    return recon_audio, interp_latent

def make_slider(max_val, min_val=0,  step=0.01, default=0, description='Interpolation'):
    return FloatSlider(min=min_val, max=max_val, step=step, value=default, description=description)



# Construct a unified data structure for each sound using a list comprehension,
sound_data = batch_compute_features(sound_files, use_recon=True, model=model)





# sound_data_sorted = sorted(sound_data, key=lambda x: x['features_recon']['spectral_centroid'])

# %%
# Set up interactive widgets for timbre interpolation
# Dropdown for timbre quality
quality_options = [
    ("Spectral Centroid", "spectral_centroid"),
    ("Spectral Flatness", "spectral_flatness"),
    ("Zero Crossing Rate", "zero_crossing_rate"),
]

latent_dimension_options = [i for i in range(sound_data[0]['encoding'].shape[1])]

dimension_dropdown = Dropdown(options=latent_dimension_options, value=0, description="Latent Dimension:")
quality_dropdown = Dropdown(options=quality_options, value="spectral_centroid", description="Timbre Quality:")
lerp_slider = make_slider(max_val=len(sound_data)-1)

# display(Audio(samples_to_modify[0]['recon_audio'], rate=samples_to_modify[0]['sr']) )

import torch.nn as nn
import torch.optim as optim
import matplotlib.pyplot as plt

# Prepare latent encodings as training data
latent_encodings = [sound['encoding'].squeeze(0).T for sound in sound_data]  # shape: (time, dim)

# Create metadata vectors from 'features_recon' for each sound, resampled to match encoding length
metadata_vectors = []
latent_encodings = []  # Also collect latent encodings here
metadata_keys = list(sound_data[0]['features_recon'].keys())
for sound in sound_data:
    features = []
    enc_len = sound['encoding'].shape[-1]
    # Collect latent encoding for this item

    # Double the encoding length (resolution) for metadata and latent encoding
    enc_len = sound['encoding'].shape[-1] * 4

    # Resample latent encoding to new length and append
    latent_enc = resample(sound['encoding'].squeeze(0).T, enc_len, axis=0)
    latent_encodings.append(latent_enc)
    for key in metadata_keys:
        # Get feature value (could be scalar or array)
        val = sound['features_recon'][key]
        # print(val.shape)
        # If scalar, make it a constant vector; if array, resample to enc_len
        if np.isscalar(val):
            vec = np.full(enc_len, val)
        else:
            vec = resample(val, enc_len, axis=-1)
            # print(vec.shape)

        features.append(vec)  # Each vec is (296, 1)
        # After collecting all features, stack and transpose to (296, 5)
        features_stacked = np.stack(features, axis=-1)  # (296, 5)
    # Stack features into shape (num_features, enc_len)
    features_stacked = np.stack(features, axis=-1).squeeze()
    metadata_vectors.append(features_stacked)

# metadata_vectors: list of arrays, each (num_features, enc_len)
# latent_encodings: list of arrays, each (time, dim)
# metadata_keys: list of feature names in order

print(f'Prepared {len(latent_encodings)} latent encodings and metadata vectors. Shape of first latent encoding: {latent_encodings[0].shape}, first metadata vector: {metadata_vectors[0].shape}')
latent_data = np.concatenate(latent_encodings, axis=0)  # shape: (total_time, dim)
latent_data = torch.tensor(latent_data, dtype=torch.float32)

input_dim = latent_data.shape[1]
vae_latent_dim = len(metadata_keys)  # Number of metadata features

# # Hyperparameter search for VAE
# # You can use grid search or random search to find good hyperparameters.
# # Example: Try different latent_dim, learning rates, and batch sizes.


# latent_dims = [2, 4, 8]
# learning_rates = [1e-3, 5e-4]
# batch_sizes = [128, 256]

# best_loss = float('inf')
# best_params = None

# for latent_dim, lr, batch_size in product(latent_dims, learning_rates, batch_sizes):
#     vae = VAE(input_dim=input_dim, latent_dim=latent_dim)
#     optimizer = optim.Adam(vae.parameters(), lr=lr)
#     loss_fn = nn.MSELoss(reduction='sum')
#     vae.train()
#     for epoch in range(20):  # Short training for search
#         perm = torch.randperm(latent_data.size(0))
#         total_loss = 0
#         for i in range(0, latent_data.size(0), batch_size):
#             idx = perm[i:i+batch_size]
#             batch = latent_data[idx]
#             optimizer.zero_grad()
#             recon, mu, logvar = vae(batch)
#             loss = vae_loss(recon, batch, mu, logvar)
#             loss.backward()
#             optimizer.step()
#             total_loss += loss.item()
#     if total_loss < best_loss:
#         best_loss = total_loss
#         best_params = (latent_dim, lr, batch_size)

# print(f"Best hyperparameters: latent_dim={best_params[0]}, lr={best_params[1]}, batch_size={best_params[2]}, loss={best_loss:.2f}")

# %% 
# VAE definition
class VAE(nn.Module):
    def __init__(self, input_dim, latent_dim):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
        )
        self.fc_mu = nn.Linear(16, latent_dim)
        self.fc_logvar = nn.Linear(16, latent_dim)
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 16),
            nn.ReLU(),
            nn.Linear(16, 32),
            nn.ReLU(),
            nn.Linear(32, input_dim)
        )

    def encode(self, x):
        h = self.encoder(x)
        return self.fc_mu(h), self.fc_logvar(h)

    def reparameterize(self, mu, logvar):
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def decode(self, z):
        return self.decoder(z)

    def forward(self, x):
        mu, logvar = self.encode(x)
        z = self.reparameterize(mu, logvar)
        recon = self.decode(z)
        return recon, mu, logvar
    

def attribute_distance_loss_dimwise_vectorised(
    z,
    x_attr,
    delta=1.0,
    eps=1e-8,
):
    """
    Vectorised dimension-wise attribute regularisation.

    Args:
        z: Latent samples, shape (B, D)
        x_attr: Attribute outputs, shape (B, D)
        delta: Tanh spread hyperparameter
        eps: Sign stabilisation constant

    Returns:
        Scalar loss
    """
    B = z.shape[0]
    device = z.device

    # print(f'z.shape={z.shape}, x_attr.shape={x_attr.shape}')

    # Ensure z and x_attr are 2D and have the same shape (B, D)
    if z.ndim != 2 or x_attr.ndim != 2:
        raise ValueError("z and x_attr must be 2D tensors of shape (B, D)")
    if z.shape != x_attr.shape:
        raise ValueError(f"Shape mismatch: z.shape={z.shape}, x_attr.shape={x_attr.shape}")

    # Pairwise differences per dimension
    # Shapes: (B, B, D)
    Dz = torch.abs(z[:, None, :] - z[None, :, :])
    Dx = torch.abs(x_attr[:, None, :] - x_attr[None, :, :])

    # Transform
    latent_term = torch.tanh(delta * Dz)
    attr_term = torch.sign(Dx + eps)

    # # Upper triangular mask (i < j)
    # pair_mask = torch.triu(
    #     torch.ones(B, B, device=device, dtype=torch.bool),
    #     diagonal=1
    # )

    # # Broadcast mask to (B, B, D)
    # pair_mask = pair_mask.unsqueeze(-1).expand(-1, -1, z.shape[1])

    # MAE over valid pairs and dimensions
    loss = torch.abs(latent_term - attr_term).mean()

    return loss


# Instantiate and train VAE
vae = VAE(input_dim=input_dim, latent_dim=vae_latent_dim)
optimizer = optim.Adam(vae.parameters(), lr=1e-4)
loss_fn = nn.MSELoss(reduction='sum')

def vae_loss(recon_x, x, mu, logvar, x_attr, vae):
    alpha = 1.0  # Reconstruction loss weight
    beta = 0.1  # KL divergence weight
    theta = 10.0  # Attribute loss weight


    z = vae.reparameterize(mu, logvar)
    recon_loss = loss_fn(recon_x, x)
    kl = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())
    attr_loss = attribute_distance_loss_dimwise_vectorised(z, x_attr, delta=1.0)
    loss = alpha*recon_loss + beta*kl + theta*attr_loss
    return loss, (recon_loss, kl, attr_loss)

# Track losses for plotting
loss_history = []


# Training loop to record loss
vae.train()
epochs = 1000
batch_size = 256
total_loss_history = []
recon_loss_history = []
kl_loss_history = []
attr_loss_history = []

for epoch in range(epochs):
    perm = torch.randperm(latent_data.size(0))
    total_loss = 0
    recon_epoch = 0
    kl_epoch = 0
    attr_epoch = 0
    for i in range(0, latent_data.size(0), batch_size):
        idx = perm[i:i+batch_size]
        batch = latent_data[idx]
        # metadata_vectors is a list of arrays, each (num_features, enc_len)
        # We need to concatenate all metadata_vectors along time axis to match latent_data
        metadata_data = np.concatenate([m for m in metadata_vectors], axis=0)  # shape: (total_time, num_features)
        metadata_data = torch.tensor(metadata_data, dtype=torch.float32)
        x_attr = metadata_data[idx]
        optimizer.zero_grad()
        recon, mu, logvar = vae(batch)
        loss, (recon_loss, kl, attr_loss) = vae_loss(recon, batch, mu, logvar, x_attr, vae)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
        recon_epoch += recon_loss.item()
        kl_epoch += kl.item()
        attr_epoch += attr_loss.item()
    total_loss_history.append(total_loss)
    recon_loss_history.append(recon_epoch)
    kl_loss_history.append(kl_epoch)
    attr_loss_history.append(attr_epoch)
    if (epoch+1) % 10 == 0:
        print(f"Epoch {epoch+1}/{epochs}, Loss: {total_loss:.2f}")

# Plot VAE training losses, all scaled to [0, 1] for comparison
plt.figure(figsize=(10, 6))
loss_lists = [total_loss_history, recon_loss_history, kl_loss_history, attr_loss_history]
labels = ['Total Loss', 'Recon Loss', 'KL Loss', 'Attr Loss']
for losses, label in zip(loss_lists, labels):
    arr = np.array(losses)
    arr_min, arr_max = arr.min(), arr.max()
    if arr_max > arr_min:
        arr_scaled = (arr - arr_min) / (arr_max - arr_min)
    else:
        arr_scaled = arr  # avoid division by zero if constant
    plt.plot(arr_scaled, label=label)
plt.xlabel('Epoch')
plt.ylabel('Scaled Loss')
plt.title('VAE Training Losses (Scaled)')
plt.legend()
plt.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()
plt.show()

# Select a sample sound file
sample_idx = 0
sample_file = sound_files[sample_idx]
y, sr_ = li.load(os.path.join('sounds', sample_file), sr=None)

# 1. Original audio
print("Original audio:")
display(Audio(y, rate=sr_))

# 2. After going through the model (encode + decode)
encoding = model.encode(y)[0]
recon_audio = model.decode(encoding)
print("After model (encode + decode):")
display(Audio(recon_audio, rate=sr_))

# 3. After going through the model and the VAE
# Flatten encoding to (time, dim)
encoding_flat = encoding.squeeze(0).T
encoding_flat_tensor = torch.tensor(encoding_flat, dtype=torch.float32)
with torch.no_grad():
    mu, logvar = vae.encode(encoding_flat_tensor)
    z = vae.reparameterize(mu, logvar)
    vae_decoded = vae.decode(z)
vae_decoded_np = vae_decoded.numpy()
# Reshape back to (1, dim, time)
vae_decoded_np = vae_decoded_np.T[np.newaxis, :, :]
vae_recon_audio = model.decode(vae_decoded_np)
print("After model and VAE:")
display(Audio(vae_recon_audio, rate=sr_))

# To encode or decode: vae.encode(x), vae.decode(z)



def plot_feature_alignment(model, sound_files, file_index=1, feature_names=None, plot_encoding_axes=True, vae=None):
    """
    Loads a sound file, encodes and decodes it with the given model, computes audio features
    on the reconstruction, and plots features vs encoding axes over time.
    Optionally also plots the axes of the VAE applied to the model encoding.

    Args:
        model: The generative model with encode and decode methods.
        sound_files: List of sound file paths (relative or absolute).
        file_index: Index of the sound file to use for testing.
        feature_names: Optional list of feature names to plot (default: all).
        plot_encoding_axes: If True, plot encoding axes alongside features.
        vae: Optional VAE model to plot its axes as well.
    """
    import matplotlib.pyplot as plt

    example_file = sound_files[file_index]
    y, sr_ = li.load(os.path.join('sounds', example_file), sr=None)

    # Encode and decode
    encoding = model.encode(y)[0]  # shape: (1, latent_dim, time)
    recon_audio = model.decode(encoding)

    # Compute features on reconstruction
    centroid = li.feature.spectral_centroid(y=recon_audio, sr=sr_)[0]
    flatness = li.feature.spectral_flatness(y=recon_audio)[0]
    zcr = li.feature.zero_crossing_rate(y=recon_audio)[0]
    loudness = li.feature.rms(y=recon_audio)[0]
    pitches, mags = li.piptrack(y=recon_audio, sr=sr_)
    pitch = pitches[mags.argmax(axis=0), np.arange(mags.shape[1])]

    # Resample features to match encoding time axis
    num_points = encoding.shape[-1]
    centroid_rs = resample(centroid, num_points)
    flatness_rs = resample(flatness, num_points)
    zcr_rs = resample(zcr, num_points)
    loudness_rs = resample(loudness, num_points)
    pitch_rs = resample(pitch, num_points)

    features_dict = {
        'Spectral Centroid (Hz)': centroid_rs,
        'Spectral Flatness': flatness_rs,
        'Zero Crossing Rate': zcr_rs,
        'Loudness (RMS)': loudness_rs,
        'Pitch (Hz)': pitch_rs
    }

    if feature_names is not None:
        features_dict = {k: v for k, v in features_dict.items() if k in feature_names}

    # Prepare VAE encoding if provided
    vae_encoding = None
    if vae is not None:
        encoding_flat = encoding.squeeze(0).T  # shape: (time, dim)
        encoding_flat_tensor = torch.tensor(encoding_flat, dtype=torch.float32)
        with torch.no_grad():
            mu, logvar = vae.encode(encoding_flat_tensor)
            z = vae.reparameterize(mu, logvar)
        vae_encoding = z.numpy().T  # shape: (latent_dim, time)

    plt.figure(figsize=(15, 3 * len(features_dict)))
    for i, (feature_name, feature_vals) in enumerate(features_dict.items()):
        plt.subplot(len(features_dict), 1, i + 1)
        plt.plot(feature_vals, label=feature_name, color='tab:blue')
        plt.plot(np.arange(len(feature_vals)), feature_vals, 's', color='tab:blue', markersize=5, alpha=0.7)
        if plot_encoding_axes and i < encoding.shape[1]:
            plt.plot(encoding[0, i], label=f'Encoding axis {i}', color='tab:orange', alpha=0.7)
            plt.plot(np.arange(encoding.shape[-1]), encoding[0, i], 's', color='tab:orange', markersize=5, alpha=0.7)
        if vae_encoding is not None and i < vae_encoding.shape[0]:
            plt.plot(vae_encoding[i], label=f'VAE axis {i}', color='tab:green', alpha=0.7)
            plt.plot(np.arange(vae_encoding.shape[1]), vae_encoding[i], 's', color='tab:green', markersize=5, alpha=0.7)
        plt.xlabel('Time')
        plt.ylabel(feature_name)
        plt.title(f'{feature_name} and Encoding axes vs Time')
        plt.legend()
    plt.tight_layout()
    plt.show()

# Test the model performance on a specific sound file
plot_feature_alignment(model, sound_files, file_index=1, feature_names=None, plot_encoding_axes=True, vae=vae)



# %%
#

# Function to update sorting and interpolation
def update_interpolation(timbre_quality, x, dimension):
    # Sort audio and encodings by selected timbre quality
    # Construct a unified data structure for each sound using a list comprehension,
    corpus = batch_compute_features(sound_files, use_recon=True, model=model, use_mean=True)
    sorted_corpus = sorted(corpus, key=lambda x: x['features_recon'][timbre_quality])
    left_index = int(np.floor(x))
    right_index = min(left_index + 1, len(sorted_corpus) - 1)
    alpha = x - left_index

    #apply attribute vector between left and right to the sample encoding
    interp_audio, interp_latent = slider_to_audio(x, sorted_corpus[left_index], sorted_corpus)


    left_audio, left_latent = sorted_corpus[left_index]['raw_audio'], sorted_corpus[left_index]['encoding']
    right_audio, right_latent = sorted_corpus[right_index]['raw_audio'],  sorted_corpus[right_index]['encoding']


    # Append the interpolated sound to the sorted_corpus with a label
    interp_features = audio_features(interp_audio, sr=sr)
    interp_entry = {
        'filename': 'Interpolated',
        'focus': True,
        'raw_audio': interp_audio,
        'sr': sr,
        'encoding': interp_latent,
        'encoding_mean': interp_latent.mean(axis=-1),
        'encoding_std': interp_latent.std(axis=-1),
        'features_recon': interp_features,
        'features_raw': interp_features
    }
    corpus_with_interp = sorted_corpus + [interp_entry]

    # NEW CODE HERE
    print('interp shape', interp_entry['encoding_mean'].shape)

    # Prepare splits for plotting: 'features_recon' for corpus, 'features_recon' for interpolated
    splits = ['features_recon']
    labels = [item['filename'] for item in corpus_with_interp]
    
    display(Audio(interp_audio, rate=sr)  )
    plot_latent(dimension, [left_latent, interp_latent, right_latent], [sorted_corpus[left_index]['filename'], 'Interpolation', sorted_corpus[right_index]['filename']])
    plot_sound_features(
        corpus_with_interp,
        x_feature='filename',
        y_feature=timbre_quality,
        splits=splits,
        labels=labels,
        special_filename='Interpolation'
    )


   
    
    plot_timbre_vs_encoding(sorted_corpus, quality_dropdown, dimension)
    
    # plot_spectrograms(resampled_encodings, left_index, right_index, interp_audio, [audio['filename'] for audio in sorted_corpus])
    print(f"Interpolating between {sorted_corpus[left_index]['filename']} and {sorted_corpus[right_index]['filename']} (alpha={alpha:.2f}), sorted by {timbre_quality.replace('_',' ')}")
    # print(f'Interpolated audio has {audio_features(interp_audio)}')


# Use interact to link dropdown and sliders

# interact(update_interpolation, corpus=fixed(sound_data), timbre_quality=quality_dropdown, x=lerp_slider, dimension=dimension_dropdown)






# %%
# Timbre shifting with VAE sliders


def timbre_shift_example(encoding_flat_tensor, timbre_model, features_dict=None):
    # Pass through VAE to get latent representation
    with torch.no_grad():
        mu, logvar = timbre_model.encode(encoding_flat_tensor)
        z = timbre_model.reparameterize(mu, logvar)  # (time, vae_latent_dim)

    # Compute average per VAE channel for slider defaults
    z_avg = z.mean(dim=0).numpy()  # shape: (vae_latent_dim)

    # 4. Prepare sliders labeled by features_dict keys
    feature_labels = list(features_dict.keys()) if features_dict is not None else []
    sliders = [
        FloatSlider(
            value=z_avg[i],
            min=z_avg[i] - 2.0,
            max=z_avg[i] + 2.0,
            step=0.01,
            description=feature_labels[i] if i < len(feature_labels) else f"Attr {i}"
        )
        for i in range(len(z_avg))
    ]

    def update_from_sliders(*slider_vals):
        # Shift the VAE encoding by slider deltas and decode
        print(f"Slider values changed: {slider_vals}")  # Print every time sliders are changed
        z_shifted = z.clone()
        for i, val in enumerate(slider_vals):
            delta = val - z_avg[i]
            z_shifted[:, i] += delta
        with torch.no_grad():
            vae_decoded = timbre_model.decode(z_shifted)
        vae_decoded_np = vae_decoded.numpy().T[np.newaxis, :, :]
        recon_audio = model.decode(vae_decoded_np)
        display(Audio(recon_audio, rate=sr_))

    # Show the sliders in a vertical box
    slider_box = VBox(sliders)
    display(slider_box)
    interact(update_from_sliders, **{f"attr_{i}": sliders[i] for i in range(len(sliders))})

# 1. Load and encode the example sound
y, sr_ = li.load(os.path.join('sounds', audio_sample), sr=None)
encoding = torch.tensor(model.encode(y)[0].squeeze(0).T)   # shape: (time, dim)

timbre_shift_example(encoding, vae, features_dict={key: key for key in metadata_keys})
# %%
# Create multiple labeled sliders
sliders = [
    FloatSlider(
        min=0,
        max=10,
        step=0.1,
        value=5,
        description=f'Value {i}:',
        orientation='vertical',
        readout=True,
        readout_format='.1f'
    )
    for i in range(3)
]

# Track previous values to detect changes
prev_vals = [slider.value for slider in sliders]

def on_slider_change(*vals):
    changed = [i for i, (old, new) in enumerate(zip(prev_vals, vals)) if old != new]
    if changed:
        print(f"Changed slider(s): {changed}, New values: {vals}")
    else:
        print(f"No change. Current values: {vals}")
    # Update previous values
    for i, val in enumerate(vals):
        prev_vals[i] = val

from IPython.display import display
from ipywidgets import interact, VBox, FloatSlider
from ipywidgets import FloatSlider, jslink
import numpy as np

slider_box = VBox(sliders, layout={'flex_flow': 'row'})
display(slider_box)
interact(on_slider_change, **{f'val_{i}': sliders[i] for i in range(len(sliders))})

# %%
# Create a single vertical slider



slider = FloatSlider(
    value=0,
    min=-5,
    max=5,
    step=0.01,
    description='Timbre:',
    orientation='vertical',
    readout=True,
    readout_format='.2f',
    continuous_update=False
)

def on_slider_change(value):
    """Called when slider value changes"""
    # audio_sample = sound_files[int(value*len(sound_files))]  # Use the first sound file as an example
    # y, sr_ = li.load(os.path.join('sounds', audio_sample), sr=None)
    # y_scaled = y * value
    # display(Audio(y_scaled, rate=sr_, normalize=False))  # Scale audio volume by slider valuedisplay(Audio(y, rate=sr_))  # Just an example action

    audio_sample = sound_files[0]  # Use the first sound file as an example
    y, sr_ = li.load(os.path.join('sounds', audio_sample), sr=None)

    #encode with model and vae
    encoding = model.encode(y)[0].squeeze(0).T  # shape: (1, latent_dim, time)
    encoding_tensor = torch.tensor(encoding, dtype=torch.float32)

    with torch.no_grad():
        mu, logvar = vae.encode(encoding_tensor)
        z = vae.reparameterize(mu, logvar)

    # Shift the VAE encoding by slider value in dimension 0 and decode
    z_shifted = z.clone()
    z_shifted[:, 1] += value
    with torch.no_grad():
        vae_decoded = vae.decode(z_shifted)
    vae_decoded_np = vae_decoded.numpy().T[np.newaxis, :, :]
    recon_audio = model.decode(vae_decoded_np)
    display(Audio(recon_audio, rate=sr_))


    print(f"Slider value: {value}")
    # print new attributes for sound
    print(f"New attributes for sound at slider value {value}:")
    ics = audio_features(recon_audio, sr=sr_)
    for key, val in ics.items():
        print(f"  {key}: {val}")


    # Add your function logic here
    # e.g., process audio, update visualization, etc.

interact(on_slider_change, value=slider)
# %%
