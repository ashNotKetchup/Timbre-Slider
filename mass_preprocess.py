from features import get_features
from load_generative_model import Model
import os

model_name = 'nasa'
model_type = 'STABLE_AUDIO'
model_location = f'generative_models/{model_name}.ts'
model = Model(model_type=model_type, model_path=[model_location])

feature_types = ['raw_features', 'audio_commons']
# feature_types = ['audio_commons']
# sample_folder_paths = ['test','Foley', 'sounds/umru']
sample_folder_paths = ['sounds/umru']
sr = 44100

for sample_folder in sample_folder_paths:
    sound_files = [
        os.path.join(sample_folder, f)
        for f in os.listdir(sample_folder)
        if f.endswith(('.wav', '.aif', '.mp3', '.ogg'))
    ]
    for feature_type in feature_types:
        feature_save_path = f'features/{os.path.basename(sample_folder)}_{model_type}_{feature_type}_preprocessed_sound_data.pkl'
        print(f'Processing {len(sound_files)} files in {sample_folder} with feature type {feature_type}')
        get_features(
            sound_files,
            feature_type,
            model=model,
            save_path=feature_save_path,
            overwrite=True,
            root_folder=''  # Use None to avoid interfering with path handling
        )
        print(f'Saved features to {feature_save_path}')
