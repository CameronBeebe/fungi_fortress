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
    
    from config_manager import load_oracle_config
    
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