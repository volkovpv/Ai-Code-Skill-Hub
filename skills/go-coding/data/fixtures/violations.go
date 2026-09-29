// Package util is a calibration fixture: exactly one violation per checker
// rule, one rule per line, so the checker reports each code once. (The
// package name itself is the GO-PKG-NAME violation.)
package util

import (
	"io/ioutil"
)

func init() {}

type counter struct {
	sync.Mutex
	n int
}

func Handle(db *sql.DB, id string, v any) error {
	fmt.Println("debug")
	dsn := os.Getenv("DATABASE_URL")
	ctx := context.Background()
	rows, err := db.QueryContext(ctx, fmt.Sprintf("SELECT * FROM orders WHERE id = '%s'", id))
	if err == sql.ErrNoRows {
		panic(err)
	}
	name := v.(string)
	var legacy interface{} = name
	out, _ := exec.Command("sh", "-c", "grep "+id+" /var/log/app.log").Output()
	cfg := &tls.Config{InsecureSkipVerify: true}
	resp, _ := http.Get("https://example.com/" + id)
	resp.Body.Close() //nolint
	time.Sleep(250)
	os.Exit(3)
	return nil
}
