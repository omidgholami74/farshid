import pm4py
from pm4py import read_xes
from pm4py.objects.log.obj import EventLog, Event, Trace
from pm4py.objects.petri_net.obj import PetriNet, Marking
from pm4py.util import xes_constants as xes
import pm4py.algo.discovery.inductive.variants.im_f.algorithm as imf
from pm4py.algo.discovery.footprints import algorithm as footprints_discovery
from pm4py.algo.evaluation.replay_fitness import algorithm as replay_fitness
from pm4py.algo.conformance.alignments.petri_net import algorithm as alignments
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn import Conv1d, Linear, LayerNorm
from torch_geometric.data import Data, Dataset, InMemoryDataset
from torch_geometric.loader import DataLoader
from torch_geometric.nn import SAGEConv
from torch_geometric.nn.aggr import SortAggregation
from torch_geometric import seed_everything
from statistics import mean, stdev
from sklearn.model_selection import train_test_split as sklearn_train_test_split
import networkx as nx
import numpy as np
from typing import Tuple, List, Optional, Dict, Any, Set
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from tqdm.auto import tqdm

# Transformer-specific imports
from torch.nn import TransformerEncoder, TransformerEncoderLayer

def add_artificial_start_end_events(log: EventLog, start_act: str = "[start]", end_act: str = "[end]", activityName_key: str = xes.DEFAULT_NAME_KEY) -> EventLog:
    for trace in log:
        start_time = trace[0][xes.DEFAULT_TIMESTAMP_KEY]
        end_time = trace[-1][xes.DEFAULT_TIMESTAMP_KEY]
        if isinstance(start_time, datetime):
            new_start = start_time - timedelta(seconds=1)
            new_end = end_time + timedelta(seconds=1)
        else:
            new_start = start_time - 1
            new_end = end_time + 1
        start_event = Event({activityName_key: start_act, xes.DEFAULT_TIMESTAMP_KEY: new_start})
        end_event = Event({activityName_key: end_act, xes.DEFAULT_TIMESTAMP_KEY: new_end})
        trace._list = [start_event, *trace._list, end_event]
    return log

def discover_model_imf(log: EventLog, noise_threshold: float=0) -> Tuple[PetriNet, Marking, Marking]:
    return imf.apply(log, {imf.Parameters.NOISE_THRESHOLD: noise_threshold})

def _get_inserted_and_deleted_activities(trace: Trace, model: PetriNet) -> Tuple[Set[Tuple[str, ...]], List[Tuple[str, ...]]]:
    alignment_result = alignments.apply(trace, *model)
    alignment = alignment_result['alignment']
    alignment = [step for step in alignment if step[0] is not None and step[1] is not None]

    d = set()
    i = set()
    current_list = []
    current_trace_index = 0
    current_starting_index = -1
    for idx, step in enumerate(alignment):
        if step[0] == '>>':
            if len(current_list) == 0 or current_list[0][0] == '>>':
                if len(current_list) == 0:
                    current_starting_index = current_trace_index
                current_list.append(step)
            else:
                i.add((current_starting_index, tuple(act for act, _ in current_list)))
                current_starting_index = current_trace_index
                current_list = [step]
        elif step[1] == '>>':
            if len(current_list) == 0 or current_list[0][1] == '>>':
                if len(current_list) == 0:
                    current_starting_index = current_trace_index
                current_list.append(step)
            else:
                d.add((current_starting_index, tuple(act for _, act in current_list)))
                current_starting_index = current_trace_index
                current_list = [step]
            current_trace_index += 1
        else:
            if len(current_list) > 0:
                if current_list[0][0] == '>>':
                    d.add((current_starting_index, tuple(act for _, act in current_list)))
                else:
                    i.add((current_starting_index, tuple(act for act, _ in current_list)))
                current_starting_index = -1
                current_list = []
            current_trace_index += 1
    if len(current_list) > 0:
        if current_list[0][0] == '>>':
            d.add((current_starting_index, tuple(act for _, act in current_list)))
        else:
            i.add((current_starting_index, tuple(act for act, _ in current_list)))
    return i, d

