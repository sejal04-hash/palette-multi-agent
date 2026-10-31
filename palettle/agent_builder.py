from palettle.model import create_model

def build_agent(agent_configs):
    agents = {}

    for agent_name , agent_config in agent_configs.items():
        # create model using model factory 

        model = create_model(agent_config)

        # store model using agent name 

        agents[agent_name] = model

    return agents