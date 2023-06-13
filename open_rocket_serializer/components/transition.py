import yaml


def search_transitions(bs, elements, ork, rocket_radius):
    transitions = bs.findAll("transition")
    top_radius = rocket_radius
    print(f"[AddTransition] {len(transitions)} found")
    transitions_parameters = {}

    for idx, transition in enumerate(transitions):
        transition_label = transition.find("name").text
        transition_ork = [ele for ele in ork.getRocket().getChild(0).getChildren()][-1]
        top_radius = transition_ork.getForeRadius()
        bottom_radius = (
            transition.find("aftradius").text
            if "auto" in transition.find("aftradius").text
            else float(transition.find("aftradius").text)
        )
        transition_length = float(transition.find("length").text)

        transition_configuration = {
            f"transitionTopRadius{idx}": float(top_radius),
            f"transitionBottomRadius{idx}": bottom_radius,
            f"transitionLength{idx}": transition_length,
            f"transitionDistanceToCM{idx}": elements[transition_label]["DistanceToCG"],
        }
        transitions_parameters.update(transition_configuration)
        top_radius = bottom_radius
        print(
            f"[AddTransition][{idx}] Configuration: \n{yaml.dump(transition_configuration, default_flow_style=False)}"
        )
    return transitions_parameters
