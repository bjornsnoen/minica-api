from dataclasses import dataclass
from datetime import datetime, timedelta
from os import chdir
from pathlib import Path
from shutil import rmtree
from subprocess import CompletedProcess, run
from typing import Optional

import toml
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


def minica_command(args: list[str]) -> CompletedProcess:
    return run([get_minica_bin()] + args, capture_output=True, cwd=cert_dir, text=True)


def get_domain_pem_file(domain: str) -> Path:
    return cert_dir / domain / "cert.pem"


def get_domain_pem(domain: str) -> x509.Certificate:
    pem = get_domain_pem_file(domain)
    if not pem.exists():
        raise HTTPException(
            status_code=404,
            detail={"message": "Domain pem not found", "domain": domain},
        )

    pem_data = pem.read_bytes()
    cert = x509.load_pem_x509_certificate(pem_data, backend=default_backend())
    return cert


@dataclass
class GeneratePemResponse:
    error: int
    message: Optional[str]


def generate_pem(domain: str) -> GeneratePemResponse:
    proc = minica_command(["--domains", domain])
    update_traefik_list()
    return GeneratePemResponse(
        proc.returncode, proc.stderr.strip() if proc.returncode > 0 else "success"
    )


def update_traefik_list():
    out_file = cert_dir / "certificates.toml"
    contents = {"tls": {"certificates": []}}
    for file in cert_dir.iterdir():
        if not file.is_dir():
            continue
        cert = file / "cert.pem"
        key = file / "key.pem"
        contents["tls"]["certificates"].append(
            {"certFile": str(cert.resolve()), "keyFile": str(key.resolve())}
        )

    with out_file.open("w") as f:
        toml.dump(contents, f)


def init():
    if not cert_dir.is_dir():
        cert_dir.mkdir()

    if not get_minica_root_cert().exists():
        print("Initializing minica root cert")
        proc = minica_command(["--ip-addresses", "127.0.0.1"])
        if proc.returncode > 0:
            print(proc.stderr.strip())
        rmtree(get_domain_pem_file("127.0.0.1").parent)

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
    cert = get_domain_pem(domain)
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


@app.get("/expires")
async def expires():
    domains: dict[str, x509.Certificate] = dict()
    for file in cert_dir.iterdir():
        if not file.is_dir():
            continue
        domains[file.name] = get_domain_pem(file.name).not_valid_after

    return domains
