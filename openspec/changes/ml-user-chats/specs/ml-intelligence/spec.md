# ml-intelligence Specification (MODIFIED by ml-user-chats)

## MODIFIED Requirements

### Requirement: Tier 5 Agent Behavior Intelligence (ADDED)

The system SHALL extract Tier 5 (Agent Behavior) features from session execution data.

The system SHALL integrate Tier 5 features with existing Tier 1-4 features in the 97-dimension feature matrix.

The system SHALL train ML models (Risk Scorer, Root Cause Classifier, Next Edit Predictor) on combined features.

The system SHALL correlate workflow compliance with task outcomes to enable statistical workflow enforcement.

The system SHALL provide correlation analysis showing impact of workflow compliance on code quality.

The system SHALL generate predictions using all 5 tiers: Pipeline, Journal, Artifacts, Git, Agent Behavior.

#### Scenario: Train Risk Scorer with Tier 5 features
- **GIVEN** a training dataset with 1000 files
- **AND** 500 files have session execution data (Tier 5)
- **AND** 500 files have no session data (Tier 5 = zeros)
- **WHEN** Risk Scorer model is trained
- **THEN** feature matrix has 97 dimensions for all files
- **AND** model learns patterns from all 5 tiers
- **AND** model achieves 5-10% higher accuracy than Tier 1-4 only

#### Scenario: Predict risk with Tier 5 features
- **GIVEN** a file api.py with workflow_compliant=False, avg_risk_score=0.8
- **AND** api.py has high cyclomatic complexity (Tier 3)
- **AND** api.py has high git churn (Tier 4)
- **WHEN** Risk Scorer predicts risk for api.py
- **THEN** predicted risk is 0.85-0.95 (very high)
- **AND** Tier 5 features contribute significantly to prediction
- **AND** explanation shows workflow violations as risk factor

#### Scenario: Predict risk without Tier 5 data
- **GIVEN** a new file new_feature.py with no session history
- **AND** new_feature.py has low complexity (Tier 3) and low churn (Tier 4)
- **WHEN** Risk Scorer predicts risk for new_feature.py
- **THEN** predicted risk is 0.1-0.2 (low)
- **AND** Tier 5 features are zero (no penalty for missing data)
- **AND** prediction is based on Tier 1-4 only

#### Scenario: Correlation analysis (workflow compliance vs outcomes)
- **GIVEN** session_executions table with 200 sessions
- **AND** 120 sessions with workflow_compliant=True
- **AND** 80 sessions with workflow_compliant=False
- **WHEN** correlation analysis is run
- **THEN** report shows:
  - Compliant sessions: avg_risk=0.15, correction_rate=11%, rollback_rate=8%
  - Non-compliant sessions: avg_risk=0.67, correction_rate=73%, rollback_rate=51%
  - Risk reduction: 78% when workflow compliant (p < 0.001)

#### Scenario: Statistical workflow enforcement
- **GIVEN** historical pattern: "skip blueprint + edit api.py = 95% failure rate"
- **AND** current session is about to edit api.py without running blueprint
- **WHEN** agent queries historical patterns
- **THEN** agent learns: "skipping blueprint on api.py has 95% failure rate"
- **AND** agent decides to run blueprint first (statistical enforcement)

---

### Requirement: Multi-Tier Feature Integration (MODIFIED)

The system SHALL extract features from 5 tiers: Pipeline (Tier 1), Journal (Tier 2), Artifacts (Tier 3), Git (Tier 4), Agent Behavior (Tier 5).

The system SHALL combine all tier features into a single 97-dimension feature matrix.

The system SHALL handle missing tier data gracefully (zeros for missing tiers).

The system SHALL normalize all features to 0.0-1.0 range for ML training.

The system SHALL accept --session-dir flag for Tier 5 feature extraction.

#### Scenario: Extract all 5 tiers (complete data)
- **GIVEN** a project with complete data for all 5 tiers
- **WHEN** features are extracted for file api.py
- **THEN** 97 features are returned
- **AND** Tier 1 features show pipeline success/failure
- **AND** Tier 2 features show journal events
- **AND** Tier 3 features show CFG complexity, security patterns
- **AND** Tier 4 features show git churn, recency
- **AND** Tier 5 features show workflow compliance, risk scores

#### Scenario: Extract with missing Tier 5 (backward compatibility)
- **GIVEN** a project with no session data
- **AND** --session-dir is not provided
- **WHEN** features are extracted for file api.py
- **THEN** 97 features are returned
- **AND** Tier 1-4 features are populated normally
- **AND** Tier 5 features are all 0.0 (no penalty)
- **AND** ML training continues without errors

