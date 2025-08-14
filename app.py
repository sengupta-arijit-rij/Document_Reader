from flask import Flask, request, jsonify
import os
import json
import shutil
import fitz  # PyMuPDF
from werkzeug.utils import secure_filename
from model_util import setup_logging, prepare_message_dl, prepare_message_trade, infer_with_retry
from utils1 import raw_text_extraction,client
from config import LOCAL_RAW_DATA_DIR, MODEL_ID, MAX_RETRIES
from prompt import prompt_trade_register, prompt_passport, prompt_dl

# ---------------------------------
# Flask App Entry Point
# ---------------------------------
app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
GENERATED_IMAGES_FOLDER = os.path.join(UPLOAD_FOLDER, "generated_images")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------------------------
# Global Configs
# ---------------------------------
VALID_DOCUMENT_TYPES_PROMPT = {
    "driving_licence": prompt_dl,
    "passport": prompt_passport,
    "trade_register": prompt_trade_register
}
VALID_DOCUMENT_TYPES = VALID_DOCUMENT_TYPES_PROMPT.keys()
IMAGE_TYPE_DOCUMENTS = ["driving_licence", "passport", "trade_register"]
PDF_TYPE_DOCUMENTS = ["trade_register"]
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png"}
ALLOWED_PDF_EXTENSIONS = {"pdf"}

# Setup logger
app_logger = setup_logging()


# ---------------------------------
# API Endpoint
# ---------------------------------
@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        doc_type = request.form.get("document_type")
        if doc_type not in VALID_DOCUMENT_TYPES:
            return jsonify({"error": f"Invalid document type. Valid types: {list(VALID_DOCUMENT_TYPES)}"}), 400

        file = request.files.get("file")
        if not file or file.filename == "":
            return jsonify({"error": "No file provided"}), 400

        if not allowed_file(file.filename, doc_type):
            return jsonify({"error": "Invalid file type"}), 400

        file_path = save_file(file)
        return process_document(file_path, doc_type)

    except Exception as e:
        app_logger.error(f"Unexpected error in /upload: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500


# ---------------------------------
# Helper Functions
# ---------------------------------
def allowed_file(filename, doc_type):
    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
    if doc_type == "trade_register":
        return ext in ALLOWED_IMAGE_EXTENSIONS.union(ALLOWED_PDF_EXTENSIONS)
    elif doc_type in IMAGE_TYPE_DOCUMENTS:
        return ext in ALLOWED_IMAGE_EXTENSIONS
    return False


def generate_images_from_pdf(file_path):
    os.makedirs(GENERATED_IMAGES_FOLDER, exist_ok=True)
    saved_image_paths = []

    try:
        doc = fitz.open(file_path)
        for page_num in range(len(doc)):
            pixmap = doc[page_num].get_pixmap(matrix=fitz.Matrix(4, 4))
            image_path = os.path.join(GENERATED_IMAGES_FOLDER, f"page_{page_num + 1}.png")
            pixmap.save(image_path)
            saved_image_paths.append(image_path)
            app_logger.info(f"Saved image: {image_path}")
        doc.close()
    except Exception as e:
        app_logger.error(f"Error generating images from PDF: {e}")

    return saved_image_paths


def delete_generated_images_folder():
    try:
        if os.path.exists(GENERATED_IMAGES_FOLDER):
            shutil.rmtree(GENERATED_IMAGES_FOLDER)
            app_logger.info(f"Deleted folder: {GENERATED_IMAGES_FOLDER}")
    except Exception as e:
        app_logger.error(f"Error deleting generated images folder: {e}")


def save_file(file):
    try:
        filename = secure_filename(file.filename)
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(save_path)
        return save_path
    except Exception as e:
        app_logger.error(f"Error saving file: {e}")
        raise


def process_document(file_path, doc_type):
    app_logger.info("**Document Processing Started**")

    ext = os.path.splitext(file_path)[1].lower().strip(".")
    images = []

    try:
        is_pdf = ext == "pdf"
        if doc_type == "trade_register" and is_pdf:
            app_logger.info("Trade register is PDF, generating images")
            images = generate_images_from_pdf(file_path)
        else:
            images = [file_path]

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        if doc_type == "trade_register" and is_pdf:
            raw_text = raw_text_extraction(file_bytes, images)
            file_name = os.path.splitext(os.path.basename(file_path))[0] + ".json"
            json_path = os.path.join(LOCAL_RAW_DATA_DIR, file_name)
            os.makedirs(LOCAL_RAW_DATA_DIR, exist_ok=True)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(raw_text, f, indent=4, ensure_ascii=False)
            app_logger.info(f"Raw text saved: {json_path}")
            messages = prepare_message_trade(ext, raw_text, VALID_DOCUMENT_TYPES_PROMPT[doc_type])
        else:
            # Normalize extension for image types
            if ext == "jpg":
                ext = "jpeg"
            messages = prepare_message_dl(VALID_DOCUMENT_TYPES_PROMPT[doc_type], file_bytes, ext)

        result = infer_with_retry(client, MODEL_ID, messages, file_path, MAX_RETRIES)
        app_logger.info("Processing completed")
        return jsonify(result), 200

    except Exception as e:
        app_logger.error(f"Error processing document: {e}")
        return jsonify({"error": "Processing failed"}), 500

    finally:
        delete_generated_images_folder()


# ---------------------------------
# Run Server
# ---------------------------------
if __name__ == "__main__":
    app_logger.info("**Starting Flask Application**")
    app.run(host='0.0.0.0', port=8080, debug=True)

