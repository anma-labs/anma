package billing

import "example.com/shop/domains/accounts" // billing may import accounts (allowed)

// invoices is a tiny in-memory store of amounts billed per user.
var invoices = map[string][]int{
	"u1": {1200, 800, 500},
	"u2": {300},
}

// CreateInvoice records an invoice for a user.
func CreateInvoice(userID string, amount int) map[string]any {
	user := accounts.GetUser(userID)
	invoices[userID] = append(invoices[userID], amount)
	return map[string]any{"user": user["id"], "amount": amount}
}

// TotalInvoiced returns the total amount invoiced to a user.
func TotalInvoiced(userID string) int {
	sum := 0
	for _, a := range invoices[userID] {
		sum += a
	}
	return sum
}
