import numpy as np
import librosa as li
from scipy.signal import resample
import os
import torch
import timbral_models
import pickle

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
            'pitch': pitch,
        }
    elif feature_type == 'audio_commons':
        features = timbral_models.timbral_extractor(audio_y, sr, verbose=False)
        if use_mean:
            for key in features:
                features[key] = features[key].mean()
    return features

def audio_commons_features(audio_y, sr=44100):
    '''Compute Audio Commons timbral features using timbral_models'''
    return timbral_models.timbral_extractor(audio_y, sr, verbose=False)

def get_pitch(y, sr):
    pitches, mags = li.piptrack(y=y, sr=sr)
    pitch_values = pitches[mags.argmax(axis=0), np.arange(mags.shape[1])]
    return pitch_values.reshape(1, -1)

def batch_compute_features(sound_files,root_folder='sounds', use_recon=True, model=None, use_mean=False, feature_type='raw_features'):
    '''
    Compute audio features for a batch of sound files.
    returns a list of dictionaries with audio data, encodings, and features for each sound file.
    :param sound_files: List of sound file names to process    
    :param root_folder: Description
    :param use_recon: Description
    :param model: Description
    :param use_mean: Description
    :param feature_type: Description
    '''
    
    audio_features_list = []
    for sound_file in sound_files:
        path = os.path.join(root_folder, sound_file)
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
    return audio_features_list, list(features.keys())


def get_features(sound_files, feature_type, model=None, save_path=None, overwrite=False):
    save_path += '.pkl' if save_path and not save_path.endswith('.pkl') else ''
    if save_path and os.path.exists(save_path) and not overwrite:
        with open(save_path, 'rb') as f:
            sound_data = pickle.load(f)
        print(f'Loaded preprocessed sound data from {save_path}.')
        return sound_data
    else:
        sound_data = batch_compute_features(sound_files, use_recon=True, model=model, feature_type=feature_type)
        if save_path:
            with open(save_path, 'wb') as f:
                pickle.dump(sound_data, f)
            print(f'Saved preprocessed sound data to {save_path}.')
        return sound_data

