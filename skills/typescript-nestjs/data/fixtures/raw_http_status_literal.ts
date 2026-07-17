// Minimal, deterministic, project-independent fixture for OBS-20260717-001:
// raw numeric HTTP-status literals used instead of `HttpStatus.*`
// (@nestjs/common) in the three positions the observation names, plus the
// equivalent clean forms that must stay unflagged.

import { Controller, HttpCode, HttpException, HttpStatus } from "@nestjs/common";

export const ProblemCode = { notFound: "not_found" } as const;

// --- dirty: raw numeric literal, each position flagged exactly once ---

export function throwNotFound(): never {
  throw new HttpException("not found", 404);
}

export const STATUS_MAP = new Map<number, string>([
  [404, ProblemCode.notFound],
]);

@Controller()
export class DirtyController {
  @HttpCode(204)
  noContent(): void {
    return;
  }
}

// --- clean: HttpStatus.* registry, none of these are flagged ---

export function throwNotFoundClean(): never {
  throw new HttpException("not found", HttpStatus.NOT_FOUND);
}

export const STATUS_MAP_CLEAN = new Map<number, string>([
  [HttpStatus.NOT_FOUND, ProblemCode.notFound],
]);

@Controller()
export class CleanController {
  @HttpCode(HttpStatus.NO_CONTENT)
  noContent(): void {
    return;
  }
}
