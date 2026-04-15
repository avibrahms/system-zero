#!/usr/bin/env node
const { spawnSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const which = (cmd) => spawnSync('which', [cmd], { encoding: 'utf-8' }).stdout.trim();
const localWheel = process.env.SYSTEM_ZERO_WHEEL || '';
const packageRoot = path.resolve(__dirname, '..');
const configPath = path.join(packageRoot, '.system-zero-cli.json');

function run(cmd, args) {
  console.log(`> ${cmd} ${args.join(' ')}`);
  const r = spawnSync(cmd, args, { stdio: 'inherit' });
  return r.status === 0;
}

function output(cmd, args) {
  const r = spawnSync(cmd, args, { encoding: 'utf-8' });
  return r.status === 0 ? r.stdout.trim() : '';
}

function isExecutable(p) {
  try {
    fs.accessSync(p, fs.constants.X_OK);
    return fs.statSync(p).isFile();
  } catch (_) {
    return false;
  }
}

function firstExecutable(paths) {
  for (const p of paths.filter(Boolean)) {
    if (isExecutable(p)) return fs.realpathSync(p);
  }
  return '';
}

function userBaseBin(pythonCmd) {
  const base = output(pythonCmd, ['-m', 'site', '--user-base']);
  return base ? path.join(base, 'bin') : '';
}

function pipxBinDir() {
  const explicit = process.env.PIPX_BIN_DIR || '';
  const fromPipx = output('pipx', ['environment', '--value', 'PIPX_BIN_DIR']);
  return explicit || fromPipx || path.join(os.homedir(), '.local', 'bin');
}

function writeCliConfig(cliPath) {
  if (!cliPath) {
    console.error('system-zero installed, but the Python sz executable could not be located.');
    process.exit(1);
  }
  fs.writeFileSync(configPath, JSON.stringify({ cliPath }, null, 2) + '\n');
  console.log(`system-zero npm wrapper will invoke ${cliPath}`);
}

(async () => {
  const target = localWheel || 'sz-cli==0.1.0';
  if (which('pipx')) {
    if (!run('pipx', ['install', target, '--force'])) process.exit(1);
    writeCliConfig(firstExecutable([path.join(pipxBinDir(), 'sz')]));
  } else if (which('pip3')) {
    if (!run('pip3', ['install', '--user', target])) process.exit(1);
    writeCliConfig(firstExecutable([path.join(userBaseBin('python3'), 'sz')]));
  } else if (which('python3')) {
    if (!run('python3', ['-m', 'pip', 'install', '--user', target])) process.exit(1);
    writeCliConfig(firstExecutable([path.join(userBaseBin('python3'), 'sz')]));
  } else {
    console.error('No Python found. Install Python 3.10+ then re-run `npm i -g system-zero`.');
    process.exit(1);
  }
  console.log('system-zero CLI (sz) installed. Run `sz --help` to begin.');
})();
