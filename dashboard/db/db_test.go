// dashboard/db/db_test.go
package db_test

import (
	"database/sql"
	"testing"
	"time"

	_ "github.com/mattn/go-sqlite3"

	"career-ops-fr/dashboard/db"
	"career-ops-fr/dashboard/model"
)

func openMemDB(t *testing.T) *db.DB {
	t.Helper()
	database, err := db.Open(":memory:")
	if err != nil {
		t.Fatalf("db.Open(:memory:) error: %v", err)
	}
	if err := database.CreateTable(); err != nil {
		t.Fatalf("CreateTable error: %v", err)
	}
	return database
}

func sampleApp() model.Application {
	return model.Application{
		Company:       "Mistral AI",
		Role:          "ML Engineer",
		OfferURL:      "https://mistral.ai/jobs/1",
		DetectionDate: time.Date(2026, 5, 25, 0, 0, 0, 0, time.UTC),
		ScoreGrade:    "A",
		ScoreValue:    4.7,
		Status:        "À envoyer",
		Contacts:      `[{"name":"Alice","linkedin":"https://linkedin.com/in/alice","email":"alice@mistral.ai"}]`,
		Notes:         "Strong match — apply immediately.",
	}
}

func TestCreateTable(t *testing.T) {
	t.Run("creates applications table", func(t *testing.T) {
		rawDB, err := sql.Open("sqlite3", ":memory:")
		if err != nil {
			t.Fatalf("sql.Open error: %v", err)
		}
		defer rawDB.Close()

		database := db.Wrap(rawDB)
		if err := database.CreateTable(); err != nil {
			t.Fatalf("CreateTable error: %v", err)
		}

		var name string
		err = rawDB.QueryRow(
			"SELECT name FROM sqlite_master WHERE type='table' AND name='applications'",
		).Scan(&name)
		if err != nil {
			t.Fatalf("table not found after CreateTable: %v", err)
		}
		if name != "applications" {
			t.Errorf("table name = %q, want %q", name, "applications")
		}
	})

	t.Run("idempotent — second call does not error", func(t *testing.T) {
		database := openMemDB(t)
		defer database.Close()
		if err := database.CreateTable(); err != nil {
			t.Errorf("second CreateTable call returned error: %v", err)
		}
	})
}

func TestInsert(t *testing.T) {
	t.Run("returns positive id", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		id, err := d.Insert(sampleApp())
		if err != nil {
			t.Fatalf("Insert error: %v", err)
		}
		if id <= 0 {
			t.Errorf("Insert returned id=%d, want > 0", id)
		}
	})

	t.Run("persists all fields", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		app := sampleApp()
		id, err := d.Insert(app)
		if err != nil {
			t.Fatalf("Insert error: %v", err)
		}
		got, err := d.GetByID(id)
		if err != nil {
			t.Fatalf("GetByID error: %v", err)
		}
		if got.Company != app.Company {
			t.Errorf("Company = %q, want %q", got.Company, app.Company)
		}
		if got.Role != app.Role {
			t.Errorf("Role = %q, want %q", got.Role, app.Role)
		}
		if got.ScoreGrade != app.ScoreGrade {
			t.Errorf("ScoreGrade = %q, want %q", got.ScoreGrade, app.ScoreGrade)
		}
		if got.ScoreValue != app.ScoreValue {
			t.Errorf("ScoreValue = %f, want %f", got.ScoreValue, app.ScoreValue)
		}
		if got.Status != app.Status {
			t.Errorf("Status = %q, want %q", got.Status, app.Status)
		}
		if got.Notes != app.Notes {
			t.Errorf("Notes = %q, want %q", got.Notes, app.Notes)
		}
		if got.Contacts != app.Contacts {
			t.Errorf("Contacts = %q, want %q", got.Contacts, app.Contacts)
		}
	})

	t.Run("nullable send_date roundtrips correctly", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		app := sampleApp()
		sendDate := time.Date(2026, 5, 26, 0, 0, 0, 0, time.UTC)
		app.SendDate = sendDate
		app.Status = "Envoyée"
		id, err := d.Insert(app)
		if err != nil {
			t.Fatalf("Insert error: %v", err)
		}
		got, err := d.GetByID(id)
		if err != nil {
			t.Fatalf("GetByID error: %v", err)
		}
		if !got.SendDate.Equal(sendDate) {
			t.Errorf("SendDate = %v, want %v", got.SendDate, sendDate)
		}
	})

	t.Run("zero send_date stored as NULL", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		app := sampleApp()
		id, err := d.Insert(app)
		if err != nil {
			t.Fatalf("Insert error: %v", err)
		}
		got, err := d.GetByID(id)
		if err != nil {
			t.Fatalf("GetByID error: %v", err)
		}
		if !got.SendDate.IsZero() {
			t.Errorf("SendDate = %v, want zero", got.SendDate)
		}
	})

	t.Run("two inserts get distinct ids", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		id1, _ := d.Insert(sampleApp())
		id2, _ := d.Insert(sampleApp())
		if id1 == id2 {
			t.Errorf("id1 == id2 == %d, expected distinct ids", id1)
		}
	})
}

