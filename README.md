# DOCKMASTER — Docker Dashboard for Raspberry Pi

A lightweight dashboard that runs on your Raspberry Pi 2 and controls Docker
containers on your TrueNAS machine via SSH.

---

## Requirements

- **Raspberry Pi 2** running Raspberry Pi OS (or similar Debian-based distro)
- **Node.js** v14+ installed on the RPi
- SSH key-based access from the RPi to TrueNAS (no password prompt)

---

## Setup

### 1. Install Node.js on RPi (if not already installed)

```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### 2. Copy this project to your RPi

```bash
scp -r docker-dashboard/ pi@<rpi-ip>:/home/pi/docker-dashboard
```

Or clone/copy however you prefer.

### 3. Install dependencies

```bash
cd ~/docker-dashboard
npm install
```

### 4. Configure your TrueNAS connection

```bash
cp .env.example .env
nano .env
```

Edit `.env` with your actual values:

```
TRUENAS_HOST=<TRUENAS_HOST>         # Your TrueNAS IP address
TRUENAS_PORT=22                     # SSH port
TRUENAS_USER=<TRUENAS_USER>         # SSH user on TrueNAS
TRUENAS_KEY_PATH=<TRUENAS_KEY_PATH> # Path to your SSH private key
PORT=3000                           # dashboard port
COMPOSE_APPS_DIR=<COMPOSE_APPS_DIR> # Path on TrueNAS where each app subdirectory contains a compose file
```

### 5. Verify SSH access works

```bash
ssh -i /home/pi/.ssh/id_rsa root@192.168.1.100 "docker ps"
```

You should see your Docker containers. If not, sort the SSH key permissions first.

### 6. Start the dashboard

```bash
npm start
```

Open a browser and go to: `http://<rpi-ip>:3000`

---

## Run on boot (optional but recommended)

Create a systemd service so the dashboard starts automatically:

```bash
sudo nano /etc/systemd/system/dockmaster.service
```

Paste:

```ini
[Unit]
Description=Dockmaster Docker Dashboard
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/docker-dashboard
ExecStart=/usr/bin/node server.js
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable dockmaster
sudo systemctl start dockmaster
```

---

## Features

- **Live status** — shows all containers (running, stopped, restarting)
- **Start / Stop / Restart** — one-click container control
- **Logs viewer** — last 80 lines of container logs
- **Connection indicator** — shows SSH link to TrueNAS is healthy
- **Auto-refresh** — polls every 15 seconds automatically

---

## Adding More Containers

No config needed — the dashboard automatically discovers all containers
(`docker ps -a`) on your TrueNAS machine. Your NextCloud container will appear
as soon as you start the dashboard.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "DISCONNECTED" in header | Check `TRUENAS_HOST` in `.env` and verify SSH works manually |
| SSH key permission error | Run `chmod 600 /home/pi/.ssh/id_rsa` |
| Containers not showing | Ensure the SSH user has permission to run `docker` commands |
| Port 3000 blocked | Change `PORT=` in `.env` or open the port in your firewall |

---

## Home Assistant integration (HACS)

The `custom_components/dockmaster/` folder is a custom integration that talks to this server's API and exposes it in Home Assistant:

- **Sensors:** NAS and Pi CPU %, RAM %, temperature and uptime; NAS container count, CPU and memory.
- **Binary sensors:** NAS SSH connection, and running state of every compose service.
- **Switches:** one per app. On starts the app (`docker compose up -d`), off stops it.
- **Buttons:** start all apps, stop all apps.

### Install

1. In HACS, open **⋮ → Custom repositories**, add this repository URL with category **Integration**.
2. Install **Dockmaster** from HACS and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → Dockmaster** and enter the address and port this server listens on (default port `3000`, e.g. the Pi's LAN IP).

Home Assistant must be able to reach the server over the LAN. The server has no authentication, so do not expose its port to the internet.
