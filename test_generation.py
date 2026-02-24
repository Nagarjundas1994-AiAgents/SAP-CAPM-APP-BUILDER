"""
End-to-End Generation Test Script

Tests the full LLM-driven generation pipeline directly via the API:
1. Create a session
2. Configure entities with a complex Supply Chain domain
3. Trigger generation via SSE endpoint
4. Monitor progress and collect generated artifacts
"""

import asyncio
import json
import sys
import time
import traceback

# Add project root to path
sys.path.insert(0, ".")

async def test_generation():
    """Run the full generation pipeline directly."""
    from backend.agents.state import create_initial_state
    from backend.agents.graph import create_builder_graph

    print("=" * 70)
    print("  SAP CAPM App Builder — Full Generation Test")
    print("  Supply Chain Management App (5 entities)")
    print("=" * 70)
    print()

    # 1. Create initial state
    print("[1/4] Creating initial state...")
    state = create_initial_state(
        session_id="test-supply-chain-001",
        project_name="SupplyChainPro",
        project_namespace="com.supplychain.pro",
        project_description="Enterprise supply chain management with procurement, inventory, warehousing, shipment tracking, and supplier management",
    )

    # 2. Configure entities (names only — LLM will generate fields)
    state["entities"] = [
        {"name": "PurchaseOrder", "description": "Purchase orders to suppliers", "fields": []},
        {"name": "Supplier", "description": "Supplier master data", "fields": []},
        {"name": "InventoryItem", "description": "Warehouse inventory items with stock tracking", "fields": []},
        {"name": "Warehouse", "description": "Physical warehouse locations", "fields": []},
        {"name": "Shipment", "description": "Shipment tracking for deliveries", "fields": []},
    ]
    state["relationships"] = [
        {"name": "poToSupplier", "source_entity": "PurchaseOrder", "target_entity": "Supplier", "type": "association", "cardinality": "n:1"},
        {"name": "itemToWarehouse", "source_entity": "InventoryItem", "target_entity": "Warehouse", "type": "association", "cardinality": "n:1"},
        {"name": "shipmentToOrder", "source_entity": "Shipment", "target_entity": "PurchaseOrder", "type": "association", "cardinality": "n:1"},
    ]
    state["business_rules"] = [
        {"name": "stockValidation", "description": "Prevent negative stock levels", "entity": "InventoryItem", "rule_type": "validation"},
        {"name": "orderApproval", "description": "Auto-approve orders under $1000", "entity": "PurchaseOrder", "rule_type": "workflow"},
        {"name": "shipmentTracking", "description": "Track shipment status transitions", "entity": "Shipment", "rule_type": "status_machine"},
    ]

    # Additional config
    state["domain_template"] = "custom"
    state["fiori_theme"] = "sap_horizon"
    state["fiori_app_type"] = "list_report"
    state["fiori_main_entity"] = "PurchaseOrder"
    state["odata_version"] = "v4"
    state["enable_draft"] = True
    state["auth_type"] = "mock"
    state["deployment_target"] = "cf"
    state["llm_provider"] = "openai"
    state["validation_retry_count"] = 0

    print(f"  → Project: {state['project_name']}")
    print(f"  → Namespace: {state['project_namespace']}")
    print(f"  → Entities: {[e['name'] for e in state['entities']]}")
    print(f"  → Relationships: {len(state['relationships'])}")
    print(f"  → Business Rules: {len(state['business_rules'])}")
    print(f"  → LLM Provider: {state['llm_provider']}")
    print()

    # 3. Create and run the graph
    print("[2/4] Creating LangGraph workflow...")
    graph = create_builder_graph()
    compiled_graph = graph.compile()
    print("  → Graph compiled successfully")
    print()

    # 4. Run the generation
    print("[3/4] Running generation pipeline...")
    print("  → This may take 2-5 minutes as each agent calls the LLM")
    print()

    start_time = time.time()

    try:
        final_state = await compiled_graph.ainvoke(state)

        elapsed = time.time() - start_time
        print()
        print(f"[4/4] Generation complete in {elapsed:.1f}s")
        print()

        # Collect results
        print("=" * 70)
        print("  RESULTS")
        print("=" * 70)

        # Agent history
        agent_history = final_state.get("agent_history", [])
        print(f"\n  Agents executed: {len(agent_history)}")
        for entry in agent_history:
            name = entry.get("agent_name", "?")
            status = entry.get("status", "?")
            icon = "✅" if status == "completed" else "❌"
            logs = entry.get("logs", [])
            last_log = logs[-1] if logs else ""
            if isinstance(last_log, dict):
                last_log = last_log.get("message", "")
            print(f"    {icon} {name}: {status} — {last_log[:80]}")

        # Generated files
        all_artifacts = []
        for key in ["artifacts_db", "artifacts_srv", "artifacts_app", "artifacts_security",
                     "artifacts_ext", "artifacts_deploy", "artifacts_deployment", "artifacts_docs"]:
            artifacts = final_state.get(key, [])
            all_artifacts.extend(artifacts)

        print(f"\n  Total files generated: {len(all_artifacts)}")
        for art in all_artifacts:
            path = art.get("path", "?")
            content = art.get("content", "")
            size = len(content)
            print(f"    📄 {path} ({size} bytes)")

        # Validation results
        errors = final_state.get("validation_errors", [])
        error_count = sum(1 for e in errors if e.get("severity") == "error")
        warning_count = sum(1 for e in errors if e.get("severity") == "warning")
        print(f"\n  Validation: {error_count} errors, {warning_count} warnings")

        # Quality score
        quality = final_state.get("quality_score")
        if quality:
            print(f"  Quality Score: {quality.get('total', 'N/A')}/100")

        # Self-healing info
        retry_count = final_state.get("validation_retry_count", 0)
        if retry_count > 0:
            print(f"  Self-healing retries: {retry_count}")

        # Status
        gen_status = final_state.get("generation_status", "unknown")
        print(f"\n  Final Status: {gen_status}")
        print()

        # Print a sample of generated code (schema.cds)
        schema = final_state.get("generated_schema_cds", "")
        if schema:
            print("=" * 70)
            print("  SAMPLE: db/schema.cds (first 50 lines)")
            print("=" * 70)
            lines = schema.split("\n")[:50]
            for line in lines:
                print(f"  {line}")
            print()

        return True

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ Generation failed after {elapsed:.1f}s")
        print(f"   Error: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_generation())
    sys.exit(0 if result else 1)
