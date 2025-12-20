FROM python:3.9-slim-bullseye

# 1. System Dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    zlib1g-dev \
    wget \
    tar \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Install Python Dependencies
# We copy requirements first to leverage Docker caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Download and Compile C Tools
# This layer won't rebuild unless you change this block
RUN wget ftp://ita.ee.lbl.gov/software/WorldCup_tools.tar.gz && \
    tar -xzvf WorldCup_tools.tar.gz && \
    gcc -O2 -o read_log -I ita_public_tools/src ita_public_tools/src/read.c ita_public_tools/src/endian.c -lz

# 4. Copy Application Code
# This is last because it changes the most often
COPY parser.py .

CMD ["bash"]
