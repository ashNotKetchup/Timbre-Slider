
from timbre_VAE.features import get_features
from timbre_VAE.load_generative_model import Model
import os

def mass_preprocess(sample_folder, model_name='nasa', model_type='STABLE_AUDIO', feature_types=None, sr=44100, overwrite=True):
    """
    Compute features for all audio files in a folder for the given model and feature types.
    Returns a dict mapping feature_type to the path of the saved features file.
    """
    if feature_types is None:
        feature_types = ['raw_features', 'audio_commons']
    model_location = f'timbre_VAE/models/RAVE_models/generative_models/{model_name}.ts'
    model = Model(model_type=model_type, model_path=[model_location])
    sound_files = [
        f for f in os.listdir(sample_folder)
        if f.endswith(('.wav', '.aif', '.mp3', '.ogg'))
    ]
    results = {}
    for feature_type in feature_types:
        feature_save_path = os.path.join(
            sample_folder,
            f"{os.path.basename(sample_folder)}_{model_type}_{feature_type}_preprocessed_sound_data.pkl",
        )
        print(f'Processing {len(sound_files)} files in {sample_folder} with feature type {feature_type}')
        get_features(
            sound_files,
            feature_type,
            model=model,
            save_path=feature_save_path,
            overwrite=overwrite,
            root_folder=sample_folder
        )
        print(f'Saved features to {feature_save_path}')
        results[feature_type] = feature_save_path
    return results

# If run as a script, keep old behavior
if __name__ == "__main__":
    mass_preprocess('sounds/umru')
