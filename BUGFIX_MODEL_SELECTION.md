# Bug Fix: Model Selection - Multiple Values for 'model' Argument

## Issue 1: Multiple Values for 'model' Argument
```
langchain_openai.chat_models.base.ChatOpenAI() got multiple values for keyword argument 'model'
```

The system was failing when trying to use the user-selected model because the `model` parameter was being passed twice to the ChatOpenAI constructor.

### Root Cause
The flow was:
1. `llm_utils.py` calls `llm_manager.generate(model=user_model)`
2. `LLMManager.generate()` passes `model` via `**kwargs` to provider's `generate()`
3. Provider's `generate()` passes `**kwargs` to `get_chat_model()`
4. `get_chat_model()` tries to pass `model` from kwargs to `ChatOpenAI()`, but also passes `model=self.model`
5. Result: `ChatOpenAI(model=self.model, ..., model=user_model)` → ERROR

### Fix
Modified all provider classes to extract and use the `model` parameter from kwargs if provided, otherwise fall back to `self.model`:

```python
def get_chat_model(self, **kwargs) -> BaseChatModel:
    temperature = kwargs.pop("temperature", 0.1)
    # Allow model override from kwargs
    model = kwargs.pop("model", self.model)
    return ChatOpenAI(
        api_key=self.api_key,
        model=model,  # Use the extracted model
        ...
    )
```

## Issue 2: Model Lost Between Agents
```
modelInput should be a valid string [type=string_type, input_value=None, input_type=NoneType]
```

After the requirements agent successfully used the user's selected model, subsequent agents were getting `model=None`.

### Root Cause
The `llm_provider` and `llm_model` fields were not defined in the `BuilderState` TypedDict schema. LangGraph uses the TypedDict schema to determine which fields to preserve between agent executions. Fields not in the schema may not be reliably preserved.

### Fix
Added `llm_provider` and `llm_model` to the `BuilderState` TypedDict in `backend/agents/state.py`:

```python
# LLM Configuration (NEW)
llm_provider: str | None  # User-selected LLM provider (openai, gemini, xai, etc.)
llm_model: str | None  # User-selected model name (grok-4-1-fast-reasoning, etc.)
```

Also added a fallback in `backend/api/plan.py` to use default values if not provided:

```python
initial_state["llm_provider"] = config.get("llm_provider", settings.default_llm_provider)
initial_state["llm_model"] = config.get("llm_model") or settings.default_llm_model
```

## Files Changed
- `backend/agents/llm_providers.py` - Updated all 6 provider classes (OpenAI, Gemini, DeepSeek, Kimi, XAI, OpenRouter)
- `backend/agents/state.py` - Added llm_provider and llm_model to BuilderState TypedDict
- `backend/api/plan.py` - Added fallback to default model if not provided

## Testing
1. Restart backend server
2. Select xAI provider with grok-4-1-fast-reasoning model in frontend
3. Start generation
4. Verify ALL agents use the selected model (check logs for "LLM Generation: provider=xai, model=grok-4-1-fast-reasoning")
5. Verify no "model=None" errors occur
