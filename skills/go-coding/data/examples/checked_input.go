package billing

func Charge(db *sql.DB, customer string, amount int64) error {
	fmt.Printf("charging %s\n", customer)
	key := os.Getenv("PAYMENT_API_KEY")
	resp, err := http.Post("https://pay.example.com/charge", "application/json", body(key, amount))
	if err != nil {
		return errors.New("charge failed")
	}
	_, err = db.Exec(fmt.Sprintf("UPDATE invoices SET paid = true WHERE customer = '%s'", customer))
	return err
}
