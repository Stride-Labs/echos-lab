import os
import importlib
from dotenv import load_dotenv

# link to _this_ file
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
load_dotenv(f"{BASE_PATH}/../.env")

personality_name = os.getenv("PERSONALITY", "hal")

# check if personality_name is set
if personality_name:
    # dynamically import the module from personalities
    module_path = f"echos_lab.engines.personalities.{personality_name}"
    try:
        personality_module = importlib.import_module(module_path)
    except ModuleNotFoundError:
        print(f"Module {module_path} not found.")
else:
    print("Environment variable 'PERSONALITY' is not set.")

INTERESTS = personality_module.INTERESTS

GOALS = personality_module.GOALS

PREFERENCES = personality_module.PREFERENCES

TOOLS_TO_EXCLUDE = personality_module.TOOLS_TO_EXCLUDE

TOOLS_TO_INCLUDE = personality_module.TOOLS_TO_INCLUDE

BOT_NAME = personality_module.BOT_NAME

try:
    TWEET_PROMPT = personality_module.TWEET_PROMPT
except Exception:
    TWEET_PROMPT = ""

try:
    TOPICS = personality_module.TOPICS
except Exception:
    TOPICS = []

try:
    EXTRA_PROMPT = personality_module.EXTRA_PROMPT
except Exception:
    EXTRA_PROMPT = ""

try:
    IMAGE_TAGS = personality_module.IMAGE_TAGS
except Exception:
    IMAGE_TAGS = []

TG_INVITE_LINK = personality_module.TG_INVITE_LINK
TWITTER_HANDLE = os.getenv("TWITTER_ACCOUNT", "")
if TWITTER_HANDLE == "":
    TWITTER_HANDLE = personality_module.TWITTER_HANDLE

try:
    MODEL_NAME = personality_module.MODEL_NAME
except Exception:
    MODEL_NAME = ""
