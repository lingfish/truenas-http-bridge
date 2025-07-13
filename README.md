# TrueNAS App: HTTP Bridge

A Dockerised HTTP bridge application for TrueNAS environments.

What does that mean? Since the TrueNAS team moved their API to use websockets (and not HTTP REST), being able to query
the API from a client that doesn't speak websockets isn't possible.

A good example of this is polling a SCALE system from Zabbix.

This app is a long-running daemon that connects (and stays connected) to a SCALE system, and listens on a chosen port
to serve "classic" HTTP GET/POST queries, acting as a HTTP-to-websockets bridge.

## Features

- Easy deployment with Docker Compose on TrueNAS via a custom app
- Uses a Python Fast API app to stay persistently connected to TrueNAS (minimising audit entries)

## Missing stuff/TODO in Zabbix template
- [X] Add discovery rules for TrueNAS pools
- [X] Add discovery rules for TrueNAS datasets
- [ ] Add discovery rules for other TrueNAS stuff
- [ ] Add graphs, triggers, etc.

## Prerequisites

- [TrueNAS](https://www.truenas.com/) installed -- **minimum tested version is 25.04**
- Installation of the Zabbix template

## Getting started

1. Login to your TrueNAS system via the web interface.
2. Click Apps -> Discover Apps -> Hamburger menu -> Install via YAML
3. Paste the contents of `docker-compose.yaml` into the text area.
4. Edit the environment variables as needed.
5. Hit Save.

## Configuration

Import the Zabbix template `truenas_template.yaml` into your Zabbix server to get the necessary items.

There is currently only discovery and items in the template.  **Pull requests are welcome and desired to add more things
to the template, such as triggers, graphs, etc.**

## How it works
The app will listen for requests on the configured port, and pass them through to the TrueNAS API. A quick curl
example:

```bash
curl -X POST "http://localhost:8000/api/core.ping" -H "Content-Type: application/json" -u "username:password" -d '{}'
"pong"
```

Perhaps something more useful:

```json
curl -X POST "http://localhost:8000/api/system.ntpserver.query" -H "Content-Type: application/json" -u "username:password" -d '{}' -s | jq .
[
  {
    "id": 1,
    "address": "0.debian.pool.ntp.org",
    "burst": false,
    "iburst": true,
    "prefer": false,
    "minpoll": 6,
    "maxpoll": 10
  },
  {
    "id": 2,
    "address": "1.debian.pool.ntp.org",
    "burst": false,
    "iburst": true,
    "prefer": false,
    "minpoll": 6,
    "maxpoll": 10
  },
  {
    "id": 3,
    "address": "2.debian.pool.ntp.org",
    "burst": false,
    "iburst": true,
    "prefer": false,
    "minpoll": 6,
    "maxpoll": 10
  }
]
```

So this means you can create, for example, Zabbix HTTP agent items to poll things, etc.

## Contact

For questions or support, please open an issue on [this repo](https://github.com/lingfish/truenas-http-bridge/issues).
Though there is a thread on the TrueNAS forums, I'd prefer to keep the discussion here on GitHub.

