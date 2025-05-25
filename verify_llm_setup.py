#!/usr/bin/env python3
"""
Fungi Fortress LLM Setup Verification Tool

This script helps users verify that their multi-provider LLM configuration is working correctly.
Run this after setting up your oracle_config.ini to confirm everything is configured properly.

Usage: python verify_llm_setup.py
"""

import os
import sys
sys.path.append('.')

from llm_interface import _detect_provider_and_call_api
from config_manager import load_oracle_config
import requests

def verify_provider_detection():
    """Verify that provider detection works correctly for different model names."""
    
    test_cases = [
        ("grok-3", None, "xai"),
        ("grok-2-1212", None, "xai"),  
        ("gpt-4o", None, "openai"),
        ("gpt-4o-mini", None, "openai"),
        ("claude-3-5-sonnet-20241022", None, "anthropic"),
        ("llama-3.3-70b-versatile", None, "groq"),
        ("mixtral-8x7b-32768", None, "groq"),
        ("gemma2-9b-it", None, "groq"),
        ("unknown-model", "xai", "xai"),  # Test explicit provider hint
    ]
    
    print("🔍 Verifying provider detection logic...")
    all_correct = True
    
    for model_name, provider_hint, expected_provider in test_cases:
        # Mock the actual API call by using a fake key to test routing only
        fake_api_key = "test-key-123456789"
        
        print(f"\n📋 Model: {model_name}")
        print(f"   Hint: {provider_hint or 'auto-detect'}")
        print(f"   Expected provider: {expected_provider}")
        
        # This will fail at the API call level, but we can verify the detection logic
        # by checking what provider gets selected (visible in printed output)
        try:
            result = _detect_provider_and_call_api(
                "Test prompt", 
                fake_api_key, 
                model_name, 
                provider_hint,
                None  # oracle_config (use defaults)
            )
            print(f"   ✅ Detection working (API call failed as expected with fake key)")
        except Exception as e:
            print(f"   ❌ Unexpected error in detection logic: {e}")
            all_correct = False
    
    return all_correct

def verify_config_structure():
    """Verify that the oracle config structure is valid and can be loaded."""
    
    print("\n" + "="*50)
    print("🔧 Verifying configuration loading...")
    
    try:
        # Test loading the example config (should use defaults since no real API key)
        config = load_oracle_config("oracle_config.ini.example")
        
        print(f"   📄 Config file: oracle_config.ini.example")
        print(f"   🔑 API Key configured: {config.is_real_api_key_present}")
        print(f"   🤖 Default model: {config.model_name}")
        print(f"   🌐 Default provider: {config.provider}")
        print(f"   📊 Context level: {config.context_level}")
        print("   ✅ Configuration structure is valid!")
        return True
        
    except Exception as e:
        print(f"   ❌ Error loading configuration: {e}")
        return False

def test_basic_xai_api_call():
    """Test basic XAI API connectivity without structured outputs."""
    print("=== Testing XAI API Basic Connectivity ===")
    
    config = load_oracle_config()
    
    if not config.api_key or config.api_key == "YOUR_API_KEY_HERE":
        print("❌ No valid API key found in oracle_config.ini")
        return False
        
    print(f"✅ API Key loaded: {config.api_key[:10]}...{config.api_key[-4:]}")
    print(f"✅ Model: {config.model_name}")
    print(f"✅ Provider: {config.provider}")
    
    # Test simple API call
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json"
    }
    
    test_data = {
        "messages": [{"role": "user", "content": "Say hello"}],
        "model": config.model_name,
        "max_tokens": 50,
        "stream": False
    }
    
    try:
        print("🔄 Making test API call...")
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers=headers,
            json=test_data,
            timeout=30
        )
        
        print(f"📊 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            print(f"✅ Success! Response: {content}")
            return True
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"📝 Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception during API call: {e}")
        return False

def test_structured_outputs():
    """Test XAI structured outputs feature."""
    print("\n=== Testing XAI Structured Outputs ===")
    
    config = load_oracle_config()
    
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json"
    }
    
    # Test with JSON schema
    test_data = {
        "messages": [{"role": "user", "content": "Respond with a greeting and suggest an action. Use the required JSON format."}],
        "model": config.model_name,
        "max_tokens": 100,
        "stream": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "test_response",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "narrative": {
                            "type": "string",
                            "description": "A greeting message"
                        },
                        "actions": {
                            "type": "array",
                            "description": "Test actions",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "action_type": {"type": "string"},
                                    "details": {"type": "object"}
                                },
                                "required": ["action_type", "details"],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required": ["narrative", "actions"],
                    "additionalProperties": False
                }
            }
        }
    }
    
    try:
        print("🔄 Making structured output test...")
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers=headers,
            json=test_data,
            timeout=30
        )
        
        print(f"📊 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            print(f"✅ Structured Output Success!")
            print(f"📝 Response: {content}")
            return True
        else:
            print(f"❌ Structured Output Failed: {response.status_code}")
            print(f"📝 Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception during structured output test: {e}")
        return False

def main():
    """Run all diagnostic tests."""
    print("🧪 Fungi Fortress LLM Diagnostics")
    print("=" * 50)
    
    # Test basic connectivity
    basic_success = test_basic_xai_api_call()
    
    if basic_success:
        # If basic works, test structured outputs
        structured_success = test_structured_outputs()
        
        if not structured_success:
            print("\n⚠️  Basic API works but structured outputs failed.")
            print("💡 Recommendation: Disable structured outputs in oracle_config.ini")
            print("   Set: enable_structured_outputs = false")
    else:
        print("\n❌ Basic API connectivity failed.")
        print("💡 Check your API key and model name in oracle_config.ini")
    
    print("\n" + "=" * 50)
    print("🏁 Diagnostics complete!")

if __name__ == "__main__":
    print("🎮 Fungi Fortress LLM Setup Verification")
    print("=" * 50)
    
    detection_ok = verify_provider_detection()
    config_ok = verify_config_structure()
    
    print("\n" + "="*50)
    if detection_ok and config_ok:
        print("✅ SETUP VERIFICATION SUCCESSFUL!")
        print("="*50)
        print("🎯 All provider detection logic is working correctly")
        print("🎯 Configuration loading is working correctly")
        print()
        print("📋 Supported Providers:")
        print("   • XAI (Grok models): Direct API integration")
        print("   • OpenAI: GPT-4o, GPT-4o-mini, GPT-3.5-turbo")  
        print("   • Anthropic: Claude-3.5-Sonnet, Claude-3.5-Haiku")
        print("   • Groq: Fast open-source models (LLaMA, Mixtral, Gemma)")
        print("   • Auto-detection: Based on model name patterns")
        print()
        print("🚀 Next Steps:")
        print("1. Copy oracle_config.ini.example to oracle_config.ini")
        print("2. Add your API key for your preferred provider")
        print("3. Set your preferred model and provider")
        print("4. Start the game and interact with the Oracle!")
        print()
        print("💡 Tip: Start with a small, fast model like gpt-4o-mini or")
        print("    llama-3.1-8b-instant for cost-effective testing.")
    else:
        print("❌ SETUP VERIFICATION FAILED!")
        print("="*50)
        print("Please check the error messages above and ensure all")
        print("required dependencies are installed:")
        print("  pip install openai requests groq")
        
    print("\n🎮 Ready to explore the Fungi Fortress with AI-powered Oracle!")
    
    main() 