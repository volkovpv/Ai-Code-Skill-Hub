/**
 * Clean domain slice: no framework imports, typed domain errors only.
 * The NestJS checker reports zero findings for this file.
 */
export type UserId = string & { readonly __brand: 'UserId' };

export class DomainError extends Error {
  public constructor(
    public readonly code: string,
    message: string,
    options?: { readonly cause?: unknown },
  ) {
    super(message, options);
    this.name = new.target.name;
  }
}

export class UserBlockedError extends DomainError {
  public constructor(public readonly userId: UserId) {
    super('user_blocked', `user ${String(userId)} is blocked`);
  }
}

export class User {
  private constructor(
    public readonly id: UserId,
    public readonly blocked: boolean,
  ) {}

  public static restore(id: UserId, blocked: boolean): User {
    return new User(id, blocked);
  }

  public assertActive(): void {
    if (this.blocked) {
      throw new UserBlockedError(this.id);
    }
  }
}
