"""
Utility functions for generating memes using the Imgflip API.
"""

from typing import Dict

import requests

from echos_lab.common.env import EnvironmentVariables as envs
from echos_lab.common.env import get_env_or_raise

IMGFLIP_API_ENDPOINT = "https://api.imgflip.com"

GET_MEME_URL = f"{IMGFLIP_API_ENDPOINT}/get_meme"
CAPTION_IMAGE_URL = f"{IMGFLIP_API_ENDPOINT}/caption_image"
AUTO_MEME_URL = f"{IMGFLIP_API_ENDPOINT}/automeme"


def imgflip_request(url: str, payload: dict, remove_watermark: bool = False) -> dict:
    """
    Confirms the user has specified an imgflip username and password and
    submits the request to the specified URL
    The username and password (and optionally specification to remove watermark)
    will be appended to the payload
    Returns the JSON data under "data", or raises an error if the request fails
    """
    auth = {
        "username": get_env_or_raise(envs.IMGFLIP_USERNAME),
        "password": get_env_or_raise(envs.IMGFLIP_PASSWORD),
        "no_watermark": 1 if remove_watermark else None,
    }
    payload = {**payload, **auth}
    response = requests.post(url, data=payload)
    response.raise_for_status()

    response_json = response.json()
    if response_json["success"]:
        return response_json["data"]

    error_message = response_json.get("error_message", "Unknown error")
    raise RuntimeError(f"Imgflip API error: {error_message}")


def load_meme_attributes(meme_id: int) -> Dict:
    """
    Get the attributes of an Imgflip meme template.

    Args:
        meme_id (int): The ID of the Imgflip meme template.

    Returns:
        A dictionary with keys "url" and "page_url" as reported by Imgflip.
    """
    payload = {"template_id": meme_id}
    return imgflip_request(url=GET_MEME_URL, payload=payload)


def caption_meme(
    template_id: int,
    *texts: str,
    font: str = 'impact',
    remove_watermark: bool = False,
) -> Dict:
    """
    Add a caption to an Imgflip meme template.

    Args:
        template_id (int): The ID of the Imgflip meme template.
        *texts: Variable number of text strings for the meme (up to 20).
        font (str): Current options are 'impact' and 'arial'. Defaults to 'impact'.
    Returns:
        A dictionary with keys "url" and "page_url" as reported by Imgflip.
    Raises:
        HTTPError: if the API cannot be reached or returns an invalid response.
        RuntimeError: if the API indicates an unsuccessful response.
        TypeError: if meme id is an invalid type
        ValueError: if font is passed an incorrect value or too many text arguments
    """
    if font.lower().strip() not in ["impact", "arial"]:
        raise ValueError("Font parameter must be either 'impact' or 'arial'.")

    # Get the meme attributes for the particular meme type (aka template)
    meme_attributes = load_meme_attributes(template_id)["meme"]

    # Confirm the provided text arguments can fit in the template
    box_count = meme_attributes["box_count"]
    if len(texts) > box_count:
        raise ValueError(f"Too many text arguments. Maximum is {box_count}, got {len(texts)}.")

    # Prepare boxes for the meme, and set text color
    # TODO: customize text color for white/black bg memes
    boxes = [{"text": text, "color": "#ffffff", "outline_color": "#000000"} for text in texts]

    # Prepare the payload
    # Format boxes as box[i][key]
    box_params = {f"boxes[{i}][{key}]": value for i, box in enumerate(boxes) for key, value in box.items()}
    payload = {"template_id": template_id, **box_params}

    return imgflip_request(url=CAPTION_IMAGE_URL, payload=payload, remove_watermark=remove_watermark)


def generate_automeme(text: str, remove_watermark: bool = False) -> Dict[str, str]:
    """
    Generate a meme using Imgflip's automeme API.

    Args:
        text (str): The text to display on the meme. This will also determine
                   which meme template to use.
        remove_watermark (bool, optional): If True, removes the imgflip.com watermark.
                                     Defaults to False.

    Returns:
        Dict[str, str]: Response data containing the meme URL and other metadata

    Raises:
        ValueError: If Imgflip credentials are missing from environment variables
        RuntimeError: If the API request fails
        requests.exceptions.RequestException: If there's a network error
    """
    payload = {"text": text}
    return imgflip_request(url=AUTO_MEME_URL, payload=payload, remove_watermark=remove_watermark)


# TODO: Remove after memes is working
# Example usage (uncomment to run various examples)
# >>> python echos_labs/engines/memes.py
if __name__ == "__main__":

    try:
        # caption_result = caption_meme(400, "Top text", "Bottom text")
        caption_result = caption_meme(29617627, "look at me", "i am the corruption now")
        # caption_result = caption_meme(84341851, "just tell the truth", "plead the fifth on everything")
        # caption_result = caption_meme(
        # 252758727, "housing crisis", "student debt", "avocado toast", "boomers blaming millennials"
        # )
        print(f"Captioned meme URL: {caption_result['url']}")
    except Exception as e:
        print(f"Error captioning meme: {str(e)}")

    # try:
    #     meme_attributes = load_meme_attributes(61544)
    #     print(f"Meme attributes: {meme_attributes}")
    # except Exception as e:
    #     print(f"Error loading meme attributes: {str(e)}")

    # result = generate_meme("Oh, you're rerunning the election? Tell me more about how democratic that is")
    # print(f"{result.get('url')}")
    # except Exception as e:
    #     print(f"Error generating meme: {str(e)}")
