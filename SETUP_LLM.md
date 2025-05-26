# 🔒 Secure LLM Setup Guide

This guide shows you how to set up LLM integration for Fungi Fortress using secure environment variables.

## ✅ Quick Setup (3 steps)

### 1. Copy the configuration template
```bash
cp llm_config.ini.example llm_config.ini
```

### 2. Set your API key as an environment variable

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

### 3. Run the game
```bash
python main.py
```

The game will automatically detect which API key to use based on your chosen model!

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

## 🔍 Verification

Run the security tests to verify everything is set up correctly:
```bash
python -m pytest tests/test_security.py -v
```

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
- Run `python verify_llm_setup.py` for detailed diagnostics. This script tests API key validity, provider detection, and basic XAI API communication directly. Note that the main game uses a more abstracted interface for LLM calls. 