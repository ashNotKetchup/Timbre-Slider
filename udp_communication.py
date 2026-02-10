from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import random
# from dummy_json import dummy_json
from timbre_VAE.load_audio import BufferManager
from timbre_VAE.load_generative_model import Model, LatentRepresentation, ControlModel
from mass_preprocess import mass_preprocess
import numpy as np
import json
from timbre_VAE.vae_train import prepare_data, VAE, train_vae
from timbre_VAE.features import batch_compute_features


import torch
# --- SETUP DEPENDENCIES/CLASSES –––
latent_representation = LatentRepresentation()
audio_handler = BufferManager()


# --- CONFIGURATION (match learn_subspace.py) ---
model_type = 'STABLE_AUDIO'
# model_type = 'RAVE'  # or 'STABLE_AUDIO', depending on the model you want to use
model_name = 'percussion'  # or any other model name as needed
model_location = f'timbre_VAE/models/RAVE_models/generative_models/{model_name}.ts'
vae_path = 'precomputed/control_models/Foley_STABLE_AUDIO_audio_commons_preprocessed_sound_data_EX_Noise_120_waterfall_creaks_vae.pt'
feature_type = 'audio_commons'
sample_folder = 'sounds/Foley'
feature_paths = None
folder_path = None
audio_path = None
metadata_keys = None

# Load generative model
gen_model = Model(model_type=model_type, model_path=[model_location])

# Get metadata keys using feature type (simulate learn_subspace.py logic)
import os
from timbre_VAE.features import get_features
print(f'preprocessing files')
sound_files = [f for f in os.listdir(sample_folder) if f.endswith(('.wav', '.aif', '.mp3', '.ogg'))][0]
sound_data, feature_keys, _ = get_features([sound_files], feature_type, model=gen_model, save_path=None, overwrite=False, root_folder=sample_folder)
from timbre_VAE.vae_train import prepare_data, VAE, train_vae
_, _, metadata_keys, input_dim, latent_dim = prepare_data(sound_data, metadata_keys=feature_keys)

# Load with VAE
# control_model = ControlModel(vae_path, input_dim=input_dim, latent_dim=latent_dim)
timbre_gen_model = None

# try:
#     timbre_gen_model = Model(
#         model_type=model_type,
#         model_path=[model_location],
#         control_vae_path=vae_path,
#         control_vae_input_dim=input_dim,
#         control_vae_latent_dim=latent_dim
#     )
#     print("Loaded timbre_gen_model successfully.")
# except Exception as e:
#     print(f"No suitable model available or failed to load: {e}")
#     print("You need to retrain the model before use.")
#     
print(f'Loaded generative model and VAE with metadata keys: {metadata_keys}, latent dim: {latent_dim} and input dim: {input_dim}')

# --- NEW: Handler for loading a folder, computing features, and retraining VAE ---
_last_loaded_features = {
    'folder_path': None,
    'feature_save_path': None,
    'sound_data': None,
    'feature_keys': None,
    'pca': None,
    'last_sample_file': None,
    'last_sample_dir': None
}

def handle_request_load_folder(message):
    global feature_paths, folder_path, audio_path, _last_loaded_features
    folder_path = message.get('content')
    print(f"Received request to load folder: {folder_path}")
    if not folder_path or not os.path.isdir(folder_path):
        return {"type": "error", "content": f"Invalid folder path: {folder_path}"}
    try:
        # Compute features (or use precomputed)
        feature_paths = mass_preprocess(folder_path, 
                                        model_name=model_name, 
                                        model_type=model_type, 
                                        overwrite=False)
        feature_save_path = feature_paths[feature_type]
        # print(f"Using features from: {feature_save_path}")

        # Store for retraining
        _last_loaded_features = {
            'folder_path': folder_path,
            'feature_save_paths': feature_paths,
            'sound_data': sound_data,
            'feature_keys': feature_keys,
            # 'pca': pca,
            'last_sample_file': audio_path,
            'last_sample_dir': folder_path
        }
        return {"type": "load_folder", "content": f"Features computed and loaded for {folder_path}"}
    except Exception as e:
        print(f"Error in handle_request_load_folder: {e}")
        return {"type": "error", "content": f"Error processing folder: {e}"}

