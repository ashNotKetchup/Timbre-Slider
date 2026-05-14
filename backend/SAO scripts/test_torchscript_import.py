"""
Testing TorchScript Model Import

This script demonstrates how to import and test the exported TorchScript model in Python.

The TorchScript model (`stable-ae-float32-torch25x.ts`) is a serialized PyTorch model 
that can be loaded and used for inference without the original source code.
"""

import librosa
import numpy as np
import soundfile as sf
import torch



# Setup device
device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
print(f"Device: {device}")

# Load TorchScript model
model_path = "streamable-stable-audio-open/exported/stable-ae-float32-torch25x.ts"
model = torch.jit.load(model_path, map_location=device)
model.eval()
print(f"\nModel loaded from: {model_path}")
print(f"Model type: {type(model)}")

# Load test audio
audio_path = librosa.example('fishin', hq=True)
wv, sr = librosa.load(audio_path, sr=44100, mono=False)
# Use longer audio: 3 seconds at 44100 Hz = 132,300 samples
duration_samples = int(sr * 3)  # 3 seconds
x = torch.tensor(wv, device=device)[:, :duration_samples].unsqueeze(0)

print(f"\nInput audio shape: {x.shape}")
print(f"  Batch: {x.shape[0]}, Channels: {x.shape[1]}, Samples: {x.shape[2]}")

# Encode
with torch.no_grad():
    latent = model.encode(x)

print(f"\nLatent shape: {latent.shape}")
print(f"  Batch: {latent.shape[0]}, Latent dims: {latent.shape[1]}, Time: {latent.shape[2]}")

# Decode
with torch.no_grad():
    y = model.decode(latent)

print(f"\nDecoded audio shape: {y.shape}")
print(f"  Batch: {y.shape[0]}, Channels: {y.shape[1]}, Samples: {y.shape[2]}")

# Save input and output audio
sr = 44100
x_np = x.cpu().numpy()[0]  # Remove batch dimension
y_np = y.cpu().numpy()[0]  # Remove batch dimension

sf.write("test_input.wav", x_np.T, sr)  # Transpose to (samples, channels)
sf.write("test_output.wav", y_np.T, sr)  # Transpose to (samples, channels)

print(f"\nSaved audio files:")
print(f"  Input:  test_input.wav")
print(f"  Output: test_output.wav")
print(f"\n✓ Success!")


