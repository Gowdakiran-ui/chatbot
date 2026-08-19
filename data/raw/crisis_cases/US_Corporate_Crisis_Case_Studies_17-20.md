# US Corporate Crisis Case Studies — Cases 17–20

---

## Case 17

**Company:** SolarWinds Corporation
**Industry:** IT / Network Management Software
**Year:** 2020 (breach discovered December; intrusion active since ~September 2019)
**Crisis Type:** Nation-state supply-chain cyberattack

**Trigger Event:** Russian intelligence-linked hackers inserted malicious code ("SUNBURST") into SolarWinds' Orion software updates starting around March 2020, reaching roughly 18,000 customers, including US federal agencies. Cybersecurity firm FireEye discovered the breach on December 12–13, 2020 while investigating the theft of its own Red Team tools, and traced it back to SolarWinds.

**Response Type:** Reactive (disclosure was triggered by an outside party, not self-detection)

**Response Speed Score:** 4/5 — SolarWinds filed an 8-K and publicly disclosed within roughly 48–72 hours of FireEye's notification (Dec 11–14); CISA issued an Emergency Directive on Dec 13. The disclosed facts held up, but the company had been sitting on an undetected breach for 9+ months.

**Transparency Score:** 2/5 — Post-breach SEC filings were later found adequate by a federal judge, but a pre-breach "Security Statement" published on SolarWinds' website was found by a court to plausibly constitute securities fraud — it overstated the company's cybersecurity posture while known weaknesses (including a leaked weak password, "solarwinds123") existed.

**Legal / Regulatory Framework Triggered:** SEC enforcement action (Securities Act §17(a), Exchange Act §10(b), §13(a), §13(b)(2)(B)) against the company and its CISO Timothy Brown; CISA Emergency Directive 21-01; congressional hearings.

**Resolution Status:** Partially Resolved — The SEC's case dragged on for years. A July 2024 ruling by Judge Paul Engelmayer (SDNY) dismissed most claims but let the Security Statement fraud claim proceed. The SEC ultimately dismissed all remaining claims with prejudice on November 20, 2025, closing the matter without a fine or admission of wrongdoing.

**What Went Right:**
- Rapid emergency patch released (hotfix within days, full fix by Jan 11, 2021)
- Immediate cooperation with CISA, FBI, and Microsoft on the joint investigation
- Filed an 8-K disclosure within days rather than staying silent
- Brought in outside incident-response firms and later a new CISO reporting structure

**What Went Wrong:**
- A known weak/leaked credential ("solarwinds123") had reportedly been exposed on a public GitHub repo before the attack
- Public-facing "Security Statement" oversold the company's security practices — this became the central basis for the SEC's surviving fraud claim
- The intrusion went undetected for roughly nine months despite the scale of access attackers gained
- Insider stock sales by executives and private-equity holders (Thoma Bravo, Silver Lake) shortly before disclosure drew public suspicion, even though investigators later found no evidence of foreknowledge

**Best Practice / What Should Have Happened:** Any public-facing statement about security posture should go through the same legal scrutiny as a financial disclosure — marketing language describing "robust" cybersecurity becomes a securities-fraud liability the moment it's inaccurate. Companies should also enforce basic credential hygiene (no default/weak passwords, MFA on all internal systems) as baseline, not aspiration, and time stock transactions by insiders with extra caution during known incident-response windows even if not legally required.

**Estimated Impact:** Stock fell roughly 25% in the days following disclosure; years of SEC litigation costs and reputational drag; SolarWinds became the reference case for "supply-chain attack" in cybersecurity discourse — a lasting search-association effect.

**Onlyne Relevance:** Legal Takedown / Crisis Comms / ORM (long-tail search association between brand name and "hack")

**Key Sources:**
- CSO Online, "The SolarWinds hack timeline: Who knew what, and when?"
- U.S. GAO WatchBlog, "SolarWinds Cyberattack Demands Significant Federal and Private-Sector Response"
- Greenberg Traurig LLP, "SEC v. SolarWinds Update" (2024)
- Harvard Law School Forum on Corporate Governance / Freshfields, "SolarWinds Dismissed" (2025)
- ChannelE2E, "SolarWinds Orion Security Breach: Cyberattack Timeline"

