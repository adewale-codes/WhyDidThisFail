#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const { diagnose, ToolError, DEFAULT_API_URL } = require('../lib/diagnose');
const { formatResult } = require('../lib/format');

const pkg = require(path.join(__dirname, '..', 'package.json'));

function printUsage() {
  console.error(`whyfail v${pkg.version} — why did this fail?

Usage:
  some-failing-command 2>&1 | npx whyfail     diagnose piped output
  npx whyfail ./build.log                     diagnose a saved log file
  npx whyfail --paste                         paste log text interactively

Options:
  --json                output the raw API response as JSON
  --format <type>        hint the log format instead of auto-detecting (python | npm | docker)
  --api-url <url>        override the API base URL (default: ${DEFAULT_API_URL})
                          also settable via WHYFAIL_API_URL
  -h, --help              show this help
`);
}

function parseArgs(argv) {
  const args = { json: false, paste: false, format: null, apiUrl: null, file: null, help: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    switch (a) {
      case '--json':
        args.json = true;
        break;
      case '--paste':
        args.paste = true;
        break;
      case '--format':
        args.format = argv[++i];
        if (args.format === undefined) throw new ToolError('--format requires a value');
        break;
      case '--api-url':
        args.apiUrl = argv[++i];
        if (args.apiUrl === undefined) throw new ToolError('--api-url requires a value');
        break;
      case '-h':
      case '--help':
        args.help = true;
        break;
      default:
        if (a.startsWith('-')) throw new ToolError(`Unknown option: ${a}`);
        if (args.file) throw new ToolError(`Unexpected extra argument: ${a}`);
        args.file = a;
    }
  }
  return args;
}

function readStream(stream) {
  return new Promise((resolve, reject) => {
    let data = '';
    stream.setEncoding('utf8');
    stream.on('data', (chunk) => (data += chunk));
    stream.on('end', () => resolve(data));
    stream.on('error', reject);
  });
}

async function main() {
  let args;
  try {
    args = parseArgs(process.argv.slice(2));
  } catch (err) {
    console.error(err.message);
    printUsage();
    process.exitCode = 1;
    return;
  }

  if (args.help) {
    printUsage();
    return;
  }

  let log;
  if (args.paste) {
    if (process.stdin.isTTY) {
      console.error('Paste your log text, then press Ctrl+D (Ctrl+Z then Enter on Windows) when done:\n');
    }
    log = await readStream(process.stdin);
  } else if (args.file) {
    try {
      log = fs.readFileSync(args.file, 'utf8');
    } catch (err) {
      console.error(`Could not read file "${args.file}": ${err.message}`);
      process.exitCode = 1;
      return;
    }
  } else if (!process.stdin.isTTY) {
    log = await readStream(process.stdin);
  } else {
    printUsage();
    process.exitCode = 1;
    return;
  }

  if (!log || !log.trim()) {
    console.error('No log input received (input was empty).');
    process.exitCode = 1;
    return;
  }

  let result;
  try {
    result = await diagnose(log, { apiUrl: args.apiUrl, formatHint: args.format });
  } catch (err) {
    console.error(err instanceof ToolError ? err.message : `Unexpected error: ${err.message}`);
    process.exitCode = 1;
    return;
  }

  if (args.json) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    console.log(formatResult(result));
  }
}

main();
