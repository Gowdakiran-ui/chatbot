Case 13
Company: Credit Suisse
Industry: Banking / Financial Services
Year: 2021 (Archegos + Greensill), building toward 2023 collapse
Crisis Type: Risk management failure / financial scandal (compounding)
Trigger Event: In March 2021, Credit Suisse was hit by the collapse of two clients within weeks of each other: supply-chain finance firm Greensill Capital filed for insolvency on March 8, forcing Credit Suisse to freeze $10 billion in linked funds, and family office Archegos Capital Management defaulted on margin calls on March 26, costing the bank $5.5 billion.
Response Type: Reactive (bordering on Delayed)
Response Speed Score: 2
Transparency Score: 2
Legal / Regulatory Framework Triggered: Swiss Financial Market Supervisory Authority (FINMA) enforcement action; UK/US regulatory scrutiny; independent board-commissioned investigation (Paul Weiss report) into Archegos
Resolution Status: Fatal — the bank never recovered reputational or investor trust and was taken over by UBS in an emergency, state-backed deal in March 2023
What Went Right: Credit Suisse commissioned an independent external investigation (Paul, Weiss) into the Archegos failure and published its findings, which is more disclosure than most banks offer after a trading loss. It also brought in an outside turnaround specialist, Antonio Horta-Osório, as chairman in mid-2021 specifically to fix risk culture.
What Went Wrong: The bank had ignored internal risk warnings about Archegos' concentrated, highly leveraged positions for months before the default — the independent report later concluded the losses stemmed from a fundamental failure of management and control in the investment bank's prime brokerage unit. Rather than stabilizing the bank, the response created a pattern investors began to expect: each scandal was followed by a slow, incomplete accounting, then another scandal. The chairman brought in to fix the culture resigned after nine months over his own Covid-rule breach. Credit Suisse's core problem wasn't any single crisis — it was that Archegos and Greensill landed on top of unresolved reputational damage from a 2019 corporate spying scandal, meaning there was no trust reserve left to draw on.
Best Practice / What Should Have Happened: Concentration-risk limits on prime brokerage clients needed hard, automatically enforced caps — not judgment calls overridden by revenue pressure. When warning signs were flagged internally (they were, repeatedly, per the Paul Weiss report), risk teams needed authority to force position reduction, not just to raise flags that got ignored. For ORM purposes: this is a case where no communications strategy could fix a trust deficit built from years of unresolved smaller scandals — the lesson is that crisis comms can't outrun a pattern of real operational failures.
Estimated Impact: ~$5.5B direct trading loss (Archegos) + ~$10B frozen Greensill-linked funds (most eventually returned to investors, some losses permanent); share price fell over 25% in 2021 alone; ultimately the bank ceased to exist as an independent entity, acquired by UBS for CHF 3 billion in March 2023 — a fraction of its prior valuation.
Onlyne Relevance: Crisis Comms / Reputational trust erosion pattern — highly relevant for showing clients how repeated incidents compound reputational damage even when each individual response is procedurally "correct"
Key Sources: finews.com, Morningstar, The Week, SWI swissinfo.ch, Forbes

Case 14
Company: British Airways
Industry: Aviation
Year: 2018
Crisis Type: Data breach / cybersecurity failure
Trigger Event: Attackers (linked to the Magecart group) compromised BA's website and app between June 22 and September 5, 2018, injecting malicious code that skimmed payment card and personal data from customers as they booked, without disrupting the normal checkout flow.
Response Type: Delayed (detection), Proactive (post-detection)
Response Speed Score: 3
Transparency Score: 4
Legal / Regulatory Framework Triggered: UK GDPR — Articles 5(1)(f) and 32 (security of processing); ICO investigation as lead EU supervisory authority
Resolution Status: Resolved (regulatory), but reputational and legal costs continued for years via class-action litigation
What Went Right: Once BA detected the breach, it moved fast: it disclosed publicly and notified the ICO and affected customers the same day it confirmed the intrusion (September 6, 2018), advised customers to contact their banks, and cooperated fully with the ICO investigation. The ICO explicitly cited BA's prompt notification and remediation steps as mitigating factors when cutting the fine from £183.39m to £20m.
What Went Wrong: The breach itself ran undetected for over two months — attackers were skimming card data from live transactions the entire time, meaning BA had no idea customers were actively being defrauded during that window. The root cause was BA logging payment data in plaintext since 2015 and lacking basic client-side security controls the ICO said were "readily available" at low cost. The failure wasn't a sophisticated, unstoppable attack — it was a known, fixable weakness left unaddressed for years.
Best Practice / What Should Have Happened: Real-time integrity monitoring on payment pages would have caught the injected skimming script within hours, not two months. Basic client-side security controls (script whitelisting, subresource integrity checks) were industry-known best practice well before 2018 — this wasn't a novel attack vector. The fast, transparent post-detection response is the template to copy; the pre-detection negligence is what clients need to be told isn't excusable just because the aftermath was well-handled.
Estimated Impact: £20m ICO fine (down from proposed £183.39m); ~429,612 individuals' data exposed, ~244,000 including full card details; group litigation settlement in 2021 covering both breach-related claims; significant but not fatal reputational damage — BA retained its market position.
Onlyne Relevance: ORM / Legal Takedown / Crisis Comms — strong template for "how to communicate well once you've already failed," useful to contrast against Marriott and Credit Suisse in this batch
Key Sources: Wikipedia (British Airways data breach), ICO/EDPB statements, CNBC, Lexology, Source Defense

