from dataclasses import dataclass
from datetime import datetime, timedelta
from os import chdir
from pathlib import Path
from shutil import rmtree
from subprocess import CompletedProcess, run
from typing import List, Optional

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

cert_dir = Path("certificates")


def get_minica_bin() -> str:
    return run(["which", "minica"], capture_output=True).stdout.strip()


def get_minica_root_cert() -> Path:
    return cert_dir / "minica.pem"


def minica_command(args: List[str]) -> CompletedProcess:
    return run([get_minica_bin()] + args, capture_output=True, cwd=cert_dir, text=True)


def get_domain_pem(domain: str) -> Path:
    return cert_dir / domain / "cert.pem"


@dataclass
class GeneratePemResponse:
    error: int
    message: Optional[str]


def generate_pem(domain: str) -> GeneratePemResponse:
    proc = minica_command(["--domains", domain])
    return GeneratePemResponse(
        proc.returncode, proc.stderr.strip() if proc.returncode > 0 else "success"
    )


def init():
    if not cert_dir.is_dir():
        cert_dir.mkdir()

    if not get_minica_root_cert().exists():
        print("Initializing minica root cert")
        proc = minica_command(["--ip-addresses", "127.0.0.1"])
        if proc.returncode > 0:
            print(proc.stderr.strip())
        rmtree(get_domain_pem("127.0.0.1").parent)

    return FastAPI()


app = init()


@app.post("/certs/{domain}", response_model=GeneratePemResponse)
async def certgen(domain: str):
    answer = generate_pem(domain)

    if answer.error > 0:
        return JSONResponse(jsonable_encoder(answer), status_code=409)

    return answer


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
    if not get_minica_root_cert().exists():
        raise HTTPException(404, {"message": "Root ca has not yet been generated"})

    return {"cert": get_minica_root_cert().read_text().strip()}
