FROM nvidia/cuda:12.6.2-cudnn-devel-ubuntu22.04

RUN apt-get update && apt-get install -y \
        git python3.11 python3-pip \
        ffmpeg libsm6 libxext6 wget


WORKDIR /ml

RUN git clone https://github.com/comfyanonymous/ComfyUI.git

WORKDIR ComfyUI
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -U "huggingface_hub[cli]" \
    gguf
	
RUN wget https://github.com/Daannko/aws/blob/425a1cf00e6063ffa2abd9b79c7b69ae0985d1c9/ComfyUI_scripts/downloader.py .

WORKDIR custom_nodes

RUN git clone https://github.com/ltdrdata/ComfyUI-Manager.git
WORKDIR ComfyUI-Manager
RUN pip install -r requirements.txt && \
    pip install insightface filterpy onnxruntime-gpu


WORKDIR /ml/ComfyUI

CMD ["bash", "-c", "python downloader.py && python main.py"]
