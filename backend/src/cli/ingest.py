import os
import click
import docx
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer

def get_text_from_pdf(file_path):
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        if page.extract_text():
            text += page.extract_text() + "\n"
    return text

def get_text_from_docx(file_path):
    doc = docx.Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])

# Fast tokenization approximation by using space-split words
def chunk_text(text, chunk_size=512, overlap=51):
    words = text.split()
    chunks = []
    # 10% overlap is approx 51 words out of 512
    for i in range(0, len(words), chunk_size - overlap):
        chunks.append(" ".join(words[i:i + chunk_size]))
    return chunks

@click.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False, dir_okay=True))
def ingest(directory):
    print(f"Ingesting from {directory}...")
    # Use environment var from docker-compose, or localhost
    qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    qdrant = QdrantClient(url=qdrant_url)
    model = SentenceTransformer("all-MiniLM-L6-v2")
    collection_name = "documents"
    
    # Check if collection exists
    try:
        qdrant.get_collection(collection_name=collection_name)
    except Exception:
        print(f"Creating collection: {collection_name}")
        qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=384,
                distance=models.Distance.COSINE
            )
        )
    
    docs_to_insert = []
    for root, _, files in os.walk(directory):
        for file in files:
            path = os.path.join(root, file)
            text = ""
            if file.endswith('.pdf'):
                print(f"Reading PDF {file}")
                text = get_text_from_pdf(path)
            elif file.endswith('.docx'):
                print(f"Reading DOCX {file}")
                text = get_text_from_docx(path)
            elif file.endswith('.txt'):
                print(f"Reading TXT {file}")
                with open(path, 'r', encoding='utf-8') as f:
                    text = f.read()
            else:
                continue
                
            chunks = chunk_text(text)
            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue
                embedding = model.encode(chunk).tolist()
                docs_to_insert.append(
                    models.PointStruct(
                        # Deterministic positive integer ID
                        id=hash(path + str(i)) % ((1<<63)-1), 
                        vector=embedding,
                        payload={
                            "filename": file,
                            "page": i+1,
                            "text": chunk
                        }
                    )
                )
    
    if docs_to_insert:
        qdrant.upsert(
            collection_name=collection_name,
            points=docs_to_insert
        )
        print(f"Inserted {len(docs_to_insert)} chunks into Qdrant.")
    else:
        print("No documents found to insert.")

if __name__ == "__main__":
    ingest()
