# Configuring LLM Providers

The framework uses a flexible, YAML-based configuration system to manage connections to various Large Language Models (LLMs), powered by `LiteLLM` on the backend. This approach allows you to easily switch between different models (like OpenAI, Gemini, Anthropic, or local models via Ollama) without changing any code.

## 1. LLM Configuration Overview

*   **Location**: All LLM configurations are defined as `.yaml` files in the `core/agent_profiles/llm_configs/` directory.
*   **Purpose**: Each file defines a reusable set of parameters for calling an LLM. This includes the model name, API key, temperature, and other settings.
*   **Separation of Concerns**: The system separates *what to do* (e.g., "use a powerful model for strategic planning") from *how to do it* (e.g., "call `gpt-4o` with a temperature of 0.5 via this specific API endpoint").

## 2. LLM Config File Structure

Each config file defines one "LLM Config" and follows a simple structure:

```yaml
# The logical name for this configuration. Referenced by Agent Profiles.
name: principal_llm 

# (Optional) Inherit from another configuration.
base_llm_config: base_default_llm 

# The type of this config file.
type: llm_config

# A human-readable description.
description_for_human: "LLM config for high-level strategic tasks (Principal/Partner)."

# The core configuration block passed to LiteLLM.
config:
  model: "openai/gemini-2.5-pro" # Note the `openai/` is to indicate the model is accessed via OpenAI-compatible API. Refer to the LiteLLM documentation for model naming details.
  max_retries: 2
  wait_seconds_on_retry: 5
  # ... other LiteLLM parameters
```

## 3. Dynamic Configuration with Environment Variables

To keep sensitive information like API keys out of config files, the system uses a special `_type: "from_env"` directive. This allows you to load values from your `.env` file at runtime.

**Example**:
Here is how `core/agent_profiles/llm_configs/base_default_llm.yaml` securely loads an API key and base URL:

```yaml
# core/agent_profiles/llm_configs/base_default_llm.yaml

config:
  api_key:
    _type: "from_env"
    var: "DEFAULT_API_KEY" # The name of the environment variable.
    required: false

  api_base:
    _type: "from_env"
    var: "DEFAULT_BASE_URL"
    required: false
```

You would then define these variables in your `.env` file:
```env
# .env file
DEFAULT_API_KEY="your-secret-api-key"
DEFAULT_BASE_URL="https://api.example.com/v1"
```

The `_type: "from_env"` directive supports three fields:
*   `var`: The name of the environment variable to read.
*   `required` (boolean): If `true`, the system will raise an error if the environment variable is not set.
*   `default`: A fallback value to use if the environment variable is not set.

## 4. Inheritance

You can create specialized configurations that inherit from a base config using the `base_llm_config` key. This is useful for defining a common set of defaults and only overriding specific parameters for different tasks.

**Example**:
The `principal_llm` config inherits from `base_default_llm` and overrides the `model` and `temperature`.

`base_default_llm.yaml`:
```yaml
name: base_default_llm
config:
  api_base: ...
  api_key: ...
  max_retries: 2
```

`principal_llm.yaml`:
```yaml
name: principal_llm
base_llm_config: base_default_llm # <-- Inherits
config:
  model: "openai/gemini-2.5-pro" # <-- Overrides/Adds
  temperature: 1.0               # <-- Overrides/Adds
```
The final configuration used for `principal_llm` will be a merge of these two files.

## 5. Linking Agent Profiles to LLM Configs

An `Agent Profile` specifies which LLM configuration it should use via the `llm_config_ref` key. This allows different agent roles (like `Principal` vs. `Associate`) to use different models or parameters.

```yaml
# core/agent_profiles/profiles/Principal_Planner_EN.yaml

name: Principal
type: principal
llm_config_ref: "principal_llm" # <-- Links to the 'principal_llm' config
...
```

## 6. Adding a New LLM Provider (e.g., Anthropic)

Follow these steps to add support for a new LLM provider:

1.  **Create a New LLM Config File**:
    Create a new file in `core/agent_profiles/llm_configs/`, for example `anthropic_llm.yaml`.

    ```yaml
    # core/agent_profiles/llm_configs/anthropic_llm.yaml
    name: anthropic_llm
    base_llm_config: base_default_llm
    type: llm_config
    description_for_human: "LLM config for Anthropic Claude models."

    config:
      # LiteLLM uses the "anthropic/" prefix to identify Claude models
      model: "anthropic/claude-3-opus-20240229"

      # Load the Anthropic API key from an environment variable
      api_key:
        _type: "from_env"
        var: "ANTHROPIC_API_KEY"
        required: true
    ```

2.  **Update Your `.env` File**:
    Add the new environment variable to your `.env` file.
    ```env
    # .env
    ANTHROPIC_API_KEY="your-anthropic-api-key"
    ```

3.  **Use it in an Agent Profile**:
    Modify an Agent Profile to use your new configuration. For example, to make the `Principal` agent use Claude:

    ```yaml
    # core/agent_profiles/profiles/Principal_Planner_EN.yaml
    name: Principal
    type: principal
    llm_config_ref: "anthropic_llm" # <-- Change to the new config
    ...
    ```

Now, when the `Principal` agent runs, it will automatically use the configuration you defined for Anthropic.
