def validation_layer(layers):
    if not layers :
        raise ValueError("at least one layer is required")

    for index , layers  in enumerate(layers):

        layer_name = layers.get("name", f"layer_{index + 1}")
        agents = layers.get("agents", [])

        if index == 0 and len(agents) >1:
            raise ValueError(f"Layer '{layer_name}' must have at least one agents.")

        # other layer 
        if index >0 and len(agents) >2 :
            raise ValueError(
                f"{layer_name}caan have maximun 2 agent "
            )

        if len(agents) == 0:
            raise ValueError(
                f"{layer_name} must contain at least 1 agent "


            )


        return True