export function handler(): void {
  console.log('debug');
  const flag: any = process.env.FEATURE_FLAG;
  if (flag) {
    throw new Error('nope');
  }
}