def extract_instance_graph(trace:Trace, model_footprint: Dict[str, Any], activityName_key:str=xes.DEFAULT_NAME_KEY):
    nodes = {event for event in trace}
    edges = {
        (e1, e2)
        for i1, e1 in enumerate(trace)
        for i2, e2 in enumerate(trace[i1+1:], start=i1+1)
        
        if (e1[activityName_key], e2[activityName_key]) in model_footprint['sequence']
        if all((e1[activityName_key], e[activityName_key]) not in model_footprint['sequence'] for e in trace[i1+1: i2]) \
        or all((e[activityName_key], e2[activityName_key]) not in model_footprint['sequence'] for e in trace[i1+1: i2])
    }

    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    return graph

def deletion_repair(trace:Trace, edges: Set[Tuple[str, str]], deletetion_index: int, deleted_activities: List[str], model_causal_relations: List[Tuple[str, str]], activityName_key:str=xes.DEFAULT_NAME_KEY) -> Set[Tuple[str,str]]:
    i = deletetion_index
    
    e_i = trace[i]
    w_r1 = {
        (e_k, e_i)
        for k, e_k in enumerate(trace[:i])
        if (e_k, e_i) in edges
        and any((e_h[activityName_key], deleted_activities[0]) in model_causal_relations for e_h in trace[k:i])
        and (deleted_activities[-1], e_i[activityName_key]) in model_causal_relations
    }
    w_r2 = {
        (e_k, e_j)
        for k, e_k in enumerate(trace[:i])
        for j, e_j in enumerate(trace[i+1:], start=i+1)
        if (e_k, e_j) in edges
        and (e_k[activityName_key], deleted_activities[0]) in model_causal_relations
        and (deleted_activities[-1], e_i[activityName_key]) in model_causal_relations
        and any((e_l, e_j) in edges for e_l in trace[i+1:j])
    }

    new_edges = edges.difference(w_r1.union(w_r2))
    for k in reversed(range(1,i)):
        e_k = trace[k]
        for j in range(i, len(trace)):
            e_j = trace[j]
            if (e_k[activityName_key], deleted_activities[0]) in model_causal_relations \
            and (deleted_activities[-1], e_j[activityName_key]) in model_causal_relations \
            and not _sequence_in_edges(tuple(evt[activityName_key] for evt in trace[k:j+1]), new_edges) \
            and (not any((e_k, e_l) in new_edges for e_l in trace[k+1:j]) \
            or not any((e_m, e_j) in new_edges for e_m in trace[k+1:i])):
                new_edges.add((e_k, e_j))
    return new_edges

def insertion_repair(trace: Trace, edges: Set[Tuple[str, str]], insertion_index: int, inserted_activities: List[str], model_causal_relations: List[Tuple[str, str]], activityName_key:str=xes.DEFAULT_NAME_KEY) -> Set[Tuple[str,str]]:
    i = insertion_index
    j = i + len(inserted_activities) - 1

    w_r1 = {
        (e_k, e_l)
        for (e_k, e_l) in edges
        if _get_event_index(trace, e_k) < i
        if i <= _get_event_index(trace, e_l) <= j 
    }

    w_r2 = {
        (e_k, e_l)
        for (e_k, e_l) in edges
        if i <= _get_event_index(trace, e_k) <= j 
        if j < _get_event_index(trace, e_l)
    }

    w_r3 = {
        (e_k, e_l)
        for (e_k, e_l) in edges
        if i <= _get_event_index(trace, e_k) <= j 
        if i <= _get_event_index(trace, e_l) <= j 
    }

    new_edges = edges.difference(w_r1.union(w_r2).union(w_r3))

    w_a1 = set()
    w_a2 = set()
    for k, e_k in enumerate(trace[j+1:], start=j+1):
        if (e_k[activityName_key] not in inserted_activities) and ((trace[i-1][activityName_key], e_k[activityName_key]) in model_causal_relations or (trace[i-1], e_k) in edges) \
        and not _sequence_in_edges(tuple(evt[activityName_key] for evt in trace[j:k+1]), new_edges):
            new_edges.add((trace[j], e_k))
            w_a1.add((trace[j], e_k))
    if i>0 and i<len(trace)-1 and (trace[i-1][activityName_key], trace[i+1][activityName_key]) not in model_causal_relations:
        new_edges.add((trace[i-1], trace[i]))
        w_a2.add((trace[i-1], trace[i]))
    else:
        for k in reversed(range(1,i)):
            e_k = trace[k]
            if e_k[activityName_key] not in inserted_activities \
            and ((e_k[activityName_key], trace[j+1][activityName_key]) in model_causal_relations or (e_k, trace[j+1]) in edges) \
            and not _sequence_in_edges(tuple(evt[activityName_key] for evt in trace[k:i+1]), new_edges):
                new_edges.add((e_k, trace[i]))
                w_a2.add((e_k, trace[i]))
    w_a3 = { (trace[k], trace[k+1]) for k in range(max(0,i-1), j-1) }
    new_edges = new_edges.union(w_a3)
    w_r4 = {
        (e_k, e_l)
        for (e_k, e_h) in w_a2
        for (e_p, e_l) in w_a1
        if any(evt[activityName_key] == e_h[activityName_key] for evt in trace[i:j+1])
        if any(evt[activityName_key] == e_p[activityName_key] for evt in trace[i:j+1])
    }

    new_edges = new_edges.difference(w_r4)
    if i>0 and i<len(trace)-1 and (trace[i-1][activityName_key], trace[i+1][activityName_key]) not in model_causal_relations:
        w_r5 = {(trace[i-1], e_k) for e_k in trace[i+1:]}
        new_edges = new_edges.difference(w_r5)

    return new_edges

