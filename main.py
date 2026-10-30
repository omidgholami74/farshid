import math
import os
import json
import copy
import time
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import partial

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from tqdm.auto import tqdm
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    confusion_matrix, classification_report,
    precision_recall_fscore_support, accuracy_score,
    mean_absolute_error, mean_squared_error, r2_score,
    top_k_accuracy_score
)
from torch.optim.swa_utils import AveragedModel, SWALR

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

import pm4py.util.xes_constants as xes
from pm4py import read_xes

# ===========================================================================
# پشتیبانی فونت فارسی
# ===========================================================================
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_RTL = True
except ImportError:
    HAS_RTL = False
    print("[Warning] arabic_reshaper یا python-bidi نصب نیست.")


def fa(text):
    if not HAS_RTL:
        return text
    return get_display(arabic_reshaper.reshape(str(text)))


FONT_PATH = "Vazirmatn-Regular.ttf"
if os.path.exists(FONT_PATH):
    fm.fontManager.addfont(FONT_PATH)
    plt.rcParams['font.family'] = fm.FontProperties(fname=FONT_PATH).get_name()
else:
    plt.rcParams['font.family'] = 'DejaVu Sans'

plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['savefig.bbox'] = 'tight'

OUTPUT_DIR = "results_tri_stream"
os.makedirs(OUTPUT_DIR, exist_ok=True)
FIG_DIR = os.path.join(OUTPUT_DIR, "figures")
os.makedirs(FIG_DIR, exist_ok=True)


