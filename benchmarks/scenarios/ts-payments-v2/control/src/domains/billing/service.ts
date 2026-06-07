// billing public surface. May import accounts (allowed).
import { getUser } from "../accounts/service";

// tiny in-memory store of amounts billed per user
const invoices: Record<string, number[]> = {
  u1: [1200, 800, 500],
  u2: [300],
};

export function createInvoice(userId: string, amount: number) {
  const user = getUser(userId);
  (invoices[userId] ??= []).push(amount);
  return { user: user.id, amount };
}

export function totalInvoiced(userId: string): number {
  return (invoices[userId] ?? []).reduce((a, b) => a + b, 0);
}
