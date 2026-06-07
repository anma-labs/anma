// billing public surface. May import accounts (allowed).
import { getUser } from "../accounts/service";

export function createInvoice(userId: string, amount: number) {
  const user = getUser(userId);
  return { user: user.id, amount };
}

export function totalInvoiced(_userId: string): number {
  return 0;
}
