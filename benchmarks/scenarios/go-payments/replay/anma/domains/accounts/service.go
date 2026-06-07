package accounts

// GetUser returns a user's basic info.
func GetUser(userID string) map[string]string {
	return map[string]string{"id": userID, "name": "Ada"}
}

// AccountSummary returns user info plus their total invoiced amount.
// `invoiced` is injected by the caller to keep accounts decoupled from billing.
func AccountSummary(userID string, invoiced int) map[string]any {
	u := GetUser(userID)
	return map[string]any{"id": u["id"], "name": u["name"], "invoiced": invoiced}
}
