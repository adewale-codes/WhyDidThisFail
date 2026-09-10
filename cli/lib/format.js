'use strict';

const CODES = {
  reset: '\x1b[0m',
  bold: '\x1b[1m',
  dim: '\x1b[2m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  cyan: '\x1b[36m',
  magenta: '\x1b[35m',
};

function colorEnabled() {
  return Boolean(process.stdout.isTTY) && !process.env.NO_COLOR;
}

function paint(code, text, enabled) {
  return enabled ? `${code}${text}${CODES.reset}` : text;
}

/**
 * Renders a /diagnose response for the terminal. Pattern-matched and
 * LLM-escalated results get a visibly different badge so the user always
 * knows whether they're looking at a well-tested known fix or Claude's
 * best analysis of something new.
 */
function formatResult(result) {
  const on = colorEnabled();
  const bold = (s) => paint(CODES.bold, s, on);
  const dim = (s) => paint(CODES.dim, s, on);
  const heading = (s) => paint(CODES.bold + CODES.cyan, s, on);

  const badge =
    result.source === 'pattern'
      ? paint(CODES.bold + CODES.green, ' ✓ KNOWN ISSUE — pattern-matched ', on)
      : paint(CODES.bold + CODES.magenta, ' ✨ AI ANALYSIS — novel issue ', on);

  const lines = [];
  lines.push('');
  lines.push(badge);
  if (result.source === 'pattern' && result.pattern_id) {
    lines.push(dim(`matched pattern: ${result.pattern_id}`));
  } else if (result.source === 'llm') {
    lines.push(dim("no known pattern matched — this is Claude's best-effort diagnosis"));
  }

  lines.push('');
  lines.push(`${bold('Format:')} ${result.detected_format}`);

  const sig = result.error_signal || {};
  const errorLine = [sig.error_type, sig.message].filter(Boolean).join(': ');
  lines.push(`${bold('Error:')} ${errorLine || '(no message extracted)'}`);
  if (sig.file) {
    lines.push(`${bold('Location:')} ${sig.file}${sig.line ? ':' + sig.line : ''}`);
  }
  if (sig.extra && sig.extra.step) {
    lines.push(`${bold('Step:')} ${sig.extra.step}${sig.extra.command ? '  (' + sig.extra.command + ')' : ''}`);
  }

  lines.push('');
  lines.push(heading('Cause'));
  lines.push(result.cause || '(none)');

  lines.push('');
  lines.push(heading('Explanation'));
  lines.push(result.explanation || '(none)');

  lines.push('');
  lines.push(heading('Fix'));
  lines.push(result.fix || '(none)');

  if (result.commands && result.commands.length) {
    lines.push('');
    lines.push(heading('Commands'));
    for (const cmd of result.commands) {
      lines.push('  ' + paint(CODES.yellow, '$ ' + cmd, on));
    }
  }

  lines.push('');
  return lines.join('\n');
}

module.exports = { formatResult, colorEnabled };
