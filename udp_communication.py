from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import builtins
import warnings
import logging
import random
import numpy as np
import torch


# --- CONSOLE LOG DEPTH ---
LOG_DEPTH = os.getenv("LOG_DEPTH", "normal").strip().lower()
if LOG_DEPTH in {"minimal", "quiet", "silent", "0"}:
    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)
    _original_print = builtins.print

    def _minimal_print(*args, **kwargs):
        msg = " ".join(str(a) for a in args).lstrip()
        starts_with_bracket = msg.startswith("[")
        looks_like_warning = (
            "warning" in msg.lower()
            or msg.startswith("UserWarning")
            or msg.startswith("FutureWarning")
            or msg.startswith("DeprecationWarning")
        )
        looks_like_error = (
            "error" in msg.lower()
            or "exception" in msg.lower()
            or "traceback" in msg.lower()
            or "✗" in msg
        )

        # In minimal mode: hide bracket-prefixed logs and warnings, keep errors.
        if (starts_with_bracket or looks_like_warning) and not looks_like_error:
            return
        _original_print(*args, **kwargs)

    builtins.print = _minimal_print

from timbre_VAE.load_audio import BufferManager
from timbre_VAE.load_generative_model import Model, LatentRepresentation, ControlModel
from timbre_VAE.logger import RequestLogger
from timbre_VAE.vae_train import prepare_data, VAE, train_vae
from timbre_VAE.features import batch_compute_features, get_features


# --- SETUP LIGHTWEIGHT DEPENDENCIES –––
request_logger = RequestLogger()
latent_representation = LatentRepresentation()
audio_handler = BufferManager()


# --- CONFIGURATION (defaults – nothing heavy happens here) ---
# model_type = 'RAVE'           # or 'STABLE_AUDIO'
model_type = 'STABLE_AUDIO' 
model_name = 'percussion'
model_location = f'timbre_VAE/models/RAVE_models/generative_models/{model_name}.ts'
vae_path = 'precomputed/control_models/Foley_STABLE_AUDIO_audio_commons_preprocessed_sound_data_EX_Noise_120_waterfall_creaks_vae.pt'
feature_type = 'pca'          # or 'raw_features', 'audio_commons'
sample_folder = 'sounds/Foley'

# --- Mutable state (initialised lazily by handlers) ---
feature_paths = None
folder_path = None
audio_path = None
metadata_keys = None
timbre_gen_model = None

# Load generative model eagerly — it's needed for almost every request
print(f"\n── Loading generative model ({model_type}) …")
gen_model = Model(model_type=model_type, model_path=[model_location])
print("── Generative model ready.\n")

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
    print(f"[load] Folder: {folder_path}")
    if not folder_path or not os.path.isdir(folder_path):
        return {"type": "error", "content": f"Invalid folder path: {folder_path}"}
    try:
        from mass_preprocess import mass_preprocess
        # Compute features (or use precomputed)
        feature_paths = mass_preprocess(folder_path, 
                                        model_name=model_name, 
                                        model_type=model_type, 
                                        overwrite=False)
        cache_key = 'raw_features' if feature_type in ('pca', 'PCA') else feature_type
        feature_save_path = feature_paths[cache_key]
        # print(f"Using features from: {feature_save_path}")

        # Store for retraining
        _last_loaded_features = {
            'folder_path': folder_path,
            'feature_save_paths': feature_paths,
            'sound_data': None,
            'feature_keys': None,
            'last_sample_file': audio_path,
            'last_sample_dir': folder_path
        }
        return {"type": "load_folder", "content": f"Features computed and loaded for {folder_path}"}
    except Exception as e:
        print(f"[load] ✗ {e}")
        return {"type": "error", "content": f"Error processing folder: {e}"}

