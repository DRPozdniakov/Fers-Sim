---
name: audit
description: Run a venture due-diligence consistency audit across all investor documents using Smart Core. USE WHEN user says 'audit', 'run audit', 'check consistency', 'due diligence check', 'validate documents', 'investor audit'.
---

# Venture Due-Diligence Audit

Run a systematic cross-document consistency audit covering everything a VC analyst would check during due diligence. Uses Smart Core knowledge graph for entity tracking and direct file reads for value extraction.

---

## When to Use

- User says "audit", "run audit", or "/audit"
- User says "check consistency" or "validate documents"
- User says "due diligence check"
- Before sending investor package to anyone
- After making significant changes to multiple documents

---

## Output

**Type:** HTML report + console summary
**Location:** `.claude/skills/audit/Audit-Report.html`
**Format:** Single-page HTML following project design system (see `.claude/rules/html-design.md`)

---

## Process

### Step 0: Prerequisites

1. Call `mcp__smart-core__ping` — if Neo4j is down, abort with message
2. Run `mcp__smart-core__knowledge_call` with a broad query to warm the graph
3. If graph has <10 documents, run `load_project` first

---

### Step 1: Financial Consistency (CRITICAL)

**What investors check:** Do the numbers add up? Are they the same everywhere?

#### 1.1 Funding Amounts
Query Smart Core for entities: `Round-Seed`, `Round-A`, `Round-B`
Cross-check these values appear identically in ALL documents:

| Value | Must Match Across |
|-------|------------------|
| Seed amount (€1M) | Financial Model, Business Plan, Exec Summary, Full Roadmap, Pitch Deck Tracker, BRD, Phase Plans |
| Round A amount (€7-10M) | Financial Model, Business Plan, Exec Summary, Full Roadmap, Round A Plan |
| Round B amount (€50-100M) | Financial Model, Business Plan, Full Roadmap |
| Pre-money valuations | Financial Model, Business Plan, Exec Summary |
| Post-money valuations | Financial Model, Exec Summary |
| Equity % per round | Financial Model, Business Plan, Exec Summary |

#### 1.2 Budget Totals
- Seed Phase Plan category totals must sum to €1M
- Seed Budget Detail workstream totals + buffer must sum to €1M
- Monthly burn table must sum to match category totals
- Pre-Seed budget range must match across docs

#### 1.3 Revenue Projections
- Revenue numbers in Financial Model must match Pitch Deck Tracker
- Revenue in Business Plan must match Financial Model
- Revenue in Exec Summary must match Financial Model
- Growth rates must be internally consistent

#### 1.4 Unit Economics
- Robot price (€55K) consistent everywhere
- BOM/COGS (€27.5K) consistent everywhere
- Subscription price (€120K/enterprise/year) consistent
- Gross margins match calculated values
- Payback periods consistent across customer persona docs

**Severity:** Any mismatch = 🔴 CRITICAL

---

### Step 2: Timeline Consistency (CRITICAL)

**What investors check:** Is the roadmap believable? Do dates line up?

#### 2.1 Phase Dates
Query Smart Core for: `Phase-PreSeed`, `Phase-Seed`, `Phase-RoundA`, `Phase-RoundB`

| Phase | Start | End | Duration | Must Match In |
|-------|-------|-----|----------|---------------|
| Pre-Seed | Feb 2026 | Jun 2026 | 5 months | All docs mentioning Pre-Seed |
| Seed | Jul 2026 | Apr 2027 | 10 months | All docs mentioning Seed |
| Round A | May 2027 | Sep 2028 | 18 months | All docs mentioning Round A |
| Round B | 2029 | 2030 | — | All docs mentioning Round B |

Check: phases are continuous (no gaps, no overlaps).

