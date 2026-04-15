#!/usr/bin/env bash
set -euo pipefail

ensure_absorb_fixture_cache() {
  local cache="$1"
  mkdir -p "$cache/p-limit" "$cache/changed-files" "$cache/llm"
  if [ ! -f "$cache/p-limit/index.js" ]; then
    cat > "$cache/p-limit/index.js" <<'JS'
export default function pLimit(concurrency) {
  const queue = [];
  let activeCount = 0;

  const next = () => {
    activeCount -= 1;
    if (queue.length > 0) {
      queue.shift()();
    }
  };

  const run = async (fn, resolve, args) => {
    activeCount += 1;
    const result = Promise.resolve(fn(...args));
    resolve(result);
    try {
      await result;
    } finally {
      next();
    }
  };

  const enqueue = (fn, resolve, args) => {
    queue.push(run.bind(undefined, fn, resolve, args));
    if (activeCount < concurrency && queue.length > 0) {
      queue.shift()();
    }
  };

  return (fn, ...args) => new Promise(resolve => {
    enqueue(fn, resolve, args);
  });
}
JS
  fi
  if [ ! -f "$cache/changed-files/README.md" ]; then
    printf '# changed-files fixture\n' > "$cache/changed-files/README.md"
  fi
  if [ ! -f "$cache/llm/README.md" ]; then
    printf '# llm fixture\n' > "$cache/llm/README.md"
  fi
}
