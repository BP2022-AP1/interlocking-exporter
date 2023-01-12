import json
from yaramo.model import Topology, Node, Edge, SignalDirection


class Exporter:
    def __init__(self, topology: Topology) -> None:
        self.topology = topology

    def export_topology(self) -> str:
        topology = {
            "axleCountingHeads": {},
            "drivewaySections": {},
            "edges": {},
            "nodes": {},
            "points": {},
            "signals": {},
            "trackVacancySections": {},
            "trackVacancySections": {},
        }

        edges = {
            edge.uuid: {
                "anschlussA": None,
                "anschlussB": None,
                "id": edge.uuid,
                "knotenA": None,
                "knotenB": None,
                "laenge": int(edge.length) if edge.length else None,
            }
            for edge in self.topology.edges.values()
        }

        signals = {
            signal.uuid: {
                "art": str(signal.kind),
			    "edge": signal.edge.uuid,
                "funktion": str(signal.function),
                "id": signal.uuid,
                "name": signal.name or "",
                "offset": signal.distance_edge,
                "rastaId": None,
                "wirkrichtung": "normal" if signal.direction == SignalDirection.IN else "reverse"
            }
            for signal in self.topology.signals.values()
        }

        points = {
            point.uuid: {
                "id": point.uuid,
                "name": point.name or "",
                "node": "",
                "rastaId": None,
            }
            for point in self.topology.nodes.values()
        }

        # Find "node" ids by concatenating edge ids for each node that connects them
        edges_per_node = self.__group_edges_per_node(self.topology.edges.values())
        edge_combinations = []
        for _edges in edges_per_node.values():
            if len(_edges) > 1:
                for i, _ in enumerate(_edges):
                    for j in range(i + 1, len(_edges)):
                        edge_combinations.append(f"{_edges[i].uuid}.{_edges[j].uuid}")
        nodes = {
            edge_combination: {"id": edge_combination}
            for edge_combination in edge_combinations
        }

        return json.dumps({
            "edges": edges,
            "nodes": nodes,
            "points": points,
            "signals": signals,
            "axleCountingHeads": {},
            "drivewaySections": {},
            "trackVacancySections": {}
            })

    def export_placement(self) -> str:
        self.__ensure_nodes_orientations()

        points = {}
        for node in self.topology.nodes.values():
            point = {
                "toe": node.connected_on_head.uuid if node.connected_on_head else "",
                "diverting": node.connected_on_right.uuid
                if node.connected_on_right
                else ""
                if node.maximum_speed_on_left
                and node.maximum_speed_on_right
                and node.maximum_speed_on_left > node.connected_on_right
                else node.connected_on_left.uuid
                if node.connected_on_left
                else "",
                "through": node.connected_on_right.uuid
                if node.connected_on_right
                else ""
                if node.maximum_speed_on_left
                and node.maximum_speed_on_right
                and node.maximum_speed_on_left > node.connected_on_right
                else node.connected_on_left.uuid
                if node.connected_on_left
                else "",
                "divertsInDirection": node.__dict__.get("direction"),
                "orientation": "Left"
                if node.__dict__.get("direction") == "normal"
                else "Right",
            }
            points[node.uuid] = point

        edges = {}
        for edge in self.topology.edges.values():
            items = [edge.node_a.uuid]
            items += (
                [
                    signal.uuid
                    for signal in sorted(edge.signals, key=lambda x: x.distance_edge)
                ]
                if len(edge.signals) > 0
                else []
            )
            items += [edge.node_b.uuid]
            edges[edge.uuid] = {"items": items, "orientation": "normal"}

        return json.dumps({"points": points, "edges": edges})

    def __ensure_nodes_orientations(self):
        # find nodes that mark topology ends
        visited_nodes = self.__group_edges_per_node(self.topology.edges.values())
        visited_nodes_length = {
            node: len(items) for node, items in visited_nodes.items()
        }

        # use on of the ends as start for a graph traversal
        start_node = self.topology.nodes.get(
            min(visited_nodes_length, key=visited_nodes_length.get)
        )
        start_direction = "normal" if not start_node.connected_on_head else "reverse"
        self.__set_node_orientation(start_node, start_direction)

    def __group_edges_per_node(self, edges: list[Edge]) -> dict[Node, list[Edge]]:
        visited_nodes = {}
        for edge in edges:
            for node in [edge.node_a, edge.node_b]:
                uuid = node.uuid
                if visited_nodes.get(uuid):
                    visited_nodes.get(uuid).append(edge)
                else:
                    visited_nodes[uuid] = [edge]
        return visited_nodes

    def __set_node_orientation(self, node: Node, direction: str):
        setattr(node, "direction", direction)

        for connected_node in node.connected_nodes:
            if not connected_node.__dict__.get("direction"):
                next_node_direction = "normal"
                if (
                    connected_node.connected_on_left == node
                    or connected_node.connected_on_right == node
                ):
                    next_node_direction = (
                        "reverse" if direction == "normal" else "normal"
                    )
                if connected_node.connected_on_head == node:
                    next_node_direction = (
                        "normal" if direction == "normal" else "reverse"
                    )

                # flip direction if connected node is connected on the head of this node
                next_node_direction = (
                    "reverse" if next_node_direction == "normal" else "normal"
                )

                self.__set_node_orientation(connected_node, next_node_direction)