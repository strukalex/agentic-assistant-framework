#!/usr/bin/env node
/**
 * Wrapper script for open-websearch MCP server.
 * 
 * Filters stdout to only pass through JSON-RPC messages (lines starting with '{' or '['),
 * redirecting all informational/logging output to stderr to comply with MCP protocol.
 * 
 * The MCP protocol requires that stdout only contains JSON-RPC messages. Any logging
 * or informational messages must go to stderr.
 */

const { spawn } = require('child_process');
const path = require('path');

// Find the open-websearch binary
const openWebsearchPath = path.join(__dirname, '..', 'node_modules', '.bin', 'open-websearch');

// Spawn the open-websearch process
// CRITICAL: Use 'pipe' for ALL stdio streams so we can intercept and filter them
const child = spawn(openWebsearchPath, [], {
  env: {
    ...process.env,
    MODE: 'stdio',
  },
  stdio: ['pipe', 'pipe', 'pipe'], // CHANGED: All pipes, not inherit
});

// Validate that streams are available
if (!child.stdin || !child.stdout || !child.stderr) {
  console.error('Error: Child process streams not available');
  process.exit(1);
}

if (!process.stdin || !process.stdout) {
  console.error('Error: Parent process streams not available');
  process.exit(1);
}

// Filter stdout: only pass through JSON lines (start with '{' or '[')
// Everything else goes to stderr
// Buffer incomplete lines to handle multi-chunk messages
let stdoutBuffer = '';

child.stdout.on('data', (data) => {
  stdoutBuffer += data.toString();
  const lines = stdoutBuffer.split('\n');
  // Keep the last (potentially incomplete) line in buffer
  stdoutBuffer = lines.pop() || '';
  
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      // Empty line - skip it (MCP protocol doesn't use empty lines)
      continue;
    }
    // Check if line looks like JSON-RPC (starts with '{' or '[')
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
      // This is a JSON-RPC message, pass to stdout
      process.stdout.write(line + '\n');
    } else {
      // This is informational output (emoji messages, etc.), redirect to stderr
      process.stderr.write('[FILTERED] ' + line + '\n');
    }
  }
});

// Flush any remaining buffer on end
child.stdout.on('end', () => {
  if (stdoutBuffer.trim()) {
    const trimmed = stdoutBuffer.trim();
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
      process.stdout.write(stdoutBuffer);
    } else {
      process.stderr.write('[FILTERED] ' + stdoutBuffer);
    }
  }
});

// Pass stderr through with prefix for clarity
child.stderr.on('data', (data) => {
  process.stderr.write(data);
});

// Forward stdin from parent to child
process.stdin.pipe(child.stdin);

// Handle process exit
child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
  } else {
    process.exit(code || 0);
  }
});

child.on('error', (error) => {
  console.error('Failed to start open-websearch:', error);
  process.exit(1);
});

// Forward signals to child
process.on('SIGTERM', () => {
  child.kill('SIGTERM');
});

process.on('SIGINT', () => {
  child.kill('SIGINT');
});

// Handle unexpected parent exit
process.on('exit', () => {
  if (!child.killed) {
    child.kill();
  }
});

