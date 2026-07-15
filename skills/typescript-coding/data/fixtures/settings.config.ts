/**
 * Configuration layer: the single place allowed to read process.env. Scanned
 * by path (a *.config.ts name) the checker stays silent; piped through stdin,
 * with no path for context, it flags the env reads — the documented limit.
 */
export interface AppConfig {
  readonly databaseUrl: string;
  readonly port: number;
}

export function loadConfig(): AppConfig {
  return {
    databaseUrl: process.env.DATABASE_URL ?? 'postgres://localhost/app',
    port: Number(process.env.PORT ?? '3000'),
  };
}
