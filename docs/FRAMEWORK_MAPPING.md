# Governance framework mapping

Each component implements a control that several frameworks ask for. As of November 2026.

| Component (file) | NIST AI RMF | EU AI Act | ISO/IEC 42001 | Singapore MGF for Agentic AI | OWASP Agentic Top 10 (2026) |
| --- | --- | --- | --- | --- | --- |
| Agent registry with named owner (`policy_packs/*.yaml`) | GOVERN: roles, inventory · MAP: purpose | Art. 26 deployer duties | Cl. 5 roles · Cl. 6 planning | 1. Assess and bound risks upfront | ASI03 Identity and Privilege Abuse |
| Hard rules, least privilege (`policy.py`) | MANAGE: risk treatment | Art. 15 cybersecurity | Cl. 8 operation | 3. Technical controls | ASI02 Tool Misuse and Exploitation |
| Session binding + no-bypass gateway (`auth.py`, `gateway.py`) | MANAGE | Art. 15 cybersecurity | Cl. 8 operation | 3. Technical controls | ASI01 Agent Goal Hijack · ASI03 |
| Anomaly detection (`detector.py`) | MEASURE: monitoring | Art. 15 robustness | Cl. 9 performance evaluation | 3. Technical controls (monitoring) | ASI08 Cascading Failures · ASI10 Rogue Agents |
| Risk score + ESCALATE to named reviewer (`risk.py`, `gateway.review`) | MANAGE: response · GOVERN: accountability | Art. 14 human oversight | Cl. 8 operation | 2. Make humans meaningfully accountable | ASI09 Human-Agent Trust Exploitation |
| Circuit breaker (`gateway.py`) | MANAGE: deactivation | Art. 14(4)(e) ability to stop | Cl. 8 operation | 2. Human override and interception | ASI10 Rogue Agents |
| Hash-chained audit log (`audit.py`) | GOVERN: transparency | Art. 12 record-keeping · Art. 26 log retention | Cl. 9 evaluation | 2. Accountability | ASI10 (investigation) |
| Explanations (`explainer.py`) | MEASURE: explainability | Art. 13 transparency | Cl. 7 communication | 4. Enable end-user responsibility | ASI09 |
| Tests, held-out attacks, metrics (`tests/`, `scripts/evaluate.py`) | MEASURE: testing, evaluation | Art. 9 risk management (testing) | Cl. 9, Cl. 10 improvement | 1. Pre-deployment testing | ASI01-ASI03 |
| Versioned policy changes via pull requests (GitHub) | GOVERN: documented processes | Art. 17 quality management | Cl. 7.5 documented information | 1. Ongoing risk assessment | n/a |

## Context notes

- **EU AI Act:** the Digital Omnibus moved Annex III high-risk obligations to 2 December 2027. A bank
  customer-service agent is not an Annex III use case (credit scoring is), so the project uses
  Articles 12-15 as a design benchmark rather than a legal requirement.
- **U.S. banking:** SR 26-2 / OCC Bulletin 2026-13 (April 2026) replaced SR 11-7 and places generative and
  agentic AI outside its formal scope, while telling banks to govern them through their own risk practices.
- **NIST:** the CAISI AI Agent Standards Initiative (February 2026) is working on agent identity and
  authorization, which is what session binding addresses.

## Sources

- NIST AI Risk Management Framework: https://www.nist.gov/itl/ai-risk-management-framework
- NIST AI Agent Standards Initiative: https://www.nist.gov/caisi/ai-agent-standards-initiative
- OWASP Top 10 for Agentic Applications 2026: https://genai.owasp.org/top-10-for-agentic-applications-2026/
- Singapore MGF for Agentic AI: https://www.mddi.gov.sg/newsroom/singapore-launches-new-model-ai-governance-framework-for-agentic-ai--/
- SR 26-2: https://www.federalreserve.gov/supervisionreg/srletters/sr2602.htm
- EU AI Act Digital Omnibus (Orrick, July 2026): https://www.orrick.com/ja-JP/Insights/2026/07/EU-AI-Act-Update-Digital-Omnibus-Finalizes-8-Compliance-Changes
