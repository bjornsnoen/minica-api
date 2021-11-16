from datetime import datetime, timedelta
from shutil import rmtree

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
from fastapi import FastAPI, HTTPException, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from minica_api.certificates import (
    CertificateDoesNotExistException,
    CertManager,
    GeneratePemResponse,
)

cert_manager = CertManager()
app = FastAPI()


@app.post("/certs/{domain}", response_model=GeneratePemResponse)
async def certgen(domain: str):
    answer = cert_manager.generate_pem(domain)

    if answer.error > 0:
        return JSONResponse(jsonable_encoder(answer), status_code=409)

    return answer


@app.put("/certs/{domain}")
async def certupdate(domain: str):
    try:
        cert = cert_manager.get_domain_pem(domain)
    except CertificateDoesNotExistException:
        raise HTTPException(404, {"message": "No such certificate", "domain": domain})

    if not cert_manager.due_to_expire(domain):
        raise HTTPException(409, {"message": "Certificate not due for expiry"})

    return cert_manager.touch_cert(domain)


@app.get("/root")
async def root():
    if not cert_manager.get_minica_root_cert_file().exists():
        raise HTTPException(404, {"message": "Root ca has not yet been generated"})

    return {"cert": cert_manager.get_minica_root_cert_file().read_text().strip()}


@app.get("/root/pem")
async def root():
    if not cert_manager.get_minica_root_cert_file().exists():
        raise HTTPException(404, {"message": "Root ca has not yet been generated"})

    return Response(
        cert_manager.get_minica_root_cert().public_bytes(Encoding.PEM),
        headers={"Content-Disposition": 'attachment; filename="cert.pem"'},
    )


@app.get("/root/der")
async def root():
    if not cert_manager.get_minica_root_cert_file().exists():
        raise HTTPException(404, {"message": "Root ca has not yet been generated"})

    return Response(
        cert_manager.get_minica_root_cert().public_bytes(Encoding.DER),
        headers={"Content-Disposition": 'attachment; filename="cert.crt"'},
    )


@app.get("/expires")
async def expires():
    domains: dict[str, x509.Certificate] = dict()
    for file in cert_manager.cert_dir.iterdir():
        if not file.is_dir():
            continue
        domains[file.name] = cert_manager.get_domain_pem(file.name).not_valid_after

    return domains
