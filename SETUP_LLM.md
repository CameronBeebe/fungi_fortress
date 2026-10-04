# 🔒 XAI (Grok) LLM Setup Guide

This guide shows you how to set up XAI (Grok) integration for Fungi Fortress.

**🎮 Note**: The game is **fully playable without an API key** using the built-in mock Oracle. This guide is only needed if you want to use live XAI (Grok) models.

## ✅ Quick Setup for Live LLM (optional)

### 1. Set your XAI API key as an environment variable

**No configuration file needed!** Just set your API key:

```bash
export XAI_API_KEY="your-xai-api-key-here"
```

### 2. (Optional) Configure model preferences

To change the default model or tweak parameters:

```bash
cp llm_config.ini.example llm_config.ini
# Edit llm_config.ini to set your preferred model
```

Available XAI models:
- `grok-4.3` (default, recommended)
- `grok-2-1212`
- `grok-beta`
- `grok-vision-beta`

### 3. Run the game

```bash
uv run fungi
# or: python main.py
```

## 🔧 Configuration Options

Edit `llm_config.ini` to customize:

- **model_name**: Choose your preferred XAI model (default: `grok-4.3`)
- **context_level**: `low`, `medium` (default), `high` - controls game context sent to Oracle
- **max_tokens**: Response length limit (cost control, default: 1000)
- **enable_structured_outputs**: Use JSON Schema for reliable action parsing (default: false)
- **enable_streaming**: Stream responses word-by-word (default: true)

## 🛡️ Security Benefits

✅ **No API keys in files** - Keys are stored in environment variables only  
✅ **No git commits** - Impossible to accidentally commit secrets  
✅ **Easy rotation** - Change keys without touching code  
✅ **Process isolation** - Keys are only visible to your game process  

## 🎮 Offline Mode (No API Key Required)

Fungi Fortress is fully playable without any API key!

When no `XAI_API_KEY` is configured, the game automatically uses a **mock Oracle** that provides:
- Deterministic, in-character responses based on keywords
- Perfect for offline play and testing
- No external API calls
- Full Oracle functionality
- Visible `[Offline Mode]` indicator in the Oracle dialog

Just run the game without setting any API key:

```bash
uv run fungi
```

## 🔍 Verification

Run the tests to verify everything works:

```bash
uv run pytest
```

All tests should pass.

To specifically test the LLM client:

```bash
uv run pytest tests/test_llm_client.py -v
```

## 💡 Tips

- Add the `export` command to your shell profile (`.bashrc`, `.zshrc`) for persistence
- Use different API keys for development and production
- The mock provider uses whole-word keyword matching for realistic offline responses
- Context levels affect both prompt size and API costs (high = more expensive)

## 🆘 Troubleshooting

**Game crashes on startup:**
- Check that you're on the latest commit of this PR
- Verify `XAI_API_KEY` is not set to a placeholder value like `YOUR_API_KEY_HERE`

**Oracle not responding with XAI key set:**
- Verify your XAI API key is valid
- Check logs in `logs/play-*.log` for error messages
- Try running without the key (offline mode) to verify the game works

**Want to test without using API credits:**
- Run without `XAI_API_KEY` set - the mock provider works perfectly offline
- Or run the test suite: `uv run pytest tests/test_llm_oracle_new.py -v`

**Still having issues?**
- Check the logs in `logs/` directory for detailed error messages
- Run `uv run pytest tests/test_llm_client.py -v` to verify the client works
- See `LLM_CLIENT.md` for architecture details
