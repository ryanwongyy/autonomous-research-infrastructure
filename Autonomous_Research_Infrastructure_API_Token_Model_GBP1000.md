# Autonomous Research Infrastructure API Token Model (`GBP 1,000`)

## Scope

This note models how many **API tokens** and how many **submission-ready academic papers** the Autonomous Research Infrastructure can produce with a pure API budget of **GBP 1,000**.

The model uses the retained AI-governance workflow already encoded in the current finance workbooks:

- 7-role generation pipeline
- 3 collegial review rounds
- independent review layers
- expected re-review rate of `40%`
- tournament judging
- RSI overhead

It is a **token-budget model**, not a staffing or QA-bandwidth model.

## FX basis

FX is inferred from ECB reference rates for **10 April 2026**:

- `EUR/USD = 1.1711`
- `EUR/GBP = 0.87105`
- inferred `USD/GBP = 1.3444693186`
- inferred `GBP/USD = 0.7437878917`

So **GBP 1,000** is modeled as approximately **USD 1,344.47**.

## Retained per-paper token envelope

Per submission-ready paper:

| Model bucket | Input tokens | Output tokens | Total tokens |
| --- | ---: | ---: | ---: |
| Claude Sonnet | 199,500 | 46,600 | 246,100 |
| Claude Opus | 104,000 | 91,000 | 195,000 |
| OpenAI GPT-4o | 111,400 | 17,600 | 129,000 |
| **Total** | **414,900** | **155,200** | **570,100** |

Important: batching changes **price**, not **token volume**. The per-paper token envelope stays the same across scenarios.

## Pricing scenarios

### 1. Standard pricing

Assumptions:

- Claude Sonnet input `USD 3.00 / 1M`
- Claude Sonnet output `USD 15.00 / 1M`
- Claude Opus input `USD 5.00 / 1M`
- Claude Opus output `USD 25.00 / 1M`
- GPT-4o input `USD 2.50 / 1M`
- GPT-4o output `USD 10.00 / 1M`

Results:

- API cost per paper: **USD 4.5470**
- API cost per paper: **GBP 3.3820**
- API cost per paper with `15%` contingency: **GBP 3.8893**
- Max papers at budget ceiling: **295**
- Max papers with `15%` contingency: **257**

Conservative corpus token total at `257` papers:

- Claude Sonnet: **63,247,700**
- Claude Opus: **50,115,000**
- GPT-4o: **33,153,000**
- **Total tokens: 146,515,700**

### 2. Claude-batched pricing

Assumptions:

- Anthropic Message Batches `50%` discount applied to Claude calls
- OpenAI pricing unchanged

Results:

- API cost per paper: **USD 2.50075**
- API cost per paper: **GBP 1.86003**
- API cost per paper with `15%` contingency: **GBP 2.13903**
- Max papers at budget ceiling: **537**
- Max papers with `15%` contingency: **467**

Conservative corpus token total at `467` papers:

- Claude Sonnet: **114,928,700**
- Claude Opus: **91,065,000**
- GPT-4o: **60,243,000**
- **Total tokens: 266,236,700**

### 3. Full batch-optimized pricing

Assumptions:

- Anthropic Message Batches `50%` discount applied to Claude calls
- OpenAI Batch API `50%` discount applied to GPT-4o calls

Results:

- API cost per paper: **USD 2.2735**
- API cost per paper: **GBP 1.69100**
- API cost per paper with `15%` contingency: **GBP 1.94465**
- Max papers at budget ceiling: **591**
- Max papers with `15%` contingency: **514**

Conservative corpus token total at `514` papers:

- Claude Sonnet: **126,495,400**
- Claude Opus: **100,230,000**
- GPT-4o: **66,306,000**
- **Total tokens: 293,031,400**

## Headline interpretation

Under the retained autonomous workflow, a **GBP 1,000 pure API budget** supports approximately:

- **257 papers** conservatively at standard pricing
- **467 papers** conservatively with Claude batching
- **514 papers** conservatively if both Claude and OpenAI batch discounts are fully usable

That implies a conservative token-processing capacity of roughly:

- **146.5 million tokens** at standard pricing
- **266.2 million tokens** with Claude batching
- **293.0 million tokens** with full batch optimization

## Practical recommendation

The safest planning number is the **standard-pricing contingent case**:

- plan for **257 submission-ready papers**
- assume **146.5 million total API tokens**

If the infrastructure can reliably queue Claude-heavy work through Message Batches, a more ambitious but still contingency-adjusted planning number is:

- **467 papers**
- **266.2 million total API tokens**

## Sources

- OpenAI API pricing: <https://openai.com/api/pricing/>
- OpenAI GPT-4o model docs: <https://platform.openai.com/docs/models/gpt-4o>
- Anthropic API pricing: <https://docs.anthropic.com/en/docs/about-claude/pricing>
- ECB FX reference rates: <https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html>