# New: Handler for retraining VAE using last loaded features
def handle_request_retrain_vae(message):
    global feature_paths, folder_path, audio_path, metadata_keys, _last_loaded_features
    global timbre_gen_model
    print("[retrain] Starting VAE retrain …")
    try:
        # Determine which folder to use
        active_folder = folder_path or sample_folder
        if not active_folder or not os.path.isdir(active_folder):
            raise ValueError(f'No valid folder path available (folder_path={folder_path}, sample_folder={sample_folder})')

        # Load features for folder
        # Prefer _last_loaded_features, fallback to global, fallback to computing fresh
        cache_key = 'raw_features' if feature_type in ('pca', 'PCA') else feature_type
        feature_save_path = None
        if _last_loaded_features and 'feature_save_paths' in _last_loaded_features:
            feature_save_path = _last_loaded_features['feature_save_paths'].get(cache_key)
        elif feature_paths:
            feature_save_path = feature_paths.get(cache_key) if isinstance(feature_paths, dict) else feature_paths

        print(f"[retrain] Feature source: {feature_save_path or 'computing fresh'}")
        # PCA uses raw_features underneath — load/compute as raw_features, project later
        compute_type = 'raw_features' if feature_type in ('pca', 'PCA') else feature_type
        sound_data, metadata_keys, pca = get_features(
            [f for f in os.listdir(active_folder) if f.endswith(('.wav', '.aif', '.mp3', '.ogg'))],
            compute_type,
            model=gen_model,
            save_path=feature_save_path,
            overwrite=False,
            root_folder=active_folder
        )

        # Load features for sample — compute raw features, PCA is applied on the combined set
        sample_sound_features, _, _ = batch_compute_features([audio_path], root_folder='', use_recon=True, model=gen_model, feature_type=compute_type)
        
        # Append the example features to the main sound_data list
        if sample_sound_features:
            sound_data = sound_data + sample_sound_features
        print(f"[retrain] {len(sound_data)} samples (incl. example)")

        # Re-run feature selection on the combined data so all samples share the same keys
        if feature_type in ('pca', 'PCA'):
            from timbre_VAE.features import pca_attributes
            metadata_keys, reduced_dicts, pca = pca_attributes(sound_data, 'features_recon')
            for i, rd in enumerate(reduced_dicts):
                sound_data[i]['features_recon'] = rd
        else:
            from timbre_VAE.features import filter_attributes
            metadata_keys, _ = filter_attributes(sound_data, 'features_recon')

        print(f"[retrain] {len(metadata_keys)} feature dims selected")

        # Prepare data for the combined set
        latent_data, metadata_vectors, metadata_keys_new, input_dim_new, latent_dim_new = prepare_data(sound_data, metadata_keys=metadata_keys)
        print(f"[retrain] Data prepared: {latent_data.shape[0]} frames, in={input_dim_new}, z={latent_dim_new}")
    # else:
        #     print("No example file to add, preparing data from sound_data only.")
        #     latent_data, metadata_vectors, metadata_keys_new, input_dim_new, latent_dim_new = prepare_data(sound_data)
        #     print(f"prepare_data output: latent_data shape {latent_data.shape}, metadata_keys_new: {metadata_keys_new}, input_dim_new: {input_dim_new}, latent_dim_new: {latent_dim_new}")
        #     input_dim_new = latent_data.shape[1]
        #     latent_dim_new = len(metadata_vectors[0][0]) if metadata_vectors and hasattr(metadata_vectors[0], '__getitem__') else latent_data.shape[1]
        #     print(f"Adjusted input_dim_new: {input_dim_new}, latent_dim_new: {latent_dim_new}")
        # print("Initializing VAE...")
        vae = VAE(input_dim=input_dim_new, latent_dim=latent_dim_new)
        vae, loss_lists, loss_labels = train_vae(vae, latent_data, metadata_vectors, num_epochs=250, batch_size=128, learning_rate=1e-3, plot_loss=True)
        print(f"[retrain] VAE trained — final loss: {loss_lists[0][-1]:.1f}")
        # Update global model (in-memory)
        timbre_gen_model = Model(model_type=model_type, model_path=[model_location], control_vae_path=None, control_vae_input_dim=input_dim_new, control_vae_latent_dim=latent_dim_new)
        timbre_gen_model.control_model = vae
        print(f"[retrain] Model updated for {_last_loaded_features['folder_path']}")
        # Encode the example audio with the new VAE and include latent in reply
        latent_reply = handle_request_latent({"type": "request_latent", "content": audio_path})
        result = {
            "type": "retrain_done",
            "content": f"VAE retrained for {_last_loaded_features['folder_path']} (sample added: {audio_path})"
        }
        if latent_reply and latent_reply.get("type") == "latent":
            result["latent"] = latent_reply["content"]
        return result
    except Exception as e:
        print(f"[retrain] ✗ {e}")
        return {"type": "error", "content": f"Error retraining VAE: {e}"}

