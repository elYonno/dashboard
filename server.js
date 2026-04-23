require('dotenv').config();
const express = require('express');
const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// --- SSH config ---
function getSshConfig() {
  const keyPath = process.env.TRUENAS_KEY_PATH || path.join(process.env.HOME, '.ssh', 'id_rsa');
  return {
    host: process.env.TRUENAS_HOST || '192.168.1.100',
    port: parseInt(process.env.TRUENAS_PORT) || 22,
    username: process.env.TRUENAS_USER || 'root',
    privateKey: fs.readFileSync(keyPath),
  };
}

// Run a command on TrueNAS over SSH, returns Promise<{ stdout, stderr, code }>
function sshExec(command) {
  return new Promise((resolve, reject) => {
    const conn = new Client();
    let stdout = '';
    let stderr = '';

    conn.on('ready', () => {
      conn.exec(command, (err, stream) => {
        if (err) { conn.end(); return reject(err); }
        stream.on('close', (code) => {
          conn.end();
          resolve({ stdout: stdout.trim(), stderr: stderr.trim(), code });
        });
        stream.on('data', (data) => { stdout += data; });
        stream.stderr.on('data', (data) => { stderr += data; });
      });
    });

    conn.on('error', (err) => reject(err));

    try {
      conn.connect(getSshConfig());
    } catch (e) {
      reject(e);
    }
  });
}

const VALID_NAME = /^[a-zA-Z0-9_\-]+$/;

// Resolve the working directory for an app by name.
// The root compose file lives in appsDir itself; its project name is the dir's basename.
function getAppDir(appsDir, appName) {
  const rootName = path.basename(appsDir.replace(/\/+$/, ''));
  return appName === rootName ? appsDir : `${appsDir}/${appName}`;
}

// Get all services and their current state for one app directory.
// Uses one SSH call: config --services gives defined services, ps -a gives running state.
async function getAppServices(appDir) {
  const cmd = `cd "${appDir}" && sudo docker compose config --services 2>/dev/null && echo '|||' && sudo docker compose ps -a --format "{{.Service}}\t{{.State}}\t{{.Status}}\t{{.Name}}" 2>/dev/null`;
  const { stdout } = await sshExec(cmd);

  const [svcSection = '', psSection = ''] = stdout.split('|||');
  const serviceNames = svcSection.split('\n').map(s => s.trim()).filter(Boolean);

  const psMap = {};
  for (const line of psSection.split('\n').filter(Boolean)) {
    const parts = line.split('\t');
    const svc = parts[0]?.trim();
    if (svc) psMap[svc] = {
      state:         parts[1]?.trim() || 'stopped',
      status:        parts[2]?.trim() || '',
      containerName: (parts[3]?.trim() || '').toLowerCase(),
    };
  }

  return serviceNames.map(name => ({
    name,
    state:         psMap[name]?.state         || 'stopped',
    status:        psMap[name]?.status        || 'not started',
    containerName: psMap[name]?.containerName || '',
  }));
}

// Discover all app names in COMPOSE_APPS_DIR
async function discoverAppNames(appsDir) {
  const hasCompose = (dir) =>
    `[ -f "${dir}docker-compose.yml" ] || [ -f "${dir}docker-compose.yaml" ] || [ -f "${dir}compose.yml" ] || [ -f "${dir}compose.yaml" ]`;

  const rootName = path.basename(appsDir.replace(/\/+$/, ''));
  const rootDir = appsDir.replace(/\/?$/, '/');
  const { stdout: rootCheck } = await sshExec(`${hasCompose(rootDir)} && echo yes || echo no`);

  const listCmd = `for d in ${appsDir}/*/; do ${hasCompose('"$d"')} && basename "$d"; done`;
  const { stdout: dirOut } = await sshExec(listCmd);
  const subNames = dirOut ? dirOut.split('\n').map(s => s.trim()).filter(Boolean) : [];

  return [
    ...(rootCheck.trim() === 'yes' ? [rootName] : []),
    ...subNames,
  ];
}

// --- API Routes ---