func TestGetAll(t *testing.T) {
	t.Run("returns empty slice when no data", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		apps, err := d.GetAll()
		if err != nil {
			t.Fatalf("GetAll error: %v", err)
		}
		if len(apps) != 0 {
			t.Errorf("GetAll returned %d rows, want 0", len(apps))
		}
	})

	t.Run("returns all inserted applications", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		d.Insert(sampleApp())
		d.Insert(sampleApp())
		apps, err := d.GetAll()
		if err != nil {
			t.Fatalf("GetAll error: %v", err)
		}
		if len(apps) != 2 {
			t.Errorf("GetAll returned %d rows, want 2", len(apps))
		}
	})

	t.Run("returned structs have correct Company", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		d.Insert(sampleApp())
		apps, err := d.GetAll()
		if err != nil {
			t.Fatalf("GetAll error: %v", err)
		}
		if apps[0].Company != "Mistral AI" {
			t.Errorf("apps[0].Company = %q, want %q", apps[0].Company, "Mistral AI")
		}
	})
}

func TestGetByID(t *testing.T) {
	t.Run("returns error for missing id", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		_, err := d.GetByID(9999)
		if err == nil {
			t.Error("expected error for missing id 9999, got nil")
		}
	})

	t.Run("returns correct application", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		id, _ := d.Insert(sampleApp())
		got, err := d.GetByID(id)
		if err != nil {
			t.Fatalf("GetByID error: %v", err)
		}
		if got.ID != id {
			t.Errorf("got.ID = %d, want %d", got.ID, id)
		}
		if got.Company != "Mistral AI" {
			t.Errorf("got.Company = %q, want %q", got.Company, "Mistral AI")
		}
	})
}

func TestUpdate(t *testing.T) {
	t.Run("updates status field", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		id, _ := d.Insert(sampleApp())
		app, _ := d.GetByID(id)
		app.Status = "Envoyée"
		app.SendDate = time.Date(2026, 5, 26, 0, 0, 0, 0, time.UTC)
		if err := d.Update(app); err != nil {
			t.Fatalf("Update error: %v", err)
		}
		updated, _ := d.GetByID(id)
		if updated.Status != "Envoyée" {
			t.Errorf("updated.Status = %q, want %q", updated.Status, "Envoyée")
		}
		if updated.SendDate.IsZero() {
			t.Error("updated.SendDate is zero after update")
		}
	})

	t.Run("updates notes field", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		id, _ := d.Insert(sampleApp())
		app, _ := d.GetByID(id)
		app.Notes = "Had a great intro call."
		if err := d.Update(app); err != nil {
			t.Fatalf("Update error: %v", err)
		}
		updated, _ := d.GetByID(id)
		if updated.Notes != "Had a great intro call." {
			t.Errorf("updated.Notes = %q, want %q", updated.Notes, "Had a great intro call.")
		}
	})

	t.Run("returns error for zero id", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		app := sampleApp()
		err := d.Update(app)
		if err == nil {
			t.Error("expected error when updating app with ID=0, got nil")
		}
	})
}

func TestDelete(t *testing.T) {
	t.Run("deletes existing row", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		id, _ := d.Insert(sampleApp())
		if err := d.Delete(id); err != nil {
			t.Fatalf("Delete error: %v", err)
		}
		_, err := d.GetByID(id)
		if err == nil {
			t.Errorf("expected error after deleting id=%d, got nil", id)
		}
	})

	t.Run("deleting nonexistent id does not error", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		if err := d.Delete(9999); err != nil {
			t.Errorf("Delete(9999) returned unexpected error: %v", err)
		}
	})
}