# ===========================================================================
# تابع کمکی: تبدیل هر شیء به نوع قابل JSON
# ===========================================================================
def to_python(v):
    if isinstance(v, torch.Tensor):
        return v.item() if v.numel() == 1 else v.tolist()
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, (np.floating, np.integer)):
        return v.item()
    if isinstance(v, dict):
        return {k: to_python(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [to_python(x) for x in v]
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


# ===========================================================================
# 1) آمار Case
# ===========================================================================
@dataclass
class CaseStatistics:
    case_id: str
    total_duration: float = 0.0
    activity_durations: dict = field(default_factory=dict)
    activity_counts: dict = field(default_factory=dict)
    wait_times: list = field(default_factory=list)
    active_times: list = field(default_factory=list)
    remaining_time_at_pos: dict = field(default_factory=dict)
    bottleneck_activities: set = field(default_factory=set)


def compute_case_statistics(case, activity_name_key, timestamp_key):
    stats = CaseStatistics(case_id=str(case.attributes.get(xes.DEFAULT_TRACEID_KEY, "")))
    events = list(case)
    if len(events) < 2:
        return stats

    timestamps = []
    activities = []
    for evt in events:
        if timestamp_key not in evt:
            continue
        timestamps.append(evt[timestamp_key])
        activities.append(evt[activity_name_key])

    if len(timestamps) < 2:
        return stats

    stats.total_duration = (timestamps[-1] - timestamps[0]).total_seconds()

    for i, ts in enumerate(timestamps):
        remaining = (timestamps[-1] - ts).total_seconds()
        stats.remaining_time_at_pos[i] = remaining

    waits = []
    for i in range(1, len(timestamps)):
        delta = (timestamps[i] - timestamps[i - 1]).total_seconds()
        waits.append(delta)
        act = activities[i - 1]
        stats.activity_durations[act] = stats.activity_durations.get(act, 0.0) + delta
        stats.activity_counts[act] = stats.activity_counts.get(act, 0) + 1

    stats.wait_times = waits

    if waits:
        threshold = np.percentile(waits, 75)
        for i in range(1, len(timestamps)):
            if waits[i - 1] >= threshold and waits[i - 1] > 0:
                stats.bottleneck_activities.add(activities[i - 1])

    return stats


# ===========================================================================
# 2) دیتاست چند-وظیفه‌ای
# ===========================================================================
class MultiTaskProcessDataset(Dataset):
    def __init__(
        self,
        eventlog,
        activities_index,
        activity_mean_wait=None,
        max_seq_len: int = 100,
        min_prefix_len: int = 2,
        use_time: bool = True,
        activity_name_key: str = xes.DEFAULT_NAME_KEY,
        timestamp_key: str = xes.DEFAULT_TIMESTAMP_KEY,
    ):
        self.activities_index = activities_index
        self.activity_to_id = {a: i for i, a in enumerate(activities_index)}
        self.max_seq_len = max_seq_len
        self.use_time = use_time
        self.num_activities = len(activities_index)

        if activity_mean_wait is None:
            activity_mean_wait = self._compute_activity_mean_wait(
                eventlog, activity_name_key, timestamp_key
            )
        self.activity_mean_wait = activity_mean_wait
        self.global_mean_wait = float(np.mean(list(activity_mean_wait.values()))) \
            if activity_mean_wait else 0.0

        self.samples = []
        self.case_ids = []
        self.case_stats = {}

        for case_idx, case in enumerate(eventlog):
            stats = compute_case_statistics(case, activity_name_key, timestamp_key)
            self.case_stats[stats.case_id] = stats

        for case_idx, case in enumerate(eventlog):
            case_id = str(case.attributes.get(xes.DEFAULT_TRACEID_KEY, case_idx))
            stats = self.case_stats.get(case_id)
            if stats is None or stats.total_duration <= 0:
                continue

            activities = []
            positions = []
            time_deltas = []
            cumulative_times = []
            remaining_times = []
            next_waits = []

            prev_ts = None
            start_ts = None

            for idx, evt in enumerate(case):
                act = evt[activity_name_key]
                if act not in self.activity_to_id:
                    continue
                act_id = self.activity_to_id[act]
                activities.append(act_id)
                positions.append(idx)

                if use_time and timestamp_key in evt:
                    ts = evt[timestamp_key]
                    if start_ts is None:
                        start_ts = ts
                    delta = (ts - prev_ts).total_seconds() if prev_ts is not None else 0.0
                    time_deltas.append(delta)
                    cum = (ts - start_ts).total_seconds()
                    cumulative_times.append(cum)
                    prev_ts = ts
                else:
                    time_deltas.append(0.0)
                    cumulative_times.append(0.0)

                remaining_times.append(stats.remaining_time_at_pos.get(idx, 0.0))

            for i in range(len(activities)):
                if i + 1 < len(activities):
                    next_waits.append(time_deltas[i + 1])
                else:
                    next_waits.append(0.0)

            if len(activities) < min_prefix_len + 1:
                continue

            L = len(activities)
            for i in range(min_prefix_len, L):
                prefix_acts = activities[:i]
                prefix_pos = positions[:i]
                prefix_dt = time_deltas[:i]
                prefix_cum = cumulative_times[:i]
                target_activity = activities[i]
                remaining_at_pred = remaining_times[i]

                actual_next_wait = next_waits[i]
                target_act_name = activities_index[target_activity]
                expected_wait = self.activity_mean_wait.get(
                    target_act_name, self.global_mean_wait
                )
                improvement = expected_wait - actual_next_wait

                if len(prefix_acts) > max_seq_len:
                    prefix_acts = prefix_acts[-max_seq_len:]
                    prefix_pos = prefix_pos[-max_seq_len:]
                    prefix_dt = prefix_dt[-max_seq_len:]
                    prefix_cum = prefix_cum[-max_seq_len:]

                self.samples.append({
                    "prefix_acts": prefix_acts,
                    "prefix_pos": prefix_pos,
                    "prefix_dt": prefix_dt,
                    "prefix_cum": prefix_cum,
                    "target_activity": target_activity,
                    "remaining_time": remaining_at_pred,
                    "improvement": improvement,
                    "total_duration": stats.total_duration,
                })
                self.case_ids.append(case_id)

        print(f"[Dataset] تعداد نمونه‌ها: {len(self.samples)}")
        print(f"[Dataset] تعداد caseها: {len(set(self.case_ids))}")
        print(f"[Dataset] میانگین wait سراسری: {self.global_mean_wait:.2f}s")

    @staticmethod
    def _compute_activity_mean_wait(eventlog, activity_name_key, timestamp_key):
        waits = defaultdict(list)
        for case in eventlog:
            events = [(e[timestamp_key], e[activity_name_key])
                      for e in case if timestamp_key in e]
            for i in range(len(events) - 1):
                ts1, act = events[i]
                ts2, _ = events[i + 1]
                waits[act].append((ts2 - ts1).total_seconds())
        return {a: float(np.mean(v)) for a, v in waits.items() if v}

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        s = self.samples[idx]
        acts = s["prefix_acts"]
        seq_len = len(acts)
        pad_len = self.max_seq_len - seq_len

        acts_padded = acts + [0] * pad_len
        pos_padded = s["prefix_pos"] + [0] * pad_len
        dt_padded = s["prefix_dt"] + [0.0] * pad_len
        cum_padded = s["prefix_cum"] + [0.0] * pad_len
        mask = [1] * seq_len + [0] * pad_len

        prev_acts = [0] + acts[:-1]
        prev_acts_padded = prev_acts + [0] * pad_len

        role = torch.zeros(self.max_seq_len, 2)
        role[0, 0] = 1.0
        role[seq_len - 1, 1] = 1.0

        freq = torch.zeros(self.num_activities)
        for a in acts:
            freq[a] += 1
        freq = freq / max(seq_len, 1)

        remaining_norm = math.log1p(max(s["remaining_time"], 0.0))
        improvement_norm = math.tanh(s["improvement"] / 3600.0)

        return {
            "activities": torch.tensor(acts_padded, dtype=torch.long),
            "prev_activities": torch.tensor(prev_acts_padded, dtype=torch.long),
            "positions": torch.tensor(pos_padded, dtype=torch.long),
            "time_deltas": torch.tensor(dt_padded, dtype=torch.float32),
            "cumulative_times": torch.tensor(cum_padded, dtype=torch.float32),
            "role": role,
            "activity_freq": freq,
            "mask": torch.tensor(mask, dtype=torch.bool),
            "seq_len": torch.tensor(seq_len, dtype=torch.long),
            "target_activity": torch.tensor(s["target_activity"], dtype=torch.long),
            "target_remaining": torch.tensor(remaining_norm, dtype=torch.float32),
            "target_improvement": torch.tensor(improvement_norm, dtype=torch.float32),
            "raw_remaining": torch.tensor(s["remaining_time"], dtype=torch.float32),
            "raw_improvement": torch.tensor(s["improvement"], dtype=torch.float32),
        }


# ===========================================================================
# 3) Graph Builder
# ===========================================================================
class PrefixGraphBuilder:
    def __init__(self, time_threshold_seconds=3600.0, max_nodes=64):
        self.time_threshold = time_threshold_seconds
        self.max_nodes = max_nodes

    def build(self, activities, time_deltas, max_seq_len):
        L = len(activities)
        if L > max_seq_len:
            activities = activities[-max_seq_len:]
            time_deltas = time_deltas[-max_seq_len:]
            L = max_seq_len

        N = L + 1
        node_acts = [0] + list(activities)
        node_dt = [0.0] + list(time_deltas)
        node_pos = [-1] + list(range(L))

        max_dt = max(time_deltas) if time_deltas else 1.0
        max_dt = max(max_dt, 1.0)
        dt_norm = [min(d / max_dt, 1.0) for d in node_dt]
        pos_norm = [p / max(L, 1) for p in node_pos]

        edges = []

        for i in range(1, N):
            edges.append((0, i))
            edges.append((i, 0))

        for i in range(1, N - 1):
            edges.append((i, i + 1))
            edges.append((i + 1, i))

        act_to_nodes = {}
        for i in range(1, N):
            act = node_acts[i]
            act_to_nodes.setdefault(act, []).append(i)

        for act, nodes in act_to_nodes.items():
            if 1 < len(nodes) <= 8:
                for j in range(len(nodes)):
                    for k in range(j + 1, len(nodes)):
                        edges.append((nodes[j], nodes[k]))
                        edges.append((nodes[k], nodes[j]))

        for i in range(1, N - 1):
            if node_dt[i + 1] < self.time_threshold:
                edges.append((i, i + 1))
                edges.append((i + 1, i))

        edges = list(set(edges))

        if len(edges) == 0:
            edge_index = torch.zeros((2, 0), dtype=torch.long)
        else:
            edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()

        node_features = torch.tensor(
            [[node_acts[i], dt_norm[i], pos_norm[i]] for i in range(N)],
            dtype=torch.float32,
        )

        node_mask = torch.ones(N, dtype=torch.bool)

        return {
            "node_activities": torch.tensor(node_acts, dtype=torch.long),
            "node_features": node_features,
            "edge_index": edge_index,
            "node_mask": node_mask,
            "num_nodes": N,
        }


def collate_with_graphs(batch_list, max_seq_len=100):
    graph_builder = PrefixGraphBuilder()

    node_acts_list = []
    node_feats_list = []
    edge_index_list = []
    node_offsets = []
    offset = 0

    for sample in batch_list:
        acts = sample["activities"].tolist()
        seq_len = int(sample["mask"].sum().item())
        acts = acts[:seq_len]
        dts = sample["time_deltas"][:seq_len].tolist()

        g = graph_builder.build(acts, dts, max_seq_len)

        node_acts_list.append(g["node_activities"])
        node_feats_list.append(g["node_features"])
        edge_index_list.append(g["edge_index"])
        node_offsets.append(offset)
        offset += g["num_nodes"]

    max_nodes = max(g.size(0) for g in node_acts_list)
    N_feat = node_feats_list[0].size(-1)

    node_acts_padded = torch.zeros(len(batch_list), max_nodes, dtype=torch.long)
    node_feats_padded = torch.zeros(len(batch_list), max_nodes, N_feat)
    node_mask = torch.zeros(len(batch_list), max_nodes, dtype=torch.bool)

    for i, (na, nf) in enumerate(zip(node_acts_list, node_feats_list)):
        n = na.size(0)
        node_acts_padded[i, :n] = na
        node_feats_padded[i, :n] = nf
        node_mask[i, :n] = True

    keys_to_stack = [
        "activities", "prev_activities", "positions", "time_deltas",
        "cumulative_times", "role", "activity_freq", "mask", "seq_len",
        "target_activity", "target_remaining", "target_improvement",
        "raw_remaining", "raw_improvement",
    ]
    out = {}
    for k in keys_to_stack:
        out[k] = torch.stack([s[k] for s in batch_list], dim=0)

    out["graph"] = {
        "node_activities": node_acts_padded,
        "node_features": node_feats_padded,
        "node_mask": node_mask,
        "edge_index_list": edge_index_list,
        "node_offsets": torch.tensor(node_offsets, dtype=torch.long),
    }
    return out


# ===========================================================================
# 4) بلوک‌های معماری
# ===========================================================================
class RelativePositionEncoding(nn.Module):
    def __init__(self, d_model, max_distance=128):
        super().__init__()
        self.max_distance = max_distance
        self.embedding = nn.Embedding(2 * max_distance + 1, d_model)

    def forward(self, length, device):
        range_vec = torch.arange(length, device=device)
        rel = range_vec.unsqueeze(0) - range_vec.unsqueeze(1)
        rel = rel.clamp(-self.max_distance, self.max_distance)
        rel = rel + self.max_distance
        return self.embedding(rel)


class TemporalConvBlock(nn.Module):
    def __init__(self, d_model, kernel_size=3, dilations=(1, 2, 4)):
        super().__init__()
        self.convs = nn.ModuleList()
        self.norms = nn.ModuleList()
        for d in dilations:
            padding = (kernel_size - 1) * d // 2
            self.convs.append(
                nn.Conv1d(d_model, d_model, kernel_size,
                          padding=padding, dilation=d)
            )
            self.norms.append(nn.LayerNorm(d_model))

    def forward(self, x, mask):
        h = x.transpose(1, 2)
        for conv, norm in zip(self.convs, self.norms):
            y = conv(h)
            y = y.transpose(1, 2)
            y = norm(y)
            y = F.gelu(y)
            y = y * mask.unsqueeze(-1).float()
            x = x + y
        return x


class CrossAttentionFusion(nn.Module):
    def __init__(self, d_model, nhead=8, dropout=0.1):
        super().__init__()
        self.attn = nn.MultiheadAttention(
            d_model, nhead, dropout=dropout, batch_first=True
        )
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.ffn = nn.Sequential(
            nn.Linear(d_model, d_model * 2), nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model * 2, d_model),
        )
        self.dropout = nn.Dropout(dropout)

    def forward(self, query, key_value, key_padding_mask=None):
        attn_out, _ = self.attn(
            query, key_value, key_value,
            key_padding_mask=key_padding_mask
        )
        x = self.norm1(query + self.dropout(attn_out))
        ffn_out = self.ffn(x)
        x = self.norm2(x + self.dropout(ffn_out))
        return x


class GraphConvLayer(nn.Module):
    def __init__(self, in_dim, out_dim, dropout=0.1):
        super().__init__()
        self.linear = nn.Linear(in_dim, out_dim)
        self.gate = nn.Linear(in_dim, out_dim)
        self.norm = nn.LayerNorm(out_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x, edge_index):
        N = x.size(0)
        if edge_index.size(1) == 0:
            out = self.linear(x)
        else:
            src, dst = edge_index[0], edge_index[1]
            msg = x[src]
            agg = torch.zeros_like(x)
            count = torch.zeros(N, 1, device=x.device)
            agg.index_add_(0, dst, msg)
            count.index_add_(0, dst, torch.ones_like(msg[:, :1]))
            agg = agg / count.clamp(min=1)
            out = self.linear(agg + x)

        gate = torch.sigmoid(self.gate(x))
        out = out * gate
        out = self.norm(out)
        out = F.gelu(out)
        out = self.dropout(out)
        return out


class PrefixGNN(nn.Module):
    def __init__(self, num_activities, d_model=256, num_layers=2, dropout=0.1):
        super().__init__()
        self.d_model = d_model
        self.node_act_embed = nn.Embedding(num_activities, d_model, padding_idx=0)
        self.node_feat_encoder = nn.Sequential(
            nn.Linear(2, d_model),
            nn.GELU(),
            nn.Linear(d_model, d_model),
        )
        self.gnn_layers = nn.ModuleList([
            GraphConvLayer(d_model, d_model, dropout)
            for _ in range(num_layers)
        ])
        self.final_norm = nn.LayerNorm(d_model)

    def forward(self, graph_batch):
        node_acts = graph_batch["node_activities"]
        node_feats = graph_batch["node_features"]
        node_mask = graph_batch["node_mask"]
        edge_index_list = graph_batch["edge_index_list"]
        node_offsets = graph_batch["node_offsets"]

        B, N_max = node_acts.shape

        x_act = self.node_act_embed(node_acts)
        x_num = self.node_feat_encoder(node_feats[:, :, 1:])
        x = x_act + x_num

        x_flat = x.reshape(B * N_max, self.d_model)
        mask_flat = node_mask.reshape(B * N_max)

        all_edges = []
        for b, ei in enumerate(edge_index_list):
            if ei.size(1) > 0:
                offset = node_offsets[b].item()
                all_edges.append(ei + offset)
        if all_edges:
            edge_index = torch.cat(all_edges, dim=1)
        else:
            edge_index = torch.zeros((2, 0), dtype=torch.long, device=x.device)

        x_flat = x_flat * mask_flat.unsqueeze(-1).float()

        for layer in self.gnn_layers:
            x_flat = layer(x_flat, edge_index)

        x_flat = x_flat * mask_flat.unsqueeze(-1).float()
        x_flat = self.final_norm(x_flat)

        x = x_flat.reshape(B, N_max, self.d_model)
        cls_repr = x[:, 0, :]

        mask_f = node_mask.unsqueeze(-1).float()
        mean_repr = (x * mask_f).sum(dim=1) / mask_f.sum(dim=1).clamp(min=1)

        pooled = cls_repr + mean_repr
        return pooled


# ===========================================================================
# 5) مدل Tri-Stream اصلی
# ===========================================================================
class DelayAwareTriStreamTransformer(nn.Module):
    def __init__(
        self,
        num_activities: int,
        d_model: int = 256,
        nhead: int = 8,
        num_layers: int = 6,
        dim_feedforward: int = 1024,
        dropout: float = 0.05,
        max_seq_len: int = 100,
        max_position: int = 4000,
        use_time: bool = True,
        pooling: str = "last",
        tie_weights: bool = True,
        gnn_layers: int = 2,
    ):
        super().__init__()
        self.d_model = d_model
        self.max_seq_len = max_seq_len
        self.use_time = use_time
        self.pooling = pooling
        self.num_activities = num_activities

        self.activity_embed = nn.Embedding(num_activities, d_model, padding_idx=0)
        self.prev_activity_embed = nn.Embedding(num_activities, d_model, padding_idx=0)
        self.pos_embed = nn.Embedding(max_position, d_model)
        self.rel_pos = RelativePositionEncoding(d_model, max_distance=128)

        if use_time:
            self.time_encoder = nn.Sequential(
                nn.Linear(1, d_model), nn.GELU(),
                nn.Linear(d_model, d_model), nn.LayerNorm(d_model),
            )
            self.cumtime_encoder = nn.Sequential(
                nn.Linear(1, d_model), nn.GELU(),
                nn.Linear(d_model, d_model), nn.LayerNorm(d_model),
            )

        self.role_encoder = nn.Linear(2, d_model)
        self.freq_encoder = nn.Linear(num_activities, d_model)

        self.input_norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=dim_feedforward,
            dropout=dropout, activation="gelu", batch_first=True, norm_first=False,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.final_norm = nn.LayerNorm(d_model)

        self.tcn = TemporalConvBlock(d_model, kernel_size=3, dilations=(1, 2, 4))

        self.gnn = PrefixGNN(
            num_activities=num_activities,
            d_model=d_model,
            num_layers=gnn_layers,
            dropout=dropout,
        )

        self.fusion_12 = CrossAttentionFusion(d_model, nhead=nhead, dropout=dropout)

        self.gnn_proj = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.LayerNorm(d_model),
            nn.GELU(),
        )
        self.tri_fusion = nn.Sequential(
            nn.Linear(d_model * 3, d_model * 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model * 2, d_model),
            nn.LayerNorm(d_model),
        )

        if pooling == "attention":
            self.pool_query = nn.Linear(d_model, 1)

        self.shared_head = nn.Sequential(
            nn.LayerNorm(d_model),
            nn.Linear(d_model, d_model * 2), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(d_model * 2, d_model), nn.GELU(),
        )

        self.activity_head = nn.Linear(d_model, num_activities, bias=False)
        if tie_weights:
            self.activity_head.weight = self.activity_embed.weight

        self.remaining_head = nn.Sequential(
            nn.Linear(d_model, d_model // 2), nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 2, 1),
        )

        self.improvement_head = nn.Sequential(
            nn.Linear(d_model, d_model // 2), nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 2, 1),
            nn.Tanh(),
        )

        self.bottleneck_head = nn.Sequential(
            nn.Linear(d_model, d_model // 2), nn.GELU(),
            nn.Linear(d_model // 2, 1),
        )

    def _causal_mask(self, seq_len, device):
        return torch.triu(
            torch.ones(seq_len, seq_len, device=device, dtype=torch.bool),
            diagonal=1,
        )

    def forward(self, batch):
        acts = batch["activities"]
        positions = batch["positions"]
        time_deltas = batch["time_deltas"]
        cum_times = batch["cumulative_times"]
        mask = batch["mask"]

        B, T = acts.shape

        x = self.activity_embed(acts) + self.prev_activity_embed(batch["prev_activities"])
        pos_clamped = positions.clamp(max=self.pos_embed.num_embeddings - 1)
        x = x + self.pos_embed(pos_clamped)

        if self.use_time:
            dt = torch.log1p(time_deltas.clamp(min=0)).unsqueeze(-1)
            x = x + self.time_encoder(dt)
            ct = torch.log1p(cum_times.clamp(min=0)).unsqueeze(-1)
            x = x + self.cumtime_encoder(ct)

        x = x + self.role_encoder(batch["role"])
        x = x + self.freq_encoder(batch["activity_freq"]).unsqueeze(1)

        if T > 1:
            rel_emb = self.rel_pos(T, x.device)
            x = x + rel_emb.mean(dim=0).unsqueeze(0)

        x = self.input_norm(x)
        x = self.dropout(x)

        causal_mask = self._causal_mask(T, x.device)
        key_padding_mask = ~mask
        h_trans = self.encoder(x, mask=causal_mask, src_key_padding_mask=key_padding_mask)
        h_trans = self.final_norm(h_trans)
        h_trans = h_trans + x

        h_tcn = self.tcn(x, mask)

        h_12 = self.fusion_12(h_trans, h_tcn, key_padding_mask=key_padding_mask)

        h_gnn = self.gnn(batch["graph"])
        h_gnn = self.gnn_proj(h_gnn)

        if self.pooling == "last":
            lengths = mask.sum(dim=1) - 1
            pooled_12 = h_12[torch.arange(B, device=h_12.device), lengths]
        elif self.pooling == "attention":
            scores = self.pool_query(h_12)
            scores = scores.masked_fill(~mask.unsqueeze(-1), float("-inf"))
            weights = F.softmax(scores, dim=1)
            pooled_12 = (h_12 * weights).sum(dim=1)
        else:
            mask_f = mask.unsqueeze(-1).float()
            pooled_12 = (h_12 * mask_f).sum(dim=1) / mask_f.sum(dim=1).clamp(min=1)

        tri = torch.cat([pooled_12, h_gnn, pooled_12 * h_gnn], dim=-1)
        pooled = self.tri_fusion(tri)

        shared = self.shared_head(pooled)

        activity_logits = self.activity_head(shared)
        remaining_pred = self.remaining_head(shared).squeeze(-1)
        improvement_pred = self.improvement_head(shared).squeeze(-1)
        bottleneck_logits = self.bottleneck_head(h_12).squeeze(-1)

        return {
            "activity_logits": activity_logits,
            "remaining_pred": remaining_pred,
            "improvement_pred": improvement_pred,
            "bottleneck_logits": bottleneck_logits,
            "hidden": h_12,
            "pooled": pooled,
        }


# ===========================================================================
# 6) Scheduler و Loss
# ===========================================================================
class WarmupCosineScheduler:
    def __init__(self, optimizer, warmup_steps, total_steps, base_lr, min_lr=1e-6):
        self.optimizer = optimizer
        self.warmup_steps = warmup_steps
        self.total_steps = total_steps
        self.base_lr = base_lr
        self.min_lr = min_lr
        self.step_num = 0

    def step(self):
        self.step_num += 1
        if self.step_num <= self.warmup_steps:
            lr = self.base_lr * self.step_num / self.warmup_steps
        else:
            progress = (self.step_num - self.warmup_steps) / max(1, self.total_steps - self.warmup_steps)
            progress = min(progress, 1.0)
            lr = self.min_lr + 0.5 * (self.base_lr - self.min_lr) * (1 + math.cos(math.pi * progress))
        for pg in self.optimizer.param_groups:
            pg["lr"] = lr
        return lr


class MultiTaskLoss(nn.Module):
    def __init__(self, class_weights=None, label_smoothing=0.05,
                 lambda_activity=1.0, lambda_remaining=0.3,
                 lambda_improvement=0.3, lambda_bottleneck=0.1):
        super().__init__()
        self.ce = nn.CrossEntropyLoss(
            weight=class_weights, label_smoothing=label_smoothing
        )
        self.huber = nn.HuberLoss(delta=1.0)
        self.bce = nn.BCEWithLogitsLoss()
        self.lambda_activity = lambda_activity
        self.lambda_remaining = lambda_remaining
        self.lambda_improvement = lambda_improvement
        self.lambda_bottleneck = lambda_bottleneck

    def forward(self, outputs, batch):
        loss_activity = self.ce(outputs["activity_logits"], batch["target_activity"])
        loss_remaining = self.huber(outputs["remaining_pred"], batch["target_remaining"])
        loss_improvement = self.huber(outputs["improvement_pred"], batch["target_improvement"])

        with torch.no_grad():
            td = batch["time_deltas"]
            mask = batch["mask"]
            valid_td = td[mask]
            if valid_td.numel() > 0:
                thr = valid_td.median()
            else:
                thr = torch.tensor(1.0, device=td.device)
            bottleneck_target = (td > thr).float()

        loss_bottleneck = self.bce(
            outputs["bottleneck_logits"][mask],
            bottleneck_target[mask]
        )

        total = (
            self.lambda_activity * loss_activity
            + self.lambda_remaining * loss_remaining
            + self.lambda_improvement * loss_improvement
            + self.lambda_bottleneck * loss_bottleneck
        )
        return {
            "total": total,
            "activity": loss_activity.item(),
            "remaining": loss_remaining.item(),
            "improvement": loss_improvement.item(),
            "bottleneck": loss_bottleneck.item(),
        }


# ===========================================================================
# 7) آموزش
# ===========================================================================
def train_model(
    model, train_loader, val_loader,
    epochs=150, lr=3e-4, weight_decay=1e-5,
    device="cuda" if torch.cuda.is_available() else "cpu",
    class_weights=None,
    label_smoothing=0.05,
    warmup_ratio=0.15,
    grad_clip=1.0, patience=40,
    use_amp=True,
    swa_start_epoch=80,
    swa_lr=1e-4,
):
    model = model.to(device)

    decay_params, no_decay_params = [], []
    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue
        if p.ndim <= 1 or "norm" in name.lower() or "bias" in name.lower():
            no_decay_params.append(p)
        else:
            decay_params.append(p)

    optimizer = torch.optim.AdamW(
        [
            {"params": decay_params, "weight_decay": weight_decay},
            {"params": no_decay_params, "weight_decay": 0.0},
        ],
        lr=lr, betas=(0.9, 0.98), eps=1e-9,
    )

    total_steps = len(train_loader) * epochs
    warmup_steps = int(total_steps * warmup_ratio)
    scheduler = WarmupCosineScheduler(optimizer, warmup_steps, total_steps, base_lr=lr)

    criterion = MultiTaskLoss(
        class_weights=class_weights.to(device) if class_weights is not None else None,
        label_smoothing=label_smoothing,
    )

    use_cuda = device.startswith("cuda")
    # ✅ API جدید PyTorch
    if hasattr(torch, "amp") and hasattr(torch.amp, "GradScaler"):
        try:
            scaler = torch.amp.GradScaler('cuda', enabled=use_amp and use_cuda)
        except (TypeError, RuntimeError):
            scaler = torch.cuda.amp.GradScaler(enabled=use_amp and use_cuda)
    else:
        scaler = torch.cuda.amp.GradScaler(enabled=use_amp and use_cuda)

    swa_model = AveragedModel(model)
    swa_scheduler = SWALR(optimizer, swa_lr=swa_lr)
    swa_active = False

    best_val_acc = 0.0
    best_state = None
    patience_counter = 0
    best_path = os.path.join(OUTPUT_DIR, "best_tri_stream.pt")

    history = {
        "epoch": [], "train_loss": [], "val_loss": [],
        "train_acc": [], "val_acc": [],
        "val_mae_remaining": [], "val_mae_improvement": [],
        "train_loss_activity": [], "train_loss_remaining": [],
        "train_loss_improvement": [], "train_loss_bottleneck": [],
        "lr": [], "epoch_time_sec": [], "swa_active": [],
    }

    train_start_time = time.time()

    for epoch in range(epochs):
        epoch_start = time.time()

        if epoch >= swa_start_epoch and not swa_active:
            swa_active = True
            print(f"*** SWA فعال شد از epoch {epoch+1} ***")

        model.train()
        total_loss, correct, total = 0.0, 0, 0
        sum_la, sum_lr, sum_li, sum_lb = 0.0, 0.0, 0.0, 0.0

        pbar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs}")
        for batch in pbar:
            batch_dev = {}
            for k, v in batch.items():
                if k == "graph":
                    batch_dev["graph"] = {
                        "node_activities": v["node_activities"].to(device),
                        "node_features": v["node_features"].to(device),
                        "node_mask": v["node_mask"].to(device),
                        "edge_index_list": [ei.to(device) for ei in v["edge_index_list"]],
                        "node_offsets": v["node_offsets"].to(device),
                    }
                else:
                    batch_dev[k] = v.to(device)

            optimizer.zero_grad()

            # ✅ API جدید autocast
            try:
                autocast_ctx = torch.amp.autocast('cuda', enabled=use_amp and use_cuda)
            except (TypeError, RuntimeError):
                autocast_ctx = torch.cuda.amp.autocast(enabled=use_amp and use_cuda)

            with autocast_ctx:
                outputs = model(batch_dev)
                loss_dict = criterion(outputs, batch_dev)
                loss = loss_dict["total"]

            if scaler.is_enabled():
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
                scaler.step(optimizer)
                scaler.update()
            else:
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
                optimizer.step()

            if not swa_active:
                lr_now = scheduler.step()
            else:
                swa_scheduler.step()
                lr_now = optimizer.param_groups[0]["lr"]

            # ✅ تبدیل lr_now به float برای JSON
            if isinstance(lr_now, torch.Tensor):
                lr_now = lr_now.item()
            else:
                lr_now = float(lr_now)

            total_loss += loss.item()
            sum_la += loss_dict["activity"]
            sum_lr += loss_dict["remaining"]
            sum_li += loss_dict["improvement"]
            sum_lb += loss_dict["bottleneck"]

            pred = outputs["activity_logits"].argmax(dim=-1)
            correct += (pred == batch_dev["target_activity"]).sum().item()
            total += batch_dev["target_activity"].size(0)

            pbar.set_postfix({
                "loss": f"{loss.item():.4f}",
                "acc": f"{correct/total*100:.2f}%",
                "lr": f"{lr_now:.2e}",
            })

        n_batches = len(train_loader)
        train_acc = correct / total if total > 0 else 0.0
        train_loss_avg = total_loss / n_batches

        if swa_active:
            val_metrics = evaluate_full(swa_model.module, val_loader, device, criterion)
        else:
            val_metrics = evaluate_full(model, val_loader, device, criterion)

        epoch_time = time.time() - epoch_start

        history["epoch"].append(epoch + 1)
        history["train_loss"].append(float(train_loss_avg))
        history["train_acc"].append(float(train_acc))
        history["val_loss"].append(float(val_metrics["loss"]))
        history["val_acc"].append(float(val_metrics["acc"]))
        history["val_mae_remaining"].append(float(val_metrics["mae_remaining"]))
        history["val_mae_improvement"].append(float(val_metrics["mae_improvement"]))
        history["train_loss_activity"].append(float(sum_la / n_batches))
        history["train_loss_remaining"].append(float(sum_lr / n_batches))
        history["train_loss_improvement"].append(float(sum_li / n_batches))
        history["train_loss_bottleneck"].append(float(sum_lb / n_batches))
        history["lr"].append(float(lr_now))
        history["epoch_time_sec"].append(float(epoch_time))
        history["swa_active"].append(bool(swa_active))

        print(
            f"Epoch {epoch+1}/{epochs} | loss={train_loss_avg:.4f} | "
            f"train_acc={train_acc*100:.2f}% | val_acc={val_metrics['acc']*100:.2f}% | "
            f"MAE_rem={val_metrics['mae_remaining']:.3f} | "
            f"MAE_imp={val_metrics['mae_improvement']:.3f} | "
            f"time={epoch_time:.1f}s"
        )

        if val_metrics["acc"] > best_val_acc:
            best_val_acc = val_metrics["acc"]
            patience_counter = 0
            if swa_active:
                best_state = copy.deepcopy(swa_model.module.state_dict())
            else:
                best_state = copy.deepcopy(model.state_dict())
            torch.save(best_state, best_path)
            print(f"  *** بهترین مدل: {best_val_acc*100:.2f}% ***")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"Early stopping بعد از {epoch+1} epoch")
                break

    total_train_time = time.time() - train_start_time

    if best_state is not None:
        model.load_state_dict(best_state)

    history["total_train_time_sec"] = float(total_train_time)
    history["best_val_acc"] = float(best_val_acc)

    # ✅ پاک‌سازی نهایی
    history = to_python(history)

    with open(os.path.join(OUTPUT_DIR, "training_history.json"), "w") as f:
        json.dump(history, f, indent=2)

    print(f"\n[Training] کل زمان: {total_train_time/60:.2f} دقیقه")
    print(f"[Training] بهترین دقت val: {best_val_acc*100:.2f}%")

    return model, history


# ===========================================================================
# 8) ارزیابی
# ===========================================================================
@torch.no_grad()
def evaluate_full(model, loader, device, criterion=None):
    model.eval()
    correct, total = 0, 0
    total_loss = 0.0
    all_rem_pred, all_rem_true = [], []
    all_imp_pred, all_imp_true = [], []

    for batch in loader:
        batch_dev = {}
        for k, v in batch.items():
            if k == "graph":
                batch_dev["graph"] = {
                    "node_activities": v["node_activities"].to(device),
                    "node_features": v["node_features"].to(device),
                    "node_mask": v["node_mask"].to(device),
                    "edge_index_list": [ei.to(device) for ei in v["edge_index_list"]],
                    "node_offsets": v["node_offsets"].to(device),
                }
            else:
                batch_dev[k] = v.to(device)

        outputs = model(batch_dev)

        if criterion is not None:
            loss_dict = criterion(outputs, batch_dev)
            total_loss += loss_dict["total"]

        pred = outputs["activity_logits"].argmax(dim=-1)
        correct += (pred == batch_dev["target_activity"]).sum().item()
        total += batch_dev["target_activity"].size(0)

        all_rem_pred.append(outputs["remaining_pred"].cpu())
        all_rem_true.append(batch_dev["target_remaining"].cpu())
        all_imp_pred.append(outputs["improvement_pred"].cpu())
        all_imp_true.append(batch_dev["target_improvement"].cpu())

    rem_pred = torch.cat(all_rem_pred).numpy()
    rem_true = torch.cat(all_rem_true).numpy()
    imp_pred = torch.cat(all_imp_pred).numpy()
    imp_true = torch.cat(all_imp_true).numpy()

    return {
        "acc": correct / total if total > 0 else 0.0,
        "loss": total_loss / max(len(loader), 1) if criterion else 0.0,
        "mae_remaining": mean_absolute_error(rem_true, rem_pred),
        "mae_improvement": mean_absolute_error(imp_true, imp_pred),
    }


@torch.no_grad()
def evaluate_topk(model, loader, device, k=3):
    model.eval()
    correct, total = 0, 0
    for batch in loader:
        batch_dev = {}
        for kk, v in batch.items():
            if kk == "graph":
                batch_dev["graph"] = {
                    "node_activities": v["node_activities"].to(device),
                    "node_features": v["node_features"].to(device),
                    "node_mask": v["node_mask"].to(device),
                    "edge_index_list": [ei.to(device) for ei in v["edge_index_list"]],
                    "node_offsets": v["node_offsets"].to(device),
                }
            else:
                batch_dev[kk] = v.to(device)

        outputs = model(batch_dev)
        logits = outputs["activity_logits"]
        topk = logits.topk(k, dim=-1).indices
        correct += (topk == batch_dev["target_activity"].unsqueeze(-1)).any(dim=-1).sum().item()
        total += batch_dev["target_activity"].size(0)
    return correct / total if total > 0 else 0.0


@torch.no_grad()
def collect_predictions(model, loader, device):
    model.eval()
    all_logits, all_targets = [], []
    all_rem_pred, all_rem_true = [], []
    all_imp_pred, all_imp_true = [], []
    all_raw_rem, all_raw_imp = [], []

    for batch in loader:
        batch_dev = {}
        for k, v in batch.items():
            if k == "graph":
                batch_dev["graph"] = {
                    "node_activities": v["node_activities"].to(device),
                    "node_features": v["node_features"].to(device),
                    "node_mask": v["node_mask"].to(device),
                    "edge_index_list": [ei.to(device) for ei in v["edge_index_list"]],
                    "node_offsets": v["node_offsets"].to(device),
                }
            else:
                batch_dev[k] = v.to(device)

        outputs = model(batch_dev)
        all_logits.append(outputs["activity_logits"].cpu())
        all_targets.append(batch["target_activity"])
        all_rem_pred.append(outputs["remaining_pred"].cpu())
        all_rem_true.append(batch["target_remaining"])
        all_imp_pred.append(outputs["improvement_pred"].cpu())
        all_imp_true.append(batch["target_improvement"])
        all_raw_rem.append(batch["raw_remaining"])
        all_raw_imp.append(batch["raw_improvement"])

    return {
        "logits": torch.cat(all_logits),
        "targets": torch.cat(all_targets),
        "rem_pred": torch.cat(all_rem_pred),
        "rem_true": torch.cat(all_rem_true),
        "imp_pred": torch.cat(all_imp_pred),
        "imp_true": torch.cat(all_imp_true),
        "raw_rem": torch.cat(all_raw_rem),
        "raw_imp": torch.cat(all_raw_imp),
    }


# ===========================================================================
# 9) تحلیل گلوگاه
# ===========================================================================
@torch.no_grad()
def detect_bottlenecks_and_improvements(
    model, dataset, activities_index, device,
    top_k_bottlenecks=10, top_k_improvements=10,
):
    collate_fn = partial(collate_with_graphs, max_seq_len=dataset.max_seq_len)
    loader = DataLoader(dataset, batch_size=64, shuffle=False,
                        num_workers=0, collate_fn=collate_fn)
    preds = collect_predictions(model, loader, device)

    imp_by_activity = defaultdict(list)
    rem_by_activity = defaultdict(list)
    count_by_activity = defaultdict(int)

    targets = preds["targets"].numpy()
    imp_pred = preds["imp_pred"].numpy()
    raw_rem = preds["raw_rem"].numpy()

    for i in range(len(targets)):
        act = int(targets[i])
        imp_by_activity[act].append(imp_pred[i])
        rem_by_activity[act].append(raw_rem[i])
        count_by_activity[act] += 1

    activity_mean_wait = dataset.activity_mean_wait
    activity_mean_remaining = {a: float(np.mean(v)) for a, v in rem_by_activity.items()}
    activity_improvement_potential = {a: float(np.mean(v)) for a, v in imp_by_activity.items()}

    bottleneck_ranking = sorted(
        activity_mean_wait.items(), key=lambda x: x[1], reverse=True
    )[:top_k_bottlenecks]

    improvement_ranking = sorted(
        activity_improvement_potential.items(), key=lambda x: x[1], reverse=True
    )[:top_k_improvements]

    results = {
        "bottlenecks": [
            {
                "activity_id": a,
                "activity_name": activities_index[a] if a < len(activities_index) else f"A{a}",
                "mean_wait_seconds": float(w),
                "occurrences": count_by_activity.get(a, 0),
                "mean_remaining_seconds": activity_mean_remaining.get(a, 0.0),
            }
            for a, w in bottleneck_ranking
        ],
        "improvers": [
            {
                "activity_id": a,
                "activity_name": activities_index[a] if a < len(activities_index) else f"A{a}",
                "predicted_improvement": float(v),
                "occurrences": count_by_activity.get(a, 0),
            }
            for a, v in improvement_ranking
        ],
        "activity_stats": {
            "mean_wait": {activities_index[a]: w for a, w in activity_mean_wait.items()
                          if a < len(activities_index)},
            "mean_improvement": {
                activities_index[a]: v for a, v in activity_improvement_potential.items()
                if a < len(activities_index)
            },
            "mean_remaining": {
                activities_index[a]: v for a, v in activity_mean_remaining.items()
                if a < len(activities_index)
            },
        },
    }
    return results


# ===========================================================================
# 10) نمودارها
# ===========================================================================
def save_fig(fig, name):
    path = os.path.join(FIG_DIR, f"{name}.png")
    fig.savefig(path, dpi=300, bbox_inches='tight')
    fig.savefig(os.path.join(FIG_DIR, f"{name}.pdf"), bbox_inches='tight')
    plt.close(fig)
    print(f"[Fig] {name}.png/.pdf")


def plot_learning_curves(history):
    epochs = history["epoch"]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].plot(epochs, history["train_loss"], label=fa("زیان آموزش"), color="#1F4E79", lw=2)
    axes[0].plot(epochs, history["val_loss"], label=fa("زیان اعتبارسنجی"), color="#E67E22", lw=2)
    axes[0].set_xlabel(fa("دوره"))
    axes[0].set_ylabel(fa("زیان"))
    axes[0].set_title(fa("منحنی زیان"), fontweight='bold')
    axes[0].legend(); axes[0].grid(alpha=0.3)

    axes[1].plot(epochs, [a*100 for a in history["train_acc"]], label=fa("دقت آموزش"), color="#1F4E79", lw=2)
    axes[1].plot(epochs, [a*100 for a in history["val_acc"]], label=fa("دقت اعتبارسنجی"), color="#E67E22", lw=2)
    axes[1].axhline(90, color="#C0392B", linestyle='--', lw=1.5, label=fa("آستانه ۹۰٪"))
    axes[1].set_xlabel(fa("دوره"))
    axes[1].set_ylabel(fa("دقت (٪)"))
    axes[1].set_title(fa("منحنی دقت"), fontweight='bold')
    axes[1].legend(); axes[1].grid(alpha=0.3)

    fig.suptitle(fa("شکل ۴.۱: منحنی‌های آموزش مدل Tri-Stream"), fontsize=13, fontweight='bold')
    fig.tight_layout()
    save_fig(fig, "fig_4_1_learning_curves")


def plot_multitask_losses(history):
    fig, ax = plt.subplots(figsize=(11, 5))
    epochs = history["epoch"]
    ax.plot(epochs, history["train_loss_activity"], label=fa("زیان فعالیت"), lw=2)
    ax.plot(epochs, history["train_loss_remaining"], label=fa("زیان زمان باقی‌مانده"), lw=2)
    ax.plot(epochs, history["train_loss_improvement"], label=fa("زیان بهبود تأخیر"), lw=2)
    ax.plot(epochs, history["train_loss_bottleneck"], label=fa("زیان گلوگاه"), lw=2)
    ax.set_xlabel(fa("دوره")); ax.set_ylabel(fa("زیان"))
    ax.set_title(fa("شکل ۴.۲: تفکیک زیان چهار سر خروجی"), fontweight='bold')
    ax.legend(); ax.grid(alpha=0.3)
    save_fig(fig, "fig_4_2_multitask_losses")


def plot_lr_schedule(history):
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(history["epoch"], history["lr"], color="#1F4E79", lw=2)
    ax.set_xlabel(fa("دوره")); ax.set_ylabel(fa("نرخ یادگیری"))
    ax.set_title(fa("شکل ۴.۳: نرخ یادگیری (Warmup + Cosine)"), fontweight='bold')
    ax.set_yscale('log'); ax.grid(alpha=0.3)
    save_fig(fig, "fig_4_3_lr_schedule")


def plot_topk_results(topk_results):
    ks = list(topk_results.keys())
    accs = [v*100 for v in topk_results.values()]
    colors = ["#1F4E79", "#2980B9", "#5DADE2", "#AED6F1", "#D6EAF8"][:len(ks)]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(ks, accs, color=colors, edgecolor="#1F4E79", lw=1.5)
    for bar, acc in zip(bars, accs):
        ax.text(bar.get_x()+bar.get_width()/2, acc+0.3, f"{acc:.2f}%",
                ha='center', fontweight='bold')
    ax.axhline(90, color="#C0392B", linestyle='--', lw=1.5, label=fa("آستانه ۹۰٪"))
    ax.set_ylim(min(accs)-5, 102)
    ax.set_ylabel(fa("دقت (٪)"))
    ax.set_title(fa("شکل ۴.۴: دقت Top-k"), fontweight='bold')
    ax.legend(); ax.grid(alpha=0.3, axis='y')
    save_fig(fig, "fig_4_4_topk")


def plot_confusion_matrix(model, test_loader, device, activities_index, top_n=15):
    preds = collect_predictions(model, test_loader, device)
    p = preds["logits"].argmax(dim=-1).numpy()
    t = preds["targets"].numpy()

    counts = Counter(t)
    top_classes = [c for c, _ in counts.most_common(top_n)]
    mask = np.isin(t, top_classes)
    cm = confusion_matrix(t[mask], p[mask], labels=top_classes, normalize='true')*100

    fig, ax = plt.subplots(figsize=(11, 9))
    im = ax.imshow(cm, cmap='Blues', vmin=0, vmax=100)
    ax.set_xticks(range(len(top_classes))); ax.set_yticks(range(len(top_classes)))
    labels = [activities_index[c][:20] for c in top_classes]
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel(fa("فعالیت پیش‌بینی‌شده")); ax.set_ylabel(fa("فعالیت واقعی"))
    for i in range(len(top_classes)):
        for j in range(len(top_classes)):
            v = cm[i, j]
            ax.text(j, i, f"{v:.0f}", ha='center', va='center',
                    fontsize=7, color="white" if v > 50 else "black")
    fig.colorbar(im, ax=ax, label=fa("درصد"))
    ax.set_title(fa(f"شکل ۴.۵: ماتریس درهم‌ریختگی (Top-{top_n})"), fontweight='bold')
    save_fig(fig, "fig_4_5_confusion_matrix")
    return cm, top_classes


def plot_bottleneck_analysis(bottleneck_results, activities_index, top_n=15):
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    bns = bottleneck_results["bottlenecks"][:top_n]
    names = [b["activity_name"][:18] for b in bns]
    waits = [b["mean_wait_seconds"]/60.0 for b in bns]
    axes[0].barh(names[::-1], waits[::-1], color="#C0392B", edgecolor="#7B241C")
    axes[0].set_xlabel(fa("میانگین زمان انتظار (دقیقه)"))
    axes[0].set_title(fa("شکل ۴.۶: فعالیت‌های گلوگاه"), fontweight='bold')
    axes[0].grid(alpha=0.3, axis='x')

    imps = bottleneck_results["improvers"][:top_n]
    names2 = [b["activity_name"][:18] for b in imps]
    potentials = [b["predicted_improvement"] for b in imps]
    colors = ["#27AE60" if v > 0 else "#E67E22" for v in potentials]
    axes[1].barh(names2[::-1], potentials[::-1], color=colors[::-1],
                 edgecolor="#1F4E79")
    axes[1].axvline(0, color="black", lw=1)
    axes[1].set_xlabel(fa("پتانسیل بهبود (نرمال‌شده)"))
    axes[1].set_title(fa("شکل ۴.۷: فعالیت‌های بهبوددهنده تأخیر"), fontweight='bold')
    axes[1].grid(alpha=0.3, axis='x')

    fig.suptitle(fa("شکل ۴.۶-۴.۷: تحلیل گلوگاه و پتانسیل بهبود تأخیر"),
                 fontsize=13, fontweight='bold')
    fig.tight_layout()
    save_fig(fig, "fig_4_6_7_bottleneck_analysis")


def plot_remaining_time_prediction(preds):
    rem_true = preds["rem_true"].numpy()
    rem_pred = preds["rem_pred"].numpy()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].scatter(rem_true, rem_pred, alpha=0.3, s=8, color="#2980B9")
    lim = max(rem_true.max(), rem_pred.max())
    axes[0].plot([0, lim], [0, lim], 'r--', lw=2, label=fa("خط ایده‌آل"))
    axes[0].set_xlabel(fa("زمان باقی‌مانده واقعی (log)"))
    axes[0].set_ylabel(fa("زمان باقی‌مانده پیش‌بینی‌شده (log)"))
    axes[0].set_title(fa("پیش‌بینی زمان باقی‌مانده"))
    axes[0].legend(); axes[0].grid(alpha=0.3)

    residuals = rem_pred - rem_true
    axes[1].hist(residuals, bins=50, color="#8E44AD", alpha=0.7, edgecolor="#4A235A")
    axes[1].axvline(0, color="red", linestyle='--', lw=2)
    axes[1].set_xlabel(fa("خطای پیش‌بینی (log)"))
    axes[1].set_ylabel(fa("فراوانی"))
    axes[1].set_title(fa(f"توزیع خطا — MAE={np.abs(residuals).mean():.3f}"))
    axes[1].grid(alpha=0.3)

    fig.suptitle(fa("شکل ۴.۸: ارزیابی سر پیش‌بینی زمان باقی‌مانده"),
                 fontsize=13, fontweight='bold')
    fig.tight_layout()
    save_fig(fig, "fig_4_8_remaining_time")