# New: Handler for retraining VAE using last loaded features
def handle_request_retrain_vae(message):
    global feature_paths, folder_path, audio_path, metadata_keys, _last_loaded_features
    global timbre_gen_model
    print(f"[Debug] timbre_gen_model before retrain: {timbre_gen_model}, ID: {id(timbre_gen_model)} ")
    try:
        # Load features for folder
        print(f'features {feature_paths}')
        # Prefer _last_loaded_features, fallback to global
        feature_save_path = None
        if _last_loaded_features and 'feature_save_paths' in _last_loaded_features:
            feature_save_path = _last_loaded_features['feature_save_paths'][feature_type]
        elif feature_paths:
            feature_save_path = feature_paths[feature_type]
        else:
            raise ValueError('feature_save_path not found in either _last_loaded_features or global feature_paths')
        print(f"Retraining VAE using features from: {feature_save_path}")
        sound_data, metadata_keys, pca = get_features(
            [f for f in os.listdir(folder_path) if f.endswith(('.wav', '.aif', '.mp3', '.ogg'))],
            feature_type,
            model=gen_model,
            save_path=feature_save_path,
            overwrite=False,
            root_folder=folder_path
        )

        # Load features for sample
        sample_sound_features, _, _ = batch_compute_features([audio_path], root_folder='', use_recon=True, model=gen_model, feature_type=feature_type)
        
        # Append the example features to the main sound_data list
        if sample_sound_features:
            print(f"example_sound_features: {sample_sound_features}")
            sound_data = sound_data + sample_sound_features
        print(f"Combined sound_data length: {len(sound_data)}")
        # TODO: Pick subset of metadata keys based on variance
        print(f"Loaded sound_data: {len(sound_data)}")

        # Prepare data for the combined set
        latent_data, metadata_vectors, metadata_keys_new, input_dim_new, latent_dim_new = prepare_data(sound_data, metadata_keys=metadata_keys)
        print(f"prepare_data output: latent_data shape {latent_data.shape}, metadata_keys_new: {metadata_keys_new}, input_dim_new: {input_dim_new}, latent_dim_new: {latent_dim_new}")
    # else:
        #     print("No example file to add, preparing data from sound_data only.")
        #     latent_data, metadata_vectors, metadata_keys_new, input_dim_new, latent_dim_new = prepare_data(sound_data)
        #     print(f"prepare_data output: latent_data shape {latent_data.shape}, metadata_keys_new: {metadata_keys_new}, input_dim_new: {input_dim_new}, latent_dim_new: {latent_dim_new}")
        #     input_dim_new = latent_data.shape[1]
        #     latent_dim_new = len(metadata_vectors[0][0]) if metadata_vectors and hasattr(metadata_vectors[0], '__getitem__') else latent_data.shape[1]
        #     print(f"Adjusted input_dim_new: {input_dim_new}, latent_dim_new: {latent_dim_new}")
        # print("Initializing VAE...")
        vae = VAE(input_dim=input_dim_new, latent_dim=latent_dim_new)
        print("Training VAE...")
        vae, loss_lists, loss_labels = train_vae(vae, latent_data, metadata_vectors, num_epochs=250, batch_size=128, learning_rate=1e-3)
        print(f"VAE trained. loss_lists: {loss_lists}, loss_labels: {loss_labels}")
        # Update global model (in-memory)
        print("Updating timbre_gen_model with new VAE...")
        timbre_gen_model = Model(model_type=model_type, model_path=[model_location], control_vae_path=None, control_vae_input_dim=input_dim_new, control_vae_latent_dim=latent_dim_new)
        timbre_gen_model.control_model = vae
        print(f"[DEBUG] timbre_gen_model.control_model is None after update: {timbre_gen_model.control_model is None}, id: {id(timbre_gen_model.control_model)}")
        print(f"Retrained VAE and updated model for folder: {_last_loaded_features['folder_path']}")
        handle_request_latent({"type": "request_latent", "content": audio_path})
        print(f"Re-encoded example audio with new VAE for file: {audio_path}")
        return {"type": "retrain_vae", "content": f"VAE retrained for {_last_loaded_features['folder_path']} (sample added: {audio_path})"}
    except Exception as e:
        print(f"Error in handle_request_retrain_vae: {e}")
        return {"type": "error", "content": f"Error retraining VAE: {e}"}

