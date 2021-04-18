import functools
import sys
from typing import Dict, List, NoReturn, Set, Tuple, Optional, Union
from schema import Or, Schema, Optional as Opt, SchemaError

import graphviz
import yaml


@functools.total_ordering
class Node:
    def __init__(self, name: str, attributes: Optional[Set[str]] = None):
        self.name: str = name  # identifier
        if attributes is None:
            attributes = set()
        self.attributes: Set[str] = attributes

    def __str__(self):
        return f"{self.name}_{'_'.join(sorted(self.attributes))}"

    def __lt__(self, other: 'Node') -> bool:
        return str(self.name) < str(other.name)

    def to_label(self) -> str:
        return f"<{{<b>{self.name}</b>|{'<br />'.join(sorted(self.attributes))}}}>"


@functools.total_ordering
class Edge:
    def __init__(self, source: Node, destination: Node, label: str, attributes: Optional[Set[str]] = None):
        self.source = source
        self.destination = destination
        self.label = label
        if attributes is None:
            attributes = set()
        self.attributes = attributes

    def __str__(self) -> str:
        return f"{str(self.source)}_{str(self.destination)}_{self.label}_{'_'.join(sorted(self.attributes))}"

    def __lt__(self, other: 'Edge') -> bool:
        return str(self) < str(other)

    def to_label(self) -> str:
        return f"<<b>{self.label}</b>{''.join('<br />' + attribute for attribute in sorted(self.attributes))}>"


class Onthology:
    def __init__(self):
        self.nodes: Dict[str, Node] = dict()
        self.edges: Set[Edge] = set()
        self.schema: Optional[Schema] = None

    META_ONTHOLOGY = Schema({
            # source
            str: Or(None, {
                Opt('attributes'): Or(None, {
                    str: Or(None, object)
                }),
                # destination
                Opt(str): {
                    # edge
                    str: Or(None, {
                        # attribute
                        str: Or(None, object)
                    })
                }
            })
        })

    def draw(self, output_filename: str):
        g = graphviz.Digraph(format='png')
        g.node_attr.update({'shape': 'record'})

        for node in sorted(self.nodes.values()):
            g.node(str(node), label=node.to_label())

        for edge in sorted(self.edges):
            g.edge(str(edge.source), str(edge.destination), edge.to_label())

        print(g.source)
        filename = g.render(filename=output_filename)
        print("Graph saved in", filename)

    def get_node(self, name: str) -> Node:
        if name in self.nodes:
            return self.nodes[name]
        node = Node(name)
        self.nodes[name] = node
        return node

    @staticmethod
    def load_from_yaml(filename: str, meta_onthology: Schema = None) -> Union['Onthology', NoReturn]:
        if meta_onthology is None:
            meta_onthology = Onthology.META_ONTHOLOGY

        with open(filename, 'r') as file:
            onthology_dict = yaml.safe_load(file.read())

        if meta_onthology:
            try:
                meta_onthology.validate(onthology_dict)
            except SchemaError as se:
                for error in se.errors:
                    if error:
                        print(error)

                for error in se.autos:
                    if error:
                        print(error)

                raise se

        onthology = Onthology()
        if onthology_dict is None:
            return onthology

        onthology_schema_dict = dict()
        for source, destinations in onthology_dict.items():
            source_node = onthology.get_node(source)

            if destinations is None:
                continue

            source_schema_dict = dict()
            for destination, labels in destinations.items():
                if destination == 'attributes':
                    for attribute, condition in labels.items():
                        if type(condition) == str:
                            condition = eval(condition)
                        source_schema_dict[Opt(attribute)] = condition
                        source_node.attributes.add(attribute)
                else:
                    destination_schema_dict = dict()
                    destination_node = onthology.get_node(destination)
                    for label, attributes in labels.items():
                        label_schema_dict = dict()

                        if attributes is None:
                            edge_attributes = None
                        else:
                            edge_attributes = set(attributes.keys())
                            for attribute, condition in attributes.items():
                                if type(condition) == str:
                                    condition = eval(condition)
                                label_schema_dict[Opt(attribute)] = condition

                        onthology.edges.add(Edge(source_node, destination_node, label, attributes=edge_attributes))
                        destination_schema_dict[Opt(label)] = Or(None, label_schema_dict)
                    source_schema_dict[Opt(destination)] = Or(None, destination_schema_dict)
            onthology_schema_dict[Opt(source)] = Or(None, list(source_schema_dict))
        onthology.schema = Schema(Or(None, onthology_schema_dict))
        return onthology


if __name__ == '__main__':
    try:
        onthology = Onthology.load_from_yaml(filename='onthology.yaml')
        onthology.draw(output_filename='onthology')
    except SchemaError:
        sys.exit(1)

    try:
        topology = Onthology.load_from_yaml(filename='topology.yaml', meta_onthology=onthology.schema)
        topology.draw(output_filename='topology')
    except SchemaError:
        sys.exit(2)
