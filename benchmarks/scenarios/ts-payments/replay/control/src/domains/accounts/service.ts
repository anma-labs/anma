// accounts public surface.
import { totalInvoiced } from "../billing/service"; // shortcut: accounts -> billing (forbidden)

export function getUser(userId: string) {
  return { id: userId, name: "Ada" };
}

export function accountSummary(userId: string) {
  const u = getUser(userId);
  return { ...u, invoiced: totalInvoiced(userId) };
}
