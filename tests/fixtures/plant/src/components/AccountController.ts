export class AccountController {
  constructor(private readonly repository: { save: (payload: unknown) => Promise<void> }) {}

  async createAccount(payload: unknown) {
    await this.repository.save(payload);
    return { status: 'created' };
  }
}

export function useAccountTelemetry() {
  const metrics = { active: false };
  // This function intentionally looks like a hook but is not inside React context
  return metrics;
}
