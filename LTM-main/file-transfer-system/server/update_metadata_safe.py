from supabase import create_client
from datetime import datetime

SUPABASE_URL = "https://qrzycoatheltpfiztkeh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFyenljb2F0aGVsdHBmaXp0a2VoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODY3NjA1NiwiZXhwIjoyMDc0MjUyMDU2fQ.3JmRXRDs-QcEQDHNghjTJEPvoEHA3Zx5MpioHTh9rWM"
STORAGE_BUCKET = "files"


def is_likely_fernet(blob: bytes) -> bool:
    """Simple heuristic: Fernet tokens (base64) usually start with b'gAAAA'."""
    try:
        return isinstance(blob, (bytes, bytearray)) and blob.startswith(b'gAAAA')
    except Exception:
        return False


def update_metadata():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    try:
        files = supabase.storage.from_(STORAGE_BUCKET).list()
    except Exception as e:
        print(f"Failed to list storage bucket '{STORAGE_BUCKET}': {e}")
        return

    for file in files:
        filename = file.get('name')
        print(f"Processing: {filename}")

        metadata = {
            "encrypted": "false",
            "original_size": file.get('metadata', {}).get('size', 'N/A'),
            "uploaded_by": "system",
            "uploaded_at": datetime.utcnow().isoformat(),
            "original_filename": filename,
            "content_type": file.get('metadata', {}).get('mimetype', 'application/octet-stream')
        }

        # Try to download a small sample to detect encryption (may download whole file)
        try:
            blob = supabase.storage.from_(STORAGE_BUCKET).download(filename)
            if is_likely_fernet(blob):
                metadata['encrypted'] = 'true'
                # We cannot recover the key here; leave encryption_key absent
                print(f" - Detected encrypted file (no key will be set): {filename}")
            else:
                print(f" - Not encrypted: {filename}")
        except Exception as e:
            print(f" - Warning: failed to download {filename} for inspection: {e}")

        try:
            supabase.table("files_metadata").upsert({
                "filename": filename,
                "metadata": metadata
            }).execute()
            print(f" ✓ Upserted metadata for {filename}")
        except Exception as e:
            print(f" ✗ Failed to upsert metadata for {filename}: {e}")


if __name__ == '__main__':
    print("=== SAFE METADATA BACKFILL ===")
    update_metadata()
    print("=== DONE ===")