// GET /api/apps — list all compose applications with their services
app.get('/api/apps', async (req, res) => {
  const appsDir = process.env.COMPOSE_APPS_DIR;
  if (!appsDir) return res.status(500).json({ error: 'COMPOSE_APPS_DIR not set in .env' });

  try {
    const appNames = await discoverAppNames(appsDir);
    const apps = await Promise.all(appNames.map(async name => {
      const services = await getAppServices(getAppDir(appsDir, name));
      return { name, services };
    }));
    res.json({ apps });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/apps/:appName/start — docker compose up -d (all services)
app.post('/api/apps/:appName/start', async (req, res) => {
  const { appName } = req.params;
  if (!VALID_NAME.test(appName)) return res.status(400).json({ error: 'Invalid app name' });
  const appsDir = process.env.COMPOSE_APPS_DIR;
  try {
    const { stdout, stderr, code } = await sshExec(
      `cd "${getAppDir(appsDir, appName)}" && sudo docker compose up -d 2>&1`
    );
    if (code !== 0) return res.status(500).json({ error: stderr || stdout || 'Start failed' });
    res.json({ success: true, message: `${appName} started` });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/apps/:appName/stop — docker compose stop (all services)
app.post('/api/apps/:appName/stop', async (req, res) => {
  const { appName } = req.params;
  if (!VALID_NAME.test(appName)) return res.status(400).json({ error: 'Invalid app name' });
  const appsDir = process.env.COMPOSE_APPS_DIR;
  try {
    const { stdout, stderr, code } = await sshExec(
      `cd "${getAppDir(appsDir, appName)}" && sudo docker compose stop 2>&1`
    );
    if (code !== 0) return res.status(500).json({ error: stderr || stdout || 'Stop failed' });
    res.json({ success: true, message: `${appName} stopped` });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/start-all — start all apps in parallel
app.post('/api/start-all', async (req, res) => {
  const appsDir = process.env.COMPOSE_APPS_DIR;
  if (!appsDir) return res.status(500).json({ error: 'COMPOSE_APPS_DIR not set in .env' });
  try {
    const appNames = await discoverAppNames(appsDir);
    await Promise.all(appNames.map(name =>
      sshExec(`cd "${getAppDir(appsDir, name)}" && sudo docker compose up -d 2>&1`)
    ));
    res.json({ success: true, message: 'All apps started' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/stop-all — stop all apps in parallel
app.post('/api/stop-all', async (req, res) => {
  const appsDir = process.env.COMPOSE_APPS_DIR;
  if (!appsDir) return res.status(500).json({ error: 'COMPOSE_APPS_DIR not set in .env' });
  try {
    const appNames = await discoverAppNames(appsDir);
    await Promise.all(appNames.map(name =>
      sshExec(`cd "${getAppDir(appsDir, name)}" && sudo docker compose stop 2>&1`)
    ));
    res.json({ success: true, message: 'All apps stopped' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/apps/:appName/services/:service/start — docker compose up -d <service>
app.post('/api/apps/:appName/services/:service/start', async (req, res) => {
  const { appName, service } = req.params;
  if (!VALID_NAME.test(appName) || !VALID_NAME.test(service))
    return res.status(400).json({ error: 'Invalid name' });
  const appsDir = process.env.COMPOSE_APPS_DIR;
  try {
    const { stdout, stderr, code } = await sshExec(
      `cd "${getAppDir(appsDir, appName)}" && sudo docker compose up -d ${service} 2>&1`
    );
    if (code !== 0) return res.status(500).json({ error: stderr || stdout || 'Start failed' });
    res.json({ success: true, message: `${appName}/${service} started` });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/apps/:appName/services/:service/stop — docker compose stop <service>
app.post('/api/apps/:appName/services/:service/stop', async (req, res) => {
  const { appName, service } = req.params;
  if (!VALID_NAME.test(appName) || !VALID_NAME.test(service))
    return res.status(400).json({ error: 'Invalid name' });
  const appsDir = process.env.COMPOSE_APPS_DIR;
  try {
    const { stdout, stderr, code } = await sshExec(
      `cd "${getAppDir(appsDir, appName)}" && sudo docker compose stop ${service} 2>&1`
    );
    if (code !== 0) return res.status(500).json({ error: stderr || stdout || 'Stop failed' });
    res.json({ success: true, message: `${appName}/${service} stopped` });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/apps/:appName/services/:service/logs
app.get('/api/apps/:appName/services/:service/logs', async (req, res) => {
  const { appName, service } = req.params;
  const lines = parseInt(req.query.lines) || 80;
  if (!VALID_NAME.test(appName) || !VALID_NAME.test(service))
    return res.status(400).json({ error: 'Invalid name' });
  const appsDir = process.env.COMPOSE_APPS_DIR;
  try {
    const { stdout, stderr } = await sshExec(
      `cd "${getAppDir(appsDir, appName)}" && sudo docker compose logs --tail=${lines} ${service} 2>&1`
    );
    res.json({ logs: stdout || stderr || '(no logs)' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Parse Docker memory strings like "234MiB", "1.5GiB", "512kB" to MiB
function parseDockerMem(str) {
  const m = (str || '').trim().match(/^([\d.]+)\s*(B|kB|KiB|MB|MiB|GB|GiB|TB|TiB)/i);
  if (!m) return 0;
  const v = parseFloat(m[1]);
  const u = m[2].toLowerCase();
  if (u === 'b')              return v / (1024 * 1024);
  if (u === 'kb' || u === 'kib') return v / 1024;
  if (u === 'mb' || u === 'mib') return v;
  if (u === 'gb' || u === 'gib') return v * 1024;
  if (u === 'tb' || u === 'tib') return v * 1024 * 1024;
  return v;
}

// GET /api/stats — aggregate CPU % and memory (MiB + %) across all running containers,
// plus a per-container breakdown keyed by lowercase container name.
app.get('/api/stats', async (req, res) => {
  try {
    const { stdout } = await sshExec(
      'sudo docker stats --no-stream --format "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null'
    );
    if (!stdout) return res.json({ cpu: 0, memMB: 0, memPct: 0, containers: 0, byContainer: {} });

    let totalCpu = 0;
    let totalUsedMB = 0;
    let hostMemMB = 0;
    let count = 0;
    const byContainer = {};

    for (const line of stdout.split('\n').filter(Boolean)) {
      const parts = line.split('\t');
      if (parts.length < 3) continue;
      const name   = parts[0].trim().toLowerCase();
      const cpu    = parseFloat(parts[1]) || 0;
      const memParts = parts[2].split('/');
      const usedMB = parseDockerMem(memParts[0]);
      const limitMB = parseDockerMem(memParts[1]);
      const memPct = limitMB > 0 ? (usedMB / limitMB) * 100 : 0;

      byContainer[name] = {
        cpu:   Math.round(cpu * 10) / 10,
        memMB: Math.round(usedMB),
        memPct: Math.round(memPct * 10) / 10,
      };

      totalCpu    += cpu;
      totalUsedMB += usedMB;
      if (limitMB > hostMemMB) hostMemMB = limitMB;
      count++;
    }

    const memPct = hostMemMB > 0 ? (totalUsedMB / hostMemMB) * 100 : 0;
    res.json({
      cpu:         Math.round(totalCpu * 10) / 10,
      memMB:       Math.round(totalUsedMB),
      memPct:      Math.round(memPct * 10) / 10,
      containers:  count,
      byContainer,
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/health — test SSH connectivity
app.get('/api/health', async (req, res) => {
  try {
    const { stdout } = await sshExec('echo ok');
    res.json({ connected: stdout === 'ok', host: process.env.TRUENAS_HOST });
  } catch (err) {
    res.json({ connected: false, error: err.message });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Docker Dashboard running on http://0.0.0.0:${PORT}`);
  console.log(`Connecting to TrueNAS at ${process.env.TRUENAS_HOST || '192.168.1.100'}`);
  console.log(`Compose apps directory: ${process.env.COMPOSE_APPS_DIR || '(not set — update .env)'}`);
});
