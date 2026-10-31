
from pathlib import Path

from .config import load_config, get_default_config_path
from .layer_validaor import validation_layer
from .agent_builder import build_agent
from .graph_builder import build_graph
from .error import PaletteError


def run_palette(config_path=None):

    if config_path is None:
        config_path = get_default_config_path()

    config = load_config(config_path)

    print("\nConfiguration loaded successfully")

    layers = config["layers"]

    validation_layer(layers)

    print("Layer configuration is valid")

    agents = build_agent(config["agents"])

    print("Agents built successfully")

    for name, agent_config in config["agents"].items():
        print(
            f"Agent: {name}, "
            f"Provider: {agent_config['provider']}, "
            f"Model: {agent_config['model']}"
        )

    app = build_graph(
        layers,
        agents,
        config["agents"]
    )

    print("\nGraph built successfully")

    try:
        result = app.invoke({
            "question": config["task"],
            "results": []
        })

    except PaletteError as e:
        print("\n==============================")
        print("PALETTE ERROR")
        print("==============================")
        print(e)
        return

    print("\n==============================")
    print("AGENT RESULTS")
    print("==============================")

    for item in result.get("results", []):
        print(f"\n--- {item['agent']} ---")
        print(item["answer"])

    print("\n==============================")
    print("FINAL ANSWER")
    print("==============================")

    print(result.get("final_answer", "No final answer generated."))

    try:
        png_data = app.get_graph().draw_mermaid_png()

        graph_path = Path(config_path).parent / "graph.png"

        with open(graph_path, "wb") as f:
            f.write(png_data)

        print(f"\nGraph image saved: {graph_path}")

    except Exception as e:
        print("\nGraph image could not be generated.")
        print("Reason:", e)
