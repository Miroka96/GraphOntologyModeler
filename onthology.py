import functools
import sys
from typing import Any, Dict, NoReturn, Optional, Set, Union

import graphviz
import schema
import yaml
from schema import Optional as Opt, Schema, SchemaError


@functools.total_ordering
class AbstractNode:
    def __init__(self, name: str):
        self.name: str = name

    def id(self) -> str:
        return self.name

    def __str__(self):
        return self.id()

    def __lt__(self, other: 'MetaNode') -> bool:
        return self.id() < other.id()

    def to_label(self) -> str:
        return f"<{{<b>{self.name}</b>}}>"

    def draw(self, g: graphviz.Digraph):
        g.node(name=self.id(), label=self.to_label())


class MetaNode(AbstractNode):
    def __init__(self, name: str, attributes: Optional[Set[str]] = None):
        super().__init__(name=name)
        if attributes is None:
            attributes = set()
        self.attributes: Set[str] = attributes

    def to_label(self) -> str:
        return super().to_label()[:-2] + f"|{'<br />'.join(sorted(self.attributes))}}}>"


@functools.total_ordering
class AbstractEdge:
    def __init__(self, source: AbstractNode, destination: AbstractNode, label: str):
        self.source: AbstractNode = source
        self.destination: AbstractNode = destination
        self.label: str = label

    def __str__(self) -> str:
        return f"{str(self.source)}_{str(self.destination)}_{self.label}"

    def __lt__(self, other: 'MetaEdge') -> bool:
        return str(self) < str(other)

    def to_label(self) -> str:
        return f"<<b>{self.label}</b>>"

    def draw(self, g: graphviz.Digraph):
        g.edge(self.source.id(), self.destination.id(), self.to_label())


class MetaEdge(AbstractEdge):
    def __init__(self, source: MetaNode, destination: MetaNode, label: str, attributes: Optional[Set[str]] = None):
        super().__init__(source, destination, label)
        if attributes is None:
            attributes = set()
        self.attributes = attributes

    def to_label(self) -> str:
        return super().to_label()[:-1] + f"{''.join('<br />' + attribute for attribute in sorted(self.attributes))}>"


class Node(AbstractNode):
    def __init__(self, cls: AbstractNode, name: str):
        super().__init__(name=name)
        self.cls: AbstractNode = cls
        self.attribute_values: Dict[str, Any] = dict()
        self.outgoing_edges: Set['Edge'] = set()

    def add_edge(self, edge: 'Edge'):
        self.outgoing_edges.add(edge)

    def to_label(self) -> str:
        return f"""<{{<i>{self.cls}</i><br /><b>{self.name}</b>|{
        '<br align="left"/>'.join(f"{label} = {value}" for label, value in sorted(self.attribute_values.items()))
        }}}>"""

    def draw(self, g: graphviz.Digraph):
        super().draw(g)
        for edge in self.outgoing_edges:
            edge.draw(g)


class Edge(AbstractEdge):
    def __init__(self, source: Node, destination: Node, label: str,
                 attribute_values: Optional[Dict[str, Any]] = None):
        super().__init__(source, destination, label)
        if attribute_values is None:
            attribute_values = dict()
        self.attribute_values: Dict[str, Any] = attribute_values

    def to_label(self) -> str:
        return super().to_label()[:-1] + f"""{''.join(f'<br align="left"/>{label} = {value}' 
                                                      for label, value in sorted(self.attribute_values.items()))}>"""


class Topology:
    def __init__(self):
        self.instances: Dict[str, Node] = dict()

    def add_instance(self, instance: Node):
        assert instance.id() not in self.instances
        self.instances[instance.id()] = instance

    def get_instance(self, cls: AbstractNode, name: str) -> Node:
        new_instance = Node(cls=cls, name=name)
        if new_instance.id() in self.instances:
            return self.instances[new_instance.id()]
        self.add_instance(new_instance)
        return new_instance

    def draw(self, output_filename: str):
        g = graphviz.Digraph(format='png')
        g.node_attr.update({'shape': 'record'})

        for instance in sorted(self.instances.values()):
            instance.draw(g)

        print(g.source)
        filename = g.render(filename=output_filename)
        print("Graph saved in", filename)


