// dashboard/db/db.go

// Package db provides SQLite persistence for the career-ops-fr application tracker.
package db

import (
	"database/sql"
	"errors"
	"fmt"
	"time"

	_ "github.com/mattn/go-sqlite3"

	"career-ops-fr/dashboard/model"
)

const createTableSQL = `
CREATE TABLE IF NOT EXISTS applications (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    company            TEXT    NOT NULL,
    role               TEXT    NOT NULL,
    offer_url          TEXT    NOT NULL DEFAULT '',
    detection_date     TEXT    NOT NULL,
    score_grade        TEXT    NOT NULL DEFAULT '',
    score_value        REAL    NOT NULL DEFAULT 0.0,
    status             TEXT    NOT NULL DEFAULT 'À envoyer',
    send_date          TEXT,
    contacts           TEXT    NOT NULL DEFAULT '',
    notes              TEXT    NOT NULL DEFAULT '',
    cv_path            TEXT    NOT NULL DEFAULT '',
    cover_letter_path  TEXT    NOT NULL DEFAULT '',
    follow_up_date     TEXT
)`

// Stats holds the computed summary metrics returned by GetStats.
type Stats struct {
	TotalApplications int
	ResponseRate      float64
	InterviewCount    int
	StaleCount        int
	ByStatus          map[string]int
}

// DB wraps a *sql.DB and exposes domain-level CRUD operations.
type DB struct {
	sqlDB *sql.DB
}

// Open opens (or creates) the SQLite database file at path and returns a *DB.
func Open(path string) (*DB, error) {
	sqlDB, err := sql.Open("sqlite3", path)
	if err != nil {
		return nil, fmt.Errorf("db.Open: %w", err)
	}
	return &DB{sqlDB: sqlDB}, nil
}

// Wrap constructs a *DB from an existing *sql.DB. Used in tests.
func Wrap(sqlDB *sql.DB) *DB {
	return &DB{sqlDB: sqlDB}
}

// Close closes the underlying *sql.DB.
func (d *DB) Close() error {
	return d.sqlDB.Close()
}

// CreateTable creates the applications table if it does not already exist.
func (d *DB) CreateTable() error {
	if _, err := d.sqlDB.Exec(createTableSQL); err != nil {
		return fmt.Errorf("CreateTable: %w", err)
	}
	return nil
}

func timeToNull(t time.Time) *string {
	if t.IsZero() {
		return nil
	}
	s := t.UTC().Format("2006-01-02")
	return &s
}

func nullToTime(s *string) (time.Time, error) {
	if s == nil {
		return time.Time{}, nil
	}
	t, err := time.Parse("2006-01-02", *s)
	if err != nil {
		return time.Time{}, fmt.Errorf("nullToTime: parse %q: %w", *s, err)
	}
	return t, nil
}

