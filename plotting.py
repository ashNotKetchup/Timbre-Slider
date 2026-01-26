import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import resample
import librosa as li
import os
import torch

def plot_sound_features(dataset, x_feature, y_feature, splits=None, labels=None, figsize=(12, 6), colors=None, markers=None, special_filename=None):
    special_color = '#e41a1c'  # red
    special_marker = '*'
    special_points = []
    if special_filename is not None:
        dataset_normal = [d for d in dataset if d['filename'] != special_filename]
        special_points = [d for d in dataset if d['filename'] == special_filename]
    else:
        dataset_normal = dataset
    dataset = dataset_normal
    if splits is None:
        splits = [None]
    if labels is None:
        labels = [d['filename'] for d in dataset]
    if colors is None:
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
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

# Add other plotting functions as needed (plot_latent, plot_timbre_vs_encoding, plot_spectrograms, etc.)

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
# plot_feature_alignment(model, sound_files, file_index=1, feature_names=None, plot_encoding_axes=True, vae=vae)



def plot_loss(loss_lists, labels):
    plt.figure(figsize=(10, 6))
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