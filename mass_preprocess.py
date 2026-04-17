
from timbre_VAE.features import get_features
from timbre_VAE.load_generative_model import Model
import os

def mass_preprocess(sample_folder, model_name='nasa', model_type='STABLE_AUDIO', feature_types=None, sr=44100, overwrite=True):
    """
    Compute features for all audio files in a folder for the given model and feature types.
    Returns a dict mapping feature_type to the path of the saved features file.
    """
    if feature_types is None:
        feature_types = ['raw_features', 'audio_commons', 'pca']  # Default feature types to compute
    model_location = f'timbre_VAE/models/RAVE_models/generative_models/{model_name}.ts'
    model = Model(model_type=model_type, model_path=[model_location])
    sound_files = [
        f for f in os.listdir(sample_folder)
        if f.endswith(('.wav', '.aif', '.mp3', '.ogg'))
    ]
    results = {}
    
    compute_types = [t for t in feature_types if t not in ('pca', 'PCA')]
    if compute_types:
        feature_save_base = os.path.join(
            sample_folder,
            f"{os.path.basename(sample_folder)}_{model_type}"
        )
        print(f'[preprocess] {len(sound_files)} files × {compute_types} in {os.path.basename(sample_folder)}')
        
        get_features(
            sound_files,
            compute_types,
            model=model,
            save_path=feature_save_base,
            overwrite=overwrite,
            root_folder=sample_folder
        )

        for feature_type in compute_types:
            feature_save_path = f"{feature_save_base}_{feature_type}_preprocessed_sound_data.pkl"
            print(f'[preprocess] Saved/Available → {os.path.basename(feature_save_path)}')
            results[feature_type] = feature_save_path

    # PCA reuses the raw_features cache
    if 'raw_features' in results:
        results['pca'] = results['raw_features']
        results['PCA'] = results['raw_features']
    return results

# If run as a script, keep old behavior
if __name__ == "__main__":
    mass_preprocess('sounds/umru')
