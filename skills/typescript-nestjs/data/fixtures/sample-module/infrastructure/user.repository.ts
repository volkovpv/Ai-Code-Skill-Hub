// Infrastructure layer: NestJS imports are legitimate here, but the DI token
// discipline still applies — the inline Symbol below is the one violation.
import { Inject, Injectable } from '@nestjs/common';

@Injectable()
export class UserRepository {
  public constructor(@Inject(Symbol('DATA_SOURCE')) private readonly db: unknown) {}

  public async findById(id: string): Promise<void> {
    try {
      await Promise.resolve(id);
    } catch (error: unknown) {
      // A raw throw is NOT flagged in infrastructure by the layer rule; the
      // wrap-into-domain-error discipline is reviewed, not machine-checked.
      throw new Error('driver failed', { cause: error });
    }
  }
}
