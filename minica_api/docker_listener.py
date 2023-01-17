from datetime import datetime, timedelta
from json import dumps
from os import getenv
from re import findall

import docker
from paho.mqtt.publish import single

from minica_api.certificates import CertManager


class Listener:
    def __init__(self) -> None:
        self.client = docker.APIClient(base_url=getenv("DOCKER_HOST"))
        self.cert_manager = CertManager()

    def listen(self):
        event_stream = self.client.events(
            since=datetime.today() - timedelta(hours=1),
            filters={"type": "container", "event": "start"},
            decode=True,
        )

        discovered_domains = set()

        for event in event_stream:
            labels: dict[str, str] = event["Actor"]["Attributes"]  # type: ignore
            routes = set(
                [
                    val
                    for key, val in labels.items()
                    if "traefik.http.routers" in key and key[-4:] == "rule"
                ]
            )

            for route in routes:
                domains = findall(r"(h|H)ost\(`(.+?)`\)", route)
                if len(domains) < 1:
                    continue

                for domain in domains:
                    if domain in discovered_domains:
                        continue

                    result = self.cert_manager.touch_cert(domain)
                    print(result)
                    self.publish(domain)
                    discovered_domains.add(domain)

    def publish(self, domain: str):
        if not getenv("MQTT_HOST", False) or not getenv("HOST_IP", False):
            return

        mqtt_host, port, host_ip = (
            getenv("MQTT_HOST", default=""),
            int(getenv("MQTT_PORT", 1883)),
            getenv("HOST_IP"),
        )

        single(
            getenv("MQTT_DOMAINS_TOPIC", default="domains"),
            payload=dumps({"domain": domain, "ip": host_ip}),
            hostname=mqtt_host,
            port=port,
        )


if __name__ == "__main__":
    if getenv("DOCKER_HOST", False) and getenv("DOCKER_LISTEN", False):
        listener = Listener()
        listener.listen()
    else:
        print("Environment not configured for docker socket monitoring, exiting")