func TestGetStats(t *testing.T) {
	t.Run("empty DB returns zero stats", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		stats, err := d.GetStats(time.Now())
		if err != nil {
			t.Fatalf("GetStats error: %v", err)
		}
		if stats.TotalApplications != 0 {
			t.Errorf("TotalApplications = %d, want 0", stats.TotalApplications)
		}
		if stats.ResponseRate != 0.0 {
			t.Errorf("ResponseRate = %f, want 0.0", stats.ResponseRate)
		}
		if stats.InterviewCount != 0 {
			t.Errorf("InterviewCount = %d, want 0", stats.InterviewCount)
		}
		if stats.StaleCount != 0 {
			t.Errorf("StaleCount = %d, want 0", stats.StaleCount)
		}
	})

	t.Run("response rate calculation", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		sent := time.Date(2026, 5, 20, 0, 0, 0, 0, time.UTC)
		for _, status := range []string{"Entretien RH", "Entretien tech", "Envoyée"} {
			app := sampleApp()
			app.Status = status
			app.SendDate = sent
			d.Insert(app)
		}
		stats, err := d.GetStats(time.Date(2026, 5, 25, 0, 0, 0, 0, time.UTC))
		if err != nil {
			t.Fatalf("GetStats error: %v", err)
		}
		wantRate := 2.0 / 3.0 * 100.0
		if stats.ResponseRate < wantRate-0.01 || stats.ResponseRate > wantRate+0.01 {
			t.Errorf("ResponseRate = %.4f, want ≈%.4f", stats.ResponseRate, wantRate)
		}
	})

	t.Run("interview count includes interview and beyond stages", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		for _, status := range []string{"Entretien RH", "Entretien tech", "Offre", "Envoyée", "À envoyer"} {
			app := sampleApp()
			app.Status = status
			d.Insert(app)
		}
		stats, err := d.GetStats(time.Now())
		if err != nil {
			t.Fatalf("GetStats error: %v", err)
		}
		if stats.InterviewCount != 3 {
			t.Errorf("InterviewCount = %d, want 3", stats.InterviewCount)
		}
	})

	t.Run("by status counts each status correctly", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		for _, status := range []string{"À envoyer", "Envoyée", "Envoyée", "Entretien RH"} {
			app := sampleApp()
			app.Status = status
			d.Insert(app)
		}
		stats, err := d.GetStats(time.Now())
		if err != nil {
			t.Fatalf("GetStats error: %v", err)
		}
		if stats.ByStatus["À envoyer"] != 1 {
			t.Errorf("ByStatus[\"À envoyer\"] = %d, want 1", stats.ByStatus["À envoyer"])
		}
		if stats.ByStatus["Envoyée"] != 2 {
			t.Errorf("ByStatus[\"Envoyée\"] = %d, want 2", stats.ByStatus["Envoyée"])
		}
		if stats.ByStatus["Entretien RH"] != 1 {
			t.Errorf("ByStatus[\"Entretien RH\"] = %d, want 1", stats.ByStatus["Entretien RH"])
		}
	})

	t.Run("stale count counts only Envoyée older than 7 days", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		today := time.Date(2026, 5, 25, 12, 0, 0, 0, time.UTC)
		stale := sampleApp()
		stale.Status = "Envoyée"
		stale.SendDate = today.AddDate(0, 0, -10)
		d.Insert(stale)
		fresh := sampleApp()
		fresh.Status = "Envoyée"
		fresh.SendDate = today.AddDate(0, 0, -3)
		d.Insert(fresh)
		stats, err := d.GetStats(today)
		if err != nil {
			t.Fatalf("GetStats error: %v", err)
		}
		if stats.StaleCount != 1 {
			t.Errorf("StaleCount = %d, want 1", stats.StaleCount)
		}
	})

	t.Run("total applications is correct", func(t *testing.T) {
		d := openMemDB(t)
		defer d.Close()
		for i := 0; i < 5; i++ {
			d.Insert(sampleApp())
		}
		stats, err := d.GetStats(time.Now())
		if err != nil {
			t.Fatalf("GetStats error: %v", err)
		}
		if stats.TotalApplications != 5 {
			t.Errorf("TotalApplications = %d, want 5", stats.TotalApplications)
		}
	})
}
