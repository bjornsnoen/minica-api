from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from shutil import rmtree
from subprocess import CompletedProcess, run
from typing import Optional

import toml
from cryptography import x509
from cryptography.hazmat.backends import default_backend


class CertificateDoesNotExistException(Exception):
    pass


@dataclass
class GeneratePemResponse:
    error: int
    message: Optional[str]
    domain: str


class CertManager:
    cert_dir = Path("certificates")

    def __init__(self):
        if not self.cert_dir.is_dir():
            self.cert_dir.mkdir()

        if not self.get_minica_root_cert().exists():
            print("Initializing minica root cert")
            proc = self.minica_command(["--ip-addresses", "127.0.0.1"])
            if proc.returncode > 0:
                print(proc.stderr.strip())
                exit(proc.returncode)
            rmtree(self.get_domain_pem_file("127.0.0.1").parent)
            self.get_minica_root_cert().chmod(0o644)

    def get_minica_bin(self) -> str:
        return run(["which", "minica"], capture_output=True).stdout.strip()

    def get_minica_root_cert(self) -> Path:
        return self.cert_dir / "minica.pem"

    def minica_command(self, args: list[str]) -> CompletedProcess:
        return run(
            [self.get_minica_bin()] + args,
            capture_output=True,
            cwd=self.cert_dir,
            text=True,
        )

    def get_domain_pem_file(self, domain: str) -> Path:
        return self.cert_dir / domain / "cert.pem"

    def get_domain_pem(self, domain: str) -> x509.Certificate:
        pem = self.get_domain_pem_file(domain)
        if not pem.exists():
            raise CertificateDoesNotExistException()

        pem_data = pem.read_bytes()
        cert = x509.load_pem_x509_certificate(pem_data, backend=default_backend())
        return cert

    def generate_pem(self, domain: str) -> GeneratePemResponse:
        proc = self.minica_command(["--domains", domain])
        self.update_traefik_list()
        return GeneratePemResponse(
            error=proc.returncode,
            message=proc.stderr.strip() if proc.returncode > 0 else "success",
            domain=domain,
        )

    def update_traefik_list(self):
        out_file = self.cert_dir / "certificates.toml"
        contents = {"tls": {"certificates": []}}
        for file in self.cert_dir.iterdir():
            if not file.is_dir():
                continue
            cert = file / "cert.pem"
            key = file / "key.pem"
            contents["tls"]["certificates"].append(
                {"certFile": str(cert.resolve()), "keyFile": str(key.resolve())}
            )

        with out_file.open("w") as f:
            toml.dump(contents, f)

    def update_pem(self, domain: str):
        rmtree(self.get_domain_pem_file(domain).parent)
        return self.generate_pem(domain)

    def due_to_expire(self, domain: str) -> bool:
        cert = self.get_domain_pem(domain)

        seconds_until_expired: timedelta = cert.not_valid_after - datetime.now()
        days_until_expired = int(seconds_until_expired.total_seconds() / 60 / 60 / 24)
        return days_until_expired < 31

    def touch_cert(self, domain: str) -> GeneratePemResponse:
        if self.get_domain_pem_file(domain).exists() and self.due_to_expire(domain):
            return self.update_pem(domain)
        elif not self.get_domain_pem_file(domain).exists():
            return self.generate_pem(domain)

        return GeneratePemResponse(error=0, message="Not due to expire", domain=domain)
