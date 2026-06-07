package accounts

// GetUser returns a user's basic info.
func GetUser(userID string) map[string]string {
	return map[string]string{"id": userID, "name": "Ada"}
}