// Insert inserts a new application row and returns the assigned primary key id.
func (d *DB) Insert(app model.Application) (int64, error) {
	res, err := d.sqlDB.Exec(
		`INSERT INTO applications
		    (company, role, offer_url, detection_date, score_grade, score_value,
		     status, send_date, contacts, notes, cv_path, cover_letter_path, follow_up_date)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		app.Company,
		app.Role,
		app.OfferURL,
		app.DetectionDate.UTC().Format("2006-01-02"),
		app.ScoreGrade,
		app.ScoreValue,
		app.Status,
		timeToNull(app.SendDate),
		app.Contacts,
		app.Notes,
		app.CVPath,
		app.CoverLetterPath,
		timeToNull(app.FollowUpDate),
	)
	if err != nil {
		return 0, fmt.Errorf("Insert: %w", err)
	}
	id, err := res.LastInsertId()
	if err != nil {
		return 0, fmt.Errorf("Insert LastInsertId: %w", err)
	}
	return id, nil
}

const selectQuery = `
SELECT id, company, role, offer_url, detection_date, score_grade, score_value,
       status, send_date, contacts, notes, cv_path, cover_letter_path, follow_up_date
FROM applications`

func scanApplication(rows *sql.Rows) (model.Application, error) {
	var (
		app                          model.Application
		detectionDateStr             string
		sendDateStr, followUpDateStr *string
	)
	if err := rows.Scan(
		&app.ID,
		&app.Company,
		&app.Role,
		&app.OfferURL,
		&detectionDateStr,
		&app.ScoreGrade,
		&app.ScoreValue,
		&app.Status,
		&sendDateStr,
		&app.Contacts,
		&app.Notes,
		&app.CVPath,
		&app.CoverLetterPath,
		&followUpDateStr,
	); err != nil {
		return model.Application{}, err
	}
	det, err := time.Parse("2006-01-02", detectionDateStr)
	if err != nil {
		return model.Application{}, fmt.Errorf("parse detection_date %q: %w", detectionDateStr, err)
	}
	app.DetectionDate = det
	if sd, err := nullToTime(sendDateStr); err != nil {
		return model.Application{}, err
	} else {
		app.SendDate = sd
	}
	if fud, err := nullToTime(followUpDateStr); err != nil {
		return model.Application{}, err
	} else {
		app.FollowUpDate = fud
	}
	return app, nil
}

// GetAll returns all application rows ordered by detection_date descending.
func (d *DB) GetAll() ([]model.Application, error) {
	rows, err := d.sqlDB.Query(selectQuery + " ORDER BY detection_date DESC")
	if err != nil {
		return nil, fmt.Errorf("GetAll: %w", err)
	}
	defer rows.Close()

	var apps []model.Application
	for rows.Next() {
		app, err := scanApplication(rows)
		if err != nil {
			return nil, fmt.Errorf("GetAll scan: %w", err)
		}
		apps = append(apps, app)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("GetAll rows: %w", err)
	}
	if apps == nil {
		apps = []model.Application{}
	}
	return apps, nil
}

// GetByID returns the application with the given id.
func (d *DB) GetByID(id int64) (model.Application, error) {
	rows, err := d.sqlDB.Query(selectQuery+" WHERE id = ?", id)
	if err != nil {
		return model.Application{}, fmt.Errorf("GetByID query: %w", err)
	}
	defer rows.Close()
	if !rows.Next() {
		if err := rows.Err(); err != nil {
			return model.Application{}, fmt.Errorf("GetByID rows: %w", err)
		}
		return model.Application{}, fmt.Errorf("GetByID id=%d: %w", id, sql.ErrNoRows)
	}
	app, err := scanApplication(rows)
	if err != nil {
		return model.Application{}, fmt.Errorf("GetByID scan: %w", err)
	}
	return app, nil
}

// Update replaces all fields of an existing application row.
func (d *DB) Update(app model.Application) error {
	if app.ID == 0 {
		return errors.New("Update: app.ID is zero; only persisted applications can be updated")
	}
	_, err := d.sqlDB.Exec(
		`UPDATE applications
		 SET company=?, role=?, offer_url=?, detection_date=?, score_grade=?, score_value=?,
		     status=?, send_date=?, contacts=?, notes=?, cv_path=?, cover_letter_path=?, follow_up_date=?
		 WHERE id=?`,
		app.Company,
		app.Role,
		app.OfferURL,
		app.DetectionDate.UTC().Format("2006-01-02"),
		app.ScoreGrade,
		app.ScoreValue,
		app.Status,
		timeToNull(app.SendDate),
		app.Contacts,
		app.Notes,
		app.CVPath,
		app.CoverLetterPath,
		timeToNull(app.FollowUpDate),
		app.ID,
	)
	if err != nil {
		return fmt.Errorf("Update id=%d: %w", app.ID, err)
	}
	return nil
}

// Delete removes the application row with the given id. No-op if not found.
func (d *DB) Delete(id int64) error {
	if _, err := d.sqlDB.Exec("DELETE FROM applications WHERE id = ?", id); err != nil {
		return fmt.Errorf("Delete id=%d: %w", id, err)
	}
	return nil
}

var responseStatuses = map[string]bool{
	"Entretien RH":   true,
	"Entretien tech": true,
	"Offre":          true,
	"Acceptée":       true,
	"Refusée":        true,
}

var interviewStatuses = map[string]bool{
	"Entretien RH":   true,
	"Entretien tech": true,
	"Offre":          true,
	"Acceptée":       true,
}

// GetStats computes summary statistics over all stored applications.
func (d *DB) GetStats(now time.Time) (Stats, error) {
	apps, err := d.GetAll()
	if err != nil {
		return Stats{}, fmt.Errorf("GetStats: %w", err)
	}

	byStatus := make(map[string]int, len(model.ValidStatuses))
	for _, s := range model.ValidStatuses {
		byStatus[s] = 0
	}

	var sentCount, responseCount, interviewCount, staleCount int
	for _, app := range apps {
		byStatus[app.Status]++
		if app.Status != "À envoyer" {
			sentCount++
		}
		if responseStatuses[app.Status] {
			responseCount++
		}
		if interviewStatuses[app.Status] {
			interviewCount++
		}
		if app.IsStale(now) {
			staleCount++
		}
	}

	var responseRate float64
	if sentCount > 0 {
		responseRate = float64(responseCount) / float64(sentCount) * 100.0
	}

	return Stats{
		TotalApplications: len(apps),
		ResponseRate:      responseRate,
		InterviewCount:    interviewCount,
		StaleCount:        staleCount,
		ByStatus:          byStatus,
	}, nil
}
