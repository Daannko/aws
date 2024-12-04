from os import system, name
import sys
import os
from concurrent.futures import ThreadPoolExecutor
import subprocess
from getpass import getpass

import requests.exceptions


def login_to_hf():
    inp = ""
    while inp != "y" and inp != "n" and inp != "Y" and inp != "N":
        inp = input("Do you want to login to hf? (y/n)")

    if inp == "n":
        return "Not logged in"

    token = getpass("HF-cli token: ")
    print("Logging in...")
    result = subprocess.run(["huggingface-cli", "login", "--token", token], capture_output=True, text=True)
    if "Login successful." in result.stderr:
        output = "Logged as " + subprocess.run(["huggingface-cli", "whoami"], capture_output=True, text=True).stdout
    else:
        output = f'Failed to login: Invalid token'
    return output


def clear():
    if name == 'nt':
        _ = system('cls')  # For windows
    else:
        _ = system('clear')  # Linux


def run_download(command):
    print(f"Running: {command}")
    os.system(command)


def download():
    clear()
    download = []
    for category in files_download.keys():
        if files_download[category] is None or len(files_download[category]) == 0:
            continue
        print(f'{category}: ')
        for file in files_download[category]:
            print(f'\t{file}')
            download.append(downloads.get(category).get(file) + " --quiet")
    with ThreadPoolExecutor() as executor:
        executor.map(run_download, download)


def get_input_int(size):
    try:
        print("\nq - exit\tc - continue")
        inp = input(f'Chose option (1 - {size}):')
        if inp == 'q':
            download()
            quit(0)
        elif inp == 'c':
            return -1
        inp = int(inp) - 1
        if inp < 0 or inp >= size:
            return -2
        return inp
    except SystemExit:
        exit(0)
    except:
        return -2


downloads = {
    "unet": {
        "flux1-dev-Q8_0.gguf": "huggingface-cli download city96/FLUX.1-dev-gguf flux1-dev-Q8_0.gguf --local-dir models/unet",
        "AWPortrait-FL-fp8.safetensors": "huggingface-cli download Shakker-Labs/AWPortrait-FL AWPortrait-FL-fp8.safetensors --local-dir models/unet",
        "flux-dev-fp8.safetensors": "huggingface-cli download XLabs-AI/flux-dev-fp8 flux-dev-fp8.safetensors --local-dir models/unet"
    },
    "clip": {
        "t5-v1_1-xxl-encoder-Q8_0.gguf": "huggingface-cli download city96/t5-v1_1-xxl-encoder-gguf t5-v1_1-xxl-encoder-Q8_0.gguf --local-dir models/clip",
        "t5xxl_fp8_e4m3fn_scaled.safetensors": "huggingface-cli download comfyanonymous/flux_text_encoders t5xxl_fp8_e4m3fn_scaled.safetensors --local-dir models/clip",
        "clip_l.safetensors": "huggingface-cli download comfyanonymous/flux_text_encoders clip_l.safetensors --local-dir models/clip"
    },
    "vae": {
        "diffusion_pytorch_model.safetensors": "huggingface-cli download black-forest-labs/FLUX.1-dev vae/diffusion_pytorch_model.safetensors --local-dir models/vae",
        "ae.safetensors": "huggingface-cli download black-forest-labs/FLUX.1-dev ae.safetensors --local-dir models/vae"
    },
    "loras": {
        "FLUX-dev-lora-AntiBlur.safetensors": "huggingface-cli download Shakker-Labs/FLUX.1-dev-LoRA-AntiBlur FLUX-dev-lora-AntiBlur.safetensors --local-dir models/loras",
        "lora.safetensors": "huggingface-cli download XLabs-AI/flux-RealismLora lora.safetensors --local-dir models/loras --quiet",
        "AWPortrait-FL-lora.safetensors": "huggingface-cli download Shakker-Labs/AWPortrait-FL AWPortrait-FL-lora.safetensors --local-dir models/loras",
        "filmfotos.safetensors": "huggingface-cli download Shakker-Labs/FilmPortrait filmfotos.safetensors --local-dir models/loras",
        "araminta_k_flux_koda.safetensors": "huggingface-cli download alvdansen/flux-koda araminta_k_flux_koda.safetensors --local-dir models/loras",
        "Canopus-LoRA-Flux-UltraRealism.safetensors": "huggingface-cli download prithivMLmods/Canopus-LoRA-Flux-UltraRealism-2.0 Canopus-LoRA-Flux-UltraRealism.safetensors --local-dir models/loras"
    },
    "controlnet": {
        "diffusion_pytorch_model.safetensors": "huggingface-cli download InstantX/FLUX.1-dev-Controlnet-Union diffusion_pytorch_model.safetensors --local-dir models/controlnet"
    },
    "upscale_models": {
        "diffusion_pytorch_model.safetensors": "huggingface-cli download jasperai/Flux.1-dev-Controlnet-Upscaler diffusion_pytorch_model.safetensors --local-dir models/upscale_models"
    }
}

args = sys.argv
login_output = login_to_hf()

categories = [list(downloads.keys())][0]
n_categories = len(categories)

files_download = {}

inp_c = ""
inp_f = ""
# Print categories
flag = False
# Chose categories
while True:
    clear()
    print(login_output)
    for i, category in enumerate(categories):
        print(f'{i + 1}. {category}')
    if flag:
        print("Invalid Input!")
        flag = False
    inp_c = get_input_int(n_categories)
    if inp_c == -1:
        break
    elif inp_c == -2:
        flag = True
        continue

    category = categories[inp_c]
    files = list(downloads.get(category).keys())
    n_files = len(files)
    if files_download.get(category) is None:
        files_download[category] = []

    while True:
        clear()
        print(f'{category:}')
        for j, file in enumerate(files):
            print(f'{j + 1}. {"X" if files[j] in files_download[category] else " "} {file}')

        if flag:
            print("Invalid Input!")
            flag = False

        inp_f = get_input_int(n_files)
        if inp_f == -1:
            break
        elif inp_f == -2:
            flag = True
            continue

        file = files[inp_f]
        if file in files_download[category]:
            files_download[category].remove(file)
        else:
            files_download[category].append(file)

download()
