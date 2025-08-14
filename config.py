import os

# AWS and Bedrock configuration
REGION = "us-east-1"
BUCKET = "bofa-poc"
PREFIX = "Driving License-08062025/"#"Driving License-08062025/"#Trade Register/"#"Driving License/"#"Passport/"
# MODEL_ID = "arn:aws:bedrock:us-east-1:970547359844:inference-profile/us.meta.llama4-maverick-17b-instruct-v1:0"
MODEL_ID = "arn:aws:bedrock:us-east-1:970547359844:inference-profile/us.meta.llama4-scout-17b-instruct-v1:0"
#OUTPUT_FILE = "trade_register_insights.json"#"image_insights_dl_08062025.json"
OUTPUT_FILE_MAP = {
    'Driving_License': 'result_dl_llama_scout.json',
    'app_trade_registor': 'result_trade_register2.json',
    'Passport': 'result_passport_4.json'
}
target_folder="images"
output_folder="Output_files/"
PDF_EXTENSION="pdf"

LOCAL_IMAGE_TMP_DIR = "./tmp_images"

# Supported file extensions
SUPPORTED_EXTENSION ={'.pdf','.png', '.jpg', '.jpeg'}
# Supported image extensions
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg'}

USER_INPUT = 'Driving License-08062025' # 'Driving_License' 'app_trade_registor' 'Passport'
DOCUMENT_TYPE = {'Driving License-08062025':'dl','app_trade_registor': 'trade_register2','Passport':'passport_4'}

MAX_RETRIES = 2
# Create local raw-data folder if it doesn't exist
LOCAL_RAW_DATA_DIR = "raw-data"
os.makedirs(LOCAL_RAW_DATA_DIR, exist_ok=True)