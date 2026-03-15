"""
Verify that checkpointer is disabled in the graph module.
"""
import asyncio
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

async def verify():
    """Verify checkpointer is disabled."""
    try:
        from backend.agents.graph import get_checkpointer, get_builder_graph
        
        print("✓ Successfully imported graph module")
        
        # Check checkpointer
        checkpointer = await get_checkpointer()
        if checkpointer is None:
            print("✓ Checkpointer is None (disabled)")
        else:
            print("✗ ERROR: Checkpointer is not None!")
            return False
        
        # Check compiled graph
        print("Compiling graph...")
        graph = await get_builder_graph()
        print("✓ Successfully compiled graph")
        
        # Check if graph has checkpointer
        if hasattr(graph, 'checkpointer'):
            if graph.checkpointer is None:
                print("✓ Graph checkpointer is None")
            else:
                print("✗ ERROR: Graph has a checkpointer!")
                return False
        else:
            print("✓ Graph has no checkpointer attribute")
        
        print("\n✓ ALL CHECKS PASSED - Checkpointer is disabled")
        return True
        
    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(verify())
    sys.exit(0 if result else 1)
