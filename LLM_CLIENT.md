# Unified LLM Client (XAI + Mock)

Fungi Fortress uses a unified LLM client supporting XAI (Grok) and a deterministic mock provider for offline play. This document explains the architecture and how to use it.

## Architecture

### Core Components

1. **`llm_client.py`**: Main client with `XAIProvider`, `MockLLMProvider`, and typed exceptions
2. **`llm_oracle.py`**: Oracle-specific adapter (dialogue queries)
3. **`llm_world.py`**: World seed generation adapter
4. **`config_manager.py`**: Configuration loading and client factory

### Key Features

- **XAI (Grok) provider** for live LLM integration (`https://api.x.ai/v1`)
- **Mock provider**: Deterministic, in-character responses for offline play
- **Typed exceptions**: `AuthenticationError`, `RateLimitError`, `TimeoutError`, etc.
- **Streaming support**: Both streaming and non-streaming responses
- **XAI-specific features**: `reasoning_effort` and `response_format` (JSON Schema)

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

The mock provider uses whole-word keyword matching for contextual responses:
- Greetings (`hello`, `hi`, `greet`) → Welcome message
- Quest queries (`quest`, `mission`, `goal`) → Path/forest imagery
- Fungi queries (`fungi`, `mushroom`, `spore`) → Sacred fungi lore
- Help queries (`help`, `aid`, `assist`) → Network/connection wisdom
- Unknown → Mysterious, spore-related response

## Configuration

### Environment Variables

Set your XAI API key:

```bash
export XAI_API_KEY="your-xai-api-key-here"
```

If not set, the game automatically uses the mock provider.

### `llm_config.ini`

```ini
[LLM]
model_name = grok-3-mini       # XAI model (default)
context_level = medium         # low, medium, high
max_tokens = 1000              # Response length limit
enable_streaming = true        # Word-by-word streaming
enable_structured_outputs = false  # JSON Schema for actions
```

**Security**: No API key in the file! Keys come from environment variables.

### Creating a Client

```python
from fungi_fortress.config_manager import load_llm_config

# Load config and create client
config = load_llm_config()
client = config.create_llm_client()

# Client automatically uses mock if no valid XAI_API_KEY
if client.is_mock():
    print("Running in offline mode with mock provider")
```

## XAI Provider

The XAI provider connects to `https://api.x.ai/v1` using the OpenAI SDK:

### Available Models

- `grok-3-mini` (default, recommended)
- `grok-3-mini-fast`
- `grok-3`
- `grok-3-beta`
- `grok-2-1212`
- `grok-beta`
- `grok-vision-beta`

### XAI-Specific Parameters

#### `reasoning_effort`

Controls the depth of reasoning for `grok-3-mini` models:
- `"high"` - Oracle dialogue (better quality, slower)
- `"low"` - World seed generation (faster, cheaper)
- `"medium"` - balanced

```python
response = client.chat(messages, reasoning_effort="high")
```

#### `response_format`

Enables structured output with JSON Schema:

```python
response = client.chat(
    messages,
    use_json_schema=True  # Guarantees valid JSON with Oracle actions
)
```

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

# Build Oracle messages with system prompt, context, and history
messages = llm_oracle.build_oracle_messages(
    oracle_name="Ancient Seer",
    player_query="What is my destiny?",
    game_context={"tick": 100, "depth": 2, "mission": {...}},
    history=[{"player": "Hello", "oracle": "Greetings"}],
    enable_structured_outputs=False,
)

# Non-streaming query (high reasoning effort)
response = llm_oracle.query_oracle(
    client=client,
    oracle_name="Ancient Seer",
    player_query="What is my destiny?",
    game_context=game_context,
    history=history,
    enable_structured_outputs=False,
)

# Streaming query (high reasoning effort)
for chunk in llm_oracle.query_oracle_streaming(...):
    print(chunk, end="", flush=True)
```

### Context Levels

Controlled by `llm_config.context_level`:
- **low**: tick + depth, 1 history turn
- **medium**: + mission, 3 history turns (default)
- **high**: + resources, 5 history turns

### Action Formats

The Oracle supports two output formats:

1. **Text with ACTION markers** (default):
   ```
   The fungi whisper secrets. ACTION::add_message::{"text": "A vision appears..."}
   ```

2. **JSON Schema** (when `enable_structured_outputs=true`):
   ```json
   {
     "narrative": "The fungi whisper secrets.",
     "actions": [
       {"action_type": "add_message", "details": {"text": "A vision appears..."}}
     ]
   }
   ```

## World Seed Generation

World generation uses `llm_world.py` with low reasoning effort:

```python
from fungi_fortress import llm_world

