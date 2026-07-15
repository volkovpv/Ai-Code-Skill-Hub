/**
 * Clean application slice: type-only framework import, typed domain error.
 * The NestJS checker reports zero findings for this file.
 */
import type { OnModuleInit } from '@nestjs/common';

import { User, UserBlockedError, UserId } from '../domain/user.entity';

export interface UserRepositoryPort {
  findById(id: UserId): Promise<User | null>;
}

export const USER_REPOSITORY: unique symbol = Symbol('USER_REPOSITORY');

export class ActivateUserUseCase {
  public constructor(private readonly users: UserRepositoryPort) {}

  public async execute(id: UserId): Promise<void> {
    const user = await this.users.findById(id);
    if (user === null) {
      throw new UserBlockedError(id);
    }
    user.assertActive();
  }
}

export type BootHook = OnModuleInit;
