import os
import socket
from datetime import datetime, timedelta
from ipaddress import ip_address

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

# Hằng số cho thông tin chứng chỉ
CERT_DIR = os.path.dirname(__file__)
CERTS_SUBDIR = os.path.join(CERT_DIR, "certs")
CERT_FILE = os.path.join(CERTS_SUBDIR, "server.crt")
KEY_FILE = os.path.join(CERTS_SUBDIR, "server.key")
COUNTRY_NAME = "VN"
STATE_OR_PROVINCE_NAME = "Hanoi"
LOCALITY_NAME = "Hanoi"
ORGANIZATION_NAME = "My Company"
COMMON_NAME = "localhost"
DAYS_VALID = 365


def get_local_ip():
    """
    Lấy địa chỉ IP cục bộ của máy để thêm vào chứng chỉ.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Không cần phải kết nối được, chỉ cần HĐH chọn interface phù hợp
        s.connect(("8.8.8.8", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"  # Fallback
    finally:
        s.close()
    return ip


def generate_self_signed_cert():
    """
    Tạo chứng chỉ tự ký và khóa riêng nếu chúng chưa tồn tại.
    """
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        print(f"Chứng chỉ '{CERT_FILE}' và khóa '{KEY_FILE}' đã tồn tại.")
        return

    # Đảm bảo thư mục 'certs' tồn tại
    os.makedirs(CERTS_SUBDIR, exist_ok=True)

    local_ip = get_local_ip()
    print(f"Sử dụng IP '{local_ip}' và hostname 'localhost' cho chứng chỉ.")
    print("Đang tạo chứng chỉ tự ký và khóa riêng...")

    # Tạo khóa riêng
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Ghi khóa riêng ra đĩa
    with open(KEY_FILE, "wb") as f:
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    # Các thông tin chi tiết. Đối với chứng chỉ tự ký,
    # chủ thể (subject) và nhà phát hành (issuer) là một.
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, COUNTRY_NAME),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, STATE_OR_PROVINCE_NAME),
            x509.NameAttribute(NameOID.LOCALITY_NAME, LOCALITY_NAME),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, ORGANIZATION_NAME),
            x509.NameAttribute(NameOID.COMMON_NAME, COMMON_NAME),
        ]
    )

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(
            # Chứng chỉ sẽ có hiệu lực trong DAYS_VALID ngày
            datetime.utcnow()
            + timedelta(days=DAYS_VALID)
        )
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ip_address(local_ip))]
            ),
            critical=False,
        )
        # Ký chứng chỉ bằng khóa riêng của chúng ta
        .sign(key, hashes.SHA256())
    )

    # Ghi chứng chỉ ra đĩa
    with open(CERT_FILE, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print(f"Đã tạo thành công '{CERT_FILE}' và '{KEY_FILE}'.")


if __name__ == "__main__":
    generate_self_signed_cert()