def plot_improvement_prediction(preds):
    imp_true = preds["imp_true"].numpy()
    imp_pred = preds["imp_pred"].numpy()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].scatter(imp_true, imp_pred, alpha=0.3, s=8, color="#27AE60")
    lim = max(abs(imp_true).max(), abs(imp_pred).max())
    axes[0].plot([-lim, lim], [-lim, lim], 'r--', lw=2)
    axes[0].set_xlabel(fa("پتانسیل بهبود واقعی"))
    axes[0].set_ylabel(fa("پتانسیل بهبود پیش‌بینی‌شده"))
    axes[0].set_title(fa("پیش‌بینی پتانسیل بهبود تأخیر"))
    axes[0].grid(alpha=0.3)

    try:
        from scipy.stats import spearmanr
        rho, _ = spearmanr(imp_true, imp_pred)
        text = f"Spearman ρ = {rho:.4f}"
    except ImportError:
        text = "scipy نصب نیست"

    axes[1].text(0.5, 0.5, text,
                 ha='center', va='center', fontsize=20, fontweight='bold',
                 transform=axes[1].transAxes)
    axes[1].axis('off')
    axes[1].set_title(fa("همبستگی رتبه‌ای"))

    fig.suptitle(fa("شکل ۴.۹: ارزیابی سر پتانسیل بهبود تأخیر"),
                 fontsize=13, fontweight='bold')
    fig.tight_layout()
    save_fig(fig, "fig_4_9_improvement")


