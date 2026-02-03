import numpy as np
import librosa as li
from scipy.signal import resample
import os
import torch
import timbral_models
import pickle
import pandas as pd
from sklearn.decomposition import PCA

def audio_features(audio_y, sr=44100, use_mean=False, feature_type='raw_features'):
    '''Compute timbre features for each audio file and its encoding'''

    if feature_type == 'raw_features':
        spectral_centroid = li.feature.spectral_centroid(y=audio_y, sr=sr)
        spectral_flatness = li.feature.spectral_flatness(y=audio_y)
        zero_crossings = li.feature.zero_crossing_rate(y=audio_y)
        loudness = li.feature.rms(y=audio_y)
        pitch = get_pitch(audio_y, sr)
        features = {
            'spectral_centroid': spectral_centroid.mean() if use_mean else spectral_centroid,
            'spectral_flatness': spectral_flatness.mean() if use_mean else spectral_flatness,
            'zero_crossing_rate': zero_crossings.mean() if use_mean else zero_crossings,
            'loudness': loudness.mean() if use_mean else loudness,
            'pitch': pitch.mean() if use_mean else pitch,
        }
    elif feature_type == 'audio_commons':
        features = timbral_models.timbral_extractor(audio_y, sr, verbose=False)
        # if use_mean:
        #     for key in features:
        #         features[key] = features[key].mean()
    return features

def audio_commons_features(audio_y, sr=44100):
    '''Compute Audio Commons timbral features using timbral_models'''
    return timbral_models.timbral_extractor(audio_y, sr, verbose=False)

def get_pitch(y, sr):
    pitches, mags = li.piptrack(y=y, sr=sr)
    pitch_values = pitches[mags.argmax(axis=0), np.arange(mags.shape[1])]
    return pitch_values.reshape(1, -1)

def batch_compute_features(sound_files, root_folder='sounds', use_recon=True, model=None, use_mean=False, feature_type='raw_features', pca_dim=4, pca=None):
    '''
    Compute audio features for a batch of sound files.
    If feature_type == 'PCA', fit PCA on all encodings and use PCA dimensions as features.
    Returns a list of dictionaries with audio data, encodings, and features for each sound file.
    '''
    audio_features_list = []

    all_encodings = []

    # First pass: collect all encodings for PCA if needed
    if feature_type == 'PCA':
        if pca is None:
            for sound_file in sound_files:
                print(f"Processing {sound_file} ({len(all_encodings)+1}/{len(sound_files)})")
                path = os.path.join(root_folder, sound_file)
                y, sr = li.load(path, sr=None)
                with torch.no_grad():
                    enc = model.encode(y)[0]
            # enc is (1, dim, time) -> squeeze batch, then flatten time
            enc_flat = enc.squeeze(0).reshape(enc.shape[1], -1)  # (dim, time)
            # print(f'Encoding shape for {sound_file}: {enc_flat.shape}')
            all_encodings.append(enc_flat)

            # Concatenate along the time axis: result shape (latent_dim, total_time)
            all_encodings_np = np.concatenate(all_encodings, axis=1)
            print(f'Fitting PCA on encodings of shape: {all_encodings_np.shape}')
            pca = PCA(n_components=pca_dim)
            pca.fit(all_encodings_np.T)
            # pca.
    else:
        pca = None

