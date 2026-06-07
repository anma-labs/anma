package billing

import "example.com/shop/domains/accounts" // billing may import accounts (allowed)

// CreateInvoice creates an invoice for a user.
func CreateInvoice(userID string, amount int) map[string]any {
	user := accounts.GetUser(userID)
	return map[string]any{"user": user["id"], "amount": amount}
}

// TotalInvoiced returns the total amount invoiced to a user.
func TotalInvoiced(userID string) int {
	return 0
}