def plot_prefix_length_distribution(dataset):
    lengths = [len(s["prefix_acts"]) for s in dataset.samples]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(lengths, bins=30, color="#5DADE2", edgecolor="#1F4E79", alpha=0.8)
    ax.axvline(dataset.max_seq_len, color="#C0392B", linestyle='--', lw=2,
               label=fa(f"حداکثر ({dataset.max_seq_len})"))
    ax.set_xlabel(fa("طول پیشوند"))
    ax.set_ylabel(fa("فراوانی"))
    ax.set_title(fa("شکل ۴.۱۰: توزیع طول پیشوندها"), fontweight='bold')
    ax.legend(); ax.grid(alpha=0.3)
    save_fig(fig, "fig_4_10_prefix_length")


def plot_training_time(history):
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(history["epoch"], history["epoch_time_sec"],
            color="#8E44AD", lw=2, marker='o', markersize=3)
    ax.set_xlabel(fa("دوره")); ax.set_ylabel(fa("زمان (ثانیه)"))
    ax.set_title(fa("شکل ۴.۱۱: زمان هر دوره"), fontweight='bold')
    ax.grid(alpha=0.3)
    save_fig(fig, "fig_4_11_training_time")


# ===========================================================================
# 11) ذخیره جداول
# ===========================================================================
def save_results_tables(
    history, topk_results, test_metrics, cm, top_classes,
    activities_index, precision, recall, f1, support,
    bottleneck_results, preds,
):
    summary = {
        "best_val_acc": float(history["best_val_acc"]),
        "test_acc_top1": float(test_metrics["top1"]),
        "test_acc_top3": float(test_metrics["top3"]),
        "test_acc_top5": float(test_metrics["top5"]),
        "test_acc_top10": float(test_metrics.get("top10", 0.0)),
        "test_mae_remaining": float(test_metrics.get("mae_remaining", 0.0)),
        "test_mae_improvement": float(test_metrics.get("mae_improvement", 0.0)),
        "total_epochs": len(history["epoch"]),
        "total_train_time_sec": float(history["total_train_time_sec"]),
        "avg_epoch_time_sec": float(np.mean(history["epoch_time_sec"])),
        "model_params": int(test_metrics.get("model_params", 0)),
        "architecture": "Tri-Stream (Transformer + TCN + GNN)",
    }
    summary = to_python(summary)

    with open(os.path.join(OUTPUT_DIR, "summary_results.json"), "w") as f:
        json.dump(summary, f, indent=2)

    with open(os.path.join(OUTPUT_DIR, "training_history.csv"), "w",
              newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["epoch", "train_loss", "val_loss", "train_acc", "val_acc",
                    "train_loss_activity", "train_loss_remaining",
                    "train_loss_improvement", "train_loss_bottleneck",
                    "lr", "epoch_time_sec", "swa_active"])
        for i in range(len(history["epoch"])):
            w.writerow([
                history["epoch"][i],
                f"{history['train_loss'][i]:.6f}",
                f"{history['val_loss'][i]:.6f}",
                f"{history['train_acc'][i]:.6f}",
                f"{history['val_acc'][i]:.6f}",
                f"{history['train_loss_activity'][i]:.6f}",
                f"{history['train_loss_remaining'][i]:.6f}",
                f"{history['train_loss_improvement'][i]:.6f}",
                f"{history['train_loss_bottleneck'][i]:.6f}",
                f"{history['lr'][i]:.8f}",
                f"{history['epoch_time_sec'][i]:.2f}",
                history["swa_active"][i],
            ])

    with open(os.path.join(OUTPUT_DIR, "topk_results.csv"), "w",
              newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["k", "accuracy"])
        for k, v in topk_results.items():
            w.writerow([k, f"{v:.6f}"])

    with open(os.path.join(OUTPUT_DIR, "per_class_metrics.csv"), "w",
              newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["class_id", "activity_name", "precision", "recall", "f1", "support"])
        for i, c in enumerate(top_classes):
            name = activities_index[c] if c < len(activities_index) else f"A{c}"
            w.writerow([c, name, f"{precision[i]:.4f}", f"{recall[i]:.4f}",
                        f"{f1[i]:.4f}", int(support[i])])

    np.savetxt(os.path.join(OUTPUT_DIR, "confusion_matrix.csv"),
               cm, delimiter=",", fmt="%.2f")

    with open(os.path.join(OUTPUT_DIR, "bottlenecks.csv"), "w",
              newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["rank", "activity_id", "activity_name",
                    "mean_wait_seconds", "mean_wait_minutes",
                    "occurrences", "mean_remaining_minutes"])
        for i, b in enumerate(bottleneck_results["bottlenecks"]):
            w.writerow([
                i+1, b["activity_id"], b["activity_name"],
                f"{b['mean_wait_seconds']:.2f}",
                f"{b['mean_wait_seconds']/60:.2f}",
                b["occurrences"],
                f"{b['mean_remaining_seconds']/60:.2f}",
            ])

    with open(os.path.join(OUTPUT_DIR, "improvers.csv"), "w",
              newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["rank", "activity_id", "activity_name",
                    "predicted_improvement", "occurrences"])
        for i, imp in enumerate(bottleneck_results["improvers"]):
            w.writerow([i+1, imp["activity_id"], imp["activity_name"],
                        f"{imp['predicted_improvement']:.4f}",
                        imp["occurrences"]])

    np.savez(
        os.path.join(OUTPUT_DIR, "predictions.npz"),
        rem_true=preds["rem_true"].numpy(),
        rem_pred=preds["rem_pred"].numpy(),
        imp_true=preds["imp_true"].numpy(),
        imp_pred=preds["imp_pred"].numpy(),
        raw_rem=preds["raw_rem"].numpy(),
        raw_imp=preds["raw_imp"].numpy(),
        logits=preds["logits"].numpy(),
        targets=preds["targets"].numpy(),
    )

    print(f"[Table] جداول در {OUTPUT_DIR} ذخیره شدند.")


