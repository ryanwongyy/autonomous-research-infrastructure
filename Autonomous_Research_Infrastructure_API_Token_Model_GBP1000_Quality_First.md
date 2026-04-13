# Autonomous Research Infrastructure API Token Model (`GBP 1,000`, Quality-First)

## Scope

This remodel assumes the infrastructure prioritises **quality over quantity**.

To isolate the effect of using stronger models, it keeps the **same workflow depth** and **same token envelope per paper** as the current autonomous pipeline, but upgrades the model mix to top-tier models only:

- all Claude work is priced as **Claude Opus 4.6**
- all OpenAI review and judging work is priced as **GPT-5.4**

This is an inference from the official pricing/model pages available on **13 April 2026**. It is a pricing-based definition of "best models", not an absolute benchmark claim.

## Key conclusion

For an **autonomous** paper corpus, **API spend is better value than monthly Claude/ChatGPT subscriptions**.

Why:

- ChatGPT subscriptions do **not** include API credits
- Claude subscriptions do **not** include API credits
- Anthropic states API usage is billed separately from Claude subscriptions
- OpenAI states ChatGPT Pro usage must comply with the Terms of Use and explicitly prohibits **automatically or programmatically extracting data**

So for autonomous batch production, subscriptions are not a true substitute for API purchasing. They are best treated as optional **human workbench overhead**.

## FX basis

FX is inferred from ECB reference rates for **10 April 2026**:

- `EUR/USD = 1.1711`
- `EUR/GBP = 0.87105`
- inferred `USD/GBP = 1.3444693186`
- inferred `GBP/USD = 0.7437878917`

So **GBP 1,000** is modeled as approximately **USD 1,344.47**.

## Retained per-paper token envelope

The workflow token load per paper is unchanged. Only the model pricing is upgraded.

| Bucket | Input tokens | Output tokens | Total tokens |
| --- | ---: | ---: | ---: |
| Claude Opus-priced work | 303,500 | 137,600 | 441,100 |
| GPT-5.4-priced work | 111,400 | 17,600 | 129,000 |
| **Total** | **414,900** | **155,200** | **570,100** |

## Quality-first API scenarios

### 1. Pure API, standard pricing

Assumptions:

- Claude Opus 4.6 input: `USD 5.00 / 1M`
- Claude Opus 4.6 output: `USD 25.00 / 1M`
- GPT-5.4 input: `USD 2.50 / 1M`
- GPT-5.4 output: `USD 15.00 / 1M`

Results:

- API cost per paper: **USD 5.50**
- API cost per paper: **GBP 4.0908**
- API cost per paper with `15%` contingency: **GBP 4.7045**
- Max papers at the budget ceiling: **244**
- Max papers with `15%` contingency: **212**

Conservative corpus token total at `212` papers:

- Claude Opus-priced tokens: **93,513,200**
- GPT-5.4-priced tokens: **27,348,000**
- **Total tokens: 120,861,200**

### 2. Pure API, Anthropic batch only

Assumptions:

- Anthropic Message Batches `50%` discount applied to Claude Opus work
- OpenAI pricing unchanged

Results:

- API cost per paper: **USD 3.02125**
- API cost per paper: **GBP 2.2472**
- API cost per paper with `15%` contingency: **GBP 2.5842**
- Max papers at the budget ceiling: **445**
- Max papers with `15%` contingency: **386**

Conservative corpus token total at `386` papers:

- Claude Opus-priced tokens: **170,264,600**
- GPT-5.4-priced tokens: **49,794,000**
- **Total tokens: 220,058,600**

### 3. Pure API, full batch optimization

Assumptions:

- Anthropic Message Batches `50%` discount applied to Claude Opus work
- OpenAI Batch API `50%` discount applied to GPT-5.4 work

Results:

- API cost per paper: **USD 2.75**
- API cost per paper: **GBP 2.0454**
- API cost per paper with `15%` contingency: **GBP 2.3522**
- Max papers at the budget ceiling: **488**
- Max papers with `15%` contingency: **425**

Conservative corpus token total at `425` papers:

- Claude Opus-priced tokens: **187,467,500**
- GPT-5.4-priced tokens: **54,825,000**
- **Total tokens: 242,292,500**

## Subscription comparison

Subscriptions can still be useful for human oversight, drafting, and spot checking. But for autonomous corpus production they reduce the budget left for APIs.

### Premium monthly stack: ChatGPT Pro (`USD 100`) + Claude Max 5x (`USD 100`)

Modeled monthly subscription cost:

- **GBP 148.76**

Budget left for APIs:

- **GBP 851.24**

If the remaining budget is then used for the quality-first API workflow:

- Max papers at standard pricing: **208**
- Max papers with `15%` contingency: **180**

### Heavier monthly stack: ChatGPT Pro (`USD 200`) + Claude Max 20x (`USD 200`)

Modeled monthly subscription cost:

- **GBP 297.52**

Budget left for APIs:

- **GBP 702.48**

If the remaining budget is then used for the quality-first API workflow:

- Max papers at standard pricing: **171**
- Max papers with `15%` contingency: **149**

## Recommendation

For a **quality-first autonomous** corpus under a hard budget of **GBP 1,000**:

- the best core operating model is **pure API spend**
- the safest planning case is **212 high-quality papers**
- the aggressive but still contingency-adjusted case is **386 papers** if Anthropic batch processing is operationally feasible

I would **not** treat monthly ChatGPT/Claude subscriptions as better value for money than API tokens for this use case. They make sense only if you want:

- a human researcher to supervise difficult edge cases
- manual exploratory prompting outside the pipeline
- editorial spot checks or sponsor-facing demos

## Sources

- OpenAI API pricing: <https://openai.com/api/pricing/>
- OpenAI model docs: <https://platform.openai.com/docs/models>
- ChatGPT Pro plans: <https://help.openai.com/en/articles/9793128-about-chatgpt-pro-plans>
- OpenAI terms of use: <https://openai.com/policies/terms-of-use/>
- Anthropic API pricing: <https://docs.anthropic.com/en/docs/about-claude/pricing>
- Claude pricing: <https://www.anthropic.com/pricing>
- Claude Max pricing help: <https://support.anthropic.com/en/articles/11049744-how-much-does-the-max-plan-cost>
- Anthropic API separate billing note: <https://support.claude.com/en/articles/9876003-i-subscribe-to-a-paid-claude-ai-plan-why-do-i-have-to-pay-separately-for-api-usage-on-console>
- ECB FX reference rates: <https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html>
