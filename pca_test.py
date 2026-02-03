import os
import librosa as li
import torch
import numpy as np
from sklearn.decomposition import PCA

def batch_compute_features(sound_files, root_folder='sounds', use_recon=True, model=None, use_mean=False, feature_type='raw_features', pca_dim=8):
    '''
    Compute audio features for a batch of sound files.
    If feature_type == 'PCA', fit PCA on all encodings and use PCA dimensions as features.
    Returns a list of dictionaries with audio data, encodings, and features for each sound file.
    '''
    audio_features_list = []
    all_encodings = []

    # First pass: collect all encodings for PCA if needed
    if feature_type == 'PCA':
        for sound_file in sound_files:
            path = os.path.join(root_folder, sound_file)
            y, sr = li.load(path, sr=None)
            with torch.no_grad():
                enc = model.encode(y)[0]
            # Flatten encoding to 1D if needed
            # enc_flat = enc.mean(axis=-1) if enc.ndim > 1 else enc
            
            enc_flat = enc
            # enc is (1, dim, time) -> squeeze batch, then flatten time
            enc_flat = enc.squeeze(0).reshape(enc.shape[1], -1)  # (dim, time)
            print(f'Encoding shape for {sound_file}: {enc_flat.shape}')
            all_encodings.append(enc_flat)
            # all_encodings.append(enc_flat)
        all_encodings_np = np.stack(all_encodings, axis=-1)
        print(f'Fitting PCA on encodings of shape: {all_encodings_np.shape}')
        pca = PCA(n_components=pca_dim)
        pca.fit(all_encodings_np)
    else:
        pca = None

    return

batch_compute_features()