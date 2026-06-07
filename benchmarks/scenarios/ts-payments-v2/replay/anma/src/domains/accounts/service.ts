// accounts public surface.
export function getUser(userId: string) {
  return { id: userId, name: "Ada" };
}

export function accountSummary(userId: string, invoiced = 0) {
  // `invoiced` is injected by the caller to keep accounts decoupled from billing
  const u = getUser(userId);
  return { ...u, invoiced };
}
