# 🔒 Secure LLM Setup Guide

This guide shows you how to set up LLM integration for Fungi Fortress.

**🎮 Note**: The game is **fully playable without an API key** using the built-in mock Oracle. This guide is only needed if you want to use live LLM providers.

## ✅ Quick Setup for Live LLM (optional)

### 1. Set your API key as an environment variable

**No configuration file needed!** Just set your API key:

Choose your provider and set the corresponding environment variable:

**For XAI (Grok models):**
```bash
export XAI_API_KEY="your-xai-api-key-here"
```

**For OpenAI (GPT models):**
```bash
export OPENAI_API_KEY="your-openai-api-key-here"
```

**For Anthropic (Claude models):**
```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key-here"
```

**For Groq (fast open-source models):**
```bash
export GROQ_API_KEY="your-groq-api-key-here"
```

### 2. (Optional) Configure model preferences

To change the default model or tweak parameters:

```bash
cp llm_config.ini.example llm_config.ini
# Edit llm_config.ini to set your preferred model
```

### 3. Run the game
```bash
uv run fungi
# or: python main.py
```

The game will automatically detect which API key to use based on your model!

## 🔧 Configuration Options

Edit `llm_config.ini` to customize:

- **provider**: `auto` (recommended), `xai`, `openai`, `anthropic`, `groq`
- **model_name**: Choose your preferred model
- **context_level**: `low`, `medium`, `high`
- **max_tokens**: Response length limit (cost control)

## 🛡️ Security Benefits

✅ **No API keys in files** - Keys are stored in environment variables only  
✅ **No git commits** - Impossible to accidentally commit secrets  
✅ **Easy rotation** - Change keys without touching code  
✅ **Process isolation** - Keys are only visible to your game process  

## 🎮 Offline Mode (No API Key Required)

**New in this version**: Fungi Fortress is fully playable without any API key!

When no API key is configured, the game automatically uses a **mock Oracle** that provides:
- Deterministic, in-character responses
- Perfect for offline play and testing
- No external API calls
- Full Oracle functionality

Just run the game without setting any API key:

```bash
uv run fungi
```

The game will display a subtle indicator when using offline mode.

## 🔍 Verification

Run the tests to verify everything works:
```bash
uv run pytest
```

All 205+ tests should pass, including 40 tests of the new unified LLM client.

## 💡 Tips

- Add the `export` command to your shell profile (`.bashrc`, `.zshrc`) for persistence
- Use different API keys for development and production
- The game works fine without LLM features if no API key is set

## 🆘 Troubleshooting

**Game says "API Key not configured":**
- Make sure you've set the correct environment variable for your provider
- Check that the variable name matches exactly (case-sensitive)
- Restart your terminal after setting the variable

**Wrong provider detected:**
- Set `provider = xai` (or your provider) explicitly in `llm_config.ini`
- The auto-detection is based on model names

**Still having issues?**
- Check the logs for detailed error messages
- Try running in offline mode (no API key) to isolate the issue
- Run `uv run pytest tests/test_llm_client.py -v` to verify the client works
- See `LLM_CLIENT.md` for architecture details 