# TODO: IMPORTANT: MAKE SURE THAT THE PCA FITTED ON TRAINING DATA IS APPLIED TO EVERYHTING ELSE, NOT REFITTED!

    # Second pass: compute features for each file
    for sound_file in sound_files:
        path = os.path.join(root_folder, sound_file)
        if use_recon and model is None:
            raise ValueError("Model must be provided if use_recon is True.")
        if feature_type not in ['raw_features', 'audio_commons', 'PCA']:
            raise ValueError(f"Unsupported feature_type: {feature_type}")

        y, sr = li.load(path, sr=None)
        with torch.no_grad():
            enc = model.encode(y)[0]
            y_recon = model.decode(enc) if use_recon else None

        if feature_type == 'raw_features':
            features = {
                'spectral_centroid': (li.feature.spectral_centroid(y=y_recon, sr=sr).mean() if use_mean else li.feature.spectral_centroid(y=y_recon, sr=sr)),
                'spectral_flatness': (li.feature.spectral_flatness(y=y_recon).mean() if use_mean else li.feature.spectral_flatness(y=y_recon)),
                'zero_crossing_rate': (li.feature.zero_crossing_rate(y_recon).mean() if use_mean else li.feature.zero_crossing_rate(y_recon)),
                'loudness': (li.feature.rms(y=y_recon).mean() if use_mean else li.feature.rms(y=y_recon)),
                'pitch': get_pitch(y_recon, sr),
            }
        elif feature_type == 'audio_commons':
            features_all = timbral_models.timbral_extractor(y_recon, sr, verbose=False)
            features = {k: features_all[k] for k in ['hardness', 'warmth', 'depth'] if k in features_all}
        elif feature_type == 'PCA':
            # Use the same flattening as in the first pass
            # enc_flat = enc.squeeze(0).reshape(enc.shape[1], -1)
            enc = enc.squeeze(0).T  # shape: (time, dim)
            print(f'shape of encoding for {sound_file}: {enc.shape}')
            pca_features = pca.transform(enc).squeeze()
            print(f'PCA features shape for {sound_file}: {pca_features.shape}')
            features = {f'pca_{i}': pca_features[i] for i in range(pca_dim)}

        try:
            audio_features_list.append(
                {
                    'filename': sound_file,
                    'focus': False,
                    'raw_audio': y,
                    'recon_audio': y_recon,
                    'sr': sr,
                    'encoding': enc,
                    'encoding_mean': enc.mean(axis=-1),
                    'encoding_std': enc.std(axis=-1),
                    'features_recon': features
                }
            )
        except Exception as e:
            print(f"Error processing {sound_file}: {e}")

    print(f"\nSuccessfully processed {len(audio_features_list)} files.")
    print('shapes of features_recon:', [{k: v.shape if isinstance(v, np.ndarray) else 'scalar' for k, v in item['features_recon'].items()} for item in audio_features_list])
    return audio_features_list, list(features.keys()), pca


def get_features(sound_files, feature_type, model=None, save_path=None, overwrite=False, root_folder = None):
    save_path += '.pkl' if save_path and not save_path.endswith('.pkl') else ''
    if save_path and os.path.exists(save_path) and not overwrite:
        with open(save_path, 'rb') as f:
            sound_data = pickle.load(f)
            # Also load PCA if available
            pca_path = save_path.replace('.pkl', '_pca.pkl')
            if os.path.exists(pca_path):
                with open(pca_path, 'rb') as pf:
                    pca = pickle.load(pf)
            else:
                pca = None
        print(f'Loaded preprocessed sound data from {save_path}.')
        return sound_data, None, pca
    else:
        sound_data, feature_keys, pca = batch_compute_features(sound_files, use_recon=True, model=model, feature_type=feature_type, root_folder=root_folder)
        if save_path:
            with open(save_path, 'wb') as f:
                pickle.dump(sound_data, f)
            
            #Save PCA if applicable
            if pca is not None:
                pca_path = save_path.replace('.pkl', '_pca.pkl')
                with open(pca_path, 'wb') as pf:
                    pickle.dump(pca, pf)
            print(f'Saved preprocessed sound data to {save_path}.')
        return sound_data, feature_keys, pca



# Test VAE performance on the example sound
# For each latent dimension i, intervening on z_i should cause a large, specific change in attribute a_i,
# and minimal change in all other attributes.

# A: Calculate effect size matrix
def calculate_effect_size_matrix(vae, z_init, model, metadata_keys, delta_range=None, feature_type=None):
    """
    For each latent dimension, permute z along that axis for a batch of z vectors,
    decode via vae and model, and calculate a list of attribute dicts as output.
    Returns: DataFrame with columns [dim, x, ...attributes...]
    """
    if delta_range is None:
        delta_range = np.linspace(-2, 2, 5)
    if feature_type is None:
        feature_type = 'audio_commons'
    rows = []
    num_dims = z_init.shape[1]
    with torch.no_grad():
        for dim in range(3):
            for delta in delta_range:
                z_perturbed = z_init.clone()
                z_perturbed[:, dim] += float(delta)
                # Prepare for decode if needed
                recon_mu = vae.decode(z_perturbed)
                if recon_mu.ndim == 2:
                    recon_mu_for_decode = recon_mu.unsqueeze(-1)
                else:
                    recon_mu_for_decode = recon_mu
                audio_recon = model.decode(recon_mu_for_decode)
                attrs = audio_features(audio_recon, use_mean=True, feature_type=feature_type)
                row = {
                    "dim": dim,
                    "x": delta,
                    **{key: attrs[key] for key in attrs.keys()},
                }
                rows.append(row)
    df = pd.DataFrame(rows, columns=["dim", "x"] + list(attrs.keys()))
    print(df)
    return df