# Generate world seed (uses reasoning_effort="low")
seed_dict = llm_world.generate_world_seed(
    client=client,
    prompt=world_seed_prompt,
    max_tokens=4000,
)
```

The `llm_world.generate_world_seed` function automatically extracts JSON from markdown code fences when parsing world seed responses.

## Testing

### Mock Provider Tests

```python
def test_mock_greeting():
    provider = MockLLMProvider()
    messages = [{"role": "user", "content": "Hello"}]
    response = provider.chat(messages)
    assert "Greetings, seeker" in response

def test_mock_keyword_matching():
    provider = MockLLMProvider()
    # Whole-word matching: "hi" matches but not "this"
    messages = [{"role": "user", "content": "hi"}]
    response = provider.chat(messages)
    assert "Greetings" in response
```

### Client Tests

```python
def test_client_uses_mock_without_key():
    client = LLMClient()  # No config
    assert client.is_mock()

def test_client_with_xai_key():
    config = LLMClientConfig(model="grok-3-mini", api_key="xai-test-key")
    client = LLMClient(config)
    assert not client.is_mock()
```

### Error Tests

```python
@patch('openai.OpenAI')
def test_rate_limit_error(mock_openai):
    mock_client = Mock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.side_effect = openai.RateLimitError(...)
    
    config = LLMClientConfig(model="grok-3-mini", api_key="test-key")
    client = LLMClient(config)
    
    with pytest.raises(llm_client.RateLimitError):
        client.chat([{"role": "user", "content": "test"}])
```

See `tests/test_llm_client.py` and `tests/test_llm_oracle_new.py` for complete examples.

## Migration from Old Code

### Before (old multi-provider llm_interface.py)

```python
from fungi_fortress.llm_interface import _call_llm_api

response = _call_llm_api(prompt, api_key, model, provider, config)
# Returned string errors like "Error: API Key not configured"
if "Error:" in response:
    handle_error(response)
```

### After (XAI-only llm_client)

```python
from fungi_fortress import llm_client

try:
    client = config.create_llm_client()
    response = client.chat(messages)
except llm_client.LLMError as e:
    handle_error(e.user_message())
```

### Key Changes

- **XAI + mock only**: Removed OpenAI, Anthropic, Groq, Together, Perplexity
- **No provider parameter**: Fixed to XAI (or mock when no key)
- **No base_url**: Hardcoded to `https://api.x.ai/v1`
- **No more string error checking**: Use typed exceptions
- **Messages instead of prompt strings**: List of `{"role": "...", "content": "..."}`
- **Mock is default**: Automatic fallback when no `XAI_API_KEY`

## Design Decisions

### Why XAI Only?

Simplifies the codebase and focuses on one well-supported provider:
- Removes ~200 lines of multi-provider branching code
- Eliminates provider auto-detection complexity
- Makes configuration simpler (one env var)
- XAI uses OpenAI-compatible API (easy to work with)

### Why Mock by Default?

Game should be fully playable without API keys. The mock provider:
- Is deterministic (same query → same response)
- Stays in character (Oracle voice)
- Uses whole-word keyword matching (no false positives)
- Never calls external APIs
- Perfect for tests and offline play
- Shows `[Offline Mode]` indicator in UI

### Why Typed Exceptions?

String error checking (`if "Error:" in response`) is fragile. Typed exceptions:
- Enable proper error handling with try/except
- Provide both technical and user-facing messages
- Allow callers to handle errors differently (retry, fallback, etc.)
- Make testing easier with mocks

### Security: API Key Protection

- **`field(repr=False)`** on `LLMConfig.api_key` prevents leaks in logs
- **Not in action details**: Config never serialized to game events
- **Not in logs**: Masked in all log output
- **Only in env vars**: Never in configuration files

## See Also

- `tests/test_llm_client.py` - Client and mock tests (25 tests)
- `tests/test_llm_oracle_new.py` - Oracle integration tests
- `tests/test_llm_interface_ported.py` - Game event handler tests
- `config_manager.py` - Configuration loading and validation
- `llm_interface.py` - Game event handlers (uses client internally)
