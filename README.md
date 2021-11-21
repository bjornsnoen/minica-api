# Minica API
This is a small wrapper around [jsha/minica](https://github.com/jsha/minica) (currently my own api friendly
[fork](https://github.com/bjornsnoen/minica)) using FastAPI and dockerpy.
The intended usage is as a sidecar to [traefik](https://traefik.io) in order to automatically generate ssl
certificates _locally_.

## Usage with traefik
Traefik is a reverse proxy that works particularily well with docker, allowing us to use docker labels to
define routing rules. This package comes with a script that listens for those same labels and generates
ssl certificates whenever it detects a new route, or a route whose certificate is about to expire.
To enable this behavior you need to tell it where your docker socket is, and that it should be listening.
You do this with environment variables.

* DOCKER_HOST: unix:///var/run/docker.sock
* DOCKER_LISTEN: yes

So if you were running this alongside traefik in a docker-compose stack, the definition for this service
should look something like this

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
            - "traefik.http.routers.minica.rule=Host(`minica.home`)"
            - "traefik.http.routers.minica.middlewares=redirectssl@docker"
            - "traefik.http.routers.minicasecure.rule=Host(`minica.home`)"
            - "traefik.http.routers.minicasecure.tls=true
```

Minica will create a root certificate authority in the `./certificates` directory, which you can trust
on your clients to enjoy ssl on all your services (that are using traefik).

## The API
The docker listener works very well if all your services are running in the same docker stack, and if
they're all being routed by traefik, but what about your octopi instance running on a separate raspberry
pi? This also comes with a very simple RESTful api that you can use to create certificates.
To generate a certificate for the domain `example.home`, simply POST the domain to the api.
    
`curl -X POST https://minica.home/certs/example.home`

If you attempt to POST a domain that we've already created a certificate for you'll get a 409 conflict.
If you've got a cert about to expire you can PUT it to update it. If you try to PUT a domain more than
30 days before its expiry you'll also get a 409 conflict.

`curl -X PUT https://minica.home/certs/example.home`

There is not GET api, except `/root`, which gives you the contents of `minica.pem`, in case you mess
up and expose the api to the internet.
