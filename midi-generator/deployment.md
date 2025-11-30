# Deployment Instructions - MIDI Generator on Proxmox

## Prerequisites
- **Proxmox VE Host** with an NVIDIA GPU (e.g., RTX 2070 Super).
- **NVIDIA Drivers** installed on the host (or passed through to a VM).
- **Docker** and **NVIDIA Container Toolkit** installed.

### 1. Install NVIDIA Container Toolkit (if not already installed)
On your Docker host (Proxmox shell or VM):
```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
      && curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
      && curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
            sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
            sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

## Build and Run

### 1. Build the Image
Navigate to the project directory and build the Docker image:
```bash
docker build -t midi-generator .
```
*Note: The build process will download Omnizart checkpoints, so it might take a few minutes.*

### 2. Run the Container
Run the container with GPU access:
```bash
docker run -d \
  --gpus all \
  -p 8000:8000 \
  --name midi-gen \
  midi-generator
```

### 3. Verify GPU Access
Check the logs to ensure everything started correctly:
```bash
docker logs -f midi-gen
```
You can also exec into the container and check `nvidia-smi`:
```bash
docker exec -it midi-gen nvidia-smi
```

## Usage
Send a POST request with an MP3 file to the endpoint:
```bash
curl -X POST "http://<proxmox-ip>:8000/process" \
  -F "file=@/path/to/your/song.mp3" \
  --output output_drum_loop.mid
```
