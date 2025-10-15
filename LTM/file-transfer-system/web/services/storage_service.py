import os
from datetime import datetime
from cryptography.fernet import Fernet
import pytz
import unicodedata


class StorageService:
    def __init__(self, supabase_client, bucket_name='files'):
        self.supabase = supabase_client
        self.bucket_name = bucket_name

    def sanitize_filename(self, filename: str) -> str:
        name, ext = os.path.splitext(filename)
        name = name.replace(' ', '_')
        # Preserve more characters but still sanitize dangerous ones
        # Allow alphanumeric, underscore, dash, dot, and parentheses
        # Normalize Unicode characters to ASCII (strip accents) to avoid storage key errors
        name = unicodedata.normalize('NFKD', name)
        name = name.encode('ascii', 'ignore').decode('ascii')
        name = ''.join(c for c in name if c.isalnum() or c in '_.-()')
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        # Preserve original extension case and add timestamp
        safe_ext = ext if ext else ''
        return f"{name}_{timestamp}{safe_ext}"

    def encrypt_file(self, file_data: bytes):
        key = Fernet.generate_key()
        cipher = Fernet(key)
        return cipher.encrypt(file_data), key

    def decrypt_file(self, encrypted_data: bytes, key: bytes):
        cipher = Fernet(key)
        return cipher.decrypt(encrypted_data)

    def _format_size(self, size_val) -> str:
        try:
            size = int(size_val)
            if size > 1024 * 1024:
                return f"{size / (1024 * 1024):.2f} MB"
            if size > 1024:
                return f"{size / 1024:.2f} KB"
            return f"{size} bytes"
        except Exception:
            return 'N/A'

    def upload_file(self, file_data: bytes, original_filename: str, content_type: str, uploaded_by: str, is_public: bool = False):
        """Encrypt, upload to storage, and persist custom metadata in `files_metadata` table."""
        safe_filename = self.sanitize_filename(original_filename)
        try:
            encrypted_data, encryption_key = self.encrypt_file(file_data)

            # Upload encrypted bytes to Supabase Storage
            # supabase-py accepts bytes for upload
            self.supabase.storage.from_(self.bucket_name).upload(safe_filename, encrypted_data)

            # Prepare metadata to store in DB table
            # Use Vietnam timezone for upload time
            vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
            vietnam_time = datetime.now(vietnam_tz)
            
            metadata = {
                'encrypted': 'true',
                'encryption_key': encryption_key.decode(),
                'original_filename': original_filename,
                'original_type': content_type,
                'original_size': len(file_data),
                'uploaded_by': uploaded_by,
                'uploaded_at': vietnam_time.isoformat(),
                'is_public': is_public  # Thêm trạng thái public/private vào metadata
            }
            

            # Upsert into files_metadata table so we can read custom fields later
            try:
                resp = self.supabase.table('files_metadata').upsert({
                    'filename': safe_filename,
                    'metadata': metadata
                }).execute()
                # If the upsert threw no exception, assume success. Some SDKs return wrappers.
            except Exception as e:
                # If we cannot persist the encryption key, remove the uploaded file to avoid irrecoverable encrypted data
                try:
                    self.supabase.storage.from_(self.bucket_name).remove([safe_filename])
                except Exception as remove_err:
                    print(f"CRITICAL: failed to remove orphaned uploaded file {safe_filename}: {remove_err}")
                print(f"Error: failed to upsert files_metadata for {safe_filename}: {e}")
                return {'success': False, 'error': 'Failed to persist file metadata (encryption key). Upload aborted.'}

            return {'success': True, 'filename': safe_filename}
        except Exception as e:
            print(f"Lỗi khi tải lên file: {e}")
            return {'success': False, 'error': str(e)}

    def download_file(self, filename: str):
        """Download file bytes, decrypt if needed, and return (bytes, original_filename, content_type)."""
        try:
            # Try to fetch custom metadata from DB (table may not exist)
            metadata = {}
            try:
                metadata_resp = self.supabase.table('files_metadata').select('metadata').eq('filename', filename).execute()
                if metadata_resp and getattr(metadata_resp, 'data', None):
                    metadata = metadata_resp.data[0].get('metadata', {}) or {}
            except Exception as e:
                # Don't fail hard if table missing or query fails; fall back to storage metadata
                print(f"Warning: could not read files_metadata for {filename}: {e}")
                metadata = {}

            # Download raw bytes from storage
            try:
                data = self.supabase.storage.from_(self.bucket_name).download(filename)
            except Exception as e:
                print(f"Lỗi khi download file {filename}: {e}")
                return None

            # If metadata explicitly marks the file as encrypted but the encryption_key is missing,
            # we must NOT serve the encrypted bytes back to the user. Return a structured error
            # so the web layer can surface a clear message instead of delivering garbage.
            if metadata and metadata.get('encrypted') == 'true' and not metadata.get('encryption_key'):
                print(f"Detected encrypted file {filename} but encryption_key missing in metadata")
                return {'error': 'encrypted_missing_key', 'filename': filename}

            # If there is no custom metadata but the stored bytes look like a Fernet token,
            # the file is likely encrypted but we have no metadata/key -> return structured error
            if (not metadata) and isinstance(data, (bytes, bytearray)):
                try:
                    # Fernet tokens typically start with b'gAAAA' when encoded
                    if data.startswith(b'gAAAA'):
                        print(f"Detected encrypted blob for {filename} but missing metadata/key")
                        return {'error': 'encrypted_missing_key', 'filename': filename}
                except Exception:
                    pass

            # If metadata has encryption info and a key, decrypt and return plaintext
            if metadata and metadata.get('encrypted') == 'true' and metadata.get('encryption_key'):
                try:
                    decrypted = self.decrypt_file(data, metadata['encryption_key'].encode())
                    # Validate file integrity for specific formats (e.g., .doc, .docx, .pdf)
                    original_filename = metadata.get('original_filename', '').lower()
                    if original_filename.endswith('.doc'):
                        if not decrypted.startswith(b'\xd0\xcf\x11\xe0'):  # Check for .doc magic number
                            raise ValueError("Decrypted file does not match .doc format")
                    elif original_filename.endswith('.docx'):
                        # DOCX files are ZIP files containing XML, they start with PK
                        if not decrypted.startswith(b'PK'):
                            raise ValueError("Decrypted file does not match .docx format")
                    return decrypted, metadata.get('original_filename', filename), metadata.get('original_type', 'application/octet-stream')
                except Exception as e:
                    print(f"Error decrypting file {filename}: {e}")
                    return None

            # Otherwise return raw bytes (not encrypted) along with mime/type info when available
            return data, filename, (metadata.get('original_type') if metadata else 'application/octet-stream')
        except Exception as e:
            print(f"Lỗi khi download file {filename}: {e}")
            return None

    def delete_file(self, filename: str) -> bool:
        try:
            self.supabase.storage.from_(self.bucket_name).remove([filename])
            # Also remove metadata record
            try:
                self.supabase.table('files_metadata').delete().eq('filename', filename).execute()
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"Lỗi khi xóa file: {e}")
            return False

    def list_files(self, current_user=None, public_only=False):
        """List files in storage, merge with files_metadata table, and return entries with formatted display fields.
        
        Args:
            current_user (str): Current user's username to filter private files
            public_only (bool): If True, only return public files
        """
        try:
            files = self.supabase.storage.from_(self.bucket_name).list()
            results = []
            for f in files:
                name = f.get('name')

                # Storage-provided metadata (size/mimetype/lastModified) usually under f['metadata']
                storage_meta = f.get('metadata') or {}
                size_from_storage = storage_meta.get('size') or storage_meta.get('contentLength') or f.get('size')
                created_at = f.get('created_at') or f.get('updated_at') or storage_meta.get('lastModified')

                # Fetch custom metadata
                custom_meta = {}
                try:
                    meta_resp = self.supabase.table('files_metadata').select('metadata').eq('filename', name).execute()
                    if meta_resp and getattr(meta_resp, 'data', None):
                        custom_meta = meta_resp.data[0].get('metadata', {}) or {}
                except Exception:
                    custom_meta = {}

                # Merge metadata (custom overrides storage)
                merged = {
                    'original_filename': custom_meta.get('original_filename', name),
                    'uploaded_by': custom_meta.get('uploaded_by', 'N/A'),
                    'uploaded_at': custom_meta.get('uploaded_at', created_at),
                    'original_size': custom_meta.get('original_size', size_from_storage),
                    'original_type': custom_meta.get('original_type', storage_meta.get('mimetype', 'application/octet-stream')),
                    'encrypted': custom_meta.get('encrypted', 'false'),
                    'encryption_key': custom_meta.get('encryption_key')
                }

                merged['size_display'] = self._format_size(merged.get('original_size'))
                # Format time with Vietnam timezone
                try:
                    ts = merged.get('uploaded_at')
                    if isinstance(ts, str) and 'T' in ts:
                        # Parse the timestamp - handle different formats
                        if ts.endswith('Z'):
                            # UTC format with Z
                            utc_time = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                            vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
                            vietnam_time = utc_time.astimezone(vietnam_tz)
                        elif '+' in ts or ts.count('-') > 2:
                            # Already has timezone info
                            parsed_time = datetime.fromisoformat(ts)
                            vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
                            vietnam_time = parsed_time.astimezone(vietnam_tz)
                        else:
                            # Assume UTC if no timezone info
                            utc_time = datetime.fromisoformat(ts + '+00:00')
                            vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
                            vietnam_time = utc_time.astimezone(vietnam_tz)
                        
                        merged['time_display'] = vietnam_time.strftime('%d/%m/%Y %H:%M:%S')
                    else:
                        merged['time_display'] = str(ts)
                except Exception as e:
                    print(f"Error formatting time {ts}: {e}")
                    merged['time_display'] = 'N/A'

                # Check file visibility based on metadata
                custom_meta = meta_resp.data[0].get('metadata', {}) if meta_resp and getattr(meta_resp, 'data', None) else {}
                is_public = custom_meta.get('is_public', False)
                file_owner = custom_meta.get('uploaded_by', 'N/A')

                # Skip files that don't match visibility criteria
                if public_only:
                    # Tab công khai: chỉ hiển thị file công khai
                    if not is_public:
                        continue
                else:
                    # Tab riêng tư: chỉ hiển thị file riêng tư của user hiện tại
                    if is_public or current_user != file_owner:
                        continue

                results.append({
                    'name': name,
                    'id': f.get('id'),
                    'metadata': merged
                })

            # Sort by upload time (newest first)
            results.sort(key=lambda x: x['metadata'].get('uploaded_at', ''), reverse=True)
            return results
        except Exception as e:
            # Distinguish network/connection errors from empty list: return None on error
            print(f"Lỗi khi lấy danh sách file: {e}")
            return None

    def get_public_url(self, filename: str):
        """Return a public URL for the object if available (may require public bucket)."""
        try:
            resp = self.supabase.storage.from_(self.bucket_name).get_public_url(filename)
            # SDKs vary: could be dict or string
            if isinstance(resp, dict):
                return resp.get('publicURL') or resp.get('public_url') or resp.get('url')
            return resp
        except Exception as e:
            print(f"Warning: get_public_url failed for {filename}: {e}")
            return None

    def create_signed_url(self, filename: str, expires=60):
        """Create a signed URL for the object (requires appropriate API key/permissions)."""
        try:
            resp = self.supabase.storage.from_(self.bucket_name).create_signed_url(filename, expires)
            if isinstance(resp, dict):
                return resp.get('signedURL') or resp.get('signed_url') or resp.get('url')
            return resp
        except Exception as e:
            print(f"Warning: create_signed_url failed for {filename}: {e}")
            return None