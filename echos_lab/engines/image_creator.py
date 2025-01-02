import os

import replicate
import requests

from echos_lab.common.env import EnvironmentVariables as envs
from echos_lab.common.env import get_env_or_raise

PINATA_UPLOAD_URL = "https://api.pinata.cloud/pinning/pinFileToIPFS"
IMAGE_MODEL = "black-forest-labs/flux-schnell"


def validate_image_envs():
    """
    Validates required replicate and pinata API tokens are set,
    needed to generate images from legacy agents
    """
    get_env_or_raise(envs.REPLICATE_API_TOKEN)
    get_env_or_raise(envs.PINATA_JWT)


def generate(token_symbol: str, token_name: str, token_description: str, image_attributes: str) -> str:
    """
    Generates a token logo based on the name and description
    Saves the image to a file and returns the file path
    """
    filtered_description = token_description.replace("token", "vibe").replace("coin", "vibe")

    image_prompt = f"{filtered_description}. "
    image_prompt = f"{image_attributes}"
    image_output = replicate.run(
        IMAGE_MODEL,
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

    directory_name = os.path.dirname(os.path.abspath(__file__))
    file_name = f"{directory_name}/images/{fname}.png"

    with open(file_name, "wb") as f:
        f.write(file_output.read())
    return file_name


def upload_to_pinata(file_name: str) -> dict:
    """
    Uploads a generated image to pinata, and returns the API response
    """
    headers = {"Authorization": f"Bearer {get_env_or_raise(envs.PINATA_JWT)}"}

    with open(file_name, "rb") as f:
        response = requests.post(
            PINATA_UPLOAD_URL,
            headers=headers,
            files={"file": f},
        )
    return response.json()


def generate_and_upload(token_symbol: str, token_name: str, token_description: str, image_attributes: str) -> str:
    """
    Generates an image for a newly created token, and uploads to pinata
    """
    file_name = generate(token_symbol, token_name, token_description, image_attributes)
    upload_data = upload_to_pinata(file_name)
    if 'IpfsHash' not in upload_data:
        raise ValueError("Failed to upload to Pinata")
    return upload_data['IpfsHash']
