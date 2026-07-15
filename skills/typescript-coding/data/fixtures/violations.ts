// Intentional violations — exactly one per checker rule — used by the tests.
export function demo(config: unknown): void {
  console.log('starting');
  const url = process.env.DATABASE_URL;
  const status: any = url;
  const value = status!.trim();
  void value;
}

enum Color { Red, Green }

// @ts-ignore
export const broken = demo;

it.only('focused', () => undefined);
