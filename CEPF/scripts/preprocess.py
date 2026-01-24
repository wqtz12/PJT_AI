import os
import re
import json
import firebase_admin
from firebase_admin import credentials, db
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from konlpy.tag import Okt
from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
import faiss

# --- Hugging Face Model and Faiss Index Configuration ---
MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'
EMBEDDING_DIMENSION = 384
FAISS_INDEX_PATH = 'faiss_py.index'
METADATA_PATH = 'metadata_py.json'

print(f"Loading Hugging Face tokenizer and model: {MODEL_NAME}...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModel.from_pretrained(MODEL_NAME)

#Mean Pooling - Take attention mask into account for correct averaging
def mean_pooling(model_output, attention_mask):
    token_embeddings = model_output[0] #First element of model_output contains all token embeddings
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
    sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
    return sum_embeddings / sum_mask

def get_embedding(text, model, tokenizer):
    """
    Creates an embedding for the given text using a Hugging Face transformer model.
    """
    try:
        # Tokenize sentences
        encoded_input = tokenizer(text, padding=True, truncation=True, return_tensors='pt')

        # Compute token embeddings
        with torch.no_grad():
            model_output = model(**encoded_input)

        # Perform pooling
        sentence_embedding = mean_pooling(model_output, encoded_input['attention_mask'])
        return sentence_embedding.numpy()
    except Exception as e:
        print(f"Error creating embedding: {e}")
        return None

# --- Faiss Index Initialization ---
if os.path.exists(FAISS_INDEX_PATH):
    print(f"Loading Faiss index from {FAISS_INDEX_PATH}...")
    faiss_index = faiss.read_index(FAISS_INDEX_PATH)
else:
    print(f"Creating new Faiss index with dimension {EMBEDDING_DIMENSION}...")
    faiss_index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)

# --- Metadata Initialization ---
if os.path.exists(METADATA_PATH):
    with open(METADATA_PATH, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
else:
    metadata = {}

def initialize_firebase():
    """
    Initializes the Firebase Admin SDK.
    """
    try:
        database_url = "https://fir-101-e0467-default-rtdb.firebaseio.com"
        project_id = "fir-101-e0467"
        cred_path = "/Users/jbs/career-experience-and-path-for-the-future/src/config/serviceAccountKey.json"
        
        if not os.path.exists(cred_path):
            print(f"Error: Service account key file not found at '{cred_path}'")
            return False

        cred = credentials.Certificate(cred_path)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred, {
                'databaseURL': database_url,
                'projectId': project_id,
            })
        return True
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        return False

def is_korean(text):
    return re.search(r'[ㄱ-ㅎㅏ-ㅣ가-힣]', text) is not None

def preprocess_text(text):
    if not isinstance(text, str) or not text.strip():
        return []

    if is_korean(text):
        os.environ['JAVA_HOME'] = '/opt/homebrew/opt/openjdk@11'
        okt = Okt()
        normalized_text = re.sub(r'[^가-힣0-9a-zA-Z\s]', '', text) # Updated regex to include Korean characters
        morphemes = okt.morphs(normalized_text, stem=True)
        korean_stopwords = ['의', '가', '이', '은', '들', '는', '좀', '잘', '걍', '과', '도', '를', '으로', '자', '에', '와', '한', '하다', '을', 'ㅋㅋ', 'ㅠㅠ', 'ㅎ']
        tokens = [word for word in morphemes if word not in korean_stopwords and len(word) > 1]
    else:
        normalized_text = re.sub(r'[^a-z\s]', '', text.lower())
        words = word_tokenize(normalized_text)
        english_stopwords = set(stopwords.words('english'))
        tokens = [word for word in words if word not in english_stopwords and word.isalpha()]
        
    return tokens

def main():
    if not initialize_firebase():
        return

    db_path = '/experiences'
    ref = db.reference(db_path)
    
    print(f"\nFetching data from Firebase Realtime Database at '{db_path}'...")
    data = ref.get()

    if not data:
        print(f"No data found at '{db_path}'.")
        return

    print("\n--- Starting data preprocessing ---")
    
    embeddings_to_add = []
    metadata_to_add = []

    try:
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict) and 'content' in value:
                    original_text = value['content']
                    
                    print(f"\n[Entry: {key}]")
                    print(f"  - Original (partial): {original_text[:150].strip()}...")
                    
                    processed_tokens = preprocess_text(original_text)
                    print(f"  - Processed tokens: {processed_tokens}")

                    text_for_embedding = " ".join(processed_tokens)
                    if text_for_embedding:
                        embedding = get_embedding(text_for_embedding, model, tokenizer)
                        if embedding is not None:
                            print(f"  - Embedding (partial): {embedding[:5]}...")
                            
                            embeddings_to_add.append(embedding)
                            
                            # Store metadata with a reference to the vector's future index
                            new_metadata = {
                                "firebase_key": key,
                                "original_text": original_text,
                                "processed_tokens": processed_tokens,
                                "source": "firebase/experiences"
                            }
                            metadata_to_add.append(new_metadata)
                        else:
                            print("  - Embedding creation failed.")
                    else:
                        print("  - No text to embed.")
        else:
            print("Error: Unexpected data format. Expected a dictionary from Firebase.")

        if embeddings_to_add:
            print("\nAdding new embeddings to Faiss index...")
            start_index = faiss_index.ntotal
            faiss_index.add(np.array(embeddings_to_add).astype('float32'))
            print(f"{len(embeddings_to_add)} embeddings added.")

            for i, new_meta in enumerate(metadata_to_add):
                metadata[str(start_index + i)] = new_meta

            print("Saving Faiss index and metadata...")
            faiss.write_index(faiss_index, FAISS_INDEX_PATH)
            with open(METADATA_PATH, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=4)
            print("Faiss index and metadata saved.")

    except FileNotFoundError as e:
        print(f"\nError: {e}")
        print("\n--- KoNLPy (Korean processor) Error ---")
        print("This error occurred because KoNLPy could not find the required Java environment.")
        print("To resolve this, please install Java (OpenJDK 11 recommended) and set the JAVA_HOME environment variable correctly.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
    finally:
        print("\n--- Data preprocessing finished ---")

if __name__ == '__main__':
    try:
        nltk.data.find('tokenizers/punkt')
        nltk.data.find('corpora/stopwords')
    except nltk.downloader.DownloadError:
        print("Downloading NLTK data (punkt, stopwords)...")
        nltk.download('punkt', quiet=True)
        nltk.download('stopwords', quiet=True)
        print("Download complete.")

    main()