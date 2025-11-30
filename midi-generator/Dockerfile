FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

WORKDIR /app

# Install system dependencies
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    git \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install build dependencies first (Cython is required for madmom)
RUN pip install --no-cache-dir Cython numpy

# Install Python dependencies
# Note: omnizart might require some specific handling, we'll start with pip
RUN pip install --no-cache-dir -r requirements.txt

# Install omnizart models (this might be large, better to do it in build or run script, 
# but for now let's try to install the package properly)
# Omnizart requires `omnizart download-checkpoints` to be run. 
# We will do this in the entrypoint or a separate setup step to avoid huge image size if possible,
# or bake it in if we want faster startup. Let's bake it in for convenience.
RUN omnizart download-checkpoints

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