def handle_request_latent(message):
    global audio_path, metadata_keys, timbre_gen_model
    filepath = message['content']
    print(f"[encode] File: {os.path.basename(filepath)}")

    audio_path = filepath.strip('""')
    try:
        audio_handler.load_buffer(audio_path)
        audio_in = audio_handler.get_input_buffer()
        assert isinstance(audio_in, np.ndarray), 'internal buffer has wrong type, not numpy'
    except Exception as e:
        print(f"[encode] ✗ Load failed: {e}")
        return {"type": "error", "content": f"Error loading audio: {e}"}

    try:
        if timbre_gen_model is None or timbre_gen_model.control_model is None:
            audio_handler.set_output_buffer(audio_in)
            print("[encode] ⚠ No model trained yet — passthrough input to output")
            print("No model trained yet. Passing input audio through to output.")
            return {
                "type": "warning",
                "content": "No model trained yet. Passing input audio through to output."
            }
        # Encode with generative model
        latent_vector, latent_text = timbre_gen_model.encode(audio_in)
        assert isinstance(latent_vector, np.ndarray) and isinstance(latent_text, str), 'encodings not right type'
        print(f'[encode] Latent shape: {latent_vector.shape}')

        # to json
        latent_representation.set_latent_representation(latent_vector, latent_text)
        latent_representation.fit(output_range=2)
        latent_json = latent_representation.to_json()
        assert isinstance(latent_json, dict), 'json not a dictionary'

        bias_array = [0 for _ in range(len(metadata_keys))]
        scale_array = [1 for _ in range(len(metadata_keys))]
        latent_json['bias'] = bias_array
        latent_json['scale'] = scale_array
        latent_json['metadata_keys'] = [k.replace('_', ' ').title() for k in metadata_keys]

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
        print(f"[encode] ✗ {e}")
        return {"type": "error", "content": f"Error encoding latent: {e}"}


def handle_request_audio(message):
    global audio_path
    latent_data = message['content']
    print("[decode] Received latent data")
    try:
        if timbre_gen_model is None or timbre_gen_model.control_model is None:
            passthrough_audio = audio_handler.get_input_buffer()
            if isinstance(passthrough_audio, np.ndarray):
                audio_handler.set_output_buffer(passthrough_audio, save_plot=True)
                print("[decode] ⚠ No model trained yet — passthrough input to output")
                print("No model trained yet. Passing input audio through to output.")
                return {
                    "type": "warning",
                    "content": "No model trained yet. Passing input audio through to output."
                }

        if not isinstance(latent_data, dict):
            # Try to parse as JSON string
            try:
                latent_data = json.loads(latent_data)
            except Exception as e:
                raise ValueError(f"Could not parse latent_data as JSON: {e}")
            if not isinstance(latent_data, dict):
                raise ValueError("Expected a dictionary for latent_data after JSON parse, got {}".format(type(latent_data)))
        latent_representation.from_json(latent_data)
        bias = np.array(latent_data['bias'], dtype=np.float32)
        scale = np.array(latent_data['scale'], dtype=np.float32)
        latent_vector, latent_text = latent_representation.get_latent_representation()

        # Ensure bias/scale match the number of latent dims
        n_latent = latent_vector.shape[1]
        bias = bias[:n_latent].reshape(1, n_latent, 1)
        scale = scale[:n_latent].reshape(1, n_latent, 1)
        latent_vector_scaled = latent_vector * scale + bias
        audio_out = timbre_gen_model.decode(latent_vector_scaled, latent_text)
        print("[decode] Done")
        audio_handler.set_output_buffer(audio_out, save_plot=True)
        return {"type": "decoded", "content": "Decoded successfully"}
        
    except Exception as e:
        print(f"[decode] ✗ {e}")
        return {"type": "error", "content": f"Error handling latent message: {e}"}

