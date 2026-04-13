# Autonomous Research Infrastructure Financial Model (`GBP 1,000`, `Claude Max` + Premium APIs)

## Objective

Model a **one-month** operating plan for the Autonomous Research Infrastructure under a hard budget of **GBP 1,000**, assuming:

- a **Claude Max** subscription for one month
- API token spend for autonomous production
- **highest-quality academic outputs**
- the **best and most advanced models** available from the relevant providers

## Recommended model stack

For this brief, the strongest defensible stack is:

- **Claude Max 5x** for human supervision, editorial triage, and difficult edge-case prompting in `claude.ai`
- **Claude Opus 4.6 API** for all Claude-side production work
- **GPT-5.4 Pro API** for all OpenAI-side review, judging, and independent challenge work

Inference from official sources on **13 April 2026**:

- Anthropic’s current flagship Claude API line is **Opus 4.6**
- OpenAI’s highest-end API model is **GPT-5.4 Pro**, described as the model for maximum performance

## Important constraint

The Claude Max subscription does **not** replace API spending.

- Anthropic states that paid Claude plans and API billing are separate
- extra usage on Max eventually shifts into consumption-based billing
- therefore the subscription should be treated as a **human workbench**, not as the production engine

## FX basis

FX is inferred from ECB reference rates for **10 April 2026**:

- `EUR/USD = 1.1711`
- `EUR/GBP = 0.87105`
- inferred `GBP/USD = 0.7437878917`
- inferred `USD/GBP = 1.3444693186`

So **GBP 1,000** is modeled as approximately **USD 1,344.47**.

## Token envelope per finished paper

This model keeps the same workflow depth as the current Autonomous Research Infrastructure and only upgrades the model quality.

Per submission-ready paper:

| Bucket | Input tokens | Output tokens | Total tokens |
| --- | ---: | ---: | ---: |
| Claude Opus 4.6-priced work | 303,500 | 137,600 | 441,100 |
| GPT-5.4 Pro-priced work | 111,400 | 17,600 | 129,000 |
| **Total** | **414,900** | **155,200** | **570,100** |

## Premium API pricing assumptions

### Claude Opus 4.6 API

- input: `USD 5.00 / 1M tokens`
- output: `USD 25.00 / 1M tokens`
- Message Batches discount: `50%`

### GPT-5.4 Pro API

- input: `USD 30.00 / 1M tokens`
- output: `USD 180.00 / 1M tokens`
- Batch/Flex pricing: `50%` of standard rate

## Subscription tiers modeled

### Option A. Claude Max 5x

- one-month subscription cost: **USD 100**
- converted monthly cost: **GBP 74.38**
- API budget left: **GBP 925.62**

### Option B. Claude Max 20x

- one-month subscription cost: **USD 200**
- converted monthly cost: **GBP 148.76**
- API budget left: **GBP 851.24**

## Output capacity under `Claude Max 5x`

### Standard premium API pricing

Assumes:

- Claude Opus 4.6 at standard API pricing
- GPT-5.4 Pro at standard API pricing

Results:

- API cost per paper: **GBP 8.5294**
- API cost per paper with `15%` contingency: **GBP 9.8088**
- papers at budget ceiling: **108**
- papers with `15%` contingency: **94**

Conservative token throughput at `94` papers:

- Claude tokens: **41,463,400**
- GPT-5.4 Pro tokens: **12,126,000**
- **Total tokens: 53,589,400**

### Anthropic batch only

Assumes:

- Claude Opus 4.6 batched
- GPT-5.4 Pro still standard priced

Results:

- API cost per paper: **GBP 6.6857**
- API cost per paper with `15%` contingency: **GBP 7.6886**
- papers at budget ceiling: **138**
- papers with `15%` contingency: **120**

Conservative token throughput at `120` papers:

- Claude tokens: **52,932,000**
- GPT-5.4 Pro tokens: **15,480,000**
- **Total tokens: 68,412,000**

### Full batch optimization

Assumes:

- Claude Opus 4.6 batched
- GPT-5.4 Pro batch-priced

Results:

- API cost per paper: **GBP 4.2647**
- API cost per paper with `15%` contingency: **GBP 4.9044**
- papers at budget ceiling: **217**
- papers with `15%` contingency: **188**

Conservative token throughput at `188` papers:

- Claude tokens: **82,926,800**
- GPT-5.4 Pro tokens: **24,252,000**
- **Total tokens: 107,178,800**

## Output capacity under `Claude Max 20x`

### Standard premium API pricing

- API cost per paper: **GBP 8.5294**
- API cost per paper with `15%` contingency: **GBP 9.8088**
- papers at budget ceiling: **99**
- papers with `15%` contingency: **86**

Conservative token throughput at `86` papers:

- Claude tokens: **37,934,600**
- GPT-5.4 Pro tokens: **11,094,000**
- **Total tokens: 49,028,600**

### Anthropic batch only

- papers at budget ceiling: **127**
- papers with `15%` contingency: **110**

Conservative token throughput at `110` papers:

- Claude tokens: **48,521,000**
- GPT-5.4 Pro tokens: **14,190,000**
- **Total tokens: 62,711,000**

### Full batch optimization

- papers at budget ceiling: **199**
- papers with `15%` contingency: **173**

Conservative token throughput at `173` papers:

- Claude tokens: **76,310,300**
- GPT-5.4 Pro tokens: **22,317,000**
- **Total tokens: 98,627,300**

## Recommendation

If the budget must include a one-month Claude Max subscription, the best setup is:

- **Claude Max 5x**, not `Max 20x`
- **Claude Opus 4.6 API** for autonomous production
- **GPT-5.4 Pro API** for the highest-end independent review/judging work

That is the best quality-preserving configuration because:

- `Max 5x` gives access to the premium Claude app experience without consuming too much of the budget
- `Max 20x` reduces output count but does not improve the API model quality
- the real quality driver is the API model stack, not the more expensive Max tier

### Practical planning number

For a premium, quality-first monthly run, I would plan around the conservative **standard premium API** case under `Claude Max 5x`:

- **94 submission-ready papers**
- **53.6 million total tokens**

If asynchronous batching is operationally feasible and acceptable for latency:

- **120 papers** is the stronger contingency-adjusted target with Anthropic batching only
- **188 papers** is the upper contingency-adjusted target with full batch optimization

## Sources

- OpenAI GPT-5.4 Pro model docs: <https://developers.openai.com/api/docs/models/gpt-5.4-pro>
- OpenAI GPT-5.4 release: <https://openai.com/index/introducing-gpt-5.4/>
- Anthropic API pricing: <https://docs.anthropic.com/en/docs/about-claude/pricing>
- Anthropic pricing page: <https://www.anthropic.com/pricing>
- Claude Max pricing: <https://support.anthropic.com/en/articles/11049744-how-much-does-the-max-plan-cost>
- Claude subscription/API billing separation: <https://support.claude.com/en/articles/9876003-i-subscribe-to-a-paid-claude-ai-plan-why-do-i-have-to-pay-separately-for-api-usage-on-console>
- ECB FX reference rates: <https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html>
