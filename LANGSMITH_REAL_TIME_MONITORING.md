# LangSmith Real-Time Graph Monitoring Guide

## Overview
Your project is already configured with LangSmith tracing. You can monitor your LangGraph workflow in real-time through the LangSmith web interface.

## Current Configuration

From your `.env` file:
```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=<YOUR_API_KEY>
LANGCHAIN_PROJECT=sap-app-builder
```

## How to Access LangSmith

### Step 1: Open LangSmith Dashboard
1. Go to: **https://smith.langchain.com**
2. Sign in with your LangChain account
3. Your API key is already configured, so traces should appear automatically

### Step 2: Navigate to Your Project
1. In the LangSmith dashboard, look for the project dropdown
2. Select: **"sap-app-builder"** (your LANGCHAIN_PROJECT name)
3. You'll see all traces from your application

### Step 3: View Real-Time Traces
When you run a workflow:
1. **Traces appear in real-time** as the workflow executes
2. Each agent execution creates a new trace
3. You can see:
   - Agent execution order
   - Input/output for each agent
   - Timing information
   - Errors and retries
   - LLM calls and responses

## What You'll See in LangSmith

### Graph Visualization
LangSmith provides a visual representation of your LangGraph:
- **Nodes**: Each agent (requirements, enterprise_architecture, etc.)
- **Edges**: Connections between agents
- **Conditional Edges**: Decision points (retry, continue, self-heal)
- **Current State**: Which agent is currently executing
- **Completed Nodes**: Agents that have finished

### Trace Details
For each trace, you can see:
- **Agent Name**: Which agent is running
- **Status**: in_progress, completed, failed
- **Duration**: How long each agent took
- **Input State**: What data the agent received
- **Output State**: What data the agent produced
- **LLM Calls**: All LLM requests and responses
- **Errors**: Any exceptions or validation errors
- **Retry Attempts**: How many times an agent retried

### Real-Time Features
- **Live Updates**: Traces update as the workflow runs
- **Streaming**: See LLM responses as they stream
- **Progress Tracking**: Monitor which agent is currently executing
- **Error Detection**: Immediately see when an agent fails

## Monitoring Your 28-Agent Workflow

Your workflow has 28 agents in sequence. In LangSmith, you'll see:

1. **Sequential Execution**:
   ```
   requirements → gate_1 → enterprise_architecture → gate_2 → 
   domain_modeling → data_modeling → db_migration → gate_3 → ...
   ```

2. **Parallel Phases** (shown as concurrent branches):
   - Phase 1: service_exposure + integration_design
   - Phase 2: error_handling + audit_logging + api_governance
   - Phase 3: fiori_ui + security + multitenancy + i18n + feature_flags
   - Phase 4: testing + documentation + observability

3. **Human Gates** (7 gates):
   - These appear as interruption points
   - Note: Currently disabled since checkpointing is off

4. **Self-Healing Loops**:
   - When an agent retries, you'll see the loop back
   - The multitenancy bug you just fixed would have shown 300+ retries

## Useful LangSmith Features

### 1. Filter Traces
- Filter by status (success, error, pending)
- Filter by agent name
- Filter by time range
- Search by session ID

### 2. Compare Runs
- Compare different workflow executions
- See performance improvements
- Identify bottlenecks

### 3. Debug Errors
- Click on failed traces
- See the exact error message
- View the stack trace
- See the input that caused the error

### 4. Performance Analysis
- See which agents take the longest
- Identify slow LLM calls
- Optimize based on timing data

### 5. Cost Tracking
- Monitor LLM token usage
- Track API costs per agent
- Optimize expensive operations

## Troubleshooting

### Traces Not Appearing?
1. **Check environment variables are loaded**:
   ```bash
   python -c "import os; print('LANGCHAIN_TRACING_V2:', os.getenv('LANGCHAIN_TRACING_V2'))"
   ```

2. **Verify API key is valid**:
   - Go to https://smith.langchain.com/settings
   - Check your API keys
   - Regenerate if needed

3. **Restart the server**:
   ```bash
   # Stop current server (Ctrl+C)
   # Restart with environment variables
   python -m uvicorn backend.main:app --reload --port 8000
   ```

4. **Check network connectivity**:
   - Ensure you can reach https://api.smith.langchain.com
   - Check firewall settings

### Traces Are Delayed?
- LangSmith may have a few seconds delay
- Refresh the page
- Check your internet connection

### Too Many Traces?
- Use filters to narrow down
- Create separate projects for different environments
- Archive old traces

## Advanced: Custom Trace Metadata

You can add custom metadata to traces by modifying the graph configuration:

```python
# In backend/agents/graph.py
config = {
    "recursion_limit": 300,
    "configurable": {
        "thread_id": session_id
    },
    "metadata": {
        "project_name": initial_state.get("project_name"),
        "user_id": initial_state.get("user_id"),
        "environment": "development",
    }
}
```

This metadata will appear in LangSmith for easier filtering and analysis.

## Quick Start Checklist

- [x] LangSmith configured in `.env`
- [x] API key set
- [x] Project name set (`sap-app-builder`)
- [ ] Server restarted with new environment
- [ ] Open https://smith.langchain.com
- [ ] Navigate to "sap-app-builder" project
- [ ] Run a workflow
- [ ] Watch traces appear in real-time

## Example: Monitoring the Multitenancy Bug Fix

After restarting the server with the multitenancy fix:

1. **Start a new workflow** with `multitenancy_enabled: false`
2. **Open LangSmith** and navigate to your project
3. **Watch the trace** as it progresses through agents
4. **When it reaches multitenancy agent**:
   - Before fix: You'd see 300+ retry attempts
   - After fix: You'll see it complete in one attempt with `{"enabled": False}`
5. **Verify the workflow continues** to the next agent (i18n)

## Resources

- **LangSmith Docs**: https://docs.smith.langchain.com
- **LangGraph Tracing**: https://langchain-ai.github.io/langgraph/how-tos/tracing/
- **Your Dashboard**: https://smith.langchain.com/o/default/projects/p/sap-app-builder

## Pro Tips

1. **Keep LangSmith open** while developing - it's like a debugger for your agents
2. **Use session IDs** to track specific workflow runs
3. **Add custom tags** to traces for easier filtering
4. **Export traces** for offline analysis
5. **Set up alerts** for failed traces (LangSmith Pro feature)
6. **Use the playground** to test individual agents
7. **Share traces** with your team for collaboration

## Next Steps

1. Restart your server to load the multitenancy fix
2. Open LangSmith dashboard
3. Start a new workflow
4. Watch the real-time execution
5. Verify the multitenancy agent completes without errors
