# Autonomous Research Infrastructure Financial Model (`GBP 1,000`, `Claude Max 20x`)

## Objective

Model a **one-month** operating plan for the Autonomous Research Infrastructure under a hard budget of **GBP 1,000**, assuming:

- **Claude Max 20x** for one month
- API token spend for autonomous production
- the **highest-quality academic outputs**
- the **most advanced models** available for the production workflow

## Model stack

This remodel uses:

- **Claude Max 20x** as the paid Claude subscription
- **Claude Opus 4.6 API** for Claude-side autonomous production
- **GPT-5.4 Pro API** for top-tier independent review, judging, and challenge work

The subscription is treated as a **human workbench**, while the APIs remain the production engine.

## Important constraint

Claude Max 20x does **not** replace API billing.

- Anthropic bills Claude subscriptions separately from API usage
- so the Max plan improves the app-side working environment, but it does not remove the need to buy API tokens for autonomous runs

## FX basis

FX is inferred from ECB reference rates for **10 April 2026**:

- `EUR/USD = 1.1711`
- `EUR/GBP = 0.87105`
- inferred `GBP/USD = 0.7437878917`
- inferred `USD/GBP = 1.3444693186`

So **GBP 1,000** is modeled as approximately **USD 1,344.47**.

## Token envelope per finished paper

This model keeps the same workflow depth as the current infrastructure and upgrades only the model quality.

Per submission-ready paper:

| Bucket | Input tokens | Output tokens | Total tokens |
| --- | ---: | ---: | ---: |
| Claude Opus 4.6-priced work | 303,500 | 137,600 | 441,100 |
| GPT-5.4 Pro-priced work | 111,400 | 17,600 | 129,000 |
| **Total** | **414,900** | **155,200** | **570,100** |

## Premium pricing assumptions

### Claude Opus 4.6 API

- input: `USD 5.00 / 1M tokens`
- output: `USD 25.00 / 1M tokens`
- Message Batches discount: `50%`

### GPT-5.4 Pro API

- input: `USD 30.00 / 1M tokens`
- output: `USD 180.00 / 1M tokens`
- Batch pricing: `50%`

### Claude Max 20x subscription

- monthly price: **USD 200**
- converted monthly cost: **GBP 148.76**
- API budget remaining: **GBP 851.24**

## Output capacity under `Claude Max 20x`

### 1. Standard premium API pricing

Assumes:

- Claude Opus 4.6 at standard API pricing
- GPT-5.4 Pro at standard API pricing

Results:

- API cost per paper: **GBP 8.5294**
- API cost per paper with `15%` contingency: **GBP 9.8088**
- papers at budget ceiling: **99**
- papers with `15%` contingency: **86**

Conservative token throughput at `86` papers:

- Claude tokens: **37,934,600**
- GPT-5.4 Pro tokens: **11,094,000**
- **Total tokens: 49,028,600**

### 2. Anthropic batch only

Assumes:

- Claude Opus 4.6 batched
- GPT-5.4 Pro still standard priced

Results:

- API cost per paper: **GBP 6.6857**
- API cost per paper with `15%` contingency: **GBP 7.6886**
- papers at budget ceiling: **127**
- papers with `15%` contingency: **110**

Conservative token throughput at `110` papers:

- Claude tokens: **48,521,000**
- GPT-5.4 Pro tokens: **14,190,000**
- **Total tokens: 62,711,000**

### 3. Full batch optimization

Assumes:

- Claude Opus 4.6 batched
- GPT-5.4 Pro batch-priced

Results:

- API cost per paper: **GBP 4.2647**
- API cost per paper with `15%` contingency: **GBP 4.9044**
- papers at budget ceiling: **199**
- papers with `15%` contingency: **173**

Conservative token throughput at `173` papers:

- Claude tokens: **76,310,300**
- GPT-5.4 Pro tokens: **22,317,000**
- **Total tokens: 98,627,300**

## Recommendation

If the one-month plan must use **Claude Max 20x**, the cleanest quality-first planning number is the conservative standard case:

- **86 submission-ready papers**
- **49.0 million total tokens**

If batching is operationally feasible:

- **110 papers** is the stronger contingency-adjusted target with Anthropic batching only
- **173 papers** is the upper contingency-adjusted target with full batch optimization

The model quality does not improve by moving from Max 5x to Max 20x; what changes is that more of the `GBP 1,000` budget is spent on the subscription and less remains for production APIs. But if `Max 20x` is the required operating setup, the figures above are the right budget envelope.

## Sources

- OpenAI GPT-5.4 Pro model docs: <https://developers.openai.com/api/docs/models/gpt-5.4-pro>
- OpenAI GPT-5.4 release: <https://openai.com/index/introducing-gpt-5.4/>
- Anthropic API pricing: <https://docs.anthropic.com/en/docs/about-claude/pricing>
- Anthropic pricing page: <https://www.anthropic.com/pricing>
- Claude Max pricing: <https://support.anthropic.com/en/articles/11049744-how-much-does-the-max-plan-cost>
- Claude subscription/API billing separation: <https://support.claude.com/en/articles/9876003-i-subscribe-to-a-paid-claude-ai-plan-why-do-i-have-to-pay-separately-for-api-usage-on-console>
- ECB FX reference rates: <https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html>