# ===========================================================================
# 12) پیشنهاد برای پیشوند دلخواه
# ===========================================================================
@torch.no_grad()
def recommend_improvements_for_prefix(
    model, prefix_activities, activities_index, dataset, device, top_k=5,
):
    model.eval()
    act_to_id = dataset.activity_to_id
    seq = [act_to_id[a] for a in prefix_activities if a in act_to_id]
    seq_len = len(seq)
    if seq_len == 0:
        return {"next_activity_recommendations": [],
                "predicted_remaining_time_log": 0.0,
                "predicted_improvement": 0.0}

    pad_len = dataset.max_seq_len - seq_len

    acts_padded = seq + [0] * pad_len
    pos_padded = list(range(seq_len)) + [0] * pad_len
    dt_padded = [0.0] * dataset.max_seq_len
    cum_padded = [0.0] * dataset.max_seq_len
    mask = [1] * seq_len + [0] * pad_len
    prev_acts = [0] + seq[:-1]
    prev_acts_padded = prev_acts + [0] * pad_len

    role = torch.zeros(1, dataset.max_seq_len, 2)
    role[0, 0, 0] = 1.0
    role[0, seq_len-1, 1] = 1.0

    freq = torch.zeros(1, dataset.num_activities)
    for a in seq:
        freq[0, a] += 1
    freq = freq / max(seq_len, 1)

    graph = PrefixGraphBuilder().build(seq, [0.0]*seq_len, dataset.max_seq_len)

    batch = {
        "activities": torch.tensor([acts_padded], dtype=torch.long).to(device),
        "prev_activities": torch.tensor([prev_acts_padded], dtype=torch.long).to(device),
        "positions": torch.tensor([pos_padded], dtype=torch.long).to(device),
        "time_deltas": torch.tensor([dt_padded], dtype=torch.float32).to(device),
        "cumulative_times": torch.tensor([cum_padded], dtype=torch.float32).to(device),
        "role": role.to(device),
        "activity_freq": freq.to(device),
        "mask": torch.tensor([mask], dtype=torch.bool).to(device),
        "graph": {
            "node_activities": graph["node_activities"].unsqueeze(0).to(device),
            "node_features": graph["node_features"].unsqueeze(0).to(device),
            "node_mask": graph["node_mask"].unsqueeze(0).to(device),
            "edge_index_list": [graph["edge_index"].to(device)],
            "node_offsets": torch.tensor([0], dtype=torch.long).to(device),
        },
    }

    outputs = model(batch)
    probs = F.softmax(outputs["activity_logits"], dim=-1)[0]
    imp = outputs["improvement_pred"][0].item()
    rem = outputs["remaining_pred"][0].item()

    topk_probs, topk_ids = probs.topk(top_k)

    recommendations = []
    for p, aid in zip(topk_probs.tolist(), topk_ids.tolist()):
        name = activities_index[aid] if aid < len(activities_index) else f"A{aid}"
        recommendations.append({
            "activity": name,
            "probability": p,
            "predicted_delay_improvement": imp,
        })

    return {
        "next_activity_recommendations": recommendations,
        "predicted_remaining_time_log": rem,
        "predicted_improvement": imp,
    }