class Onthology:
    def __init__(self):
        self.meta_nodes: Dict[str, MetaNode] = dict()
        self.meta_edges: Dict[str, Dict[str, MetaEdge]] = dict()
        self.schema: Optional[Schema] = None

    def add_edge(self, edge: MetaEdge):
        if edge.source.id() not in self.meta_edges:
            self.meta_edges[edge.source.id()] = dict()

        self.meta_edges[edge.source.id()][edge.label] = edge

    def get_all_edges(self) -> Set[MetaEdge]:
        return {edge for source_dict in self.meta_edges.values()
                for edge in source_dict.values()}

    def get_edge_by_source_and_label(self, source_id: Union[str, MetaNode], label: str) -> Optional[MetaEdge]:
        if isinstance(source_id, MetaNode):
            source_id = str(source_id)
        return self.meta_edges.get(source_id, dict()).get(label, None)

    META_ONTHOLOGY = Schema({
        # source
        str: schema.Or(None, {
            Opt('attributes'): schema.Or(None, {
                str: schema.Or(None, object)
            }),
            # edge
            Opt(str): schema.And({
                # destination
                str: schema.Or(None, {
                    # attribute
                    str: schema.Or(None, object)
                })
            }, lambda d: len(d) == 1, error='exactly one destination is required')
        })
    })

    def draw(self, output_filename: str):
        g = graphviz.Digraph(format='png')
        g.node_attr.update({'shape': 'record'})

        for node in sorted(self.meta_nodes.values()):
            g.node(str(node), label=node.to_label())

        for edge in sorted(self.get_all_edges()):
            g.edge(str(edge.source), str(edge.destination), edge.to_label())

        print(g.source)
        filename = g.render(filename=output_filename)
        print("Graph saved in", filename)

    def get_node(self, name: str) -> MetaNode:
        if name in self.meta_nodes:
            return self.meta_nodes[name]
        node = MetaNode(name)
        self.meta_nodes[name] = node
        return node

    @staticmethod
    def load_onthology_from_yaml(filename: str, meta_onthology: Schema = None) -> Union['Onthology', NoReturn]:
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
        for source_label, edge_labels in onthology_dict.items():
            source_node = onthology.get_node(source_label)

            if edge_labels is None:
                continue

            source_schema_dict = dict()
            for edge_label, destination_labels in edge_labels.items():
                assert destination_labels is not None, \
                    f"edge label '{edge_label}' in source '{source_label}' has no children"

                if edge_label == 'attributes':
                    for attribute_label, validation_condition in destination_labels.items():
                        if type(validation_condition) == str:
                            validation_condition = eval(validation_condition)
                        source_schema_dict[Opt(attribute_label)] = validation_condition
                        source_node.attributes.add(attribute_label)
                else:
                    assert len(destination_labels) <= 1, \
                        f"edge label '{edge_label}' in source '{source_label}' has more than one destination"
                    assert len(destination_labels) > 0, \
                        f"edge label '{edge_label}' in source '{source_label}' is missing a destination"

                    destination_label, attribute_labels = next(iter(destination_labels.items()))

                    attribute_labels_schema_dict = dict()
                    if attribute_labels is None:
                        edge_attributes = None
                    else:
                        for attribute_label, validation_condition in attribute_labels.items():
                            if type(validation_condition) == str:
                                validation_condition = eval(validation_condition)
                            attribute_labels_schema_dict[Opt(attribute_label)] = validation_condition
                        edge_attributes = set(attribute_labels.keys())

                    destination_node = onthology.get_node(destination_label)
                    onthology.add_edge(MetaEdge(source_node, destination_node, edge_label, attributes=edge_attributes))

                    source_schema_dict[Opt(edge_label)] = {str: schema.Or(None, attribute_labels_schema_dict)}
            onthology_schema_dict[Opt(source_label)] = schema.Or(None, {str: schema.Or(None, source_schema_dict)})
        onthology.schema = Schema(schema.Or(None, onthology_schema_dict))
        return onthology

    def load_topology(self, filename: str) -> Topology:
        with open(filename, 'r') as file:
            topology_dict = yaml.safe_load(file.read())

        try:
            self.schema.validate(topology_dict)
        except SchemaError as se:
            for error in se.errors:
                if error:
                    print(error)
            for error in se.autos:
                if error:
                    print(error)
            raise se

        topology = Topology()
        for source_cls_id, source_instances in topology_dict.items():
            source_cls = self.meta_nodes[source_cls_id]
            for source_name, attribute_labels in source_instances.items():
                source_instance = Node(cls=source_cls, name=source_name)
                for attribute_label, attribute_values in attribute_labels.items():
                    edge = self.get_edge_by_source_and_label(source_cls_id, attribute_label)
                    if edge is None:
                        source_instance.attribute_values[attribute_label] = attribute_values
                    else:
                        destination_cls_id = edge.destination.id()
                        destination_cls = self.meta_nodes[destination_cls_id]
                        for destination_name, attributes in attribute_values.items():
                            destination_instance = topology.get_instance(cls=destination_cls, name=destination_name)
                            new_edge = Edge(source=source_instance,
                                            destination=destination_instance,
                                            label=attribute_label,
                                            attribute_values=attributes)
                            source_instance.add_edge(new_edge)
                topology.add_instance(source_instance)
        return topology


if __name__ == '__main__':
    try:
        onthology = Onthology.load_onthology_from_yaml(filename='onthology.yaml')
        onthology.draw(output_filename='onthology')
    except SchemaError:
        sys.exit(1)

    try:
        topology = onthology.load_topology(filename='topology.yaml')
        topology.draw(output_filename='topology')
    except SchemaError:
        sys.exit(2)