#### Scenario: Feature dimension consistency
- **GIVEN** model trained on 97 dimensions without Tier 5
- **WHEN** new data with Tier 5 is added
- **THEN** feature matrix remains 97 dimensions
- **AND** model can retrain on new data
- **AND** predictions use Tier 5 when available, ignore when missing

---

### Requirement: ML Model Training with Session Data (MODIFIED)

The system SHALL train Risk Scorer with Tier 5 features when --session-dir is provided.

The system SHALL train Root Cause Classifier with Tier 5 features to identify workflow-related root causes.

The system SHALL train Next Edit Predictor with Tier 5 features to predict likely file modifications.

The system SHALL measure accuracy improvement with Tier 5 vs without Tier 5.

The system SHALL report feature importance showing contribution of each tier.

#### Scenario: Measure accuracy improvement with Tier 5
- **GIVEN** a test dataset with 200 files (100 with Tier 5 data)
- **WHEN** Risk Scorer is trained twice:
  - Once with Tier 1-4 only (baseline)
  - Once with Tier 1-5 (complete)
- **THEN** accuracy with Tier 5 is 5-10% higher than baseline
- **AND** precision/recall improve for high-risk files
- **AND** false positive rate decreases

#### Scenario: Feature importance analysis
- **GIVEN** Risk Scorer trained on all 5 tiers
- **WHEN** feature importance is calculated
- **THEN** report shows contribution of each tier:
  - Tier 1 (Pipeline): 10-15%
  - Tier 2 (Journal): 5-10%
  - Tier 3 (Artifacts): 30-40%
  - Tier 4 (Git): 20-30%
  - Tier 5 (Agent Behavior): 15-25%

#### Scenario: Root Cause Classifier with workflow violations
- **GIVEN** a file api.py with multiple bugs
- **AND** api.py was modified without running blueprint (workflow violation)
- **WHEN** Root Cause Classifier predicts root cause
- **THEN** predicted root cause includes "Workflow Violation: Blueprint Not Run"
- **AND** confidence is high (>0.8) based on Tier 5 correlation data

#### Scenario: Next Edit Predictor with session patterns
- **GIVEN** historical pattern: "edit auth.py → 85% also edit auth_service.py"
- **AND** current session just edited auth.py
- **WHEN** Next Edit Predictor predicts next file
- **THEN** auth_service.py is top prediction (confidence >0.8)
- **AND** prediction is based on Tier 5 session correlation data

---

### Requirement: CLI Integration for Session Analysis (MODIFIED)

The system SHALL accept --session-dir flag in `aud learn` command.

The system SHALL accept --analyze-sessions flag to run session analysis before training.

The system SHALL accept --show-correlations flag to display workflow correlation statistics.

The system SHALL display Tier 5 statistics when --session-analysis flag is used.

The system SHALL log "Tier 5 (Agent Behavior) features loaded" when session data is available.

#### Scenario: Train with session directory
- **GIVEN** a project with session logs in ~/.claude/projects/MyProject
- **WHEN** `aud learn --session-dir ~/.claude/projects/MyProject` is run
- **THEN** session logs are parsed
- **AND** Tier 5 features are extracted
- **AND** models are trained with all 5 tiers
- **AND** log shows "Tier 5 (Agent Behavior) features loaded from 194 sessions"

#### Scenario: Analyze sessions before training
- **GIVEN** a project with session logs not yet analyzed
- **WHEN** `aud learn --session-dir <dir> --analyze-sessions` is run
- **THEN** SessionAnalysis runs on all sessions
- **AND** session_executions table is populated
- **AND** Tier 5 features are extracted
- **AND** models are trained

#### Scenario: Display correlation statistics
- **GIVEN** session_executions table with 200 analyzed sessions
- **WHEN** `aud learn --show-correlations` is run
- **THEN** CLI displays:
  - Sessions analyzed: 200
  - Workflow compliance rate: 60% (120/200)
  - Compliant avg risk: 0.15, correction rate: 11%
  - Non-compliant avg risk: 0.67, correction rate: 73%
  - Risk reduction: 78% when compliant (p < 0.001)

#### Scenario: Display session analysis statistics
- **GIVEN** session logs with 194 sessions
- **WHEN** `aud learn --session-dir <dir> --session-analysis` is run
- **THEN** CLI displays:
  - Sessions analyzed: 194
  - Total tool calls: 602
  - Total edits: 39
  - Blind edits detected: 11
  - Workflow violations: 87 (44.8%)
