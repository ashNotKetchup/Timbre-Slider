# %% [markdown]
#  This notebook finds the most similar latent point to an input sound, then applies the difference derived in interpolation to that sound.

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
from sklearn.decomposition import PCA



# %%
# Model and data setup
model_name: str = 'percussion'
model_location:str = 'generative_models/'+model_name+'.ts'
control_model_location = 'control_models/vae_scripted_model.ts'
audio_sample = 'UMRU_chord_loop_atmosphere_140_Abmin.wav'
model_type = 'RAVE'
# model_type = 'STABLE_AUDIO'


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


def batch_compute_features(sound_files, use_recon:bool=True, model=None):
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
                    'zero_crossing_rate': (zcr := li.feature.zero_crossing_rate(y).mean())
                },
                'features_recon': {
                    'spectral_centroid': (centroid_recon := li.feature.spectral_centroid(y=y_recon, sr=sr_).mean()),
                    'spectral_flatness': (flatness_recon := li.feature.spectral_flatness(y=y_recon).mean()),
                    'zero_crossing_rate': (zcr_recon := li.feature.zero_crossing_rate(y_recon).mean())
                    }
                }
                 
            )
            # print(f"Processed: {Path(sound_file).name} - Centroid: {centroid_recon:.2f} Hz, Flatness: {flatness_recon:.4f}, Zero Crossings: {zcr_recon:.4f}")
        except Exception as e:
            print(f"Error processing {sound_file}: {e}")
    print(f"\nSuccessfully processed {len(audio_features)} files.")

    # # Stack all encodings into a single 2D array for PCA (samples x features)
    # all_encodings = np.array([item['encoding'][0].reshape(item['encoding'][0].shape[0], -1).mean(axis=0) for item in audio_features])
    # all_encodings = np.stack(all_encodings, axis=0)

    # # Choose 2D or 3D PCA
    # n_components = 3 if all_encodings.shape[0] > 2 else 2
    # pca = PCA(n_components=n_components)
    # encoding_pca = pca.fit_transform(all_encodings)

    # # Append PCA result to each element
    # for idx, item in enumerate(audio_features):
    #     item['encoding_pca'] = encoding_pca[idx]
    # all_encodings = [item['encoding'][0].reshape(item['encoding'][0].shape[0], -1).mean(axis=0) for item in audio_features]
    # all_encodings = np.stack(all_encodings, axis=0)

    # # Choose 2D or 3D PCA
    # n_components = 3 if all_encodings.shape[0] > 2 else 2
    # pca = PCA(n_components=n_components)
    # encoding_pca = pca.fit_transform(all_encodings)
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
    # Add model type and name to title
    title = f"{y_feature.replace('_', ' ').capitalize()} vs {x_feature.replace('_', ' ').capitalize()} | Model: {model_type}"
    if model_type == 'RAVE':
        title += f" ({model_name})"
    plt.title(title)
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
        title = f"{feature.replace('_', ' ').capitalize()} (Raw vs. Reconstructed) | Model: {model_type}"
        if model_type == 'RAVE':
            title += f" ({model_name})"
        plt.title(title)
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
    title = f'Latent Dimension {dim} | Model: {model_type}'
    if model_type == 'RAVE':
        title += f" ({model_name})"
    plt.title(title)
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
        title = f"{quality_dropdown.label} vs Encoding Mean | Model: {model_type}"
        if model_type == 'RAVE':
            title += f" ({model_name})"
        plt.title(title)

        plt.subplot(1, 2, 2)
        plt.scatter(encoding_stds, timbre_qualities, c='g')
        for i, label in enumerate(filenames):
            plt.annotate(label, (encoding_stds[i], timbre_qualities[i]), fontsize=8, alpha=0.7)
        plt.xlabel(f'Encoding Std (dimension {dimension})')
        plt.ylabel(quality_dropdown.label)
        title = f"{quality_dropdown.label} vs Encoding Std (Variance) | Model: {model_type}"
        if model_type == 'RAVE':
            title += f" ({model_name})"
        plt.title(title)

        plt.tight_layout()
        plt.show()

# Plot spectrograms for left, right, and interpolated audio
def plot_spectrograms(encodings, left_index, right_index, interpolated_audio, labels):
        fig, axs = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
        base_titles = [
            f"Left: {labels[left_index]}",
            f"Right: {labels[right_index]}",
            "Interpolated"
        ]
        titles = []
        for t in base_titles:
            title = f"{t} | Model: {model_type}"
            if model_type == 'RAVE':
                title += f" ({model_name})"
            titles.append(title)
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
def slider_to_audio(position:float, audio_sample:dict, sorted_corpus:list[dict],latent_model=model):
    left_index = int(np.floor(position))
    right_index = min(left_index + 1, len(sorted_corpus) - 1)
    alpha = position - left_index
    # interp_latent = apply_attribute_vector(sorted_corpus[left_index]['encoding'], sorted_corpus[right_index]['encoding'], audio_sample['encoding'], alpha)
    interp_latent = interpolate_latents(sorted_corpus[left_index]['encoding'], sorted_corpus[right_index]['encoding'], alpha)
    recon_audio = latent_model.decode(interp_latent)
    return recon_audio, interp_latent

