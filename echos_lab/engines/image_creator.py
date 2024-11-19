import replicate
import requests
from dotenv import load_dotenv

import os

# link to _this_file
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
load_dotenv(f"{BASE_PATH}/../.env")

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
if REPLICATE_API_TOKEN == "":
    raise ValueError("REPLICATE_API_TOKEN not found in .env file")

PINATA_JWT = os.getenv("PINATA_JWT", "")
if PINATA_JWT == "":
    raise ValueError("PINATA_JWT not found in .env file")

IMAGE_MODEL = "black-forest-labs/flux-schnell"


def generate(token_symbol: str, token_name: str, token_description: str, image_attributes: str) -> str:
    '''
    Generates a token logo based on the name and description
    Saves the image to a file and returns the file path
    '''
    filtered_description = token_description.replace("token", "vibe").replace("coin", "vibe")
    image_prompt = f"{filtered_description}. "
    image_prompt = f"{image_attributes}"
    image_output = replicate.run(
        "black-forest-labs/flux-schnell",
        input={
            "prompt": image_prompt,
            "go_fast": True,
            "megapixels": "1",
            "num_outputs": 1,
            "aspect_ratio": "1:1",
            "output_format": "png",
            "output_quality": 80,
            "num_inference_steps": 4,
        },
    )
    file_output = image_output[0]  # type: ignore
    alphanumeric_name = "".join(c for c in token_name if c.isalnum())
    fname = f"{token_symbol}_{alphanumeric_name}"
    file_name = f"{BASE_PATH}/images/{fname}.png"
    with open(file_name, "wb") as f:
        f.write(file_output.read())
    return file_name


def upload_to_pinata(file_name: str) -> dict:
    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
    headers = {"Authorization": f"Bearer {PINATA_JWT}"}

    with open(file_name, "rb") as f:
        response = requests.post(
            url,
            headers=headers,
            files={"file": f},
        )
    return response.json()


def generate_and_upload(token_symbol: str, token_name: str, token_description: str, image_attributes: str) -> str:
    file_name = generate(token_symbol, token_name, token_description, image_attributes)
    upload_data = upload_to_pinata(file_name)
    if 'IpfsHash' not in upload_data:
        raise ValueError("Failed to upload to Pinata")
    return upload_data['IpfsHash']
