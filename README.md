# Vertica Sentiment UDSF (jev_sentiment)

A Vertica User-Defined Scalar Function (UDSF) that sends text to a remote Typesafe-compatible Jev AI
gateway hosted by Vercel for sentiment analysis and returns an encoded sentiment label.

This example demonstrates:

- Writing a Python UDSF with only the Python **standard library** (no
  third-party packages), so it runs inside Vertica's minimal Python
  environment.
- Reading secrets (API endpoint and key) from **UDX parameters** supplied at
  call time via `USING PARAMETERS`.
- Calling a remote HTTP API from inside a `processBlock()` loop.
- Handling errors gracefully by emitting `NULL` instead of aborting the query.

It's fast as LLM-based AI goes: 1000 text samples in 3 minutes on a single node, or about 200 ms per text sample.

---

## How it works

The function takes two SQL arguments:

| Argument        | Type    | Description                                  |
| --------------- | ------- | -------------------------------------------- |
| `state`         | varchar | The text to evaluate (e.g. an IMDB review).  |
| `instructions`  | varchar | The evaluation instructions sent to the API. |

It returns an `int` encoded label:

| Return | Meaning  |
| ------ | -------- |
| `0`    | negative |
| `1`    | positive |
| `NULL` | error    |

The function POSTs the text to the gateway, parses the nested
`answers.sentiment.score` field from the JSON response, and encodes it
(`1` = positive, `0` = negative).

---

## Requirements

- Vertica with Python UDx support enabled (Python UDSFs always run **fenced**).
- The Vertica nodes must be able to reach the AI gateway over HTTPS.
- Python 3 standard library only — no `pip` packages required.

---

## Installation

### 1. Copy the source to a path readable by Vertica

The file must live in a location the `dbadmin` user (or whichever user runs
Vertica) can read:

```bash
scp jev_sentiment_udsf.py dbadmin@vertica-node:/home/dbadmin/
```

### 2. Create the library and function

```sql
CREATE LIBRARY jevailib AS '/home/dbadmin/jev_sentiment_udsf.py' LANGUAGE 'Python';

CREATE FUNCTION jev_sentiment AS
LANGUAGE 'Python' NAME 'jev_sentiment_factory' LIBRARY jevailib fenced;
```

### 3. Reload after editing the source

When you change `jev_sentiment_udsf.py`, drop and recreate both:

```sql
DROP FUNCTION jev_sentiment;
DROP LIBRARY jevailib;

CREATE LIBRARY jevailib AS '/home/dbadmin/jev_sentiment_udsf.py' LANGUAGE 'Python';

CREATE FUNCTION jev_sentiment AS
LANGUAGE 'Python' NAME 'jev_sentiment_factory' LIBRARY jevailib fenced;
```

---

## Usage

```sql
SELECT jev_sentiment(
           review,                        -- state
           'What is the sentiment?'       -- instructions
       USING PARAMETERS
           endpoint = 'https://ai-gateway.vercel.sh/typesafe/v1/systemone',
           api_key  = 'your-api-key'
       ) AS predicted
FROM imdb;
```

### UDX parameters

| Parameter   | Type    | Required | Description                                      |
| ----------- | ------- | -------- | ------------------------------------------------ |
| `endpoint`  | varchar | yes      | The AI gateway URL.                              |
| `api_key`   | varchar | yes      | The bearer token for the gateway.                |
| `verify_ssl`| bool    | no       | Set to `false` to skip TLS verification (test).  |

### Example: compare predictions against labels

Given a table like:

```sql
CREATE TABLE imdb (
    filename  varchar(256),
    sentiment varchar(10),     -- training label: '0' or '1'
    review    varchar(32767)
);
```

A ready-to-use sample table and data are provided in `setup.sql`:

```bash
vsql -f setup.sql
```

It creates `imdb_sample` with five labeled reviews (`1` = positive, `0` =
negative).

Compute accuracy directly in SQL:

```sql
SELECT
    COUNT(*)                          AS total,
    SUM((predicted = label)::int)     AS matches,
    SUM((predicted <> label)::int)    AS misclassified,
    AVG((predicted = label)::int) * 100 AS accuracy_pct
FROM (
    SELECT
        jev_sentiment(review, 'What is the sentiment?'
            USING PARAMETERS
                endpoint = 'https://ai-gateway.vercel.sh/typesafe/v1/systemone',
                api_key  = 'your-api-key') AS predicted,
        sentiment AS label
    FROM imdb_sample
) t;
```

---

## Notes & caveats

- **`fenced` is mandatory.** Python UDxs always run in a separate process, so
  `fenced` must appear in the `CREATE FUNCTION` statement.
- **TLS verification** is on by default. For local testing against a
  self-signed endpoint, pass `verify_ssl = false`. Do not disable it in
  production.
- **Proxy settings:** `urllib` honors the standard `HTTP_PROXY` /
  `HTTPS_PROXY` / `NO_PROXY` environment variables **in the fence process**.
  If your gateway is on an internal/VPN address, make sure the Vertica user's
  `NO_PROXY` includes that host, or requests will be routed through a proxy
  and fail.
- **Secrets in query text:** passing `api_key` via `USING PARAMETERS` embeds
  the key in the query text, which may appear in query history
  (`dc_requests_issued`). For production, prefer `ALTER SESSION SET UDPARAMETER
  FOR ...` or another server-side secret mechanism.
- **Errors emit `NULL`.** A scalar function must output one value per input
  row, so on any failure the function logs the error and returns `NULL`
  rather than aborting the block.
- **Logging:** `server_interface.log()` output goes to the Vertica UDx log;
  check `vertica.log` for `ERROR: ...` messages when debugging.
