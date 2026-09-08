"""Destination-bound inspection transports. Secrets never enter listing metadata."""

import ssl
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from purecipher.curation.http_auth import checked_url
from purecipher.outbound_security import PinnedDNSAsyncTransport


def client_factory(url, options=None):
    checked_url(url)
    options = options or {}
    context = ssl.create_default_context()
    if options.get("kind") == "mtls":
        # OpenSSL loads the key into the context before these private files are removed.
        with tempfile.TemporaryDirectory(prefix="mcp-inspection-") as directory:
            cert, key = Path(directory) / "cert.pem", Path(directory) / "key.pem"
            for path, value in (
                (cert, options["certificate"]),
                (key, options["private_key"]),
            ):
                path.touch(mode=0o600)
                path.write_text(value)
            context.load_cert_chain(cert, key, password=options.get("key_password"))

    class BoundTransport(PinnedDNSAsyncTransport):
        async def handle_async_request(self, request):
            target = urlsplit(str(request.url))
            original = urlsplit(url)
            if (target.scheme, target.netloc) != (original.scheme, original.netloc):
                raise ValueError("Credential destination changed")
            if options.get("kind") == "aws_sigv4":
                from botocore.auth import SigV4Auth
                from botocore.awsrequest import AWSRequest
                from botocore.credentials import Credentials

                body = await request.aread()
                signed = AWSRequest(
                    method=request.method,
                    url=str(request.url),
                    data=body,
                    headers=dict(request.headers),
                )
                credentials = Credentials(
                    options["access_key"],
                    options["secret_key"],
                    options.get("session_token"),
                )
                SigV4Auth(credentials, options["service"], options["region"]).add_auth(
                    signed
                )
                request.headers.update(dict(signed.headers))
            return await super().handle_async_request(request)

    def factory(**kwargs):
        kwargs.pop("follow_redirects", None)
        kwargs.pop("trust_env", None)
        return httpx.AsyncClient(
            **kwargs,
            follow_redirects=False,
            trust_env=False,
            transport=BoundTransport(
                transport=httpx.AsyncHTTPTransport(verify=context, trust_env=False)
            ),
        )

    return factory
