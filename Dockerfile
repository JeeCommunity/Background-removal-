FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Node.js, npm, wget for pre-downloading model
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    wget \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy package files and install frontend dependencies
COPY package.json bun.lock* ./
RUN npm install --legacy-peer-deps

# Copy frontend source and build
COPY index.html vite.config.ts tsconfig.json ./
COPY src ./src
RUN npm run build

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the ultra-lightweight u2netp model (4.7MB) during build
# so it is permanently baked into the Docker image and NEVER downloads at runtime!
RUN mkdir -p /root/.u2net && \
    wget -q --show-progress -O /root/.u2net/u2netp.onnx https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx

# Copy backend code
COPY main.py .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
