#!/usr/bin/env node
const { spawnSync } = require('child_process');
const which = (cmd) => spawnSync('which', [cmd], { encoding: 'utf-8' }).stdout.trim();
const localWheel = process.env.SYSTEM_ZERO_WHEEL || '';

function run(cmd, args) {
  console.log(`> ${cmd} ${args.join(' ')}`);
  const r = spawnSync(cmd, args, { stdio: 'inherit' });
  return r.status === 0;
}

(async () => {
  const target = localWheel || 'system-zero==0.1.0';
  if (which('pipx')) {
    if (!run('pipx', ['install', target, '--force'])) process.exit(1);
  } else if (which('pip3')) {
    if (!run('pip3', ['install', '--user', target])) process.exit(1);
  } else if (which('python3')) {
    if (!run('python3', ['-m', 'pip', 'install', '--user', target])) process.exit(1);
  } else {
    console.error('No Python found. Install Python 3.10+ then re-run `npm i -g system-zero`.');
    process.exit(1);
  }
  console.log('system-zero CLI (sz) installed. Run `sz --help` to begin.');
})();
