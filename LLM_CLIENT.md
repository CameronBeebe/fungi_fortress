# Unified LLM Client

Fungi Fortress uses a unified LLM client for all language model interactions. This document explains the architecture and how to use it.

## Architecture

### Core Components

1. **`llm_client.py`**: Main client with typed exceptions and mock provider
2. **`llm_oracle.py`**: Oracle-specific adapter (dialogue queries)
3. **`llm_world.py`**: World seed generation adapter
4. **`config_manager.py`**: Configuration loading and client factory

### Key Features

- **Single OpenAI-compatible interface** for all providers
- **Typed exceptions**: `AuthenticationError`, `RateLimitError`, `TimeoutError`, etc.
- **Mock provider**: Deterministic, in-character responses for offline play
- **Streaming support**: Both streaming and non-streaming from one code path
- **Auto-detection**: Provider detection from model name

## Using the Mock Provider

The mock provider enables **fully playable offline mode**. When no API key is configured:

```python
from fungi_fortress.llm_client import LLMClient

# No API key -> automatic mock
client = LLMClient()
assert client.is_mock()  # True

# Mock gives deterministic, in-character responses
response = client.chat([{"role": "user", "content": "Hello Oracle"}])
# Returns: "Greetings, seeker. The mycelial network pulses with ancient knowledge..."
```

The mock provider responds contextually:
- Greetings → Welcome message
- Quest queries → Path/forest imagery
- Fungi queries → Sacred fungi lore
- Help queries → Network/connection wisdom
- Unknown → Mysterious, spore-related response

## Configuration

### Environment Variables

Set the appropriate API key for your provider:

```bash
export OPENAI_API_KEY="sk-..."
export XAI_API_KEY="xai-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GROQ_API_KEY="gsk_..."
```

### `llm_config.ini`

```ini
[LLM]
provider = auto                # auto-detect from model
model_name = gpt-4o-mini      # or grok-3-mini, claude-3-5-sonnet-20241022, etc.
max_tokens = 1000
timeout_seconds = 60
```

No API key in the file! Keys come from environment variables for security.

### Creating a Client

```python
from fungi_fortress.config_manager import load_llm_config

# Load config and create client
config = load_llm_config()
client = config.create_llm_client()

# Client automatically uses mock if no valid API key
if client.is_mock():
    print("Running in offline mode with mock provider")
```

## Supported Providers

All providers use OpenAI-compatible APIs:

| Provider    | Base URL                              | Example Models                    |
|-------------|---------------------------------------|-----------------------------------|
| OpenAI      | https://api.openai.com/v1            | gpt-4o, gpt-4o-mini              |
| XAI (Grok)  | https://api.x.ai/v1                  | grok-3, grok-3-mini              |
| Anthropic   | https://api.anthropic.com/v1         | claude-3-5-sonnet-20241022       |
| Groq        | https://api.groq.com/openai/v1       | llama-3.3-70b-versatile          |
| Together    | https://api.together.xyz/v1          | meta-llama/...                   |
| Perplexity  | https://api.perplexity.ai            | llama-3.1-sonar-large-128k-online |

Provider auto-detection works by model name pattern matching.

## Error Handling

All errors inherit from `LLMError` with typed subclasses:

```python
from fungi_fortress import llm_client

try:
    response = client.chat(messages)
except llm_client.AuthenticationError as e:
    print(e.user_message())  # "The Oracle's connection is disrupted. (Authentication failed)"
except llm_client.RateLimitError as e:
    print(e.user_message())  # "The Oracle is overwhelmed by queries. Please wait."
except llm_client.TimeoutError as e:
    print(e.user_message())  # "The Oracle's response faded into silence."
except llm_client.LLMError as e:
    print(e.user_message())  # Generic fallback
```

Each exception has:
- Technical details in `str(exception)`
- Player-friendly message in `.user_message()`

## Oracle Integration

The Oracle uses `llm_oracle.py` for prompt building and queries:

```python
from fungi_fortress import llm_oracle

# Build Oracle messages
messages = llm_oracle.build_oracle_messages(
    oracle_name="Ancient Seer",
    player_query="What is my destiny?",
    game_context={"tick": 100, "depth": 2, "mission": {...}},
    history=[{"player": "Hello", "oracle": "Greetings"}],
)

# Non-streaming query
response = llm_oracle.query_oracle(
    client=client,
    oracle_name="Ancient Seer",
    player_query="What is my destiny?",
    game_context=game_context,
    history=history,
)

# Streaming query
for chunk in llm_oracle.query_oracle_streaming(...):
    print(chunk, end="", flush=True)
```

## World Seed Generation

World generation uses `llm_world.py`:

```python
from fungi_fortress import llm_world

# Generate world seed
seed_dict = llm_world.generate_world_seed(
    client=client,
    prompt=world_seed_prompt,
    max_tokens=4000,
)
```

The client handles JSON extraction from markdown code fences automatically.

## Testing

### Mock Provider Tests

```python
def test_mock_greeting():
    provider = MockLLMProvider()
    messages = [{"role": "user", "content": "Hello"}]
    response = provider.chat(messages)
    assert "Greetings, seeker" in response
```

### Client Tests

```python
def test_client_uses_mock_without_key():
    client = LLMClient()  # No config
    assert client.is_mock()
```

### Error Tests

```python
@patch('openai.OpenAI')
def test_rate_limit_error(mock_openai):
    # Setup mock to raise openai.RateLimitError
    # ...
    with pytest.raises(llm_client.RateLimitError):
        client.chat(messages)
```

See `tests/test_llm_client.py` and `tests/test_llm_oracle_new.py` for complete examples.

## Migration from Old Code

### Before (old llm_interface.py)

```python
from fungi_fortress.llm_interface import _call_llm_api

response = _call_llm_api(prompt, api_key, model, provider, config)
# Returned string errors like "Error: API Key not configured"
if "Error:" in response:
    handle_error(response)
```

### After (new llm_client)

```python
from fungi_fortress import llm_client

try:
    client = config.create_llm_client()
    response = client.chat(messages)
except llm_client.LLMError as e:
    handle_error(e.user_message())
```

### Key Changes

- **No more string error checking**: Use typed exceptions
- **Messages instead of prompt strings**: List of `{"role": "...", "content": "..."}`
- **No provider parameter**: Auto-detected from config
- **Mock is default**: Automatic fallback when no key configured

## Design Decisions

### Why OpenAI-Compatible Only?

OpenAI's API format has become the de facto standard. Most providers (XAI, Groq, Together, Perplexity) support it. Anthropic has OpenAI-compatible endpoints. This allows:

- Single code path for all providers
- Easy testing with mocks
- Future provider additions without code changes

### Why Mock by Default?

Game should be fully playable without API keys. The mock provider:

- Is deterministic (same query → same response)
- Stays in character (Oracle voice)
- Never calls external APIs
- Perfect for tests and offline play

### Why Typed Exceptions?

String error checking (`if "Error:" in response`) is fragile. Typed exceptions:

- Enable proper error handling with try/except
- Provide both technical and user-facing messages
- Allow callers to handle errors differently
- Make testing easier

## See Also

- `tests/test_llm_client.py` - Client and mock tests (28 tests)
- `tests/test_llm_oracle_new.py` - Oracle integration tests (12 tests)
- `config_manager.py` - Configuration loading
- `llm_interface.py` - Game event handlers (uses client internally)