# Handler for setting regularisation/model_type and reloading the generative model
def handle_set_regularisation(message):
    global feature_type, folder_path
    reg_type = message.get('content')
    print(f"[config] Feature type → {reg_type}")
    valid_types = ['pca', 'raw_features', 'audio_commons']
    if reg_type in valid_types:
        feature_type = reg_type
        # Reload folder if already loaded
        if folder_path:
            print(f"[config] Reloading folder with {feature_type} …")
            folder_reply = handle_request_load_folder({'content': folder_path})
            if folder_reply.get("type") == "error":
                return folder_reply
            return {
                "type": "set_regularisation_done",
                "content": f"Set feature_type to {feature_type} and reloaded folder: {folder_path}."
            }
        else:
            return {
                "type": "set_regularisation_done",
                "content": f"Set feature_type to {feature_type}. No folder loaded yet."
            }
    else:
        return {"type": "error", "content": f"Unknown regularisation type: {reg_type}"}


# --- Handler for export_sound (logging only, no-op) ---
def handle_export_sound(message):
    """Log the export-sound request and return an acknowledgement. No side-effects."""
    return {"type": "export_sound_logged", "content": "Export sound event logged."}


# --- Handler for saving / exporting logs ---
def handle_save_logs(message):
    """Open a save-file dialogue so the user can export the request/response log."""
    print(f"[logs] Saving {request_logger.count} entries …")
    saved_path = request_logger.open_save_dialogue()
    if saved_path:
        return {"type": "save_logs_done", "content": f"Logs saved to {saved_path}"}
    else:
        return {"type": "save_logs_cancelled", "content": "Save dialog was cancelled or failed."}


# --- Switch map/dictionary ---
handlers = {
    "request_latent": handle_request_latent,
    "request_audio": handle_request_audio,
    "request_load_folder": handle_request_load_folder,
    "request_retrain_vae": handle_request_retrain_vae,
    "set_regularisation": handle_set_regularisation,
    "export_sound": handle_export_sound,
    "save_logs": handle_save_logs,
    "export_logs": handle_save_logs,
}



"""
UDP Server Message Types:
    - request_latent: expects {"type": "request_latent", "content": <audio file path>} to encode audio to latent.
    - request_audio: expects {"type": "request_audio", "content": <latent data dict>} to decode latent to audio.
    - request_load_folder: expects {"type": "request_load_folder", "content": <folder path>} to compute features for all audio in the folder and load them for retraining.
    - request_retrain_vae: expects {"type": "request_retrain_vae"} to retrain the VAE using the most recently loaded features.
    - export_sound: expects {"type": "export_sound", "content": <any>} to log an export-sound event (no-op, logging only).
    - save_logs / export_logs: expects {"type": "save_logs"} or {"type": "export_logs"} to open a file-save dialog and export all logged requests/responses.
"""

class SimpleHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence default HTTP access logs in minimal mode.
        if LOG_DEPTH in {"minimal", "quiet", "silent", "0"}:
            return
        super().log_message(format, *args)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        message = json.loads(body.decode())

        # init reply
        reply = {"type": "None", "content": "None"}

        # --- Switch dispatcher ---
        msg_type = message['type']
        if msg_type in handlers:
            reply = handlers[msg_type](message)
        else:
            reply = {"type": "error", "content": f"Unknown message type: {msg_type}"}
        
        # --- Log request + response ---
        request_logger.log(request=message, response=reply)

        reply_bytes = json.dumps(reply).encode()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(reply_bytes)))
            self.end_headers()
            self.wfile.write(reply_bytes)
        except BrokenPipeError:
            print(f"[server] Client disconnected (type: {reply.get('type', '?')})")

        print(f"← {reply['type']}")


server = HTTPServer(("127.0.0.1", 5000), SimpleHandler)
print("\n🎛  MALT server listening on http://127.0.0.1:5000\n")
server.serve_forever()
