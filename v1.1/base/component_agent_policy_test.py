from __future__ import annotations

"""Deterministic tests for the real-component retrieval policy used by the local agent."""

import agents
import component_registry as registry


def ids(text: str):
    return [x["id"] for x in agents._candidate_pool(text, registry, limit=28)]


pi4 = ids("Add a Raspberry Pi 4 Model B 8GB to this design")
assert "compute.raspberry_pi_4_model_b_8gb" in pi4, pi4
assert pi4.index("compute.raspberry_pi_4_model_b_8gb") < 5, pi4

pi5 = ids("Use a Raspberry Pi 5 8GB")
assert "compute.raspberry_pi_5_8gb" in pi5, pi5
assert pi5.index("compute.raspberry_pi_5_8gb") < 5, pi5

pololu = ids("Use the Pololu D24V50F5 5V regulator")
assert "power.pololu.d24v50f5" in pololu, pololu
assert pololu.index("power.pololu.d24v50f5") < 5, pololu

stepper = agents._candidate_pool("I need a NEMA 17 stepper motor", registry, limit=20)
assert any(x["id"] == "motor.stepperonline.17hs19-2004s1" for x in stepper), [x["id"] for x in stepper]
# A real manufacturer entry should outrank generic NEMA-17 proxies when both are relevant.
real_i = next(i for i,x in enumerate(stepper) if x["id"] == "motor.stepperonline.17hs19-2004s1")
generic_i = min((i for i,x in enumerate(stepper) if x["manufacturer"] == "Generic"), default=999)
assert real_i < generic_i, [(x["id"],x["retrieval_score"]) for x in stepper]

# Retrieval payloads must expose the information the planner needs to decide whether
# a candidate is mechanically trustworthy instead of guessing from its name.
sample = next(x for x in agents._candidate_pool("Raspberry Pi 5", registry) if x["id"] == "compute.raspberry_pi_5_8gb")
for key in ("dimensions_mm","geometry_fidelity","geometry_assets","trust_score","source"):
    assert key in sample, sample
assert sample["geometry_fidelity"] == "official_step", sample
assert sample["geometry_assets"] >= 1, sample
assert sample["trust_score"] >= 90, sample

print("ForgeCAD agent real-component policy: PASS")
