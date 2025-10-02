import requests
import logging
from .. import config

logger = logging.getLogger(__name__)


def _send_webhook(url, data):
    """Hàm chung để gửi webhook."""
    if "YOUR_N8N" in url:
        logger.warning(f"URL Webhook chưa được cấu hình: {url}. Bỏ qua việc gửi.")
        return
    try:
        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        logger.info(f"Gửi webhook thành công tới {url} với dữ liệu: {data}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Không thể gửi webhook tới {url}: {e}")


def notify_upload(username, filename, filesize):
    """Thông báo sự kiện upload file."""
    data = {
        "event": "file_upload",
        "username": username,
        "filename": filename,
        "filesize": filesize,
    }
    _send_webhook(config.N8N_UPLOAD_WEBHOOK, data)


def notify_download(username, filename):
    """Thông báo sự kiện download file."""
    data = {"event": "file_download", "username": username, "filename": filename}
    _send_webhook(config.N8N_DOWNLOAD_WEBHOOK, data)


def notify_delete(username, filename):
    """Thông báo sự kiện xóa file."""
    data = {"event": "file_delete", "username": username, "filename": filename}
    _send_webhook(config.N8N_DELETE_WEBHOOK, data)
