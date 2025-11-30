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

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
