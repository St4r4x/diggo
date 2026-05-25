// dashboard/model/application_test.go
package model_test

import (
	"testing"
	"time"

	"career-ops-fr/dashboard/model"
)

func TestValidStatuses(t *testing.T) {
	t.Run("count is nine", func(t *testing.T) {
		if got := len(model.ValidStatuses); got != 9 {
			t.Errorf("len(ValidStatuses) = %d, want 9", got)
		}
	})

	t.Run("first status is À envoyer", func(t *testing.T) {
		if model.ValidStatuses[0] != "À envoyer" {
			t.Errorf("ValidStatuses[0] = %q, want %q", model.ValidStatuses[0], "À envoyer")
		}
	})

	t.Run("terminal statuses are last three", func(t *testing.T) {
		last3 := model.ValidStatuses[6:]
		want := map[string]bool{"Acceptée": true, "Refusée": true, "Abandonnée": true}
		for _, s := range last3 {
			if !want[s] {
				t.Errorf("unexpected terminal status %q", s)
			}
		}
	})

	t.Run("contains all expected values", func(t *testing.T) {
		expected := []string{
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
		set := make(map[string]bool, len(model.ValidStatuses))
		for _, s := range model.ValidStatuses {
			set[s] = true
		}
		for _, e := range expected {
			if !set[e] {
				t.Errorf("ValidStatuses missing %q", e)
			}
		}
	})
}

func TestApplicationInstantiation(t *testing.T) {
	t.Run("minimal required fields", func(t *testing.T) {
		app := model.Application{
			Company:       "Mistral AI",
			Role:          "ML Engineer",
			OfferURL:      "https://mistral.ai/jobs/1",
			DetectionDate: time.Date(2026, 5, 25, 0, 0, 0, 0, time.UTC),
			ScoreGrade:    "A",
			ScoreValue:    4.7,
			Status:        "À envoyer",
		}
		if app.Company != "Mistral AI" {
			t.Errorf("Company = %q, want %q", app.Company, "Mistral AI")
		}
		if app.Status != "À envoyer" {
			t.Errorf("Status = %q, want %q", app.Status, "À envoyer")
		}
	})

	t.Run("optional fields default to zero values", func(t *testing.T) {
		app := model.Application{
			Company:       "HuggingFace",
			Role:          "NLP Engineer",
			OfferURL:      "https://hf.co/jobs/2",
			DetectionDate: time.Date(2026, 5, 25, 0, 0, 0, 0, time.UTC),
			ScoreGrade:    "B",
			ScoreValue:    4.1,
			Status:        "Envoyée",
		}
		if app.ID != 0 {
			t.Errorf("ID = %d, want 0", app.ID)
		}
		if !app.SendDate.IsZero() {
			t.Errorf("SendDate should be zero, got %v", app.SendDate)
		}
		if !app.FollowUpDate.IsZero() {
			t.Errorf("FollowUpDate should be zero, got %v", app.FollowUpDate)
		}
		if app.CVPath != "" {
			t.Errorf("CVPath should be empty, got %q", app.CVPath)
		}
		if app.CoverLetterPath != "" {
			t.Errorf("CoverLetterPath should be empty, got %q", app.CoverLetterPath)
		}
		if app.Notes != "" {
			t.Errorf("Notes should be empty, got %q", app.Notes)
		}
		if app.Contacts != "" {
			t.Errorf("Contacts should be empty string, got %q", app.Contacts)
		}
	})
}

func TestIsStale(t *testing.T) {
	now := time.Date(2026, 5, 25, 12, 0, 0, 0, time.UTC)

	tests := []struct {
		name     string
		status   string
		sendDate time.Time
		want     bool
	}{
		{
			name:     "Envoyée sent 10 days ago is stale",
			status:   "Envoyée",
			sendDate: now.AddDate(0, 0, -10),
			want:     true,
		},
		{
			name:     "Envoyée sent exactly 7 days ago is not stale (boundary)",
			status:   "Envoyée",
			sendDate: now.AddDate(0, 0, -7),
			want:     false,
		},
		{
			name:     "Envoyée sent 8 days ago is stale",
			status:   "Envoyée",
			sendDate: now.AddDate(0, 0, -8),
			want:     true,
		},
		{
			name:     "Envoyée sent 3 days ago is not stale",
			status:   "Envoyée",
			sendDate: now.AddDate(0, 0, -3),
			want:     false,
		},
		{
			name:     "Entretien RH with old send_date is not stale",
			status:   "Entretien RH",
			sendDate: now.AddDate(0, 0, -30),
			want:     false,
		},
		{
			name:     "Envoyée with zero send_date is not stale",
			status:   "Envoyée",
			sendDate: time.Time{},
			want:     false,
		},
		{
			name:     "À envoyer is never stale",
			status:   "À envoyer",
			sendDate: now.AddDate(0, 0, -30),
			want:     false,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			app := model.Application{
				Company:       "Test Co",
				Role:          "Engineer",
				OfferURL:      "https://test.com",
				DetectionDate: now.AddDate(0, 0, -14),
				ScoreGrade:    "B",
				ScoreValue:    3.5,
				Status:        tc.status,
				SendDate:      tc.sendDate,
			}
			got := app.IsStale(now)
			if got != tc.want {
				t.Errorf("IsStale(%v) = %v, want %v (status=%q, sendDate=%v)",
					now, got, tc.want, tc.status, tc.sendDate)
			}
		})
	}
}

func TestFollowUpAlertDays(t *testing.T) {
	if model.FollowUpAlertDays != 7 {
		t.Errorf("FollowUpAlertDays = %d, want 7", model.FollowUpAlertDays)
	}
}
