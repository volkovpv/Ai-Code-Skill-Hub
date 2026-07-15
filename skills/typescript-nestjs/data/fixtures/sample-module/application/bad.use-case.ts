// Intentional violations in the application layer — used by the skill's tests.
import { Inject } from '@nestjs/common';

export class BadUseCase {
  public constructor(@Inject('USER_REPOSITORY') private readonly users: unknown) {}
}
