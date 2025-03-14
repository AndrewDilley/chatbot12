import os
import json
import faiss
import numpy as np
from docx import Document
from PyPDF2 import PdfReader
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

from config import DOCUMENTS_PATH, PREPROCESSED_PATH, SHAREPOINT_LINKS

FILES = list(SHAREPOINT_LINKS.keys())

dimension = 1536  # Embedding vector size
index = faiss.IndexFlatL2(dimension)  # FAISS index
text_map = []  # To map indices to text and filenames

os.makedirs(PREPROCESSED_PATH, exist_ok=True)

def extract_text_from_word(file_path):
    doc = Document(file_path)
    return "\n".join([paragraph.text for paragraph in doc.paragraphs])

def extract_text_from_pdf(file_path):
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def split_text_into_paragraph_chunks(text, max_chunk_size=800, min_chunk_size=100):
    """
    Splits text based on paragraph boundaries.
    Groups paragraphs together until the chunk length approaches max_chunk_size.
    """
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks = []
    current_chunk = ""
    for p in paragraphs:
        if current_chunk:
            # Check if adding the new paragraph exceeds the max_chunk_size
            if len(current_chunk) + len(p) + 1 <= max_chunk_size:
                current_chunk += " " + p
            else:
                # Only append if the current chunk meets the minimum size requirement
                if len(current_chunk) >= min_chunk_size:
                    chunks.append(current_chunk)
                    current_chunk = p
                else:
                    current_chunk += " " + p
        else:
            current_chunk = p
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

def generate_embedding_for_chunk(chunk):
    response = client.embeddings.create(
        input=chunk,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

def preprocess_documents():
    global index, text_map
    index.reset()
    text_map = []

    for file in FILES:
        file_path = os.path.join(DOCUMENTS_PATH, file)
        print(f"Processing file: {file_path}")
        if file.lower().endswith(".docx"):
            text = extract_text_from_word(file_path)
        elif file.lower().endswith(".pdf"):
            text = extract_text_from_pdf(file_path)
        else:
            print(f"Skipping unsupported file format: {file}")
            continue

        # Split the document into chunks based on paragraph boundaries
        chunks = split_text_into_paragraph_chunks(text, max_chunk_size=800, min_chunk_size=100)
        print(f"Split {file} into {len(chunks)} chunks based on paragraphs.")

        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            embedding = generate_embedding_for_chunk(chunk)
            index.add(np.array([embedding]).astype('float32'))
            text_map.append((chunk, file))
            print(f"Indexed chunk {i+1} from {file} (length: {len(chunk)} characters)")

    # Save FAISS index
    index_file_path = os.path.join(PREPROCESSED_PATH, "faiss_index.bin")
    faiss.write_index(index, index_file_path)
    print(f"FAISS index saved to {index_file_path}")

    # Save text map
    text_map_file_path = os.path.join(PREPROCESSED_PATH, "text_map.json")
    with open(text_map_file_path, "w") as f:
        json.dump(text_map, f)
    print(f"Text map saved to {text_map_file_path}")

if __name__ == "__main__":
    preprocess_documents()
