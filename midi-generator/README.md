# MP3 to MIDI Percussion Generator

A Dockerized Python application that transforms MP3 audio files into MIDI percussion sequences. Designed for musicians and producers, it automatically extracts drum tracks, identifies the best loopable section, and transcribes it into MIDI for use in your DAW.

## Key Features

*   **GPU-Accelerated Source Separation**: Uses **Demucs** (Hybrid Transformer) powered by PyTorch and CUDA to isolate drums from full mixes with state-of-the-art quality.
*   **Intelligent Loop Detection**: Features a custom "4 on the Floor" heuristic to find the most rhythmic, bass-heavy sections of the track.
*   **Advanced Transcription**: Uses spectral analysis to distinguish between Kick, Snare, and Hi-Hats.
*   **Adjustable Quantization**: Selectable output quantization (1/4, 1/8, 1/16, 1/32) to snap beats to the grid for easy DAW integration.
*   **Web Interface**: Simple drag-and-drop UI with real-time progress tracking and tempo detection.
*   **Containerized**: Fully Dockerized with NVIDIA GPU passthrough support for easy deployment on Proxmox or Linux servers.

## Algorithmic Innovations

This project implements custom signal processing logic to improve upon standard beat detection libraries:

### 1. "4 on the Floor" Loop Selection
Standard "loudness" detection often picks sections with loud vocals or crashes. Our algorithm prioritizes the "groove":
*   **Low-Pass Filtering**: The audio is filtered at **200Hz** before analysis.
*   **Onset Strength**: We calculate the rhythmic energy of this bass-heavy signal.
*   **Groove Matching**: The system looks for the 4-bar window with the highest low-end rhythmic activity, ensuring the selected loop captures the core beat (Kick/Bass) rather than just high-frequency noise.

### 2. Band Energy Ratio Classification
To accurately distinguish between Kicks, Snares, and Hi-Hats, we moved beyond simple spectral centroids:
*   **Band Energy Split**: For each detected hit, we compare the energy in the **Low Band (<150Hz)** versus the **High Band (>2000Hz)**.
*   **Ratio Analysis**:
    *   **Kick**: If Low Energy dominates (Low > 0.8 * High), it's classified as a Kick (MIDI 36).
    *   **Snare/Hat**: If High Energy dominates, we use the **Spectral Centroid** to further distinguish between a Snare (MIDI 38) and a Closed Hi-Hat (MIDI 42).
This approach significantly reduces false positives where a heavy Snare might be mistaken for a Kick due to its body, or a Kick mistaken for a low tom.

## GPU Acceleration (CUDA)

This application is built to leverage **NVIDIA CUDA** cores for massive performance gains:

*   **Parallel Processing**: The core separation engine, **Demucs**, is a deep learning model based on Hybrid Transformers. These models involve millions of matrix multiplications that can be executed in parallel on a GPU.
*   **Speedup**: On a CPU, separating a 3-minute song might take 2-3 minutes (1x real-time). With a GPU like the **NVIDIA RTX 2070 Super**, this drops to seconds (often 20-50x faster), allowing for near-instant feedback in the web UI.
*   **PyTorch Optimization**: The Docker image is built on `pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime`, ensuring that all tensor operations are natively optimized for the underlying hardware.

## Deployment

See [deployment.md](deployment.md) for detailed instructions on how to deploy this on a Proxmox LXC container with GPU passthrough.
