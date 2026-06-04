# How to Run

There are two versions of this software:

- **Standalone** (`dist_standalone_*`) — no additional software required. Includes a self-contained app.
- **Max** (`dist_max_*`) — requires Max/MSP to be installed. Includes the Max patch for advanced patching.

## Installation

### Standalone version

1. Run the `run_server` script — this launches the backend server required to encode and decode audio. Keep it in the same folder as everything else.
2. Open the `frontend.app` included in the folder.

### Max version

1. Download and install [Max/MSP](https://cycling74.com/downloads).
2. Run the `run_server` script — this launches the backend server. Keep it in the same folder as everything else.
3. A user interface should launch; if not, open `frontend/frontend.maxpat` manually.

## Training Model

MALT is a system for manipulating an audio sample using a corpus of sounds. It needs a folder of samples to do this. Select a folder of samples by clicking the load folder (1) button in the interface. Note: all sounds should be less than 40 seconds long.

To train a model, press the retrain_vae (4) button in the interface. Before doing this, you can select a representation mode from the following:

- **Raw audio features**: Computes raw audio features such as pitch and spectral centroid
- **Semantic**: Computes timbre semantic features such as 'hardness', 'brightness' etc. based on AudioCommons descriptors
- **PCA**: Find 4 principal components which create the most change in the descriptors. These are unlabeled but can create huge changes in the characteristics of the sound

## Manipulating Sounds

Once a model has been trained, import a sample with the `import sample` (2) button. You can preview, loop, and export your sample. To support our research, export logs with each sample export. To manipulate your sound, use:

- **Bias sliders**: These shift an aspect of a sound (e.g., make it brighter)
- **Scale sliders**: These accentuate existing aspects of the sound (e.g., make the bright bits brighter with positive values, or make the bright bits darker with negative values)
- **Trajectory sliders**: You can see the movement of an aspect over time with the trajectory sliders. Draw new trajectories to influence the sound
