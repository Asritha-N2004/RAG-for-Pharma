"""HTTPS-only allowlisted fetch with public IP pinning, bounded reads and redirect revalidation."""
import http.client,ipaddress,socket,ssl,os
from urllib.parse import urlsplit,urljoin
from app.core.config import MAX_UPLOAD
OFFICIAL={'www.fda.gov','www.ema.europa.eu','health.ec.europa.eu','database.ich.org','www.who.int','cdn.who.int','cdsco.gov.in','picscheme.org'}
def validate_url(url):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port not in {None,443} or not parsed.hostname:
        raise ValueError('Source requires HTTPS on port 443 without credentials')
    allowed=OFFICIAL|set(filter(None,os.getenv('SOURCE_ALLOWED_HOSTS','').split(',')))
    if parsed.hostname.lower() not in allowed:raise ValueError('Host is not in the official-source allowlist')
    addresses={x[4][0] for x in socket.getaddrinfo(parsed.hostname,443,type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):raise ValueError('Source DNS must resolve exclusively to public IP addresses')
    return parsed,sorted(addresses)[0]
class PinnedConnection(http.client.HTTPSConnection):
    def __init__(self,host,address):super().__init__(host,timeout=30);self.address=address
    def connect(self):
        raw=socket.create_connection((self.address,443),timeout=self.timeout)
        try:self.sock=ssl.create_default_context().wrap_socket(raw,server_hostname=self.host)
        except Exception:raw.close();raise
def fetch(url):
    for _ in range(4):
        parsed,address=validate_url(url);connection=PinnedConnection(parsed.hostname,address)
        try:
            connection.request('GET',parsed.path+('?' +parsed.query if parsed.query else ''),headers={'User-Agent':'Python-urllib/3.12','Accept':'*/*'})
            response=connection.getresponse()
            if response.status in {301,302,303,307,308}:
                url=urljoin(url,response.getheader('Location',''));continue
            if response.status!=200:raise ValueError(f'Official source returned HTTP {response.status}')
            length=response.getheader('Content-Length')
            if length and int(length)>MAX_UPLOAD:raise ValueError('Remote document exceeds upload limit')
            data=response.read(MAX_UPLOAD+1)
            if len(data)>MAX_UPLOAD:raise ValueError('Remote document exceeds upload limit')
            from email.message import Message
            disposition=Message();disposition['Content-Disposition']=response.getheader('Content-Disposition','')
            name=disposition.get_filename() or parsed.path.rsplit('/',1)[-1] or 'regulation.pdf'
            if data.startswith(b'%PDF-') and not name.lower().endswith('.pdf'):name+='.pdf'
            return name,data,url
        finally:connection.close()
    raise ValueError('Source redirected too many times')
