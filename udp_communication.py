from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import random
# from dummy_json import dummy_json
from timbre_VAE.load_audio import BufferManager
from timbre_VAE.load_generative_model import Model, LatentRepresentation, ControlModel
import numpy as np
import json


# --- SETUP DEPENDENCIES/CLASSES –––
latent_representation = LatentRepresentation()
audio_handler = BufferManager()

# --- CONFIGURATION (match learn_subspace.py) ---
model_type = 'STABLE_AUDIO'
model_name = 'percussion'  # or any other model name as needed
model_location = f'timbre_VAE/models/RAVE_models/generative_models/{model_name}.ts'
vae_path = 'precomputed/control_models/Foley_STABLE_AUDIO_audio_commons_preprocessed_sound_data_EX_Noise_120_waterfall_creaks_vae.pt'
feature_type = 'audio_commons'
sample_folder = 'sounds/Foley'

# Load generative model
gen_model = Model(model_type=model_type, model_path=[model_location])

# Get metadata keys using feature type (simulate learn_subspace.py logic)
import os
from timbre_VAE.features import get_features
print(f'preprocessing files')
sound_files = [f for f in os.listdir(sample_folder) if f.endswith(('.wav', '.aif', '.mp3', '.ogg'))][0]
sound_data, feature_keys, _ = get_features([sound_files], feature_type, model=gen_model, save_path=None, overwrite=False, root_folder=sample_folder)
from timbre_VAE.vae_train import prepare_data
_, _, metadata_keys, input_dim, latent_dim = prepare_data(sound_data)

# Load with VAE
# control_model = ControlModel(vae_path, input_dim=input_dim, latent_dim=latent_dim)
gen_model = Model(model_type=model_type, model_path=[model_location], control_vae_path=vae_path, control_vae_input_dim=input_dim, control_vae_latent_dim=latent_dim)


print(f'Loaded generative model and VAE with metadata keys: {metadata_keys}, latent dim: {latent_dim} and input dim: {input_dim}')

def handle_request_latent(message):
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
        # Encode with generative model
        latent_vector, latent_text = gen_model.encode(audio_in)
        assert isinstance(latent_vector, np.ndarray) and isinstance(latent_text, str), 'encodings not right type'
        print('Encoded latent vector has size: ', latent_vector.shape)

        # # Optionally encode with VAE (control model)
        # latent_vector_flat = latent_vector.squeeze(0).T if latent_vector.ndim == 3 else latent_vector
        # vae_z, vae_mu, vae_logvar = control_model.encode(latent_vector_flat)

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
        audio_out = gen_model.decode(latent_vector_scaled, latent_text)
        print("Decoded audio from latent representation successfully.")
        audio_handler.set_output_buffer(audio_out)
        return {"type": "decoded", "content": "Decoded successfully"}
        print(latent_data['vae_z'].shape)
        vae_z_dict = latent_data['vae_z']
        dim_keys = sorted(vae_z_dict.keys(), key=lambda k: int(k.replace('dim', '')))
        vae_z_arr = np.stack([vae_z_dict[k] for k in dim_keys], axis=1)

        # Try both (T, D) and (D, T) and pick the one that works
        try:
            vae_decoded = control_model.decode(vae_z_arr)
            audio_out = gen_model.decode(vae_decoded)
        except Exception as e:
            print(f"First decode attempt failed with shape {vae_z_arr.shape}: {e}")
            vae_z_arr_T = vae_z_arr.T
            vae_decoded = control_model.decode(vae_z_arr_T)
            audio_out = gen_model.decode(vae_decoded)
        audio_handler.set_output_buffer(audio_out)
        return {"type": "decoded", "content": "Decoded successfully"}
    except Exception as e:
        print(f"Error handling latent message: {e}")
        return {"type": "error", "content": f"Error handling latent message: {e}"}


# --- Switch map/dictionary ---
handlers = {
    "request_latent": handle_request_latent,
    "request_audio": handle_request_audio
}


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
