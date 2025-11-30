# Deployment Instructions - MIDI Generator on Proxmox

## Prerequisites
- **Proxmox VE Host** with an NVIDIA GPU (e.g., RTX 2070 Super).
- **NVIDIA Drivers** installed on the host (or passed through to a VM).
- **Docker** and **NVIDIA Container Toolkit** installed.

### Option 1: Docker on Proxmox Host (Direct)
If you have Docker installed directly on the Proxmox host (Debian), follow these steps.

1. **Install NVIDIA Container Toolkit**:
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

### Option 2: Docker in Proxmox LXC Container
If you are running Docker inside an LXC container, you must configure GPU passthrough first.

1. **On Proxmox Host**:
   - Install NVIDIA drivers.
   - Find the GPU device IDs: `ls -l /dev/nvidia*`
   - Edit the LXC config: `/etc/pve/lxc/<CTID>.conf`
   - Add the following lines (adjust cgroup version if needed, usually v2 for Proxmox 7+):
     ```
     lxc.cgroup2.devices.allow: c 195:* rwm
     lxc.mount.entry: /dev/nvidia0 dev/nvidia0 none bind,optional,create=file
     lxc.mount.entry: /dev/nvidiactl dev/nvidiactl none bind,optional,create=file
     lxc.mount.entry: /dev/nvidia-uvm dev/nvidia-uvm none bind,optional,create=file
     lxc.mount.entry: /dev/nvidia-modeset dev/nvidia-modeset none bind,optional,create=file
     ```

2. **Inside LXC Container**:
   - Install the **EXACT SAME VERSION** of NVIDIA drivers as the host using the `.run` file with `--no-kernel-module`.
     ```bash
     ./NVIDIA-Linux-x86_64-xxx.xx.run --no-kernel-module
     ```
   - Install Docker and NVIDIA Container Toolkit as shown in Option 1.
   - **Important**: When running Docker inside LXC, you may need to disable seccomp or run as privileged if you encounter permission errors.
     ```bash
     docker run -d \
       --gpus all \
       --privileged \
       -p 8000:8000 \
       --name midi-gen \
       midi-generator
     ```


## Build and Run

### 1. Get the Code
Clone the repository to your Proxmox host or LXC container:
```bash
git clone https://github.com/raychour/MP3-to-MIDI-Percussion-Generator.git
cd MP3-to-MIDI-Percussion-Generator
```

### 2. Build the Image
Build the Docker image:
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

### Web Interface
1.  Open your browser and navigate to `http://<proxmox-ip>:8000`.
2.  Drag and drop your MP3 file into the drop zone.
3.  Click **Process Audio**.
4.  Once complete, click **Download MIDI** to get your drum loop.

### API Usage
Send a POST request with an MP3 file to the endpoint:
```bash
curl -X POST "http://<proxmox-ip>:8000/process" \
  -F "file=@/path/to/your/song.mp3" \
  --output output_drum_loop.mid
```