---

## Case 18

**Company:** Colonial Pipeline Company
**Industry:** Critical Infrastructure / Energy (fuel pipeline operator)
**Year:** 2021
**Crisis Type:** Ransomware attack on critical infrastructure

**Trigger Event:** On May 7, 2021, the DarkSide ransomware group encrypted Colonial's IT billing systems after using a compromised VPN password tied to an inactive account that lacked multi-factor authentication. Colonial proactively shut down the entire pipeline as a precaution against the malware spreading to operational technology.

**Response Type:** Proactive on operational shutdown; Delayed/inconsistent on ransom-payment messaging

**Response Speed Score:** 4/5 — Colonial confirmed the attack publicly the same day and shut down the pipeline within hours to contain it. However, initial public reporting suggested the company had "no intention" of paying a ransom, when in fact it authorized a $4.4M payment on May 8, less than 24 hours after the attack — undercutting the accuracy of the early messaging.

**Transparency Score:** 3/5 — The company acknowledged the incident quickly, but the ransom-payment contradiction created a credibility gap that persisted until CEO Joseph Blount testified before the Senate on June 8, 2021, and directly confirmed the payment and rationale.

**Legal / Regulatory Framework Triggered:** TSA Security Directives (Pipeline-2021-01 and -02, the first mandatory federal cybersecurity rules for pipeline operators); DOT/PHMSA proposed roughly $1 million in fines tied to safety-related aspects of the shutdown; CISA/FBI joint cybersecurity advisories; Senate Homeland Security Committee hearings.

**Resolution Status:** Resolved — Full pipeline service resumed May 12, 2021 (5 days after shutdown). The DOJ recovered roughly $2.3 million of the $4.4 million ransom in June 2021 by tracing the Bitcoin wallet.

**What Went Right:**
- Fast, proactive shutdown to prevent malware from reaching operational technology systems
- Same-day public acknowledgment of the attack
- Full cooperation with the FBI, which enabled the partial ransom recovery — a first of its kind at the time
- CEO testified openly and directly before Congress rather than sending a spokesperson or issuing written statements only

**What Went Wrong:**
- A legacy VPN account without multi-factor authentication was the entry point — a well-known, preventable gap
- Public messaging about the ransom payment was inconsistent with what the company had actually decided to do, creating a "caught in a contradiction" narrative
- Recovery of billing/business systems lagged behind the operational restart, prolonging the perception of disorganization
- DOT later found safety-process violations connected to how the shutdown decision was executed

**Best Practice / What Should Have Happened:** Enforce MFA across all remote-access accounts, including dormant or legacy ones — this was the single point of failure. On messaging, a company should pick one accurate public position on a ransom decision and hold it; saying "we won't pay" while quietly paying is worse for trust than saying "we are evaluating options and will disclose our decision." Crisis communications should separate operational-status updates (which can and should move fast) from strategic decisions like ransom payment (which need a single accountable spokesperson and consistent message).

**Estimated Impact:** $4.4 million ransom paid ($2.3 million recovered); an industry estimate placed the cost of the week-long disruption at roughly $8 million in lost net income and $25 million in lost revenue; East Coast fuel shortages and panic buying; a presidential emergency declaration; ~$1 million in proposed DOT fines; became the case that triggered mandatory federal pipeline cybersecurity regulation.

**Onlyne Relevance:** Crisis Comms / ORM (national media narrative control during an active infrastructure crisis)

**Key Sources:**
- MSSP Alert, "Colonial Pipeline Cyberattack: Timeline and Ransomware Attack Recovery Details"
- Chainalysis, "How FBI Investigators Traced DarkSide's Funds"
- Idaho National Laboratory (INL/CyOTE), "Case Study: DarkSide Ransomware Attack on Colonial Pipeline"
- U.S. Department of Energy, "Colonial Pipeline Cyber Incident"
- EBSCO Research Starters, "Colonial Pipeline"

---

## Case 19

**Company:** Enron Corporation
**Industry:** Energy / Commodities Trading
**Year:** 2001
**Crisis Type:** Accounting fraud / corporate governance collapse

