// Intentional violations in the domain layer — used by the skill's tests.
import { Injectable } from '@nestjs/common';

@Injectable()
export class BadEntity {
  public check(value: string | null): string {
    if (value === null) {
      throw new Error('value is required');
    }
    return value;
  }
}
