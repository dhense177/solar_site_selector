"""
Script to export the LangGraph diagram to a PNG file.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from sql_agent import app

# Get the graph from the compiled app
graph = app.get_graph()

# Generate Mermaid diagram
mermaid_diagram = graph.draw_mermaid()

# Save Mermaid diagram
output_path = sys.argv[1] if len(sys.argv) > 1 else "graph_diagram.mmd"
with open(output_path, 'w') as f:
    f.write(mermaid_diagram)

print(f"✅ Mermaid diagram saved to: {output_path}")
print("\nTo convert to PNG:")
print("  1. Use online editor: https://mermaid.live/ (paste the .mmd file content)")
print("  2. Or install mermaid-cli: npm install -g @mermaid-js/mermaid-cli")
print(f"     Then run: mmdc -i {output_path} -o {output_path.replace('.mmd', '.png')}")

