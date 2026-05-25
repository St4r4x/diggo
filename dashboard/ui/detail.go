// dashboard/ui/detail.go
package ui

import (
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"career-ops-fr/dashboard/model"
)

// SaveMsg is sent when the user saves the form.
type SaveMsg struct{ App model.Application }

// CancelMsg is sent when the user presses Esc.
type CancelMsg struct{}

const (
	fieldCompany = iota
	fieldRole
	fieldOfferURL
	fieldDetectionDate
	fieldScoreGrade
	fieldScoreValue
	fieldStatus
	fieldSendDate
	fieldFollowUpDate
	fieldCVPath
	fieldCoverLetterPath
	fieldNotes
	fieldCount
)

var (
	detailLabelStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("243")).Width(22)
	detailErrorStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("196")).Bold(true)
	detailTitleStyle = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("212")).MarginBottom(1)
	detailHintStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("240")).Italic(true)
)

var fieldLabels = [fieldCount]string{
	"Company", "Role", "Offer URL", "Detection date", "Grade", "Score",
	"Status", "Send date", "Follow-up date", "CV path", "Cover letter", "Notes",
}

// DetailModel is the Bubble Tea model for the application detail/edit form.
type DetailModel struct {
	inputs   [fieldCount]textinput.Model
	focusIdx int
	isNew    bool
	app      model.Application
	errorMsg string
}

// NewDetailModel constructs a DetailModel pre-populated with app's values.
func NewDetailModel(app model.Application, isNew bool) DetailModel {
	m := DetailModel{isNew: isNew, app: app}
	values := [fieldCount]string{
		app.Company, app.Role, app.OfferURL,
		formatDate(app.DetectionDate), app.ScoreGrade, formatFloat(app.ScoreValue),
		app.Status, formatDate(app.SendDate), formatDate(app.FollowUpDate),
		app.CVPath, app.CoverLetterPath, app.Notes,
	}
	for i := 0; i < fieldCount; i++ {
		ti := textinput.New()
		ti.Placeholder = fieldLabels[i]
		ti.SetValue(values[i])
		ti.Width = 50
		if i == fieldCompany {
			ti.Focus()
		}
		m.inputs[i] = ti
	}
	return m
}

func formatDate(t time.Time) string {
	if t.IsZero() {
		return ""
	}
	return t.UTC().Format("2006-01-02")
}

func formatFloat(f float64) string {
	if f == 0 {
		return ""
	}
	return strconv.FormatFloat(f, 'f', -1, 64)
}

func parseDate(s string) (time.Time, error) {
	s = strings.TrimSpace(s)
	if s == "" {
		return time.Time{}, nil
	}
	return time.Parse("2006-01-02", s)
}

// IsNew reports whether this form is for a new application.
func (m DetailModel) IsNew() bool { return m.isNew }

// GetApplication returns the Application built from the current form values.
func (m DetailModel) GetApplication() model.Application {
	app := m.app
	app.Company = m.inputs[fieldCompany].Value()
	app.Role = m.inputs[fieldRole].Value()
	app.OfferURL = m.inputs[fieldOfferURL].Value()
	app.DetectionDate, _ = parseDate(m.inputs[fieldDetectionDate].Value())
	app.ScoreGrade = m.inputs[fieldScoreGrade].Value()
	app.ScoreValue, _ = strconv.ParseFloat(m.inputs[fieldScoreValue].Value(), 64)
	app.Status = m.inputs[fieldStatus].Value()
	app.SendDate, _ = parseDate(m.inputs[fieldSendDate].Value())
	app.FollowUpDate, _ = parseDate(m.inputs[fieldFollowUpDate].Value())
	app.CVPath = m.inputs[fieldCVPath].Value()
	app.CoverLetterPath = m.inputs[fieldCoverLetterPath].Value()
	app.Notes = m.inputs[fieldNotes].Value()
	return app
}

// Validate checks required fields. Returns error message or "".
func (m DetailModel) Validate() string {
	if strings.TrimSpace(m.inputs[fieldCompany].Value()) == "" {
		return "Company is required"
	}
	if strings.TrimSpace(m.inputs[fieldRole].Value()) == "" {
		return "Role is required"
	}
	if strings.TrimSpace(m.inputs[fieldDetectionDate].Value()) == "" {
		return "Detection date is required"
	}
	if _, err := parseDate(m.inputs[fieldDetectionDate].Value()); err != nil {
		return fmt.Sprintf("Detection date: %v", err)
	}
	if strings.TrimSpace(m.inputs[fieldScoreGrade].Value()) == "" {
		return "Score grade is required"
	}
	if sv := strings.TrimSpace(m.inputs[fieldScoreValue].Value()); sv != "" {
		if _, err := strconv.ParseFloat(sv, 64); err != nil {
			return "Score value must be a number (e.g. 4.5)"
		}
	}
	statusVal := strings.TrimSpace(m.inputs[fieldStatus].Value())
	valid := false
	for _, s := range model.ValidStatuses {
		if s == statusVal {
			valid = true
			break
		}
	}
	if !valid {
		return fmt.Sprintf("Invalid status %q", statusVal)
	}
	return ""
}

// Init satisfies tea.Model.
func (m DetailModel) Init() tea.Cmd { return textinput.Blink }

// Update handles keypresses.
func (m DetailModel) Update(msg tea.Msg) (DetailModel, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch msg.String() {
		case "esc":
			return m, func() tea.Msg { return CancelMsg{} }
		case "ctrl+s":
			if errMsg := m.Validate(); errMsg != "" {
				m.errorMsg = errMsg
				return m, nil
			}
			return m, func() tea.Msg { return SaveMsg{App: m.GetApplication()} }
		case "tab":
			m.inputs[m.focusIdx].Blur()
			m.focusIdx = (m.focusIdx + 1) % fieldCount
			m.inputs[m.focusIdx].Focus()
			return m, textinput.Blink
		case "shift+tab":
			m.inputs[m.focusIdx].Blur()
			m.focusIdx = (m.focusIdx - 1 + fieldCount) % fieldCount
			m.inputs[m.focusIdx].Focus()
			return m, textinput.Blink
		}
	}
	var cmd tea.Cmd
	m.inputs[m.focusIdx], cmd = m.inputs[m.focusIdx].Update(msg)
	return m, cmd
}

// View renders the detail form.
func (m DetailModel) View() string {
	var sb strings.Builder
	title := "New Application"
	if !m.isNew {
		title = fmt.Sprintf("Edit — #%d %s", m.app.ID, m.app.Company)
	}
	sb.WriteString(detailTitleStyle.Render(title) + "\n")
	for i := 0; i < fieldCount; i++ {
		label := detailLabelStyle.Render(fieldLabels[i] + ":")
		sb.WriteString(fmt.Sprintf("%s  %s\n", label, m.inputs[i].View()))
	}
	if m.errorMsg != "" {
		sb.WriteString("\n" + detailErrorStyle.Render("Error: "+m.errorMsg) + "\n")
	}
	sb.WriteString("\n" + detailHintStyle.Render("Tab: next  Ctrl+S: save  Esc: cancel"))
	return sb.String()
}