def _get_event_index(case: Trace, event: Event):
    for i, e in enumerate(case):
        if e == event:
            return i
    return -1

def _sequence_in_edges(sequence: Tuple[str,...], edges: Set[Tuple[Event, Event]]):
    return all((sequence[i], sequence[i+1]) in edges for i in range(len(sequence)-1))

def irregular_graph_repairing(instance_graph: nx.DiGraph, trace: Trace, d: set, i: set, model_causal_relations: List[Tuple[str, str]], activityName_key:str=xes.DEFAULT_NAME_KEY):
    new_edges = set(instance_graph.edges)
    for idx, act in d:
        new_edges = deletion_repair(trace, new_edges, idx, act, model_causal_relations, activityName_key)
    for idx, act in i:
        new_edges = insertion_repair(trace, new_edges, idx, act, model_causal_relations, activityName_key)
    
    new_graph = nx.DiGraph()
    new_graph.update(nodes=instance_graph.nodes, edges=new_edges)
    return new_graph

def discover_instance_graphs_big(log:EventLog, model: Any, activityName_key:str=xes.DEFAULT_NAME_KEY) -> List[nx.DiGraph]:
    for case in log:
        for idx, evt in enumerate(case):
            evt["big-algorithm::index"] = idx
    
    model_footprint = footprints_discovery.apply(*model)    

    result = []
    for trace in tqdm(log, "Discovering Instance Graphs. Completed Traces"):
        instance_graph = extract_instance_graph(trace, model_footprint, activityName_key)
        i, d = _get_inserted_and_deleted_activities(trace, model)
        if len(d.union(i)) != 0:
            instance_graph = irregular_graph_repairing(instance_graph, trace, d, i, model_footprint['sequence'])
        relabeled_ig = nx.relabel_nodes(instance_graph, mapping={evt: (idx, evt[activityName_key]) for idx, evt in enumerate(trace)})
        relabeled_ig.caseid = trace.attributes[xes.DEFAULT_TRACEID_KEY]
        result.append(relabeled_ig)	
    return result

def make_training_data(log: EventLog, model: Tuple[PetriNet, Marking, Marking], activityName_key:str = xes.DEFAULT_NAME_KEY) -> List[Tuple[nx.DiGraph, str]]:
    instance_graphs = discover_instance_graphs_big(log, model, activityName_key)
    training_data = []
    for instance_graph in instance_graphs:
        if len(list(nx.simple_cycles(instance_graph))) > 0:
            continue
        nodes = instance_graph.nodes
        for g, node in enumerate(sorted(nodes, key=lambda node: node[0])[2:], start=2):
            node_index, node_label = node
            allowed_nodes = set(node for node in nodes if node[0] < g)
            subgraph = instance_graph.subgraph(allowed_nodes)
            subgraph.caseid = instance_graph.caseid
            training_data.append((subgraph, node_label))
    return training_data

