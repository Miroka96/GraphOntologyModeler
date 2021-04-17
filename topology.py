import functools
from typing import Iterable, List, Set, Tuple

import graphviz as gv


@functools.total_ordering
class Port:
    pass


@functools.total_ordering
class Network:
    pass


@functools.total_ordering
class Interface:

    def __init__(self, node: 'Node', name: str, ip: str = "?"):
        self.node: 'Node' = node
        self.name: str = name
        self.ip: str = ip
        self.connected_to: Set['Interface'] = set()
        self.services: Set['Service'] = set()

    def connect_to(self, interface: 'Interface') -> 'Interface':
        self.connected_to.add(interface)
        interface.connected_to.add(self)
        return self

    def __str__(self):
        return f"{type(self).__name__}_{self.node}_{self.name}_{self.ip}"

    def to_label(self) -> str:
        return f"<{{<b>{type(self).__name__}</b><br />{self.name}}}|ip = {self.ip}>"

    def __lt__(self, other: 'Interface') -> bool:
        return str(self) < str(other)

    def host(self, service: 'Service') -> 'Interface':
        self.services.add(service)
        service.binds.add(self)
        return self

    def add_service(self, name: str) -> 'Service':
        service = Service(node=self.node, name=name)
        self.node.topology.service(service)
        self.host(service)
        return service

    def get_connections(self) -> List[Tuple['Interface']]:
        return [tuple(sorted({self, interface})) for interface in self.connected_to]

    def draw(self, g: gv.Digraph):
        g.node(name=str(self), label=self.to_label())

    @staticmethod
    def draw_edges(g: gv.Digraph, interfaces: Iterable['Interface']):
        connections = set()
        for interface in interfaces:
            connections.update(interface.get_connections())

        for connection in connections:
            g.edge(str(connection[0]), str(connection[1]), label="connected", attrs={'dir': 'none'})


@functools.total_ordering
class Service:
    def __init__(self, node: 'Node', name: str):
        self.node: 'Node' = node
        self.name: str = name
        self.uses: Set['Service'] = set()
        self.binds: Set[Interface] = set()

    def bind_to(self, interface: Interface) -> 'Service':
        interface.host(self)
        return self

    def use(self, service: 'Service') -> 'Service':
        self.uses.add(service)
        return self

    def __str__(self):
        return f"{type(self).__name__}_{self.node}_{self.name}"

    def to_label(self) -> str:
        return f"<{{<b>{type(self).__name__}</b><br />{self.name}}}>"

    def __lt__(self, other: 'Service') -> bool:
        return str(self) < str(other)

    def draw(self, g: gv.Digraph):
        g.node(name=str(self), label=self.to_label())

    @staticmethod
    def draw_edges(g: gv.Digraph, services: Iterable['Service']):
        for service in services:
            for use in service.uses:
                g.edge(str(service), str(use), label="uses")

            for bind in service.binds:
                g.edge(str(service), str(bind), label="bindsTo")


@functools.total_ordering
class Node:
    def __init__(self, topology: 'Topology', hostname: str):
        self.topology: 'Topology' = topology
        self.hostname: str = hostname
        self.interfaces: Set[Interface] = set()
        self.services: Set[Service] = set()

    def host(self, service: Service) -> 'Node':
        self.services.add(service)
        service.host = self
        return self

    def attach(self, interface: Interface) -> 'Node':
        self.interfaces.add(interface)
        interface.host = self
        return self

    def __str__(self):
        return f"{type(self).__name__}_{self.hostname}"

    def __lt__(self, other: 'Node') -> bool:
        return str(self) < str(other)

    def add_interface(self, name: str, ip: str) -> Interface:
        interface = Interface(node=self, name=name, ip=ip)
        self.topology.interface(interface)
        self.attach(interface)
        return interface

    def add_service(self, name: str) -> Service:
        service = Service(node=self, name=name)
        self.topology.service(service)
        self.host(service)
        return service

    def to_label(self) -> str:
        return f"<{{<b>{type(self).__name__}</b><br />{self.hostname}}}>"

    def draw(self, g: gv.Digraph):
        g.node(name=str(self), label=self.to_label())

    @staticmethod
    def draw_edges(g: gv.Digraph, nodes: Iterable['Node']):
        for node in nodes:
            for interface in node.interfaces:
                g.edge(str(node), str(interface), label="net")

            for service in node.services:
                g.edge(str(node), str(service), label="hosts")


class Topology:
    def __init__(self, environment: str = "?"):
        self.environment: str = environment
        self.nodes: Set[Node] = set()
        self.services: Set[Service] = set()
        self.interfaces: Set[Interface] = set()

    def node(self, node: Node) -> 'Topology':
        self.nodes.add(node)
        node.topology = self
        return self

    def service(self, service: Service) -> 'Topology':
        self.services.add(service)
        return self

    def interface(self, interface: Interface) -> 'Topology':
        self.interfaces.add(interface)
        return self

    def add_node(self, hostname: str) -> Node:
        node = Node(topology=self, hostname=hostname)
        self.node(node)
        return node

    def __str__(self) -> str:
        return f"<{type(self).__name__}>\n{self.environment}"

    def draw(self, output_filename='topology'):
        g = gv.Digraph(format='png')
        g.node_attr.update({'shape': 'record'})

        for node in self.nodes:
            node.draw(g)

        for service in self.services:
            service.draw(g)

        for interface in self.interfaces:
            interface.draw(g)

        Interface.draw_edges(g, self.interfaces)
        Service.draw_edges(g, self.services)
        Node.draw_edges(g, self.nodes)

        print(g.source)
        filename = g.render(filename=output_filename)
        print("Graph saved in", filename)
