/**
 * Calibration fixture for the checker's lexical masking: every rule of the
 * skill is quoted below inside a string, template literal, regex literal, or
 * comment — and none of it is executable code, so the checker must report
 * ZERO findings for this file. Code inside template interpolations is still
 * scanned (see the tests for the positive case).
 */

// In comments nothing counts: console.log('x'); enum E {} process.env.HOME
/* Nor in block comments: const b: any = null; token!.value; it.only(...) */

export const QUOTED_RULES = {
  consoleBan: 'never call console.log(anything) in shipped code',
  enumBan: "native enum Color { Red } is banned",
  envBan: `process.env.SECRET must stay in the config layer`,
  anyBan: 'a value typed ": any" defeats strict mode',
  suppressBan: 'do not write @ts-ignore or eslint-disable comments',
  pragmaAsData: 'skill-check-ignore: TS-ENV -- a pragma in a string is data',
} as const;

// A regex literal is masked too — including rule-like text inside it:
export const RULE_MENTION_RE = /console\.log\(|enum\s+[A-Z]|@ts-ignore/u;

// Division is not a regex start; nothing after `/` is masked here:
export const HALF = 4 / 2;

// A multi-line template literal stays masked across lines:
export const DOC = `
  examples that must not fire:
    console.error('boom');
    const x: any = 1;
    it.only('nope', () => {});
`;