**Trigger Event:** On October 16, 2001, Enron reported a $618 million third-quarter loss and a $1.2 billion reduction in shareholder equity tied to off-balance-sheet special purpose entities (SPEs) used to hide debt. This followed a February 2001 Fortune article questioning the company's opacity and CEO Jeff Skilling's abrupt resignation on August 14, 2001.

**Response Type:** Denial-Silence, escalating to Delayed

**Response Speed Score:** 1/5 — No proper response existed; every reassurance the company gave was later proven false. On the August 14 investor call, Chairman Ken Lay told analysts "I never felt better about the company" while declining to provide more disclosure. The SEC opened a formal investigation October 22; Arthur Andersen instructed staff to destroy Enron-related documents on October 12 — obstruction, not response.

**Transparency Score:** 1/5 — Active concealment through complex SPE structures, destroyed audit documents, and public statements contradicted by internal knowledge of the company's true financial position.

**Legal / Regulatory Framework Triggered:** SEC formal investigation (October 2001); DOJ criminal investigation (January 2002); the Powers Report, an independent board-commissioned investigation (February 2002); Arthur Andersen convicted of obstruction of justice (later overturned by the Supreme Court in 2005, by which point the firm no longer existed); directly led to the Sarbanes-Oxley Act of 2002.

**Resolution Status:** Fatal — Enron filed for Chapter 11 bankruptcy on December 2, 2001, the largest corporate bankruptcy in US history at the time ($63.4 billion in assets). Arthur Andersen was dissolved. More than 20 executives were eventually convicted. Ken Lay was convicted in 2006 but died before sentencing; Jeffrey Skilling was convicted and served over a decade in prison.

**What Went Right:**
- The board eventually commissioned an independent investigation (the Powers Report) that publicly laid out the SPE structure once collapse was unavoidable
- Internal whistleblower Sherron Watkins raised concerns in an August 2001 memo to Lay, creating a documented internal warning that later became public

**What Went Wrong:**
- Executives actively built and concealed a web of off-balance-sheet partnerships (LJM, Chewco, and others) to hide debt and inflate results
- Lay gave investors and employees false reassurance while some insiders sold stock
- Auditor Arthur Andersen had a structural conflict of interest, earning substantial consulting fees alongside audit fees from the same client, and its staff destroyed documents rather than escalating concerns
- No proactive disclosure occurred until credit downgrades and a failed merger with Dynegy made collapse unavoidable

**Best Practice / What Should Have Happened:** Auditor independence has to be structural, not aspirational — a firm should not both audit and consult for the same client at this scale. Off-balance-sheet obligations and related-party transactions need to be disclosed as they're created, not discovered by outsiders. When an internal whistleblower raises a specific, documented concern, it needs an independent investigation immediately, not a private conversation with the person it implicates. And a false "everything is fine" statement to investors does more lasting damage to trust than an early, accurate admission of trouble — Lay's August reassurance became the single most-cited example of the crisis, more than the SPEs themselves.

**Estimated Impact:** $63.4 billion in assets lost in bankruptcy; roughly 4,000 employees lost their jobs immediately; approximately 15,000 employees' retirement savings, tied to Enron stock, were wiped out; stock fell from a peak of $90 (August 2000) to $0.26 (November 2001); Arthur Andersen's collapse cost roughly 85,000 jobs worldwide; directly caused the Sarbanes-Oxley Act, reshaping US corporate governance and audit law.

**Onlyne Relevance:** Crisis Comms / ORM — the reference case for what a company name becomes permanently synonymous with; useful for illustrating long-tail search association risk decades after the event.

**Key Sources:**
- TIME, "Chronology of a Collapse — Behind the Enron Scandal"
- Levin Center for Oversight and Democracy, "Congress and the Enron Scandal"
- Britannica, "Enron scandal"
- EBSCO Research Starters, "Enron collapse"

---

## Case 20

**Company:** WorldCom, Inc.
**Industry:** Telecommunications
**Year:** 2002
**Crisis Type:** Accounting fraud (the largest in US history at the time)

