"""Firebase client — optional. Falls back to in-memory if no credentials. PRD §5.3."""

import os
import json
from functools import lru_cache

_firestore_client = None
_firebase_available = False

def _try_init_firebase():
    """Try to initialize Firebase. Returns (client, success)."""
    global _firebase_available
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if firebase_admin._DEFAULT_APP_NAME in firebase_admin._apps:
            _firebase_available = True
            return firestore.client()

        # Option 1: Service account JSON file
        sa_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if sa_path and os.path.exists(sa_path):
            cred = credentials.Certificate(sa_path)
        # Option 2: JSON string in env var (HuggingFace Spaces)
        elif sa_json := os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON'):
            sa_dict = json.loads(sa_json)
            cred = credentials.Certificate(sa_dict)
        # Option 3: Emulator
        elif os.getenv('FIRESTORE_EMULATOR_HOST'):
            cred = credentials.ApplicationDefault()
        else:
            return None

        firebase_admin.initialize_app(cred, {
            'projectId': os.getenv('FIREBASE_PROJECT_ID', 'mailmind-dev')
        })
        _firebase_available = True
        return firestore.client()
    except Exception:
        return None


@lru_cache(maxsize=1)
def get_firestore_client():
    """Get Firestore client or None if Firebase is not configured."""
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = _try_init_firebase()
    return _firestore_client


def is_firebase_available() -> bool:
    """Check if Firebase is configured and available."""
    get_firestore_client()
    return _firebase_available


# In-memory fallback store
_memory_store: dict = {
    'episodes': {},
    'action_logs': {},
    'grader_runs': {},
}


def save_document(collection: str, doc_id: str, data: dict):
    """Save to Firebase if available, else in-memory."""
    client = get_firestore_client()
    if client:
        try:
            client.collection(collection).document(doc_id).set(data, merge=True)
        except Exception:
            pass  # Non-blocking — don't crash on Firebase errors
    else:
        if collection not in _memory_store:
            _memory_store[collection] = {}
        _memory_store[collection][doc_id] = data


def get_document(collection: str, doc_id: str) -> dict | None:
    """Get from Firebase if available, else in-memory."""
    client = get_firestore_client()
    if client:
        try:
            doc = client.collection(collection).document(doc_id).get()
            return doc.to_dict() if doc.exists else None
        except Exception:
            pass
    return _memory_store.get(collection, {}).get(doc_id)
