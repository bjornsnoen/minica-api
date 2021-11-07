from datetime import datetime, timedelta
from os import chdir
from pathlib import Path
from shutil import rmtree
from subprocess import run
from typing import Optional

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from fastapi import FastAPI, HTTPException
from pydantic.dataclasses import dataclass

cert_dir = Path("certificates")


def init():
    if not cert_dir.is_dir():
        cert_dir.mkdir()

    return FastAPI()


app = init()


def get_minica_bin() -> str:
    return run(["which", "minica"], capture_output=True).stdout.strip()


def get_domain_pem(domain: str) -> Path:
    return cert_dir / domain / "cert.pem"


@dataclass
class GeneratePemResponse:
    error: int
    message: Optional[str]


def generate_pem(domain: str) -> GeneratePemResponse:
    proc = run(
        [get_minica_bin(), "-domains", domain], capture_output=True, cwd=cert_dir
    )
    return GeneratePemResponse(
        proc.returncode, proc.stderr.strip() if proc.returncode > 0 else "success"
    )


@app.post("/certs/{domain}")
async def certgen(domain: str):
    return generate_pem(domain)


@app.put("/certs/{domain}")
async def certupdate(domain: str):
    pem = get_domain_pem(domain)
    if not pem.exists():
        raise HTTPException(
            status_code=404,
            detail={"message": "Domain pem not found"},
        )

    pem_data = pem.read_bytes()
    cert = x509.load_pem_x509_certificate(pem_data, backend=default_backend())
    seconds_until_expired: timedelta = cert.not_valid_after - datetime.now()
    days_until_expired = int(seconds_until_expired.total_seconds() / 60 / 60 / 24)
    if days_until_expired > 30:
        raise HTTPException(409, {"message": "Certificate not due for expiry"})

    rmtree(pem.parent)
    return generate_pem(domain)

@app.get("/root")
async def root():
    pem: Path = cert_dir / "minica.pem"
    if not pem.exists():
        raise HTTPException(404, {"message": "Root ca has not yet been generated"})

    return {"cert": pem.read_text().strip()}