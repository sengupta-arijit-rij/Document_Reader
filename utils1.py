import boto3
import fitz 
import os,logging,time,io
import json
import traceback
from config import *
from prompt import *
from botocore.exceptions import ClientError
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import ProcessPoolExecutor
import concurrent.futures 




# Initialize AWS clients
s3_client = boto3.client("s3", region_name=REGION)
client = boto3.client("bedrock-runtime", region_name=REGION)




def upload_image_to_blob(image_bytes, blob_name):
    try:
        s3_client.put_object(
            Bucket=BUCKET,
            Key=blob_name,
            Body=image_bytes,
            ContentType="image/png"
        )
        url = f"{blob_name}"
        print("S3 uploaded URL:", url)
        return url
    except Exception as e:
        print(f"Error uploading {blob_name}: {e}")
        return None

def save_pdf_pages_as_images(blob_name, output_folder):
    try:
        # Download PDF from S3
        response = s3_client.get_object(Bucket=BUCKET, Key=blob_name)
        pdf_bytes = response["Body"].read()

        # Load PDF using fitz (PyMuPDF)
        doc = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")

        image_blob_names = []
        image_bytes_list = []

        for page_num in range(len(doc)):
            pixmap = doc[page_num].get_pixmap(matrix=fitz.Matrix(4, 4))  # 4x zoom
            img_bytes = pixmap.tobytes("png")
            image_blob_name = f"{output_folder}/page_{page_num + 1}.png"
            image_blob_names.append(image_blob_name)
            image_bytes_list.append(img_bytes)

        doc.close()

        # Upload images in parallel
        image_urls = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_blob = {
                executor.submit(upload_image_to_blob, img_bytes, blob_name): blob_name
                for img_bytes, blob_name in zip(image_bytes_list, image_blob_names)
            }

            for future in concurrent.futures.as_completed(future_to_blob):
                url = future.result()
                if url:
                    image_urls.append(url)

        return image_urls

    except ClientError as e:
        print(f"AWS S3 ClientError: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return []


### AWS ###
def retry_operation(operation, max_try=3, retry_delay=5):
    """
    Retries a given operation up to max_try times with a delay between attempts.
    """
    attempt = 0
    while attempt < max_try:
        try:
            attempt += 1
            logging.info(f"Attempt {attempt}/{max_try} to execute operation.")
            result = operation()
            logging.info(f"result: {result}")
            # print(f"result: {result}")
            if result:
                return result  # Success
        except Exception as e:
            logging.error(f"Error on attempt {attempt}: {e}")
            if attempt == max_try:
                return None  # Failure after max retries
            time.sleep(retry_delay)
    return None

def raw_text_extraction_1(pdf_bytes,images_list):
    document = fitz.open(stream=pdf_bytes)
    list1 = []
    
    for i,page in enumerate(document):
        dic = {}
        text = page.get_text()
        print(f'Page Number {i} we are processing-----')
        dic["Page Number"] = str(i+1)
        dic["Paragraph_data"] = str(text)
        
        if i < len(images_list):
            blob_name = images_list[i]
            print(blob_name)
            response = s3_client.get_object(Bucket=BUCKET, Key=blob_name)
            image_bytes = response["Body"].read()
            ext = os.path.splitext(blob_name)[1].lower().strip(".")
        
            def gen_text():
                # Prepare message for Bedrock model
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"text": trade_register_raw_data},
                            {"image": {"format": ext, "source": {"bytes": image_bytes}}}
                        ]
                    }
                ]

                # Invoke model
                response = client.converse(
                    modelId=MODEL_ID,
                    messages=messages,
                    inferenceConfig={
                        "maxTokens": 8192,
                        "temperature": 1,
                        "topP": 0.9
                    }
                )

                response_text = response["output"]["message"]["content"][0]["text"]
                response_text=response_text.strip("```json").replace("```","").strip("\n").strip()
                print("geenrated text==\n",response_text)
                return json.loads(response_text)
            
            if dic["Paragraph_data"] == "":
                print("data did not extracted")
                dic["Paragraph_data"] = retry_operation(gen_text)
        
        print(f"Page {i} processed successfully")
        list1.append(dic)
    return list1


def raw_text_extraction(pdf_bytes, images_list):
    document = fitz.open(stream=pdf_bytes)
    list1 = []

    for i, page in enumerate(document):
        dic = {}
        text = page.get_text()
        print(f"Page Number {i} we are processing-----")
        dic["Page Number"] = str(i + 1)
        dic["Paragraph_data"] = str(text)

        # If we have a corresponding local image for this page
        if i < len(images_list):
            image_path = images_list[i]
            print(f"Using local image: {image_path}")

            # Read local image bytes
            with open(image_path, "rb") as img_file:
                image_bytes = img_file.read()
            ext = os.path.splitext(image_path)[1].lower().strip(".")

            def gen_text():
                # Prepare message for Bedrock model
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"text": trade_register_raw_data},
                            {"image": {"format": ext, "source": {"bytes": image_bytes}}}
                        ]
                    }
                ]

                # Invoke model
                response = client.converse(
                    modelId=MODEL_ID,
                    messages=messages,
                    inferenceConfig={
                        "maxTokens": 8192,
                        "temperature": 1,
                        "topP": 0.9
                    }
                )

                response_text = response["output"]["message"]["content"][0]["text"]
                response_text = response_text.strip("```json").replace("```", "").strip("\n").strip()
                print("Generated text==\n", response_text)
                return json.loads(response_text)

            # If text from PDF page is empty, try extracting from image via model
            if dic["Paragraph_data"].strip() == "":
                print("No text from PDF — extracting from image...")
                dic["Paragraph_data"] = retry_operation(gen_text)

        print(f"Page {i} processed successfully")
        list1.append(dic)

    document.close()
    return list1


