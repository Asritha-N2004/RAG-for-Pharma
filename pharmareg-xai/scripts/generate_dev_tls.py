"""Generate a localhost-only development certificate without installing a trust root."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import ipaddress,os
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization,hashes
root=Path(__file__).resolve().parents[1];folder=root/'storage'/'tls';folder.mkdir(parents=True,exist_ok=True)
certificate=folder/'localhost.crt';private=folder/'localhost.key'
if not certificate.exists() and not private.exists():
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048);name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')]);now=datetime.now(timezone.utc)
    cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=2)).not_valid_after(now+timedelta(days=30)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),x509.IPAddress(ipaddress.ip_address('127.0.0.1')),x509.IPAddress(ipaddress.ip_address('::1'))]),critical=False).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).sign(key,hashes.SHA256())
    with os.fdopen(os.open(private,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as file:file.write(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    certificate.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
if not certificate.exists() or not private.exists():raise SystemExit('Incomplete existing TLS pair; supply a matching certificate/key')
print('Development certificate created or already present:',certificate)
