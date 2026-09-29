// Package orders is a calibration sample: framework-free Go that satisfies
// every rule of the coding standard, so the convention checker finds nothing.
package orders

import (
	"context"
	"crypto/rand"
	"crypto/subtle"
	"database/sql"
	"errors"
	"fmt"
	"io"
	"iter"
	"log/slog"
	"net/http"
	"os"
	"os/exec"
	"regexp"
	"strings"
	"sync"
	"time"
)

// Tunables are named once, next to the code that owns them.
const (
	requestTimeout  = 10 * time.Second
	maxBodyBytes    = 1 << 20
	maxParallelLoad = 8
)

// ErrNotFound reports that no order exists for the requested ID.
var ErrNotFound = errors.New("orders: not found")

var orderIDPattern = regexp.MustCompile(`^ord_[a-z0-9]{12}$`)

// OrderID identifies an order. Build one with ParseOrderID only.
type OrderID string

// ParseOrderID validates raw input at the boundary and brands it as an OrderID.
func ParseOrderID(raw string) (OrderID, error) {
	if !orderIDPattern.MatchString(raw) {
		return "", &ValidationError{Field: "order_id"}
	}
	return OrderID(raw), nil
}

// ValidationError reports which input field failed validation.
type ValidationError struct {
	Field string
}

func (e *ValidationError) Error() string {
	return "orders: invalid " + e.Field
}

// Status is the closed set of order states; the zero value is not a state.
type Status uint8

// The order states.
const (
	StatusUnspecified Status = iota
	StatusPending
	StatusPaid
	StatusCancelled
	statusCount // end marker: every constant above it is a member of the set
)

// Statuses yields every valid status, derived from the constant block itself.
func Statuses() iter.Seq[Status] {
	return func(yield func(Status) bool) {
		for s := StatusUnspecified + 1; s < statusCount; s++ {
			if !yield(s) {
				return
			}
		}
	}
}

func (s Status) String() string {
	switch s {
	case StatusUnspecified:
		return "unspecified"
	case StatusPending:
		return "pending"
	case StatusPaid:
		return "paid"
	case StatusCancelled:
		return "cancelled"
	default:
		return fmt.Sprintf("Status(%d)", uint8(s))
	}
}

// Money is an amount in minor currency units; never a float.
type Money int64

// Order is one customer order.
type Order struct {
	ID     OrderID
	Status Status
	Total  Money
}

// Event is a sealed sum type: only this package can add variants.
type Event interface {
	isEvent()
}

// OrderPaid records a completed payment.
type OrderPaid struct {
	ID     OrderID
	Amount Money
}

// OrderCancelled records a cancellation and its reason.
type OrderCancelled struct {
	ID     OrderID
	Reason string
}

func (OrderPaid) isEvent()      {}
func (OrderCancelled) isEvent() {}

// Describe renders an event; an unknown variant is an error, never a guess.
func Describe(e Event) (string, error) {
	switch ev := e.(type) {
	case OrderPaid:
		return fmt.Sprintf("order %s paid %d", ev.ID, ev.Amount), nil
	case OrderCancelled:
		return fmt.Sprintf("order %s cancelled: %s", ev.ID, ev.Reason), nil
	default:
		return "", fmt.Errorf("orders: unknown event %T", e)
	}
}

// Store is the narrow view of persistence this package consumes.
type Store interface {
	Find(ctx context.Context, id OrderID) (Order, error)
}

// Service coordinates order operations.
type Service struct {
	store  Store
	logger *slog.Logger
	now    func() time.Time
}

// NewService wires a Service; the clock is injected so tests control time.
func NewService(store Store, logger *slog.Logger, now func() time.Time) *Service {
	return &Service{store: store, logger: logger, now: now}
}

// Status returns the current status of an order.
func (s *Service) Status(ctx context.Context, id OrderID) (Status, error) {
	order, err := s.store.Find(ctx, id)
	if err != nil {
		return StatusUnspecified, fmt.Errorf("find order %s: %w", id, err)
	}
	s.logger.InfoContext(ctx, "order status read", slog.String("order_id", string(id)))
	return order.Status, nil
}

