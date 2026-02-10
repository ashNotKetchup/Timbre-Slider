from sklearn.cluster import KMeans
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
                'spectral_bandwidth': (li.feature.spectral_bandwidth(y=y_recon, sr=sr).mean() if use_mean else li.feature.spectral_bandwidth(y=y_recon, sr=sr)),
                'spectral_rolloff': (li.feature.spectral_rolloff(y=y_recon, sr=sr).mean() if use_mean else li.feature.spectral_rolloff(y=y_recon, sr=sr)),
                'spectral_contrast': (li.feature.spectral_contrast(y=y_recon, sr=sr).mean() if use_mean else li.feature.spectral_contrast(y=y_recon, sr=sr)),
            }
        elif feature_type == 'audio_commons':
            features_all = timbral_models.timbral_extractor(y_recon, sr, verbose=False)
            features = {k: features_all[k] for k in ['hardness', 'warmth', 'depth', 'brightness', 'roughness', 'sharpness', 'boominess'] if k in features_all}
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

    key_features, reduced_dicts = filter_attributes(audio_features_list, 'features_recon')
    print(f"\nSuccessfully processed {len(audio_features_list)} files.")
    print('shapes of features_recon:', [{k: v.shape if isinstance(v, np.ndarray) else 'scalar' for k, v in item['features_recon'].items()} for item in audio_features_list])
    return audio_features_list, key_features, pca


def get_features(sound_files, feature_type, model=None, save_path=None, overwrite=False, root_folder = None):
    if save_path:
        save_path += '.pkl' if not save_path.endswith('.pkl') else ''
        key_features_path = save_path.replace('.pkl', '_key_features.pkl')
        pca_path = save_path.replace('.pkl', '_pca.pkl')

        # Try loading cached data
        if os.path.exists(save_path) and not overwrite:
            with open(save_path, 'rb') as f:
                sound_data = pickle.load(f)
            # Load PCA if available
            pca = None
            if os.path.exists(pca_path):
                with open(pca_path, 'rb') as pf:
                    pca = pickle.load(pf)
            # Load key_features if available
            if os.path.exists(key_features_path):
                with open(key_features_path, 'rb') as kf:
                    key_features = pickle.load(kf)
            else:
                key_features, _ = filter_attributes(sound_data, 'features_recon')
                with open(key_features_path, 'wb') as kf:
                    pickle.dump(key_features, kf)
            print(f'Loaded preprocessed sound data from {save_path}.')
            return sound_data, key_features, pca

    # Compute features and save if needed
    sound_data, key_features, pca = batch_compute_features(sound_files, use_recon=True, model=model, feature_type=feature_type, root_folder=root_folder)
    if save_path:
        with open(save_path, 'wb') as f:
            pickle.dump(sound_data, f)
        with open(key_features_path, 'wb') as kf:
            pickle.dump(key_features, kf)
        if pca is not None:
            with open(pca_path, 'wb') as pf:
                pickle.dump(pca, pf)
        print(f'Saved preprocessed sound data to {save_path}.')
    return sound_data, key_features, pca


# --- Feature clustering and selection ---
def filter_attributes(array_of_dicts, key, n_clusters=4, random_state=0):
    """
    Given a list of dicts (dataset) and a key (e.g. 'features_recon'),
    clusters the features (columns) and selects the feature with the highest variance from each cluster.
    Returns (selected_feature_names, reduced_dicts).
    """
    # Extract feature dicts and build DataFrame
    # If feature values are arrays (e.g. time-series), unstack each array
    # element into its own row so the DataFrame contains only scalars.
    feature_dicts = []
    for d in array_of_dicts:
        fd = d[key]
        # Check if any value is an array-like (ndarray with size > 1)
        has_arrays = any(
            isinstance(v, np.ndarray) and v.size > 1 for v in fd.values()
        )
        if has_arrays:
            # Flatten every array value and expand into multiple scalar rows
            flat = {}
            for k, v in fd.items():
                arr = np.asarray(v).ravel()
                flat[k] = arr
            # All arrays should have the same length after flattening
            length = max(len(v) for v in flat.values())
            for i in range(length):
                row = {}
                for k, v in flat.items():
                    row[k] = v[i] if i < len(v) else np.nan
                feature_dicts.append(row)
        else:
            # Already scalar values – keep as a single row
            scalar_fd = {
                k: (v.item() if isinstance(v, np.ndarray) and v.size == 1 else v)
                for k, v in fd.items()
            }
            feature_dicts.append(scalar_fd)
    df = pd.DataFrame(feature_dicts)
    print("[filter_attributes] DataFrame preview:")
    print(df.head())
    print("[filter_attributes] Features DataFrame before filtering:")
    print(df)
    # Drop columns with non-numeric or all-NaN values
    df = df.select_dtypes(include=[np.number]).dropna(axis=1, how='all')
    if df.shape[1] == 0:
        print("[filter_attributes] All features are NaN or non-numeric. No valid features to cluster.")
        return [], []
    # Fallback: if only one row, return all features
    if len(df) == 1:
        print("[filter_attributes] Only one sample present. Returning all features.")
        selected_features = list(df.columns)
        reduced_dicts = [{f: df.iloc[0][f] for f in selected_features}]
        return selected_features, reduced_dicts
    # Additional check: if all values in all columns are NaN
    if df.isna().all().all():
        print("[filter_attributes] All feature values are NaN after filtering. Returning empty results.")
        return [], []

    # Cluster features (columns)
    X = df.values
    X = np.nan_to_num(X)  # Replace NaNs with 0 for clustering
    # Transpose: cluster columns (features)
    X_T = X.T
    n_clusters = min(n_clusters, X_T.shape[0])
    print(f"[filter_attributes] Clustering {X_T.shape[0]} features into {n_clusters} clusters.")
    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    cluster_labels = kmeans.fit_predict(X_T)

    # For each cluster, select the feature with the highest variance
    selected_features = []
    for cluster in range(n_clusters):
        cluster_cols = df.columns[cluster_labels == cluster]
        if len(cluster_cols) == 0:
            continue
        # Compute variance for each feature in the cluster
        variances = df[cluster_cols].var(axis=0)
        print(f"[filter_attributes] Variances for cluster {cluster}: {variances}")
        # Only consider features with non-NaN variance
        valid_variances = variances.dropna()
        if valid_variances.empty:
            # Skip this cluster if all variances are NaN
            continue
        best_feature = valid_variances.idxmax()
        selected_features.append(best_feature)

    # Reduce each dict to only selected features
    reduced_dicts = []
    for d in array_of_dicts:
        reduced = {f: d[key][f] for f in selected_features if f in d[key]}
        reduced_dicts.append(reduced)

    if len(selected_features) == 0:
        print("[filter_attributes] No features selected after clustering. Returning input results.")
        return list(df.columns), feature_dicts  # Return original features if none selected

    print(f"[filter_attributes] Selected features: {selected_features}")
    return selected_features, reduced_dicts


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
        for dim in range(num_dims):
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