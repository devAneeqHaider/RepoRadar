"""Build the frontend-facing dependency graph from parsed modules."""


def build_graph(parsed: dict) -> dict:
    """Return ``{"nodes": [...], "edges": [...]}`` per the API contract.

    Nodes are modules (``type: "module"``) and classes (``type: "class"``,
    id ``"<module>.<Class>"``). Edges are module->class ``"contains"`` links
    and module->module ``"imports"`` links, the latter only when the target
    is a module inside the analyzed repository.
    """
    modules: dict = parsed.get("modules", {})
    nodes: list[dict] = []
    edges: list[dict] = []

    for dotted in sorted(modules):
        info = modules[dotted]
        node_id = dotted or info["path"]
        label = dotted.split(".")[-1] if dotted else info["path"]
        nodes.append(
            {"id": node_id, "label": label, "type": "module", "path": info["path"]}
        )
        for cls in info.get("classes", []):
            class_id = f"{node_id}.{cls['name']}"
            nodes.append(
                {
                    "id": class_id,
                    "label": cls["name"],
                    "type": "class",
                    "path": info["path"],
                }
            )
            edges.append({"from": node_id, "to": class_id, "type": "contains"})

    module_ids = set(modules)
    for dotted in sorted(modules):
        src_id = dotted or modules[dotted]["path"]
        for target in modules[dotted].get("imported_modules", []):
            if target in module_ids and target != dotted:
                edges.append({"from": src_id, "to": target, "type": "imports"})

    # Deduplicate while preserving order.
    seen: set[tuple[str, str, str]] = set()
    unique_edges: list[dict] = []
    for edge in edges:
        key = (edge["from"], edge["to"], edge["type"])
        if key not in seen:
            seen.add(key)
            unique_edges.append(edge)
    return {"nodes": nodes, "edges": unique_edges}