# ===========================================================================
# 13) Main
# ===========================================================================
def main():
    LOG_PATH = "BPI_Challenge_2012.xes.gz"
    LOGNAME = "bpi2012_tri_stream"
    MAX_SEQ_LEN = 100

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    print("در حال خواندن event log ...")
    log = read_xes(LOG_PATH)

    activities_index = sorted({
        evt[xes.DEFAULT_NAME_KEY] for case in log for evt in case
    })
    activities_index = ["<PAD>"] + activities_index
    num_activities = len(activities_index)
    print(f"تعداد فعالیت‌ها: {num_activities}")

    print("در حال ساخت دیتاست چند-وظیفه‌ای ...")
    dataset = MultiTaskProcessDataset(
        eventlog=log,
        activities_index=activities_index,
        max_seq_len=MAX_SEQ_LEN,
        min_prefix_len=2,
        use_time=True,
    )

    unique_cases = list(set(dataset.case_ids))
    train_cases, test_cases = train_test_split(unique_cases, train_size=0.67, random_state=42)
    train_cases, val_cases = train_test_split(train_cases, train_size=0.8, random_state=42)

    train_set_s, val_set_s, test_set_s = set(train_cases), set(val_cases), set(test_cases)
    train_idx = [i for i, c in enumerate(dataset.case_ids) if c in train_set_s]
    val_idx = [i for i, c in enumerate(dataset.case_ids) if c in val_set_s]
    test_idx = [i for i, c in enumerate(dataset.case_ids) if c in test_set_s]

    print(f"train: {len(train_idx)} | val: {len(val_idx)} | test: {len(test_idx)}")

    dataset_stats = {
        "num_activities": num_activities,
        "num_samples_total": len(dataset.samples),
        "num_cases_total": len(set(dataset.case_ids)),
        "num_train_samples": len(train_idx),
        "num_val_samples": len(val_idx),
        "num_test_samples": len(test_idx),
        "num_train_cases": len(train_set_s),
        "num_val_cases": len(val_set_s),
        "num_test_cases": len(test_set_s),
        "max_seq_len": MAX_SEQ_LEN,
        "min_prefix_len": 2,
        "global_mean_wait_seconds": float(dataset.global_mean_wait),
        "architecture": "Tri-Stream (Transformer + TCN + GNN)",
    }
    with open(os.path.join(OUTPUT_DIR, "dataset_stats.json"), "w") as f:
        json.dump(dataset_stats, f, indent=2)

    train_set = torch.utils.data.Subset(dataset, train_idx)
    val_set = torch.utils.data.Subset(dataset, val_idx)
    test_set = torch.utils.data.Subset(dataset, test_idx)

    collate_fn = partial(collate_with_graphs, max_seq_len=MAX_SEQ_LEN)

    train_loader = DataLoader(train_set, batch_size=64, shuffle=True,
                              num_workers=0, collate_fn=collate_fn)
    val_loader = DataLoader(val_set, batch_size=128, shuffle=False,
                            num_workers=0, collate_fn=collate_fn)
    test_loader = DataLoader(test_set, batch_size=128, shuffle=False,
                             num_workers=0, collate_fn=collate_fn)

    label_counts = Counter()
    for i in train_idx:
        label_counts[dataset.samples[i]["target_activity"]] += 1
    total_samples = sum(label_counts.values())
    class_weights = torch.ones(num_activities)
    for c in range(num_activities):
        if c in label_counts and label_counts[c] > 0:
            class_weights[c] = (total_samples / (num_activities * label_counts[c])) ** 0.25
    class_weights = class_weights / class_weights.sum() * num_activities
    class_weights[0] = 0.0
    print(f"وزن کلاس‌ها (نمونه): {class_weights[:10]}")

    model = DelayAwareTriStreamTransformer(
        num_activities=num_activities,
        d_model=256, nhead=8, num_layers=6, dim_feedforward=1024,
        dropout=0.05, max_seq_len=MAX_SEQ_LEN, max_position=4000,
        use_time=True, pooling="last", tie_weights=True,
        gnn_layers=2,
    )
    model_params = sum(p.numel() for p in model.parameters())
    print(f"تعداد پارامترها: {model_params:,}")

    model, history = train_model(
        model, train_loader, val_loader,
        epochs=150, lr=3e-4, weight_decay=1e-5, device=device,
        class_weights=class_weights, label_smoothing=0.05,
        warmup_ratio=0.15, patience=40, use_amp=True,
        swa_start_epoch=80, swa_lr=1e-4,
    )

    print("\n" + "="*60)
    print("ارزیابی نهایی روی مجموعه آزمون")
    print("="*60)

    test_top1 = evaluate_topk(model, test_loader, device, k=1)
    test_top3 = evaluate_topk(model, test_loader, device, k=3)
    test_top5 = evaluate_topk(model, test_loader, device, k=5)
    test_top10 = evaluate_topk(model, test_loader, device, k=10)
    test_metrics_full = evaluate_full(model, test_loader, device)

    topk_results = {
        "Top-1": test_top1, "Top-3": test_top3,
        "Top-5": test_top5, "Top-10": test_top10,
    }
    for k, v in topk_results.items():
        print(f"Test Accuracy ({k}): {v*100:.2f}%")
    print(f"MAE remaining: {test_metrics_full['mae_remaining']:.4f}")
    print(f"MAE improvement: {test_metrics_full['mae_improvement']:.4f}")

    test_metrics = {
        "top1": test_top1, "top3": test_top3,
        "top5": test_top5, "top10": test_top10,
        "mae_remaining": test_metrics_full["mae_remaining"],
        "mae_improvement": test_metrics_full["mae_improvement"],
        "model_params": model_params,
    }

    print("\nتحلیل گلوگاه و پتانسیل بهبود ...")
    bottleneck_results = detect_bottlenecks_and_improvements(
        model, test_set, activities_index, device,
        top_k_bottlenecks=15, top_k_improvements=15,
        base_dataset=dataset,
    )

    print("\n🔴 گلوگاه‌های اصلی:")
    for i, b in enumerate(bottleneck_results["bottlenecks"][:10]):
        print(f"  {i+1}. {b['activity_name']}: "
              f"{b['mean_wait_seconds']/60:.1f} دقیقه، "
              f"تکرار: {b['occurrences']}")

    print("\n🟢 فعالیت‌های بهبوددهنده تأخیر:")
    for i, imp in enumerate(bottleneck_results["improvers"][:10]):
        print(f"  {i+1}. {imp['activity_name']}: "
              f"improvement={imp['predicted_improvement']:.3f}")

    print("\nتولید شکل‌ها ...")
    plot_learning_curves(history)
    plot_multitask_losses(history)
    plot_lr_schedule(history)
    plot_topk_results(topk_results)
    cm, top_classes = plot_confusion_matrix(model, test_loader, device, activities_index)
    plot_bottleneck_analysis(bottleneck_results, activities_index)

    preds = collect_predictions(model, test_loader, device)
    plot_remaining_time_prediction(preds)
    plot_improvement_prediction(preds)
    plot_prefix_length_distribution(dataset)
    plot_training_time(history)

    precision, recall, f1, support = precision_recall_fscore_support(
        preds["targets"].numpy(),
        preds["logits"].argmax(-1).numpy(),
        labels=top_classes, zero_division=0,
    )
    save_results_tables(
        history, topk_results, test_metrics, cm, top_classes,
        activities_index, precision, recall, f1, support,
        bottleneck_results, preds,
    )

    report = classification_report(
        preds["targets"].numpy(),
        preds["logits"].argmax(-1).numpy(),
        labels=list(range(num_activities)),
        target_names=[str(a)[:30] for a in activities_index],
        zero_division=0, output_dict=True,
    )
    with open(os.path.join(OUTPUT_DIR, "classification_report.json"), "w") as f:
        json.dump(to_python(report), f, indent=2, ensure_ascii=False)

    torch.save(model.state_dict(), os.path.join(OUTPUT_DIR, f"{LOGNAME}_model.pt"))

    print("\n" + "="*60)
    print("نمونه پیشنهاد برای یک پیشوند دلخواه")
    print("="*60)
    sample_case = None
    for case in log:
        if len(case) >= 6:
            sample_case = case
            break
    if sample_case:
        prefix = [evt[xes.DEFAULT_NAME_KEY] for evt in list(sample_case)[:4]]
        print(f"پیشوند: {prefix}")
        rec = recommend_improvements_for_prefix(
            model, prefix, activities_index, dataset, device, top_k=5
        )
        print("\nپیشنهاد فعالیت‌های بعدی:")
        for r in rec["next_activity_recommendations"]:
            print(f"  • {r['activity']} — احتمال: {r['probability']*100:.2f}%")
        print(f"\nتخمین پتانسیل بهبود تأخیر: {rec['predicted_improvement']:.4f}")
        print(f"تخمین زمان باقی‌مانده (log): {rec['predicted_remaining_time_log']:.4f}")

    print(f"\n✅ تمام نتایج در پوشه '{OUTPUT_DIR}' ذخیره شدند.")


if __name__ == "__main__":
    main()