// Minimal, project-independent reproduction.
// typescript-eslint's promise-function-async with { allowAny: false } reports
// any function whose declared return type is `unknown`, because it cannot
// prove the value is not a Promise (documented rule limitation). The value
// here is trivially not a Promise, so the narrow, justified, single-rule
// disable below is the sanctioned linter-level escape hatch.
// eslint-disable-next-line @typescript-eslint/promise-function-async -- upstream rule limitation: unknown return is not a Promise here
const passthrough = (value: unknown): unknown => value;
export { passthrough };