// LoadAll fetches orders with at most maxParallelLoad calls in flight: a slot
// is taken before each goroutine starts, so the input size never decides how
// many goroutines run, and LoadAll waits for every goroutine it started.
func (s *Service) LoadAll(ctx context.Context, ids []OrderID) ([]Order, error) {
	orders := make([]Order, len(ids))
	errs := make([]error, len(ids))
	slots := make(chan struct{}, maxParallelLoad)
	var wg sync.WaitGroup
	for i, id := range ids {
		select {
		case slots <- struct{}{}:
		case <-ctx.Done():
			wg.Wait()
			return nil, fmt.Errorf("load orders: %w", ctx.Err())
		}
		wg.Go(func() {
			defer func() { <-slots }()
			orders[i], errs[i] = s.store.Find(ctx, id)
		})
	}
	wg.Wait()
	if err := errors.Join(errs...); err != nil {
		return nil, fmt.Errorf("load orders: %w", err)
	}
	return orders, nil
}

// LoadStatus reads one status through a parameterized query.
func LoadStatus(ctx context.Context, db *sql.DB, id OrderID) (Status, error) {
	var status Status
	row := db.QueryRowContext(ctx, "SELECT status FROM orders WHERE id = $1", string(id))
	if err := row.Scan(&status); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return StatusUnspecified, ErrNotFound
		}
		return StatusUnspecified, fmt.Errorf("scan status of %s: %w", id, err)
	}
	return status, nil
}

// NewHTTPClient returns a client that can never wait forever.
func NewHTTPClient() *http.Client {
	return &http.Client{Timeout: requestTimeout}
}

// FetchReceipt downloads a receipt with a request context and a size cap.
func FetchReceipt(ctx context.Context, client *http.Client, receiptURL string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, receiptURL, http.NoBody)
	if err != nil {
		return nil, fmt.Errorf("build receipt request: %w", err)
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("get receipt: %w", err)
	}
	defer func() { _ = resp.Body.Close() }() // read side: nothing is lost
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("get receipt: unexpected status %d", resp.StatusCode)
	}
	body, err := io.ReadAll(io.LimitReader(resp.Body, maxBodyBytes))
	if err != nil {
		return nil, fmt.Errorf("read receipt: %w", err)
	}
	return body, nil
}

// Revision runs a program directly with an argument list, never via a shell.
func Revision(ctx context.Context, repoDir string) (string, error) {
	cmd := exec.CommandContext(ctx, "git", "rev-parse", "HEAD")
	cmd.Dir = repoDir
	out, err := cmd.Output()
	if err != nil {
		return "", fmt.Errorf("git rev-parse: %w", err)
	}
	return strings.TrimSpace(string(out)), nil
}

// ReadAttachment opens a user-named file that must stay inside dir.
func ReadAttachment(dir, name string) ([]byte, error) {
	root, err := os.OpenRoot(dir)
	if err != nil {
		return nil, fmt.Errorf("open attachment root: %w", err)
	}
	defer func() { _ = root.Close() }() // read side: nothing is lost
	data, err := root.ReadFile(name)
	if err != nil {
		return nil, fmt.Errorf("read attachment %q: %w", name, err)
	}
	return data, nil
}

// NewToken returns a random, URL-safe secret.
func NewToken() string {
	return rand.Text()
}

// TokensEqual compares secrets in constant time.
func TokensEqual(got, want string) bool {
	return subtle.ConstantTimeCompare([]byte(got), []byte(want)) == 1
}

// AsValidation extracts a ValidationError from a wrapped chain.
func AsValidation(err error) (*ValidationError, bool) {
	return errors.AsType[*ValidationError](err)
}

// FieldOf reads a field name from a value whose dynamic type is unknown.
func FieldOf(v any) (string, bool) {
	ve, ok := v.(*ValidationError)
	if !ok {
		return "", false
	}
	return ve.Field, true
}
