from typing import TypedDict, Annotated
from operator import add

from prompt_toolkit import prompt
from .model import invoke_model
from langgraph.graph import StateGraph, START, END




# =========================================================
# Shared State
# =========================================================

class GraphState(TypedDict, total=False):

    question: str

    results: Annotated[list, add]

    final_answer: str


# =========================================================
# Create Agent Node
# =========================================================

def create_agent_node(
    agent_name,
    model,
    agent_config
):
    def agent_node(state):

        question = state["question"]

        previous_results = state.get(
            "results",
            []
        )

        role = agent_config.get(
            "role",
            agent_name
        )

        instructions = agent_config.get(
            "instructions",
            ""
        )

        # ==========================================
        # FINAL AGENT
        # ==========================================

        if agent_config.get("final", False):

            previous_text = "\n\n".join(
                [
                    f"""
AGENT: {item['agent']}

ANSWER:
{item['answer']}
"""
                    for item in previous_results
                ]
            )

            prompt = f"""
You are the FINAL ANSWER GENERATOR.

Your job is to answer the user's question.

USER QUESTION:
{question}

Here are the answers produced by other agents:

{previous_text}

Your instructions:
{instructions}

IMPORTANT:
- Do NOT talk about agents.
- Do NOT say "I understand the instructions".
- Do NOT describe what you are going to do.
- Do NOT repeat these instructions.
- Directly write the final answer.
- Combine the useful information from the previous answers.
- Remove duplicate information.
- Correct obvious mistakes.
- Make the answer clear and beginner-friendly.

FINAL ANSWER:
"""

        # ==========================================
        # NORMAL AGENTS
        # ==========================================

        else:

            previous_text = ""

            if previous_results:

                previous_text = "\n\n".join(
                    [
                        f"""
AGENT: {item['agent']}

ANSWER:
{item['answer']}
"""
                        for item in previous_results
                    ]
                )

            prompt = f"""
You are {role}.

USER QUESTION:
{question}

YOUR ROLE:
{instructions}
"""

            if previous_text:

                prompt += f"""

Previous agents' answers:

{previous_text}

Use these answers when useful.
"""

            prompt += """

Now perform your task.
Return only your actual answer.
"""

        # ==========================================
        # CALL MODEL
        # ==========================================

        response = invoke_model(
        model,
    prompt,
    agent_config["provider"],
    agent_config["model"]
)

        answer = response.content

        # ==========================================
        # OUTPUT
        # ==========================================

        output = {
            "results": [
                {
                    "agent": agent_name,
                    "answer": answer
                }
            ]
        }

        if agent_config.get("final", False):

            output["final_answer"] = answer

        return output

    return agent_node


# =========================================================
# Build Graph
# =========================================================

def build_graph(
    layers,
    agents,
    agent_configs
):

    graph = StateGraph(
        GraphState
    )

    # -----------------------------------------
    # Create nodes
    # -----------------------------------------

    for layer in layers:

        for agent_name in layer["agents"]:

            model = agents[agent_name]

            agent_config = agent_configs[
                agent_name
            ]

            node = create_agent_node(
                agent_name,
                model,
                agent_config
            )

            graph.add_node(
                agent_name,
                node
            )

    # -----------------------------------------
    # START → first layer
    # -----------------------------------------

    for agent_name in layers[0]["agents"]:

        graph.add_edge(
            START,
            agent_name
        )

    # -----------------------------------------
    # Connect layers
    # -----------------------------------------

    for i in range(
        len(layers) - 1
    ):

        current_layer = layers[i]["agents"]

        next_layer = layers[i + 1]["agents"]

        for current_agent in current_layer:

            for next_agent in next_layer:

                graph.add_edge(
                    current_agent,
                    next_agent
                )

    # -----------------------------------------
    # Last layer → END
    # -----------------------------------------

    for agent_name in layers[-1]["agents"]:

        graph.add_edge(
            agent_name,
            END
        )

    return graph.compile()