class EnhancedBIGInstancegraphDataset(InMemoryDataset):
    def __init__(
        self,
        eventlog: EventLog,
        logname: str,
        root: str = "./data",
        transform=None,
        process_model: Tuple[PetriNet, Marking, Marking] = None,
        imf_noise_thresh: float = 0,
        force_reprocess: bool = False,
        case_level_attributes: List[str] = None,
        event_level_attributes: List[str] = None,
        z_score_normalize: bool = True,
    ):
        self.z_score_normalize = z_score_normalize
        self.case_level_attributes = case_level_attributes if case_level_attributes is not None else []
        self.event_level_attributes = event_level_attributes if event_level_attributes is not None else []
        self.eventlog = add_artificial_start_end_events(eventlog) if process_model is None else eventlog
        self.activities_index = list(sorted(list(set(evt[xes.DEFAULT_NAME_KEY] for case in self.eventlog for evt in case))))
        self.logname = logname
        self.process_model = process_model
        self.imf_noise_thresh = imf_noise_thresh
        self.force_reprocess = force_reprocess
        self.savefile = f"data_{self.logname}_enhanced.pt"

        self.case_attribute_vals = {attr: list(set(case.attributes.get(attr, None) for case in eventlog if case.attributes.get(attr, None) is not None)) for attr in self.case_level_attributes}
        self.categorical_case_attrs = {attr for attr, vals in self.case_attribute_vals.items() if any(isinstance(val, str) for val in vals)}
        self.case_attr_z_normalization = {}
        for attr in self.case_level_attributes:
            if attr not in self.categorical_case_attrs:
                vals = [case.attributes[attr] for case in eventlog if attr in case.attributes]
                if vals:
                    self.case_attr_z_normalization[attr] = (mean(vals), stdev(vals))

        self.event_attribute_vals = {attr: list(set(event.get(attr, None) for case in eventlog for event in case if event.get(attr, None) is not None)) for attr in self.event_level_attributes}
        self.categorical_event_attrs = {attr for attr, vals in self.event_attribute_vals.items() if any(isinstance(val, str) for val in vals)}
        self.event_attr_z_normalization = {}
        for attr in self.event_level_attributes:
            if attr not in self.categorical_event_attrs:
                vals = [event[attr] for case in eventlog for event in case if attr in event]
                if vals:
                    self.event_attr_z_normalization[attr] = (mean(vals), stdev(vals))

        super().__init__(root, transform)
        self.data, self.slices = torch.load(self.processed_paths[0], weights_only=False)

    @property
    def raw_file_names(self):
        return []

    @property
    def processed_file_names(self):
        return [self.savefile] if not self.force_reprocess else ["force-reprocess"]

    def process(self):
        if self.process_model is None:
            self.process_model = discover_model_imf(self.eventlog, self.imf_noise_thresh)

        data = make_training_data(self.eventlog, self.process_model, xes.DEFAULT_NAME_KEY)

        data_list = [self._networkx_to_pytorch_graph(graph, label) for graph, label in tqdm(data, desc="Converting networkx graphs to PyG Graphs")]

        data, slices = self.collate(data_list)
        torch.save((data, slices), self.processed_paths[0])

    def _make_feature_vector(self, node, caseid):
        idx, activity = node
        ret = np.zeros(len(self.activities_index) + 2)
        ret[0] = idx
        ret[self.activities_index.index(activity) + 1] = 1

        case = next((case for case in self.eventlog if case.attributes[xes.DEFAULT_TRACEID_KEY] == caseid), None)
        if case is None:
            raise ValueError(f"Case {caseid} not found in event log")
        if idx > 0:
            time_delta = (case[idx][xes.DEFAULT_TIMESTAMP_KEY] - case[idx - 1][xes.DEFAULT_TIMESTAMP_KEY]).total_seconds()
            ret[-1] = time_delta / 3600.0 if self.z_score_normalize else time_delta
        else:
            ret[-1] = 0.0

        if self.case_level_attributes:
            case_level_attrs = np.array([])
            for attr in self.case_level_attributes:
                val = case.attributes.get(attr, 0)
                if attr not in self.categorical_case_attrs:
                    if self.z_score_normalize and attr in self.case_attr_z_normalization:
                        m, std = self.case_attr_z_normalization[attr]
                        case_level_attrs = np.append(case_level_attrs, (val - m) / std if std > 0 else val)
                    else:
                        case_level_attrs = np.append(case_level_attrs, val)
                else:
                    if val in self.case_attribute_vals[attr]:
                        case_level_attrs = np.concatenate((case_level_attrs, self._one_hot_encode(val, self.case_attribute_vals[attr])))
                    else:
                        case_level_attrs = np.concatenate((case_level_attrs, np.zeros(len(self.case_attribute_vals[attr]))))
            ret = np.concatenate((ret, case_level_attrs))

        if self.event_level_attributes:
            event = case[idx]
            event_level_attrs = np.array([])
            for attr in self.event_level_attributes:
                val = event.get(attr, 0)
                if attr not in self.categorical_event_attrs:
                    if self.z_score_normalize and attr in self.event_attr_z_normalization:
                        m, std = self.event_attr_z_normalization[attr]
                        event_level_attrs = np.append(event_level_attrs, (val - m) / std if std > 0 else val)
                    else:
                        event_level_attrs = np.append(event_level_attrs, val)
                else:
                    if val in self.event_attribute_vals[attr]:
                        event_level_attrs = np.concatenate((event_level_attrs, self._one_hot_encode(val, self.event_attribute_vals[attr])))
                    else:
                        event_level_attrs = np.concatenate((event_level_attrs, np.zeros(len(self.event_attribute_vals[attr]))))
            ret = np.concatenate((ret, event_level_attrs))

        return ret

    def _one_hot_encode(self, value, index):
        ret = np.zeros(len(index))
        if value in index:
            ret[index.index(value)] = 1
        return ret

    def _networkx_to_pytorch_graph(self, graph: nx.DiGraph, label: str) -> Data:
        edge_index = torch.tensor(np.array([
            [edge[0][0], edge[1][0]]
            for edge in graph.edges
        ]), dtype=torch.int64)
        x = torch.tensor(np.array([self._make_feature_vector(node, graph.caseid) for node in sorted(graph.nodes, key=lambda v: v[0])]), dtype=torch.float32)
        data = Data(
            x=x,
            edge_index=edge_index.t().contiguous(),
            y=self._one_hot_encode(label, self.activities_index),
        )
        return data

