import os
os.environ["HF_HUB_DISABLE_XET"] = "1"

import argparse
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument("--model_name", required=True)
parser.add_argument("--local_dir", required=True)

arg = parser.parse_args()

model_repo_name = arg.model_name
local_dir = arg.local_dir

download_command = [
    "hf", "download", model_repo_name, "--local-dir", local_dir
]


try:
    subprocess.run(download_command, check=True)
    print("Model downloaded successfully")
except subprocess.CalledProcessError as e:
    print(f"Error occurred:\n\n{e}")
except FileNotFoundError:
    print("Error: 'hf' command not found — is huggingface_hub[cli] installed?")