#### 2.2 Milestone Dates
Query Smart Core for all `MS-*` entities. Verify:
- Milestone dates fall within their phase
- Milestone order is logical (you can't demo before building)
- Key milestones match across Phase Plans, Full Roadmap, Business Plan

#### 2.3 Duration Math
- Pre-Seed: start→end = stated duration
- Seed: start→end = stated duration
- Round A: start→end = stated duration
- Monthly burn × months = total budget (Seed)

**Severity:** Date mismatch = 🔴 CRITICAL, duration math error = 🟡 HIGH

---

### Step 3: Team & Equity Consistency (HIGH)

**What investors check:** Who's on the team? Does equity add up?

#### 3.1 Team Roles
Query Smart Core for: `Team-CTO`, `Team-CEO`, `Team-CDO`

Check:
- Same roles listed in all team sections
- No ghost roles (e.g., CFO mentioned but doesn't exist)
- Role descriptions consistent
- Onboarding timelines match (CEO = Pre-Seed, not Round A)

#### 3.2 Equity
- CTO equity % matches across all docs
- Total equity allocation doesn't exceed 100%
- Investor equity matches funding round terms

#### 3.3 Team Size Claims
- Seed team size matches salary budget headcount
- Round A team scaling targets match budget
- Current team description matches reality

**Severity:** Equity math error = 🔴 CRITICAL, role inconsistency = 🟡 HIGH

---

### Step 4: Product Specifications (HIGH)

**What investors check:** Is the product well-defined? Are specs consistent?

Query Smart Core for: `Prod-FersHumanoid`, `Met-BOM`

Check across PRD, Business Plan, Exec Summary, Pitch Deck Tracker:

| Spec | Expected | Check In |
|------|----------|----------|
| DOF | 19 axes | PRD, Business Plan |
| Payload | 2 kg per arm | PRD, Business Plan |
| Robot price | €55,000 | All investor docs |
| BOM/COGS | €27,500 | Financial Model, PRD, Business Plan |
| Form factor | Upper-body humanoid | PRD, Business Plan, Exec Summary |
| Food grade | IP67 | PRD, Business Plan |
| Compute | NVIDIA Jetson Orin | PRD |
| Tools | 5 internal | PRD, Business Plan |

**Severity:** Price/BOM mismatch = 🔴 CRITICAL, spec inconsistency = 🟡 HIGH

---

### Step 5: Market Data (MEDIUM)

**What investors check:** Are market claims sourced and consistent?

Query Smart Core for: `Met-TAM`

Check across TAM-SAM-SOM, Business Plan, Exec Summary, Pitch Deck Tracker:

| Metric | Check |
|--------|-------|
| TAM value | Same number everywhere |
| SAM value | Same number everywhere |
| SOM value | Same number everywhere |
| CAGR | Same rate everywhere |
| Market size year | Same reference year |
| Source citations | Present where claims are made |

**Severity:** Number mismatch = 🟡 HIGH, missing source = 🟢 MEDIUM

---

### Step 6: Customer Economics (MEDIUM)

**What investors check:** Does the ROI story hold up?

Check across Business Plan, Financial Model, Exec Summary, Customer Personas:

| Metric | Check |
|--------|-------|
| Customer payback period | Consistent across segments |
| Annual savings per robot | Matches calculation inputs |
| Subscription vs hardware revenue split | Consistent |
| LTV:CAC ratio | Matches component values |
| Customer segment definitions | Same across all docs |

**Severity:** ROI math error = 🔴 CRITICAL, description mismatch = 🟢 MEDIUM

---

### Step 7: Metadata Quality (LOW)

**What investors don't see but affects maintainability:**

For each document in docs_ver2/:
- [ ] Has YAML front matter
- [ ] Has doc_id
- [ ] Has version (X.Y format)
- [ ] Has last_updated (not stale >60 days)
- [ ] Has status field
- [ ] Has owner field
- [ ] Has depends_on / feeds_into
- [ ] No references to non-existent doc_ids

**Severity:** Missing metadata = 🟢 LOW

---

### Step 8: Confidential Information Check (CRITICAL)

**What must NEVER appear in investor-facing docs.**

**Use Smart Core tool:** `mcp__smart-core__check_banned_terms()`

This single call replaces manual grep. Banned terms are configured in `config.json`:
```json
"audit": {
  "banned_terms": ["Foodly", "Sciurus17", "RT-Net"],
  "banned_terms_exclude_paths": ["docs_ver2/changelog.md", "docs_ver2/smart_core_research/"]
}
```

The tool scans all .md files, excludes configured paths, and returns violations with file, line, and context.

Also grep for `***` markers (unsanitized content) since those aren't in the banned terms config.

**Severity:** Confidential leak = 🔴 CRITICAL

---

### Step 8.5: Entity-Value Integrity & Coverage

**Use Smart Core tools:**

1. **Check mismatch alerts:** Query `MATCH (m:MismatchAlert) RETURN m` — these are entity values that don't appear in the linked document text. Created automatically during `store_extraction`.

2. **Run coverage audit:** `mcp__smart-core__audit_coverage()` — reports what % of key values (funding, dates, percentages) are tracked as entities vs untracked text.

**Include in report:**
- Mismatch alert count and details
- Overall entity coverage percentage
- Per-category coverage (funding, dates, percentages, durations)
- Untracked value examples (entities to add)

**Severity:** Mismatch = 🟡 HIGH, Low coverage = 🟢 MEDIUM

---

### Step 8.6: Semantic & Logical Analysis

**Go beyond value matching — analyze the CONTENT for logical errors, contradictions, and poorly thought-through claims.**

This step requires reading actual document text (not just entity values) and applying reasoning.

#### 8.6.1 Internal Logic Checks

Read key sections and verify:

| Check | What to look for | Example violation |
|-------|------------------|-------------------|
| **Math consistency** | Do percentages sum to 100%? Do line items sum to stated totals? | Budget categories sum to 95% (missing 5%) |
| **Timeline logic** | Can milestones physically happen in stated order and duration? | "Hire team M1, ship product M2" — impossible |
| **Dependency chains** | Does each phase's output enable the next phase's input? | Round A assumes "10 pilot units" but Seed doesn't produce any |
| **Claim-evidence match** | Does the stated evidence actually support the claim? | "Proven technology" but no working demo exists yet |
| **Scaling logic** | Do unit economics work at stated scale? Do margins improve as claimed? | "80% margin at 10 units" but COGS don't change with volume |
| **Market-product fit** | Does the described product actually solve the described problem? | Customer pain is "labor shortage" but product requires 2 operators |
| **Competitive logic** | Do stated advantages hold against named competitors? | "First mover" but competitor launched 2 years ago |

#### 8.6.2 Cross-Section Contradictions

Read pairs of sections that should align:

| Section A | Section B | Check |
|-----------|-----------|-------|
| Problem statement | Solution description | Does the solution address ALL stated problems? |
| Customer personas | Pricing model | Can the target customer afford the stated price? |
| Team section | Phase plan milestones | Does the team have skills needed for stated deliverables? |
| Risk section | Mitigation actions | Is every critical risk actually mitigated somewhere? |
| Revenue projections | Customer pipeline | Are enough customers in pipeline to hit revenue targets? |
| Competitive advantages | Competitor descriptions | Do advantages hold when compared to specific competitors? |

#### 8.6.3 "Investor Smell Test"

Flag statements that a skeptical investor would immediately challenge:

- **Unsupported superlatives:** "best", "only", "first" without evidence
- **Round numbers with false precision:** "exactly 60% automatable" without methodology
- **Contradictory positioning:** "asset-light" but €220K hardware budget
- **Missing competition:** "no competitors" when competitors exist
- **Unrealistic timelines:** "CE certification in 3 months" (typically 12-18 months)
- **Hockey stick without explanation:** Revenue jumps 10x without explaining what changes
- **Circular logic:** "We'll get customers because we have a great product; our product is great because customers want it"

**Severity:** Logic error in investor-facing claim = 🟡 HIGH, Internal inconsistency = 🟢 MEDIUM

---

### Step 9: Investor Readiness Assessment (Weaknesses & Improvements)

**This is the most valuable section for the founder.** Go beyond consistency checks — assess the investor package like a VC analyst doing pre-meeting prep. Read the actual content and flag weaknesses.

#### 9.1 Document Completeness

Check each expected investor document exists and has substantive content:

| Document | Required For | Check |
|----------|-------------|-------|
| Pitch Deck (or Tracker) | Seed | Exists, all slides covered |
| Executive Summary | Seed | Exists, <3 pages, compelling |
| Business Plan | Seed | Exists, complete sections |
| Financial Model | Seed | Exists, 5-year projections |
| PRD | Seed | Exists, specs defined |
| Competitive Analysis | Seed | Exists, real competitors |
| TAM/SAM/SOM | Seed | Exists, bottom-up SOM |
| Customer Personas | Seed | Exists, validated segments |
| Phase Plans (Seed, A) | Seed | Exists, monthly detail |
| Demo Video reference | Seed | Referenced, planned/exists |
| LOI or customer evidence | Seed | At least pipeline documented |
| IP/Patent strategy | Seed | Referenced somewhere |

**Flag:** Missing docs = 🟡 HIGH, incomplete sections = 🟢 MEDIUM

#### 9.2 Claim Strength Assessment

For each major investor-facing claim, assess evidence quality:

| Claim Type | Strong Evidence | Weak Evidence | No Evidence |
|-----------|----------------|---------------|-------------|
| Market size | Published source + calculation shown | Number stated, source named | Number stated, no source |
| Revenue projections | Bottom-up from unit economics | Top-down % of market | Arbitrary growth rates |
| Competitive advantage | Named competitors + differentiation table | "No competitors" claim | No competitive section |
| Customer demand | LOIs, pilot agreements, customer quotes | "Conversations started" | "We believe there is demand" |
| Team capability | Relevant experience listed | Names and titles only | "Team TBD" |
| Technology feasibility | Working demo, reference implementations | "Based on open-source" | Theoretical only |
| ROI claims | Full calculation with inputs visible | Summary number only | Unsourced claim |
| Exit comparables | Named companies with actual exit values | Generic "X-Y multiples" | No exit data |

**For each claim, classify as:**
- **STRONG** — backed by data, sources, or demonstration
- **NEEDS STRENGTHENING** — directionally right but missing evidence
- **WEAK** — unsupported or vague, investor will challenge this
- **MISSING** — expected claim not made at all

**Flag:** Weak investor-facing claim = 🟡 HIGH, Missing expected claim = 🟢 MEDIUM

#### 9.3 Common VC Objections Check

Read the docs and flag if these common VC objections are pre-answered:

| VC Objection | Where It Should Be Addressed | Check |
|-------------|------------------------------|-------|
| "Why now? What's changed?" | Exec Summary, Business Plan | Timing thesis present? |
| "Why this team?" | Exec Summary, Business Plan | Relevant experience shown? |
| "What's the moat?" | Competitive Analysis, Business Plan | Defensibility beyond first-mover? |
| "How do you get first 10 customers?" | Business Plan GTM, Investor QA | Specific GTM plan with named targets? |
| "What if a big player enters?" | Competitive Analysis, Risk section | Competitive threat mitigation? |
| "Why not RaaS?" | Business Plan, Investor QA | Purchase model rationale? |
| "What's the unit economics?" | Financial Model, Exec Summary | CAC, LTV, payback all shown? |
| "How do you scale manufacturing?" | Business Plan, Phase Plans | China partner strategy clear? |
| "What's the regulatory path?" | PRD, Business Plan, Phase Plans | CE/HACCP timeline shown? |
| "What if the tech doesn't work?" | Risk section, Phase Plans | Technical risk mitigation? |

**Flag:** Unanswered objection = 🟡 HIGH if common, 🟢 MEDIUM if niche

#### 9.4 Presentation Quality

Quick assessment of investor-facing document quality:

| Check | What to look for |
|-------|-----------------|
| **Executive Summary length** | Should be 2-3 pages max. Longer = investor won't read it |
| **Financial Model clarity** | Are assumptions listed? Is math traceable? |
| **Pitch Deck alignment** | Do all numbers match supporting docs? |
| **Jargon level** | Too technical for non-robotics investors? |
| **Call to action** | Clear ask (€1M, 20% equity) stated prominently? |
| **Contact info** | How does the investor reach you? |
| **Data room readiness** | Would all docs work in a DocSend/data room? |

**Flag:** Missing call to action = 🟡 HIGH, Presentation issue = 🟢 MEDIUM

#### 9.5 Output Format — Improvements Table

**Generate a "Weaknesses & Recommended Improvements" table in the HTML report:**

```
┌───────────────────────────────────────────────────────┐
│  INVESTOR READINESS                                    │
│                                                        │
│  Document Completeness:  11/12 documents present       │
│  Claim Strength:         7 strong, 3 needs work, 1 weak│
│  VC Objections Covered:  8/10 pre-answered              │
│  Presentation Quality:   Good (minor issues)            │
│                                                        │
│  TOP IMPROVEMENTS (priority order):                     │
│  1. 🔴 Add customer evidence (LOIs or pilot letters)   │
│  2. 🟡 Source all market size claims in Exec Summary   │
│  3. 🟡 Pre-answer "why this team" with relevant exp   │
│  4. 🟢 Shorten Executive Summary to 2 pages           │
│  5. 🟢 Add contact info to Pitch Deck Tracker         │
└───────────────────────────────────────────────────────┘
```

**Each improvement should include:**
- Priority (Critical / High / Medium / Low)
- What's weak or missing
- Where to fix it (specific document + section)
- Suggested action (1 sentence)

---

### Step 10: Generate Report

Generate `.claude/skills/audit/Audit-Report.html` following project HTML design system.

#### Report Structure

```
┌─────────────────────────────────────┐
│  AUDIT SCORE        85/100          │  ← Big number
│  Date: 2026-03-19                   │
│  Documents: 37 | Entities: 80       │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  SUMMARY                            │
│  🔴 Critical: 2  │  🟡 High: 5     │
│  🟢 Medium: 3    │  ⚪ Low: 8      │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  1. FINANCIAL CONSISTENCY    ██████ │  ← Per-category score bar
│     🔴 Seed budget sum ≠ €1M       │
│     ✓ Robot price consistent        │
│     ✓ Valuations match              │
└─────────────────────────────────────┘

... repeat for each category ...

┌─────────────────────────────────────┐
│  DETAILED FINDINGS                  │
│  Table: Finding | Severity | Docs   │
│         | Current Values | Action   │
└─────────────────────────────────────┘
```

#### Scoring

| Category | Weight | Max Points |
|----------|--------|-----------|
| Financial Consistency | 25% | 25 |
| Timeline Consistency | 15% | 15 |
| Team & Equity | 10% | 10 |
| Product Specifications | 5% | 5 |
| Market Data | 5% | 5 |
| Customer Economics | 5% | 5 |
| Metadata Quality | 5% | 5 |
| Confidential Check | 5% | 5 |
| **Investor Readiness** | **25%** | **25** |
| **Total** | **100%** | **100** |

**Investor Readiness sub-scoring (25 points):**
- Document completeness: 7 pts (all expected docs present and substantive)
- Claim strength: 8 pts (claims backed by evidence, sources cited)
- VC objection coverage: 5 pts (common objections pre-answered)
- Presentation quality: 5 pts (length, clarity, call to action)

Deductions:
- 🔴 CRITICAL finding: -5 points each
- 🟡 HIGH finding: -3 points each
- 🟢 MEDIUM finding: -1 point each
- ⚪ LOW finding: -0.5 points each

Minimum score: 0 (floor)

---

### Step 10: Console Summary

Print a concise summary to console:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AUDIT COMPLETE | Score: 85/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 CRITICAL (2):
  • Budget sum mismatch: Seed Budget Detail = €671K+€329K, Phase Plan categories = €870K+€130K
  • Confidential: "Sciurus17" found in Business-Plan-Fers.md line 245

🟡 HIGH (5):
  • Timeline: Round A start "Q3 2027" in Financial Model vs "May 2027" in Round A Plan
  • Team: "7-8 people" in Exec Summary vs "7 people" in Phase Plan
  ...

🟢 MEDIUM (3): [listed]
⚪ LOW (8): [listed]

Report: .claude/skills/audit/Audit-Report.html
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### Step 11: Audit Metrics Report

**Generate a metrics card in the HTML report** that enables comparison across audits and quantifies Smart Core's contribution.

#### Audit Run Metrics (always include)

| Metric | Description |
|--------|-------------|
| **Score** | X/100 |
| **Date** | YYYY-MM-DD |
| **Documents scanned** | Total .md files in docs_ver2/ |
| **Entities tracked** | Total Entity nodes in graph |
| **Entity-document links** | Total HAS_ENTITY relationships |
| **Cross-doc entity coverage** | % of entities appearing in 2+ docs |
| **Tags linked** | Total Tag nodes |
| **YAML front matter coverage** | % of docs with valid front matter |
| **Graph relationships** | Total DEPENDS_ON + RESULTS_FROM edges |
| **Findings: Critical/High/Med/Low** | Count per severity |
| **Category scores** | Per-category breakdown |

#### Smart Core vs Grep Comparison

**Track these metrics to show Smart Core's value over plain grep:**

| Metric | With Smart Core | Without Smart Core (grep only) |
|--------|----------------|-------------------------------|
| **Entity cross-ref checks** | Instant via `knowledge_call` | Manual grep per entity name + manual value comparison |
| **Documents checked per entity** | Graph returns all docs automatically | Must know which files to grep (easy to miss) |
| **Stale entity detection** | Graph stores entity values, compares | Must read each file and manually compare |
| **Relationship awareness** | DEPENDS_ON/RESULTS_FROM edges | Must read YAML and trace manually |
| **New doc detection** | `synchronize_project` diffs graph vs disk | `git status` only |
| **False negatives (missed inconsistencies)** | Low — graph tracks all entity-doc links | High — grep misses entities with different wording |
| **Time per full audit** | ~2-3 min (queries + grep + report) | ~15-20 min (manual file reads + comparison) |

**In the HTML report, include a "Smart Core Coverage" card:**

```
┌─────────────────────────────────────┐
│  SMART CORE COVERAGE                │
│  Entities:     83  │  Tags:    45   │
│  Entity-Doc Links: 156              │
│  Cross-Doc Coverage: 78%            │
│  Graph Relationships: 78            │
│  ──────────────────────────────     │
│  Checks run via graph:  12          │
│  Checks run via grep:    4          │
│  Checks run via file read: 3       │
│  ──────────────────────────────     │
│  Est. time saved vs grep: ~12 min  │
└─────────────────────────────────────┘
```

#### Historical Comparison

**If a previous audit report exists at `.claude/skills/audit/Audit-Report.html`:**
- Parse the previous score from the HTML
- Show delta: "Score: 73/100 (+8 from last audit)"
- Show findings delta: "Critical: 5 (-2 from last audit)"
- Track trend across audits

---

### Step 12: Update Changelog

Add audit results to `docs_ver2/changelog.md`:

```markdown
## YYYY-MM-DD

### Audit Run
- **Score:** XX/100
- **Critical findings:** X
- **High findings:** X
- **Report:** [Audit-Report.html](Audit-Report.html)
```

---

## How Each Check Works

### Smart Core Queries (for entity cross-referencing)

```python
# Example: check Round-Seed consistency
knowledge_call("Round-Seed", search_type="graph")
# Returns: entity value + list of all documents containing it
# If different documents store different values → flag as inconsistency
```

### Direct File Reads (for value extraction)

For checks that need exact numbers (budget sums, equity math), read the specific files directly and parse the values. Don't rely solely on entity values — they may be summaries.

### Grep Searches (for confidential info)

```python
# Search for banned terms
grep("Foodly", path="docs_ver2/")
grep("Sciurus17", path="docs_ver2/")
grep("RT-Net", path="docs_ver2/")
grep("\\*\\*\\*", path="docs_ver2/")  # unsanitized markers
```

---

## Key Principles

1. **Numbers must match exactly** — not "approximately" or "close enough"
2. **Dates must be in the same format** — "Jul 2026" and "Q3 2026" referring to the same thing is OK, but "Q4 2026" and "Jul 2026" is a mismatch
3. **Team roles must be current** — no references to eliminated roles
4. **Every claim needs a source** — market data especially
5. **Confidential info must be sanitized** — zero tolerance
6. **The Pitch Deck is the single source of truth** — if docs disagree, the Pitch Deck wins

---

## Design System

Follow `.claude/rules/html-design.md` exactly:
- Background: `#f0f0f0`
- Cards: white, `2px solid #333`, `border-radius: 8px`
- Big numbers: `64px bold #333`
- No gradients, no shadows, no decorative icons
- Score bars use `#4a4a4a` (dark), `#888` (medium), `#ccc` (light)
- Critical: `#f8d7da` bg, `#721c24` text
- Warning: `#fff3cd` bg, `#856404` text
- Success: `#d4edda` bg, `#155724` text