class EnhancedDGCNN(nn.Module):

    def __init__(self,
            dataset: Dataset,
            graph_conv_layer_sizes: List[int],
            sort_pool_k: int,
            sizes_1d_convolutions: List[int],
            dense_layer_sizes: List[int],
            dropout_rate: float,
            learning_rate: float,
            activities_index: List[str],
            transformer_nhead: int = 8,
            transformer_dim_feedforward: int = 128,
            transformer_layers: int = 2,
            use_cuda_if_available: bool = True
        ):
        super().__init__()

        if use_cuda_if_available and torch.cuda.is_available():
            self.device = torch.device("cuda:0")
            print("Using GPU")
        else:
            self.device = torch.device("cpu")
            print("Using CPU")

        self.graph_conv_layer_sizes = graph_conv_layer_sizes
        self.sort_pool_k = sort_pool_k
        self.sizes_1d_convolutions = sizes_1d_convolutions
        self.dense_layer_sizes = dense_layer_sizes
        self.dropout_rate = dropout_rate
        self.learning_rate = learning_rate

        self.KERNEL_SIZE = min(sort_pool_k, len(graph_conv_layer_sizes))

        self.num_features = dataset.num_node_features
        self.num_output_features = len(activities_index)

        self.conv1 = SAGEConv(self.num_features, graph_conv_layer_sizes[0])
        self.convs = nn.ModuleList([SAGEConv(in_size, out_size) for in_size, out_size in zip(graph_conv_layer_sizes, graph_conv_layer_sizes[1:])])
        self.conv_norm = LayerNorm(graph_conv_layer_sizes[-1])

        transformer_layer = TransformerEncoderLayer(
            d_model=graph_conv_layer_sizes[-1],
            nhead=transformer_nhead,
            dim_feedforward=transformer_dim_feedforward,
            dropout=dropout_rate,
            batch_first=True
        )
        self.transformer = TransformerEncoder(transformer_layer, num_layers=transformer_layers)

        pooled_dim = self.sort_pool_k * graph_conv_layer_sizes[-1]
        self.gate = Linear(2 * pooled_dim, pooled_dim)

        self.conv1d = Conv1d(graph_conv_layer_sizes[-1], sizes_1d_convolutions[0], self.KERNEL_SIZE)
        self.conv1ds = nn.ModuleList([Conv1d(in_size, out_size, self.KERNEL_SIZE) for in_size, out_size in zip(sizes_1d_convolutions, sizes_1d_convolutions[1:])])
        self.conv1d_norm = LayerNorm(sizes_1d_convolutions[-1])

        input_dense_size = sizes_1d_convolutions[-1] * (self.sort_pool_k - self.KERNEL_SIZE + 1)
        self.linear = Linear(input_dense_size, dense_layer_sizes[0])
        self.linears = nn.ModuleList([Linear(in_size, out_size) for in_size, out_size in zip(dense_layer_sizes, dense_layer_sizes[1:])])
        self.linear_output = Linear(dense_layer_sizes[-1], self.num_output_features)

        self.attention_weights = None

    def reset_parameters(self):
        self.conv1.reset_parameters()
        for conv in self.convs:
            conv.reset_parameters()
        self.conv1d.reset_parameters()
        for conv1d in self.conv1ds:
            conv1d.reset_parameters()
        self.linear.reset_parameters()
        for linear in self.linears:
            linear.reset_parameters()
        self.linear_output.reset_parameters()
        self.gate.reset_parameters()

    def forward(self, data):
        x, edge_index, batch = data.x, data.edge_index, data.batch

        x = F.relu(self.conv1(x, edge_index))
        for conv in self.convs:
            x = F.relu(conv(x, edge_index))
        x_gnn = self.conv_norm(x)

        module = SortAggregation(k=self.sort_pool_k)
        x_pooled = module(x_gnn, batch)

        batch_size = x_pooled.size(0)
        feat = self.graph_conv_layer_sizes[-1]
        x_gnn_seq = x_pooled.view(batch_size, self.sort_pool_k, feat)

        x_transformer_seq = self.transformer(x_gnn_seq)

        self.attention_weights = self.transformer.layers[-1].self_attn(x_gnn_seq, x_gnn_seq, x_gnn_seq)[1]

        x_gnn = x_gnn_seq.view(batch_size, -1)
        x_transformer = x_transformer_seq.view(batch_size, -1)

        x_combined = torch.cat([x_gnn, x_transformer], dim=-1)
        gate = torch.sigmoid(self.gate(x_combined))
        x = gate * x_gnn + (1 - gate) * x_transformer

        x = x.view(batch_size, self.sort_pool_k, feat).permute(0, 2, 1)
        x = F.relu(self.conv1d(x))
        for conv1d in self.conv1ds:
            x = F.relu(conv1d(x))
        
        # Permute to apply LayerNorm on the channel dimension
        x = x.permute(0, 2, 1)  # [batch, length, channels]
        x = self.conv1d_norm(x)
        x = x.permute(0, 2, 1)  # back to [batch, channels, length]

        x = x.reshape(batch_size, -1)

        x = F.dropout(x, p=self.dropout_rate, training=self.training)

        x = F.relu(self.linear(x))
        for linear in self.linears:
            x = F.relu(linear(x))
        x = self.linear_output(x)
        return x

    def __repr__(self):
        params = {
            "Graph Conv. Layer Sizes": self.graph_conv_layer_sizes,
            "Sort Pool K": self.sort_pool_k,
            "1D Conv. Sizes": self.sizes_1d_convolutions,
            "Dense Layer Sizes": self.dense_layer_sizes,
            "Dropout Rate": self.dropout_rate,
            "Learning Rate": self.learning_rate,
            "Distinct Activities": self.num_output_features,
        }
        return self.__class__.__name__ + " Model: " + str(params)

