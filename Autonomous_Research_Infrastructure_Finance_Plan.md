# Finance Plan: Autonomous research infrastructure for AI governance

Date: 2026-04-13
Currency: USD

## Executive summary

The recommended operating plan is a 12-month core budget of approximately **$600,000** for running the autonomous research infrastructure for AI governance at a credible, fundable scale. This plan is aligned to the current AI-governance throughput target of **28 submission-ready papers per year**, with 11 paper families, a 7-role bounded pipeline, 5-layer independent review, family-local benchmarking, and selective public release.

The most important financial insight is that **token spend is not the main cost driver**. Under the current model, the largest costs are:

- personnel and oversight,
- data access and source maintenance,
- publication and submission reserves.

API spend is strategically important, but financially minor relative to the rest of the system.

## Planning inputs

This plan is based on:

- the existing workbook model in `/Users/ryanwong/ProjectAPE Replica/ProjectAPE_Finance_Plan_100_Papers.xlsx`,
- the AI-governance operating assumptions in [/Users/ryanwong/ProjectAPE Replica/backend/domain_configs/ai_governance.yaml](/Users/ryanwong/ProjectAPE%20Replica/backend/domain_configs/ai_governance.yaml),
- the workflow and review architecture in [/Users/ryanwong/ProjectAPE Replica/frontend/src/app/methodology/page.tsx](/Users/ryanwong/ProjectAPE%20Replica/frontend/src/app/methodology/page.tsx),
- current official pricing references for OpenAI, Anthropic, and Vercel.

## What should be financed

The infrastructure should be financed as three separate buckets:

1. **Core platform operations**
   Covers staff, data access, compute, QA, review coordination, and everyday model usage.
2. **Publication and submission reserve**
   Covers APCs, submission fees, formatting, editing, and resubmission costs.
3. **Strategic expansion reserve**
   Covers new data licenses, new paper families, sponsor reporting, partner integrations, and additional expert review capacity.

This separation matters. It prevents publication fees from crowding out infrastructure reliability and makes sponsor conversations cleaner.

## Core operating model

### Recommended annual target

- **28 submission-ready papers per year**
- aligned to the `submission_ready: 28` target in the AI-governance config
- enough throughput to demonstrate credibility without forcing the system into a paper-mill posture

### Recommended annual budget

| Budget bucket | Annual amount |
| --- | ---: |
| Core platform operations, incl. contingency | $539,722 |
| Publication reserve, incl. contingency | $55,907 |
| **Total recommended annual budget** | **$595,630** |

Rounded fundraising target: **$600,000 per year**

### Budget logic

The current workbook implies:

- fixed monthly operating cost of about **$39,087** before contingency,
- annual fixed cost of about **$469,040** before contingency,
- non-publication variable cost of about **$10.14 per paper**,
- publication and submission reserve of about **$1,736 per paper**.

For 28 submission-ready papers per year, that yields:

- **core operations before contingency:** about **$469,324**
- **publication reserve before contingency:** about **$48,615**
- **all-in annual spend before contingency:** about **$517,939**
- **all-in annual spend with 15% contingency:** about **$595,630**

Equivalent monthly planning number: about **$49,636 per month**.

## Cost structure

For the core 28-paper operating model, the cost mix is approximately:

- **79.16% personnel**
- **9.85% data access**
- **9.39% publication reserve**
- **1.55% compute and hosting**
- **0.05% AI pipeline, review, and judging tokens**

### Implication

Do **not** over-focus on shaving token costs. Even material token savings will barely move the total budget. The bigger levers are:

- staffing design,
- publication strategy,
- data-license discipline,
- sponsor-funded expansion rather than sponsor-funded conclusions.

## Scenario budgets

The workbook is best understood as a production-surge model. For operating the infrastructure over a year, the following three scenarios are more useful.

### 1. Pilot scenario

Purpose:
- prove workflow reliability,
- publish early exemplars,
- demonstrate benchmark quality,
- prepare for anchor fundraising.

Assumptions:
- 12 submission-ready papers per year,
- roughly half-scale staffing,
- reduced data-access footprint,
- selective publication subsidy rather than broad APC coverage.

Recommended budget:
- **$295,000 per year**

Use this if the goal is validation, not full institutional throughput.

### 2. Core scenario

Purpose:
- run the infrastructure credibly,
- hit the current AI-governance annual target,
- support fundraising from universities, foundations, and selected corporate sponsors.

Assumptions:
- 28 submission-ready papers per year,
- current staffing and data model from the workbook,
- dedicated publication reserve,
- 15% contingency.

Recommended budget:
- **$600,000 per year**

This is the recommended planning baseline.

