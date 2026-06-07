package accounts

import "example.com/shop/domains/billing" // shortcut: accounts -> billing (forbidden)

// GetUser returns a user's basic info.
func GetUser(userID string) map[string]string {
	return map[string]string{"id": userID, "name": "Ada"}
}

// AccountSummary returns user info plus their total invoiced amount.
func AccountSummary(userID string) map[string]any {
	u := GetUser(userID)
	return map[string]any{"id": u["id"], "name": u["name"], "invoiced": billing.TotalInvoiced(userID)}
}