class EnhancedBIGDGCNN:
    
    def __init__(self,
                 layer_sizes: List[int],
                 sort_pooling_k: int,
                 sizes_1d_convolutions: List[int] = [32],
                 dense_layer_sizes: List[int] = [32],
                 dropout_rate: float = 0.1,
                 learning_rate: float = 1e-3,
                 batch_size: int = 32,
                 epochs: int = 100,
                 transformer_nhead: int = 8,
                 transformer_dim_feedforward: int = 128,
                 transformer_layers: int = 2,
                 seed: Optional[int] = None,
                use_cuda_if_available: bool = True
                ):
        if seed is not None:
            seed_everything(seed)
        self.seed = seed

        self.layer_sizes = layer_sizes
        self.sort_pooling_k = sort_pooling_k
        self.sizes_1d_convolutions = sizes_1d_convolutions
        self.dense_layer_sizes = dense_layer_sizes
        self.dropout_rate = dropout_rate
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.epochs = epochs
        self.transformer_nhead = transformer_nhead
        self.transformer_dim_feedforward = transformer_dim_feedforward
        self.transformer_layers = transformer_layers
        self.use_cuda_if_available = use_cuda_if_available

    def train(self, 
                  log: EventLog,
                  logname: str,
                  process_model: Optional[Tuple[PetriNet, Marking, Marking]]=None,
                  imf_noise_thresh: Optional[float] =None,
                  train_test_split: float=0.67,
                  train_validation_split: float=0.8,
                  activityName_key:str=xes.DEFAULT_NAME_KEY,
                  torch_load_path:  Optional[str] =None,
                  case_level_attributes: Optional[List[str]] =None,
                  event_level_attributes: Optional[List[str]] =None,
                  force_reprocess_dataset: bool=False
                ):
        case_level_attributes = case_level_attributes if case_level_attributes is not None else []
        event_level_attributes = event_level_attributes if event_level_attributes is not None else []

        log = add_artificial_start_end_events(log, activityName_key=activityName_key)
        if process_model is None:
            if imf_noise_thresh is not None:
                process_model = discover_model_imf(log, imf_noise_thresh)
            else:
                noise_thresh = 1.0
                condition = True
                while condition:
                    process_model = discover_model_imf(log, noise_thresh)
                    noise_thresh -= 0.1
                    fitness_results = replay_fitness.apply(
                        log,
                        *process_model,
                        variant=replay_fitness.Variants.TOKEN_BASED,
                        parameters={'show_progress_bar': False}
                    )
                    condition = fitness_results['percentage_of_fitting_traces'] < 0.9 and noise_thresh >= 0  
                print(f"Discovered model using IMf with noise threshold {noise_thresh+0.1}")
        self.process_model = process_model
        self.dataset = EnhancedBIGInstancegraphDataset(
            log,
            logname + f"_noisethresh_{int((noise_thresh+0.1)*100)}",
            process_model=process_model,
            case_level_attributes=case_level_attributes,
            event_level_attributes=event_level_attributes,
            force_reprocess=force_reprocess_dataset
        )

        self.activities_index = self.dataset.activities_index

        self.train_split, self.test_split = sklearn_train_test_split(self.dataset, train_size=train_test_split, shuffle=False, random_state=self.seed)
        self.train_split, self.validation_split = sklearn_train_test_split(self.train_split, train_size=train_validation_split, shuffle=False, random_state=self.seed)

        self.train_data = DataLoader(self.train_split, batch_size=self.batch_size, shuffle=True)
        self.validation_data = DataLoader(self.validation_split, batch_size=self.batch_size, shuffle=True)
        self.test_data = DataLoader(self.test_split, batch_size=self.batch_size, shuffle=True)


        if torch_load_path is not None:
            self.model = torch.load(torch_load_path, weights_only=False)
            print(f"Model loaded from {torch_load_path}")
        else:
            self.model = EnhancedDGCNN(
                dataset=self.dataset,
                graph_conv_layer_sizes=self.layer_sizes,
                sort_pool_k=self.sort_pooling_k,
                sizes_1d_convolutions=self.sizes_1d_convolutions,
                dense_layer_sizes=self.dense_layer_sizes,
                dropout_rate=self.dropout_rate,
                learning_rate=self.learning_rate,
                activities_index=self.activities_index,
                transformer_nhead=self.transformer_nhead,
                transformer_dim_feedforward=self.transformer_dim_feedforward,
                transformer_layers=self.transformer_layers,
                use_cuda_if_available=self.use_cuda_if_available
            )
            self.model = self.model.to(self.model.device)

            self._training_loop()
            print(f"Training Completed")

        self.test_accuracy = self.evaluate(self.test_data)*100
        print(f"Accuracy on Test Set: {self.test_accuracy:.4f}%")

    def _training_loop(self):
        self.model.train(True)

        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.learning_rate)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=10)
        criterion = torch.nn.CrossEntropyLoss()

        self.train_losses = []
        self.validation_losses = []

        self.train_accuracies = []
        self.validation_accuracies = []

        for epoch in range(self.epochs):
            self.model.train(True)
            train_loss = 0
            for b in self.train_data:
                batch = b.to(self.model.device)
                optimizer.zero_grad(set_to_none=True)

                out = self.model(batch)
                label = batch.y.view(out.shape[0],-1)

                loss = criterion(out, label)

                loss.backward()
                optimizer.step()
                train_loss += loss.item()

            valid_loss = 0

            for b in self.validation_data:
                batch = b.to(self.model.device)
                out = self.model(batch)
                label = batch.y.view(out.shape[0],-1)
                loss = criterion(out, label)
                valid_loss += loss.item()
            this_epoch_losses = (train_loss/len(self.train_data), valid_loss/len(self.validation_data))
            scheduler.step(this_epoch_losses[1])
            valid_accuracy = self.evaluate(self.validation_data)
            print(f"Epoch {epoch+1} completed. Train. Loss: {this_epoch_losses[0]}, Valid. Loss: {this_epoch_losses[1]}; Valid. Accuracy: {valid_accuracy*100:.4f}%")

            self.train_losses.append(this_epoch_losses[0])
            self.validation_losses.append(this_epoch_losses[1])

            self.train_accuracies.append(self.evaluate(self.train_data))
            self.validation_accuracies.append(valid_accuracy)


    def evaluate(self, test_dataset: DataLoader) -> float:
        num_correct = 0
        total = 0
        self.model.eval()

        with torch.no_grad():
            for b in test_dataset:
                batch = b.to(self.model.device)

                out = self.model(batch)
                label = batch.y.view(out.shape)

                predictions = torch.argmax(out, dim=1)
                ground_truth = torch.argmax(label, dim=1).to(self.model.device)

                total += len(predictions)
                num_correct += torch.sum(predictions == ground_truth).item()
        return num_correct/total


    def evaluate_for_activity_set(self, test_dataset: DataLoader, activities: List[str], return_total: bool=False):
        num_correct = 0
        total = 0
        self.model.eval()

        with torch.no_grad():
            for b in test_dataset:
                batch = b.to(self.model.device)

                out = self.model(batch)
                label = batch.y.view(out.shape)

                predictions = torch.argmax(out, dim=1)
                ground_truth = torch.argmax(label, dim=1).to(self.model.device)


                considered = [
                    (prediction, ground_truth)
                    for prediction, ground_truth in zip(predictions, ground_truth)
                    if self.activities_index[ground_truth.item()] in activities
                ]
                total += len(considered)
                num_correct += len([x for x in considered if x[0] == x[1]])
        return num_correct/total if not return_total else (num_correct/total, total)

    def save(self, path: str):
        torch.save(self.model, path)

    def plot_training_history(self) -> plt.Figure:
        fig, ax = plt.subplots(2, 1, figsize=(8, 10))

        ax[0].plot(self.train_accuracies, label="Train")
        ax[0].plot(self.validation_accuracies, label="Validation")
        ax[0].set_ylabel("Accuracy", fontsize=14)

        ax[1].plot(self.train_losses, label="Train")
        ax[1].plot(self.validation_losses, label="Validation")
        ax[1].set_ylabel("Loss", fontsize=14)

        ax[1].set_xlabel("Epoch", fontsize=14)
        ax[0].legend(loc="upper right")
        ax[1].legend(loc="upper right")

        return fig

    def visualize_attention(self, data: Data) -> plt.Figure:
        self.model.eval()
        with torch.no_grad():
            _ = self.model(data.to(self.model.device))
            attn_weights = self.model.attention_weights[0].mean(dim=0).cpu().numpy()  # Average over heads, take first batch
        fig, ax = plt.subplots(figsize=(10, 8))
        im = ax.imshow(attn_weights, cmap='viridis')
        ax.set_title("Transformer Attention Weights")
        ax.set_xlabel("Node Index")
        ax.set_ylabel("Node Index")
        fig.colorbar(im)
        return fig

# Example usage
if __name__ == "__main__":
    log = read_xes("BPI_Challenge_2012.xes.gz")
    model = EnhancedBIGDGCNN(
        sort_pooling_k=30,
        layer_sizes=[32] * 4,
        batch_size=32,
        learning_rate=1e-3,
        dropout_rate=0.1,
        dense_layer_sizes=[32],
        epochs=100,
        transformer_nhead=8,
        transformer_dim_feedforward=128,
        transformer_layers=2,
        seed=42
    )
    model.train(
        log,
        logname="bpi2012_enhanced",
        case_level_attributes=["AMOUNT_REQ"],
        event_level_attributes=["org:resource"],
        force_reprocess_dataset=True
    )
    fig = model.plot_training_history()
    plt.show()