def handle_request_latent(message):
    global audio_path, metadata_keys, timbre_gen_model
    filepath = message['content']
    print("Python received file path to encode:", filepath)

    audio_path = filepath.strip('""')
    try:
        audio_handler.load_buffer(audio_path)
        audio_in = audio_handler.get_input_buffer()
        audio_handler.set_output_buffer(audio_in)
        assert isinstance(audio_in, np.ndarray), 'internal buffer has wrong type, not numpy'
    except Exception as e:
        print(f"Error loading audio: {e}")
        return {"type": "error", "content": f"Error loading audio: {e}"}

    try:
        # Debug: check if control_model is set
        print("[DEBUG] timbre_gen_model.control_model is None:", timbre_gen_model.control_model is None, "id:", id(timbre_gen_model.control_model))
        # Encode with generative model
        latent_vector, latent_text = timbre_gen_model.encode(audio_in)
        assert isinstance(latent_vector, np.ndarray) and isinstance(latent_text, str), 'encodings not right type'
        print('Encoded latent vector has size: ', latent_vector.shape)

        # to json
        latent_representation.set_latent_representation(latent_vector, latent_text)
        latent_representation.fit(output_range=2)
        latent_json = latent_representation.to_json()
        assert isinstance(latent_json, dict), 'json not a dictionary'

        bias_array = [0 for _ in range(len(metadata_keys))]
        scale_array = [1 for _ in range(len(metadata_keys))]
        latent_json['bias'] = bias_array
        latent_json['scale'] = scale_array
        latent_json['metadata_keys'] = metadata_keys

        return {"type": "latent", "content": latent_json}
        # # vae_z as dict of axes, Bias/scale as arrays
        # if vae_z.ndim == 2:
        #     vae_z_dict = {f"dim{i}": vae_z[:, i].tolist() for i in range(vae_z.shape[1])}
        # else:
        #     vae_z_dict = {"dim0": vae_z.tolist()}
        #
        # return {
        #     "type": "latent",
        #     "content": {
        #         "vae_z": vae_z_dict,
        #         "metadata_keys": metadata_keys,
        #         "bias": bias_array,
        #         "scale": scale_array
        #     }
        # }
    except Exception as e:
        print(f"Error encoding latent: {e}")
        return {"type": "error", "content": f"Error encoding latent: {e}"}


def handle_request_audio(message):
    global audio_path
    latent_data = message['content']
    print("Python received latent data:", 
        #   latent_data
          )
    try:
        if not isinstance(latent_data, dict):
            # Try to parse as JSON string
            try:
                latent_data = json.loads(latent_data)
            except Exception as e:
                raise ValueError(f"Could not parse latent_data as JSON: {e}")
            if not isinstance(latent_data, dict):
                raise ValueError("Expected a dictionary for latent_data after JSON parse, got {}".format(type(latent_data)))
        print(f"Parsed latent data successfully. Keys: {list(latent_data.keys())}")
        latent_representation.from_json(latent_data)
        print("Extracted latent representation from JSON successfully.")
        bias = np.array(latent_data['bias'], dtype=np.float32)
        scale = np.array(latent_data['scale'], dtype=np.float32)
        latent_vector, latent_text = latent_representation.get_latent_representation()

        # Ensure bias/scale match the number of latent dims
        n_latent = latent_vector.shape[1]
        bias = bias[:n_latent].reshape(1, n_latent, 1)
        scale = scale[:n_latent].reshape(1, n_latent, 1)
        latent_vector_scaled = latent_vector * scale + bias
        print("Successfully applied bias and scale to latent representation.")
        audio_out = timbre_gen_model.decode(latent_vector_scaled, latent_text)
        print("Decoded audio from latent representation successfully.")
        audio_handler.set_output_buffer(audio_out, save_plot=True)
        return {"type": "decoded", "content": "Decoded successfully"}
        
    except Exception as e:
        print(f"Error handling latent message: {e}")
        return {"type": "error", "content": f"Error handling latent message: {e}"}


# --- Switch map/dictionary ---
handlers = {
    "request_latent": handle_request_latent,
    "request_audio": handle_request_audio,
    "request_load_folder": handle_request_load_folder,
    "request_retrain_vae": handle_request_retrain_vae
}



"""
UDP Server Message Types:
    - request_latent: expects {"type": "request_latent", "content": <audio file path>} to encode audio to latent.
    - request_audio: expects {"type": "request_audio", "content": <latent data dict>} to decode latent to audio.
    - request_load_folder: expects {"type": "request_load_folder", "content": <folder path>} to compute features for all audio in the folder and load them for retraining.
    - request_retrain_vae: expects {"type": "request_retrain_vae"} to retrain the VAE using the most recently loaded features.
"""

class SimpleHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        message = json.loads(body.decode())

        # init reply
        reply = {"type": "None", "content": "None"}

        # --- Switch dispatcher ---
        msg_type = message['type']
        print("Python received message of type:", msg_type)
        
        if msg_type in handlers:
            reply = handlers[msg_type](message)
        else:
            print(f"Unknown message type: {msg_type}")
            reply = {"type": "error", "content": f"Unknown message type: {msg_type}"}
        
        reply_bytes = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(reply_bytes)))
        self.end_headers()
        self.wfile.write(reply_bytes)

        print("Python sent reply of type:", reply['type'])


server = HTTPServer(("127.0.0.1", 5000), SimpleHandler)
print("Python server running on port 5000")
server.serve_forever()
