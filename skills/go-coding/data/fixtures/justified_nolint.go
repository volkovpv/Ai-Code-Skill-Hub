// Package justified is a calibration fixture for the one sanctioned lint
// suppression shape: line-scoped, exactly one linter (or one check, or one
// rule), and a written reason. GO-SUPPRESS must stay silent on every line.
package justified

import (
	"crypto/sha1" //nolint:gosec // G505: SHA-1 names git objects here, not a security control
	"encoding/hex"
)

// GitBlobID reproduces git's object naming, which is defined as SHA-1; the
// digest is an identifier here, not a security control.
func GitBlobID(content []byte) string {
	sum := sha1.Sum(content) //nolint:gosec // git object IDs are SHA-1 by definition, not a security use
	return hex.EncodeToString(sum[:])
}

// LegacyDigest is the same computation for a standalone staticcheck run.
func LegacyDigest(content []byte) [20]byte {
	//lint:ignore SA1019 the upstream format fixes the algorithm; replacement tracked upstream
	return sha1.Sum(content)
}

// GosecNative is the same computation annotated for a standalone gosec run.
func GosecNative(content []byte) [20]byte {
	return sha1.Sum(content) // #nosec G401 -- git object IDs are SHA-1 by definition
}
