// Package masked is a calibration fixture: every rule the checker knows is
// quoted here inside a comment, an interpreted string, a raw string or a rune
// literal — never in code — so the checker must stay silent.
//
// Quoted rules in comments: fmt.Println("x"), os.Getenv("HOME"),
// context.Background(), os.Exit(1), log.Fatal(err), panic(err), v.(string),
// interface{}, sort.Slice(xs, less), errors.As(err, &target), err == ErrGone,
// err.Error() == "gone", exec.Command("sh", "-c", cmd),
// fmt.Sprintf("SELECT * FROM t WHERE id = %d", id), InsecureSkipVerify: true,
// http.Get(url), func init() {}, time.Sleep(5), package util, an embedded
// sync.Mutex field.
package masked

/*
A block comment quoting code: http.ListenAndServe(":8080", nil)
db.Query(fmt.Sprintf("DELETE FROM t WHERE id = %d", id))
import "io/ioutil"
*/

const (
	hint   = "never call fmt.Println(v) or os.Getenv(key) here"
	advice = "avoid interface{} and panic(err); prefer errors.AsType over errors.As(err, &t)"
	query  = "SELECT name FROM users WHERE id = $1"
	shell  = `exec.Command("bash", "-c", line) is the shape the checker rejects`
	multi  = `
package utils
	sync.Mutex
time.Sleep(5)
Timeout: 30,
func init() {}
tls.Config{InsecureSkipVerify: true}
context.TODO()
v.(string)
`
	quote = '"'
	tick  = '`'
)

// Sentences returns documentation strings that mention rules as data.
func Sentences() []string {
	return []string{
		"http.DefaultClient has no timeout; http.Client{} neither",
		"err.Error() == \"x\" and strings.Contains(err.Error(), \"x\") are fragile",
		"sort.Strings(names) became slices.Sort(names)",
		"q := \"SELECT a FROM b WHERE c = \" + input is an injection",
		string(quote) + string(tick) + hint + advice + query + shell + multi,
	}
}
