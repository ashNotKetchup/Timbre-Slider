import numpy as np
import librosa as li
from scipy.signal import resample
import os
import torch
import timbral_models


def audio_features(audio_y, sr=44100):
    '''Compute timbre features for each audio file and its encoding'''
    spectral_centroid = li.feature.spectral_centroid(y=audio_y, sr=sr)[0]
    mean_centroid = np.mean(spectral_centroid)
    spectral_flatness = li.feature.spectral_flatness(y=audio_y)[0]
    mean_flatness = np.mean(spectral_flatness)
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

def batch_compute_features(sound_files, use_recon=True, model=None, use_mean=False, feature_type='raw_features'):
    audio_features_list = []
    for sound_file in sound_files:
        path = os.path.join('sounds', sound_file)
        if use_recon and model is None:
            raise ValueError("Model must be provided if use_recon is True.")
        # Calculate different types of features based on feature_type
        if feature_type not in ['raw_features', 'audio_commons', 'PCA']:
            raise ValueError(f"Unsupported feature_type: {feature_type}")
        
        y, sr = li.load(path, sr=None)
        with torch.no_grad():
            enc = model.encode(y)[0]
            y_recon = model.decode(enc) if use_recon else None

        if feature_type == 'raw_features':
            features = {
                        'spectral_centroid': (centroid_recon := li.feature.spectral_centroid(y=y_recon, sr=sr).mean() if use_mean else li.feature.spectral_centroid(y=y_recon, sr=sr)),
                        'spectral_flatness': (flatness_recon := li.feature.spectral_flatness(y=y_recon).mean() if use_mean else li.feature.spectral_flatness(y=y_recon)),
                        'zero_crossing_rate': (zcr_recon := li.feature.zero_crossing_rate(y_recon).mean() if use_mean else li.feature.zero_crossing_rate(y_recon)),
                        'loudness': (loudness_recon := li.feature.rms(y=y_recon).mean() if use_mean else li.feature.rms(y=y_recon)),
                        'pitch': get_pitch(y_recon, sr),
                    }
            
        elif feature_type == 'audio_commons':
            features = timbral_models.timbral_extractor(y_recon, sr, verbose=False)

        try:
            audio_features_list.append(
                {
                    'filename': sound_file,
                    'focus': False,
                    'raw_audio': (y),
                    'recon_audio': (y_recon),
                    'sr': (sr := sr),
                    'encoding': (enc),
                    'encoding_mean': enc.mean(axis=-1),
                    'encoding_std': enc.std(axis=-1),
                    'features_recon': features
                }
            )
        except Exception as e:
            print(f"Error processing {sound_file}: {e}")
    print(f"\nSuccessfully processed {len(audio_features_list)} files.")
    print('shapes of features_recon:', [ {k: v.shape if isinstance(v, np.ndarray) else 'scalar' for k, v in item['features_recon'].items()} for item in audio_features_list])
    return audio_features_list, features.keys()