**Trigger Event:** In June 2002, WorldCom VP of Internal Audit Cynthia Cooper and her team, working covertly and often at night due to executive resistance, discovered that $3.8 billion in ordinary "line cost" operating expenses had been improperly reclassified as capital expenditures between 1999 and 2002, inflating reported profitability.

**Response Type:** Proactive once discovered internally, following years of executive-level Denial-Silence

**Response Speed Score:** 4/5 — Cooper reported findings to the board's audit committee on June 20, 2002. The board fired CFO Scott Sullivan on June 25 and publicly disclosed the $3.8 billion restatement to the SEC the same day — five days from internal discovery to public action. The initial figures held up, though the total fraud scope kept growing in subsequent months.

**Transparency Score:** 4/5 — Full public disclosure of the known fraud amount, same-day notification to the SEC, and cooperation with an independent KPMG review. Not a 5 because the disclosed scope kept expanding after the initial announcement, eventually reaching roughly $11 billion — meaning the first disclosure understated the true scale.

**Legal / Regulatory Framework Triggered:** SEC civil suit (filed June 26, 2002, one day after disclosure); DOJ criminal prosecution; Sarbanes-Oxley Act of 2002 (WorldCom's collapse directly accelerated its passage weeks later); federal bankruptcy court oversight.

**Resolution Status:** Resolved via bankruptcy reorganization — WorldCom filed Chapter 11 on July 21, 2002 ($107 billion in assets, $41 billion in debt, surpassing Enron as the largest US bankruptcy to date). It emerged from bankruptcy in 2004, renamed itself MCI, and was acquired by Verizon in 2006. CEO Bernard Ebbers was sentenced to 25 years in prison; CFO Scott Sullivan received 5 years after cooperating with prosecutors.

**What Went Right:**
- Internal audit, led by Cynthia Cooper, kept investigating despite direct pressure and intimidation from the CFO
- The board acted decisively once shown evidence: fired the CFO and controller within days, disclosed to the SEC the same day, and commissioned an independent KPMG review
- Brought in an outside CEO, Michael Capellas (former HP president), within months to rebuild credibility

**What Went Wrong:**
- Years of executive-level fraud (1999–2002) went undetected by external auditor Arthur Andersen — the same firm that failed to catch Enron
- CFO Sullivan reportedly confronted and intimidated internal audit staff for asking questions
- CEO Ebbers had received a $408 million personal line of credit from the company — a related-party conflict that should have been stopped by the board earlier
- The disclosed fraud total grew in stages after the initial announcement ($3.8B → $9B → ultimately ~$11B), which compounded reputational damage each time it was revised upward

**Best Practice / What Should Have Happened:** Internal audit functions need structural protection from executive retaliation — Cooper's team succeeded despite the system, not because of it. When a restatement is announced, disclose the full known scope in one release rather than in installments; each upward revision after WorldCom's initial disclosure re-opened the credibility wound. Executive personal loans and related-party transactions of this size should require independent compensation-committee approval, not board rubber-stamping. And using the same audit firm that is simultaneously failing at a peer company (Andersen/Enron) is itself a governance red flag worth acting on before a crisis, not after.

**Estimated Impact:** Roughly $11 billion in total accounting fraud identified; $107 billion in assets at bankruptcy filing (largest in US history at the time); stock collapsed from a high of $64 per share to worthless; thousands of jobs lost; directly precipitated the Sarbanes-Oxley Act of 2002, alongside Enron.

**Onlyne Relevance:** Crisis Comms / ORM — companion case to Enron; useful comparative baseline for how a fast, decisive response *after* internal discovery can still coexist with a fraud so large it destroys the company anyway.

**Key Sources:**
- Auburn University Harbert College of Business, "WorldCom's Bankruptcy Crisis" (case PDF)
- University of New Mexico, "WorldCom's Bankruptcy Crisis" (ethics case PDF)
- Wikipedia, "WorldCom scandal" and "Cynthia Cooper (accountant)"
- International Banker, "The WorldCom Scandal (2002)"
- EveryCRSReport.com, "WorldCom: The Accounting Scandal" (CRS Report, 2002)

---