### 3. Scale scenario

Purpose:
- expand reviewer capacity,
- support more active execution tracks,
- add more data licenses,
- move toward a consortium-style or multi-partner research platform.

Assumptions:
- 60 submission-ready papers per year,
- larger reviewer pool and operational team,
- expanded data and compute footprint,
- larger publication reserve.

Recommended budget:
- **$925,000 per year**

Use this only after the core scenario is functioning well.

## Recommended funding mix

For the **$600,000 core annual plan**, the recommended funding stack is:

| Source | Share | Amount |
| --- | ---: | ---: |
| Anchor philanthropy / research grant | 55% | $330,000 |
| Pooled tech-company sponsorship | 20% | $120,000 |
| Host institution support or in-kind contribution | 15% | $90,000 |
| Earned revenue: training, advisory, commissioned methods work | 10% | $60,000 |
| **Total** | **100%** | **$600,000** |

### Why this mix works

- It keeps the platform fundable even if corporate funding is delayed.
- It prevents any one sponsor from dominating the research agenda.
- It creates a path toward partial self-financing through training or methodology services.

## Guardrails for tech-company financing

Because this project studies AI governance, sponsor independence is part of the product.

Recommended safeguards:

- No single corporate sponsor should cover more than **20%** of the annual budget.
- Corporate funds should support **infrastructure lines**, not paper conclusions.
- Sponsors should have **no pre-publication approval rights**.
- All sponsor relationships should be **publicly disclosed**.
- Publication decisions should remain under the control of the research leadership, not sponsors.
- A sponsor should not be allowed to ring-fence funding to suppress work about its own products or governance practices.

These guardrails are not just ethical. They protect the platform’s long-run credibility and therefore its future fundability.

## Cost-control strategy

### 1. Ring-fence publication fees

Do not bury APCs inside the main operating budget. Treat them as a reserve that is released selectively.

### 2. Keep a pooled publication policy

Default to:

- preprints by default,
- selective open-access payments,
- strategic APC support only for high-value accepted papers,
- co-author or grant cost-sharing where appropriate.

### 3. Avoid over-building infrastructure too early

The current compute assumptions are modest. Keep them modest until throughput or storage pressure proves otherwise.

### 4. Protect the reviewer layer

If the budget must be cut, cut scale before cutting methodological oversight and human escalation.

### 5. Treat data access as a portfolio

Review all paid sources quarterly and retire low-yield licenses.

## KPIs to attach to the budget

The finance plan should be tied to visible outputs, not only spend.

Recommended annual KPIs:

- 5,000 ideas generated
- 300 locked plans
- 60 active execution projects
- 75 draft papers
- 28 submission-ready papers
- 70% of outputs beating median family benchmark
- 25% beating upper-quartile benchmark
- reviewer disagreement within the thresholds already set in the AI-governance config

These KPIs let funders see that the budget is tied to a measurable production and quality system.

## Recommended ask

If pitching externally, the cleanest message is:

> We are seeking **$600,000 for 12 months** to operate an autonomous research infrastructure for AI governance. This budget funds the core platform, expert oversight, data access, benchmarking, and a publication reserve sufficient to deliver approximately 28 submission-ready papers over one year.

If you want more runway, a practical alternative is:

> **$900,000 for 18 months**, giving the project enough time to build outputs, prove benchmark performance, and diversify its funding base.

## Sources and references

Local project inputs:

- `/Users/ryanwong/ProjectAPE Replica/ProjectAPE_Finance_Plan_100_Papers.xlsx`
- [/Users/ryanwong/ProjectAPE Replica/backend/domain_configs/ai_governance.yaml](/Users/ryanwong/ProjectAPE%20Replica/backend/domain_configs/ai_governance.yaml)
- [/Users/ryanwong/ProjectAPE Replica/frontend/src/app/methodology/page.tsx](/Users/ryanwong/ProjectAPE%20Replica/frontend/src/app/methodology/page.tsx)

Official pricing references used to sanity-check the token and hosting assumptions:

- OpenAI GPT-4o pricing: https://platform.openai.com/docs/models/gpt-4o
- OpenAI API pricing overview: https://openai.com/api/pricing/
- Anthropic model pricing: https://docs.anthropic.com/en/docs/about-claude/pricing
- Vercel pricing: https://vercel.com/pricing

## Notes

- This plan intentionally keeps the currency in USD because the existing workbook is USD-denominated.
- If the host institution requires formal indirect costs or overhead recovery, add that on top or negotiate it inside the anchor grant.
- If the publication strategy changes materially, the publication reserve should be recalculated first; it is one of the few lines that can change the total budget meaningfully.
