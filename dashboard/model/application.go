// dashboard/model/application.go

// Package model defines the core data types for the career-ops-fr application tracker.
package model

import "time"

// FollowUpAlertDays is the number of days an application may remain in "Envoyée"
// status before it is flagged as stale in the pipeline view.
const FollowUpAlertDays = 7

// ValidStatuses is the ordered list of all nine pipeline states.
var ValidStatuses = []string{
	"À envoyer",
	"Envoyée",
	"Relance",
	"Entretien RH",
	"Entretien tech",
	"Offre",
	"Acceptée",
	"Refusée",
	"Abandonnée",
}

// Application represents one tracked job application.
type Application struct {
	ID            int64
	Company       string
	Role          string
	OfferURL      string
	DetectionDate time.Time
	ScoreGrade    string
	ScoreValue    float64
	Status        string

	SendDate        time.Time
	Contacts        string
	Notes           string
	CVPath          string
	CoverLetterPath string
	FollowUpDate    time.Time
}

// IsStale reports whether the application has been sitting in "Envoyée" status
// for more than FollowUpAlertDays days as of the given reference time.
func (a Application) IsStale(now time.Time) bool {
	if a.Status != "Envoyée" {
		return false
	}
	if a.SendDate.IsZero() {
		return false
	}
	elapsed := now.Sub(a.SendDate)
	return elapsed > time.Duration(FollowUpAlertDays)*24*time.Hour
}
