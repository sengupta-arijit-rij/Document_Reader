import json
from config import MAX_RETRIES
import re
import logging


def prepare_message_dl(prompt, image_bytes, ext):
    if ext == "jpg":
        ext = "jpeg"
    return [
        {
            "role": "user",
            "content": [
                {"text": prompt},
                {"image": {"format": ext, "source": {"bytes": image_bytes}}}
            ]
        }
    ]

def prepare_message_trade(ext, raw_text_data, prompt):
    """
    Prepare message for Bedrock model.

    Args:
        ext (str): File extension (e.g., 'jpg', 'pdf').
        raw_text_data (dict or list): Extracted raw text data.
        prompt (str): The prompt text for the model.

    Returns:
        list: Messages formatted for Bedrock model.
    """
    # Normalize extension
    if ext.lower() == "jpg":
        ext = "jpeg"

    # Create messages
    return [
        {
            "role": "user",
            "content": [
                {"text": prompt},
                {"text": json.dumps(raw_text_data)}
            ]
        }
    ]

# def prepare_messages(prompt_name, prompt_value, raw_text_data=None, image_bytes=None, ext=None):

#     if prompt_name == "prompt_trade_register":
#         return prepare_message_trade(prompt_value, raw_text_data)
    
#     elif prompt_name == "prompt_dl":
#         return prepare_message_dl(prompt_value, image_bytes, ext)
    
#     else:
#         raise ValueError(f"Unsupported prompt name: {prompt_name}")

    
def infer_with_retry(client, model_id, messages,key , max_retries=MAX_RETRIES):
    for attempt in range(max_retries + 1):
        try:
            response = client.converse(
                modelId=model_id,
                messages=messages,
                inferenceConfig={
                    "maxTokens": 8192,
                    "temperature": 1,
                    "topP": 0.9
                }
            )
            response_text = response["output"]["message"]["content"][0]["text"]
            print(response_text)
            response_text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", response_text.strip(), flags=re.MULTILINE)
            print(f"AFTER : {response_text}")
            return json.loads(response_text)

        except json.JSONDecodeError as j:
            print(f"JSON DECODE ERROR: {j}")
            print(f"JSON decode failed on attempt {attempt + 1} for {key}")
            if attempt == max_retries:
                print(f"ERROR: Failed to parse JSON after {max_retries + 1} attempts")

        except Exception as e:
            print(f" Error invoking model on attempt {attempt + 1} for {key}: {e}")
            raise


def setup_logging(log_file='application.log', level=logging.INFO):
    logger = logging.getLogger(__name__)
    logger.setLevel(level)

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger
