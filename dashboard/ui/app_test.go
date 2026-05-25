// dashboard/ui/app_test.go
package ui

import (
	"database/sql"
	"testing"
	"time"

	_ "github.com/mattn/go-sqlite3"

	"career-ops-fr/dashboard/db"
	"career-ops-fr/dashboard/model"
)

// setupTestDB opens an in-memory SQLite database and creates the schema.
func setupTestDB(t *testing.T) *db.DB {
	t.Helper()
	sqlDB, err := sql.Open("sqlite3", ":memory:")
	if err != nil {
		t.Fatalf("sql.Open: %v", err)
	}
	d := db.Wrap(sqlDB)
	if err := d.CreateTable(); err != nil {
		t.Fatalf("CreateTable: %v", err)
	}
	t.Cleanup(func() { _ = d.Close() })
	return d
}

func sampleApp(company string) model.Application {
	return model.Application{
		Company:       company,
		Role:          "Engineer",
		DetectionDate: time.Date(2026, 1, 15, 0, 0, 0, 0, time.UTC),
		ScoreGrade:    "A",
		ScoreValue:    4.5,
		Status:        "À envoyer",
	}
}

// TestNewAppModel_EmptyDB verifies that NewAppModel succeeds with an empty DB.
func TestNewAppModel_EmptyDB(t *testing.T) {
	d := setupTestDB(t)
	m, err := NewAppModel(d)
	if err != nil {
		t.Fatalf("NewAppModel: %v", err)
	}
	if m.currentView != viewPipeline {
		t.Errorf("expected viewPipeline, got %d", m.currentView)
	}
	if len(m.pipeline.apps) != 0 {
		t.Errorf("expected 0 apps, got %d", len(m.pipeline.apps))
	}
}

// TestNewAppModel_WithApps verifies that NewAppModel loads existing applications.
func TestNewAppModel_WithApps(t *testing.T) {
	d := setupTestDB(t)
	if _, err := d.Insert(sampleApp("CompanyA")); err != nil {
		t.Fatalf("Insert: %v", err)
	}
	if _, err := d.Insert(sampleApp("CompanyB")); err != nil {
		t.Fatalf("Insert: %v", err)
	}

	m, err := NewAppModel(d)
	if err != nil {
		t.Fatalf("NewAppModel: %v", err)
	}
	if len(m.pipeline.apps) != 2 {
		t.Errorf("expected 2 apps, got %d", len(m.pipeline.apps))
	}
}

// TestAppModel_SaveMsg_Insert verifies that a SaveMsg with ID=0 inserts a new row.
func TestAppModel_SaveMsg_Insert(t *testing.T) {
	d := setupTestDB(t)
	m, err := NewAppModel(d)
	if err != nil {
		t.Fatalf("NewAppModel: %v", err)
	}

	app := sampleApp("NewCo")
	// app.ID == 0 → Insert path
	updatedModel, _ := m.Update(SaveMsg{App: app})
	am := updatedModel.(AppModel)

	if am.currentView != viewPipeline {
		t.Errorf("expected viewPipeline after save, got %d", am.currentView)
	}
	apps, err := d.GetAll()
	if err != nil {
		t.Fatalf("GetAll: %v", err)
	}
	if len(apps) != 1 {
		t.Errorf("expected 1 app in DB, got %d", len(apps))
	}
	if apps[0].Company != "NewCo" {
		t.Errorf("expected Company=NewCo, got %q", apps[0].Company)
	}
	if len(am.pipeline.apps) != 1 {
		t.Errorf("expected pipeline to have 1 app after reload, got %d", len(am.pipeline.apps))
	}
	if am.statusMsg == "" {
		t.Errorf("expected non-empty statusMsg after save")
	}
}

// TestAppModel_SaveMsg_Update verifies that a SaveMsg with existing ID updates the row.
func TestAppModel_SaveMsg_Update(t *testing.T) {
	d := setupTestDB(t)
	id, err := d.Insert(sampleApp("Original"))
	if err != nil {
		t.Fatalf("Insert: %v", err)
	}

	m, err := NewAppModel(d)
	if err != nil {
		t.Fatalf("NewAppModel: %v", err)
	}

	updated := sampleApp("Updated")
	updated.ID = id
	updatedModel, _ := m.Update(SaveMsg{App: updated})
	am := updatedModel.(AppModel)

	if am.currentView != viewPipeline {
		t.Errorf("expected viewPipeline after save, got %d", am.currentView)
	}
	app, err := d.GetByID(id)
	if err != nil {
		t.Fatalf("GetByID: %v", err)
	}
	if app.Company != "Updated" {
		t.Errorf("expected Company=Updated, got %q", app.Company)
	}
}

// TestAppModel_CancelMsg verifies that CancelMsg switches view back to viewPipeline.
func TestAppModel_CancelMsg(t *testing.T) {
	d := setupTestDB(t)
	m, err := NewAppModel(d)
	if err != nil {
		t.Fatalf("NewAppModel: %v", err)
	}

	// Manually set to viewDetail to simulate being in detail view.
	m.currentView = viewDetail

	updatedModel, _ := m.Update(CancelMsg{})
	am := updatedModel.(AppModel)

	if am.currentView != viewPipeline {
		t.Errorf("expected viewPipeline after cancel, got %d", am.currentView)
	}
	if am.statusMsg != "" {
		t.Errorf("expected empty statusMsg after cancel, got %q", am.statusMsg)
	}
}