Case 15
Company: Marriott International (Starwood Hotels)
Industry: Hospitality
Year: Breach originated 2014, discovered 2018, fined 2020
Crisis Type: Data breach / M&A due-diligence failure
Trigger Event: An unknown attacker (widely reported as state-linked) planted a web shell on a Starwood reservation system in 2014, maintaining undetected access for four years — including through Marriott's 2016 acquisition of Starwood — until an internal security tool flagged suspicious database activity on September 7, 2018.
Response Type: Reactive
Response Speed Score: 2
Transparency Score: 3
Legal / Regulatory Framework Triggered: UK GDPR — Articles 5(1)(f) and 32; ICO as lead EU supervisory authority, acting on behalf of all EU/EEA data protection authorities
Resolution Status: Resolved (regulatory), with reputational damage tied specifically to the due-diligence failure
What Went Right: Once the internal alert fired, Marriott investigated, blocked the intrusion, and notified the ICO within roughly two months (November 2018). It cooperated with the ICO investigation and made security improvements the regulator later credited as mitigating factors, helping cut the fine from £99.2m to £18.4m.
What Went Wrong: The central failure was pre-acquisition: Marriott bought Starwood in 2016 without discovering that Starwood's reservation database had already been compromised for two years. The ICO stated plainly that Marriott failed to do adequate cybersecurity due diligence on the deal — this wasn't a breach that happened to Marriott, it was a breach Marriott inherited and didn't check for. The exposure included highly sensitive data (unencrypted passport numbers for millions of guests), which is a worse category of harm than payment data alone.
Best Practice / What Should Have Happened: Cybersecurity due diligence needs to be a mandatory, specialist-led workstream in any acquisition involving customer databases — not a checkbox handled by generalist M&A counsel. Post-acquisition, Marriott should have run independent penetration testing and system audits on inherited infrastructure before integrating it, rather than assuming Starwood's existing security posture was sound. For ORM clients doing M&A: reputational liability transfers with the acquisition, whether or not you knew about the underlying problem.
Estimated Impact: £18.4m ICO fine (down from proposed £99.2m); ~339 million guest records exposed globally, ~30 million in the EEA, 7 million UK residents; ongoing class-action litigation and estimated total breach cost exceeding $350m including legal and remediation.
Onlyne Relevance: Legal Takedown / ORM — best case in this batch for M&A-related reputational risk, useful for advising clients on acquisition-related exposure they didn't directly create
Key Sources: Computer Weekly, ICO/EDPB statements, Herbert Smith Freehills, Cybersecurity Dive, GDPR Register

Case 16
Company: Facebook (Meta) / Cambridge Analytica
Industry: Technology / Social Media
Year: 2018 (scandal broke), underlying conduct 2007–2015
Crisis Type: Data misuse / political manipulation scandal
Trigger Event: In March 2018, The Guardian and The New York Times revealed that Cambridge Analytica had harvested the personal data of up to 87 million Facebook users (about 1 million in the UK) via a personality-quiz app, without proper consent, and used it for targeted political advertising including the 2016 US election and Brexit referendum.
Response Type: Delayed, bordering on Denial-Silence
Response Speed Score: 1
Transparency Score: 2
Legal / Regulatory Framework Triggered: UK Data Protection Act 1998 (pre-GDPR conduct window) — ICO maximum fine; broader GDPR political momentum; US FTC investigation; UK Parliamentary inquiry (DCMS Committee)
Resolution Status: Partially Resolved — regulatory penalties concluded, but the scandal permanently changed how the company was perceived and shaped GDPR's political relevance
What Went Right: Facebook eventually cooperated with the ICO investigation and publicly acknowledged it should have acted sooner. CEO Mark Zuckerberg testified before the US Congress in April 2018, and the company later reached a settlement with the ICO withdrawing mutual appeals in 2019, avoiding a prolonged legal fight.
What Went Wrong: Facebook had known about the Cambridge Analytica data misuse since 2015 — three years before it became public — and had only obtained a written certification that the data was deleted, without independently verifying it. When the story broke, the company's early response was defensive and slow rather than a direct acknowledgment; it took days of mounting media and political pressure before Zuckerberg made a public statement, and longer still before he agreed to testify. The ICO's fine was capped at £500,000 (the legal maximum under pre-GDPR rules) specifically because the conduct predated GDPR — the regulator itself noted the fine would have been far higher, potentially over $1 billion, if GDPR had applied to the underlying period.
Best Practice / What Should Have Happened: When Facebook learned in 2015 that a third party had improperly harvested user data, it should have independently audited that the data was actually deleted rather than accepting a written assurance — and should have disclosed the incident to users and regulators at that time rather than waiting for journalists to expose it three years later. A company that discovers a data misuse incident privately and chooses silence over disclosure is taking on exactly the kind of regulatory and reputational risk GDPR was designed to penalize. For ORM clients: the lesson is that "we found out and quietly fixed it" is not a substitute for disclosure, and delayed transparency reads as concealment even when there's no legal disclosure obligation at the time.
Estimated Impact: £500,000 ICO fine (maximum possible under applicable law — a token amount relative to Facebook's scale); separate $5 billion FTC settlement in the US in 2019; significant, lasting reputational damage and a #DeleteFacebook movement; direct catalyst for tougher GDPR enforcement culture across Europe.
Onlyne Relevance: ORM / GDPR / Crisis Comms — the strongest regulatory-angle case in this batch and a clear illustration of how delayed disclosure of a known problem is treated far worse than the underlying data incident itself
Key Sources: Privacy International, TechCrunch, TechRadar, UK House of Commons DCMS Committee report, NBC News