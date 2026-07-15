/**
 * Reference of the target style: strictly-typed, framework-free TypeScript.
 * The convention checker reports zero findings for this file.
 */

// --- Branded identifier -----------------------------------------------------
export type UserId = string & { readonly __brand: 'UserId' };
export const asUserId = (raw: string): UserId => raw as UserId;

// --- Constant registry: an `as const` object + union, never a native enum ---
export const USER_STATUS = {
  Active: 'active',
  Blocked: 'blocked',
} as const;
export type UserStatus = (typeof USER_STATUS)[keyof typeof USER_STATUS];

// --- Typed error with a stable code and a cause-preserving wrap -------------
export class LookupFailedError extends Error {
  public readonly code = 'lookup_failed';

  public constructor(message: string, options?: { readonly cause?: unknown }) {
    super(message, options);
    this.name = 'LookupFailedError';
  }
}

export interface User {
  readonly id: UserId;
  readonly status: UserStatus;
}

export interface UserSource {
  findById(id: UserId): Promise<User | null>;
}

// --- Errors: unknown in catch, wrap once at the source, keep the cause ------
export async function getUser(source: UserSource, id: UserId): Promise<User> {
  let user: User | null;
  try {
    user = await source.findById(id);
  } catch (error: unknown) {
    throw new LookupFailedError(`lookup failed for ${String(id)}`, { cause: error });
  }
  if (user === null) {
    throw new LookupFailedError(`user ${String(id)} not found`);
  }
  return user;
}