def make_slider(max_val, min_val=0,  step=0.01, default=0, description='Interpolation'):
    return FloatSlider(min=min_val, max=max_val, step=step, value=default, description=description)



# Construct a unified data structure for each sound using a list comprehension,
sound_data = batch_compute_features(sound_files, use_recon=True, model=model)
sound_data_sorted = sorted(sound_data, key=lambda x: x['features_recon']['spectral_centroid'])
samples_to_modify = batch_compute_features([audio_sample], use_recon=True, model=model)
# plot_sound_features(
#     sound_data_sorted,
#     x_feature='filename',
#     y_feature='spectral_centroid',
#     splits= ['features_recon','features_raw'],
#     )



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

def plot_slider_values(timbre_quality: str, corpus, slider_to_audio_func, number_of_points: int = 5):
    length = len(corpus)
    slider_values = np.linspace(0, length - 1, number_of_points)
    sorted_corpus = sorted(corpus, key=lambda x: x['features_recon'][timbre_quality])
    sr_ = corpus[0]['sr']
    audio = [
        slider_to_audio_func(x, None, sorted_corpus)[0] for x in slider_values
    ]
    timbre_features = [
        {'features_recon': {
            'spectral_centroid': (centroid_recon := li.feature.spectral_centroid(y=y_recon, sr=sr_).mean()),
            'spectral_flatness': (flatness_recon := li.feature.spectral_flatness(y=y_recon).mean()),
            'zero_crossing_rate': (zcr_recon := li.feature.zero_crossing_rate(y_recon).mean())
        }} for y_recon in audio
    ]
    # Plot slider position vs. timbre features
    plt.figure(figsize=(10, 4))
    for feature in [timbre_quality]:
        plt.plot(slider_values, [t['features_recon'][feature] for t in timbre_features], marker='o', label=feature.replace('_', ' ').capitalize())
    plt.xlabel('Slider Position')
    plt.ylabel('Timbre Feature Value')
    title = f'Slider Position vs. Timbre Features | Model: {model_type}'
    if model_type == 'RAVE':
        title += f" ({model_name})"
    plt.title(title)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.tight_layout()
    plt.show()

    # sorted_corpus = sorted(sound_data, key=lambda x: x['features_recon'][timbre_quality])
    # left_index = int(np.floor(x))
    # right_index = min(left_index + 1, len(sorted_corpus) - 1)
    # alpha = x - left_index
    # print(f"Left: {sorted_corpus[left_index]['filename']} ({sorted_corpus[left_index]['features_recon'][timbre_quality]:.2f}), Right: {sorted_corpus[right_index]['filename']} ({sorted_corpus[right_index]['features_recon'][timbre_quality]:.2f}), Alpha: {alpha:.2f}")




# Function to update sorting and interpolation
def update_interpolation(corpus, sample, timbre_quality, x, dimension):
    # Sort audio and encodings by selected timbre quality
    sorted_corpus = sorted(corpus, key=lambda x: x['features_recon'][timbre_quality])
    left_index = int(np.floor(x))
    right_index = min(left_index + 1, len(sorted_corpus) - 1)
    alpha = x - left_index

    #apply attribute vector between left and right to the sample encoding
    interp_audio, interp_latent = slider_to_audio(x, sample, sorted_corpus)


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
    print()
    plot_latent(dimension, [left_latent, interp_latent, right_latent], [sorted_corpus[left_index]['filename'], 'Interpolation', sorted_corpus[right_index]['filename']])
    plot_sound_features(
        corpus_with_interp,
        x_feature='filename',
        y_feature=timbre_quality,
        splits=splits,
        labels=labels,
        special_filename='Interpolation'
    )

    plot_slider_values(timbre_quality, corpus, slider_to_audio, number_of_points=20)

   
    
    plot_timbre_vs_encoding(sorted_corpus, quality_dropdown, dimension)
    
    # plot_spectrograms(resampled_encodings, left_index, right_index, interp_audio, [audio['filename'] for audio in sorted_corpus])
    print(f"Interpolating between {sorted_corpus[left_index]['filename']} and {sorted_corpus[right_index]['filename']} (alpha={alpha:.2f}), sorted by {timbre_quality.replace('_',' ')}")
    # print(f'Interpolated audio has {audio_features(interp_audio)}')


# Use interact to link dropdown and sliders

interact(update_interpolation, sample= fixed(samples_to_modify[0]), corpus=fixed(sound_data), timbre_quality=quality_dropdown, x=lerp_slider, dimension=dimension_dropdown)





