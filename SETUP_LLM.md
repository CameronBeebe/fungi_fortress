# 🔒 XAI (Grok) LLM Setup Guide

This guide shows you how to set up XAI (Grok) integration for Fungi Fortress.

**🎮 Note**: The game is **fully playable without an API key** using the built-in mock Oracle. This guide is only needed if you want to use live XAI (Grok) models.

## ✅ Quick Setup for Live LLM (optional)

### 1. Set your XAI API key as an environment variable

**No configuration file needed!** Just set your API key:

```bash
export XAI_API_KEY="your-xai-api-key-here"
```

All other settings use programmer-controlled defaults in `LLMConfig` (`fungi_fortress/config_manager.py`).

### 2. Run the game

```bash
uv run fungi
# or: python main.py
```

## 🔧 Configuration Options

All configuration defaults are defined in the `LLMConfig` dataclass in `fungi_fortress/config_manager.py`. Only `XAI_API_KEY` is read from the environment. No user config file.

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
