# Minica API
This is a small wrapper around [jsha/minica](https://github.com/jsha/minica)
(currently my own api friendly [fork](https://github.com/bjornsnoen/minica))
using FastAPI and dockerpy. The intended usage is as a sidecar to
[traefik](https://traefik.io) in order to automatically generate ssl
certificates _locally_.

## Usage with traefik
Traefik is a reverse proxy that works particularily well with docker, allowing
us to use docker labels to define routing rules. This package comes with a
script that listens for those same labels and generates ssl certificates
whenever it detects a new route, or a route whose certificate is about to
expire. To enable this behavior you need to tell it where your docker socket
is, and that it should be listening. You do this with environment variables.

* DOCKER_HOST: unix:///var/run/docker.sock
* DOCKER_LISTEN: yes

So if you were running this alongside traefik in a docker-compose stack, the
definition for this service should look something like this

```yml
services:
  minica:
    image: ghcr.io/bjornsnoen/minica-traefik-api:latest
    volumes:
      - ./certificates:/app/certificates
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      DOCKER_HOST: "unix:///var/run/docker.sock"
      DOCKER_LISTEN: "yes"
    restart: unless-stopped
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.minica.rule=Host(`minica.localhost`)"
      - "traefik.http.routers.minica.middlewares=redirectssl@docker"
      - "traefik.http.routers.minicasecure.rule=Host(`minica.localhost`)"
      - "traefik.http.routers.minicasecure.tls=true"

  traefik:
    container_name: traefik
    image: traefik:v2.5
    command:
      - "--log.level=DEBUG"
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--providers.file.directory=/app/certificates"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./certificates:/app/certificates
    restart: unless-stopped
    ports:
      - 80:80
      - 443:443
    labels:
      - "traefik.enable=true"
      - "traefik.http.middlewares.redirectssl.redirectscheme.scheme=https"
      - "traefik.http.routers.traefik.rule=Host(`traefik.localhost`)"
      - "traefik.http.routers.traefik.middlewares=redirectssl@docker"
      - "traefik.http.routers.traefiksecure.rule=Host(`traefik.localhost`)"
      - "traefik.http.routers.traefiksecure.tls=true"
      - "traefik.http.services.traefik.loadbalancer.server.port=8080"
```

Minica will create a root certificate authority in the `./certificates`
directory, which you can trust on your clients to enjoy ssl on all your
services (that are using traefik).

## The API
The docker listener works very well if all your services are running in the
same docker stack, and if they're all being routed by traefik, but what about
your octopi instance running on a separate raspberry pi? This also comes with a
very simple RESTful api that you can use to create certificates.

### Generating certificates
To generate a certificate for the domain `example.localhost`, simply POST the domain
to the api.

`curl -X POST https://minica.localhost/certs/example.localhost`

If you attempt to POST a domain that we've already created a certificate for
you'll get a 409 conflict. 

### Generating wildcards
The API supports creating wildcard certificates, although creating certificates
is so easy you should probably consider if you really need a wildcard. When
creating wildcard certificates, you can tell minica to also include the base
domain in the SAN extension (basically allow the certificate to be valid for
both *.domain.tld and domain.tld). To instruct the api to do this, post
`include_base_domain=True` in the request body.

```
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"include_base_domain": true}' \
  https://minica.localhost/certs/\*.example.localhost
```

### Renewing certificates
If you've got a cert about to expire you can PUT it
to update it. If you try to PUT a domain more than 30 days before its expiry
you'll also get a 409 conflict.

`curl -X PUT https://minica.localhost/certs/example.localhost`

To see when your certificates are going to expire, use `/expires`

`curl https://minica.localhost/expires | jq .`

### Retrieving certificates
There is no GET api for retrieving domain certificates,in case you mess up and
expose the api to the internet. You can however fetch the minica root
certificate at `/root`, `/root/pem`, and `/root/der` which gives you the
contents of `minica.pem` in the specified format. 

## Configuration
The service is configured via environment variables.

### Docker
To automatically generate certificates for running docker container configured
with traefik you're going to want to enable the docker listener by setting the
following variables and mounting the docker unix socket into the container as
shown in the usage section.

| Env var       | Description                            | Recommended                   |
|---------------|----------------------------------------|-------------------------------|
| DOCKER_HOST   | Where the docker socket is going to be | "unix:///var/run/docker.sock" |
| DOCKER_LISTEN | Whether to enable the docker listener  | "yes"                         |

### User id and group id
For some usecases it might be useful to generate the certificates owned by
another user than root. To do this, use the following variables

| Env var  | Description                                   | Default |
|----------|-----------------------------------------------|---------|
| USER_ID  | The user id that should own the certificates  | 0       |
| GROUP_ID | The group id that should own the certificates | 0       |

### MQTT publishing
If you enable the docker listener, you can also optionally enable MQTT
publishing of discovered domains. The message will by default be published on
the `domains` topic, but that's configurable via env vars. You must define at
least MQTT_HOST and HOST_IP for the listener to publish found domains to MQTT.

| Env var            | Description                                                                 | Default |
|--------------------|-----------------------------------------------------------------------------|---------|
| MQTT_HOST          | IP address or domain where MQTT is running.                                 | None    |
| MQTT_PORT          | Port MQTT is running on.                                                    | 1883    |
| HOST_IP            | The IP address of the machine running docker. Published along with domains. | None    |
| MQTT_DOMAINS_TOPIC | The MQTT topic on which to publish discovered domain.                       | domains |

The message published will be a json string with two fields, domain and ip, like this:
```json
{
  "domain": "discovered_domain.tld",
  "ip": "192.168.1.10"
}
```
