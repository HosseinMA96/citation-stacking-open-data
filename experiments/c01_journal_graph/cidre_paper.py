"""CIDRE as specified in Kojaku, Livan & Masuda (2021), Sci Rep, doi:10.1038/s41598-021-93572-3.

Thin wrapper around the `cidre` 0.0.1 package (identical to GitHub master 5b582b7, 2021-08-12).
The package's EdgeFilter (dcSBM Poisson test, lambda clipped at 1, Benjamini-Hochberg) is used
unchanged. Three gaps between the package and the paper's Methods are closed here:

1. Excessive edge, condition 1 (paper Methods): more than half of the citations from i to j in
   year t go to papers from the last 2 years. Not in the package; applied here as an AND with
   the significance test when `W_all` (citations to papers of any earlier year) is given.
2. theta_w = 50: groups whose within-group citations (self-loops excluded) are fewer than
   theta_w are removed. Not implemented in the package.
3. networkx >= 3 removed `from_scipy_sparse_matrix`, which `Cidre.detect` calls; weak
   components are found with scipy instead.
"""
import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components

from cidre.cidre import Group
from cidre.filters import EdgeFilter

THETA = 0.15      # donor/recipient threshold (paper)
THETA_W = 50      # minimum within-group citations (paper)
ALPHA = 0.01      # BH significance level (paper)


def excessive_edges(W, group_membership=None, W_all=None, alpha=ALPHA, min_expected_weight=1):
    """Return the edge-filtered network Abar (only excessive edges, no self-loops)."""
    W = sparse.csr_matrix(W)
    ef = EdgeFilter(alpha=alpha, min_edge_weight=0, min_expected_weight=min_expected_weight,
                    remove_selfloop=True)
    ef.fit(W, group_membership=group_membership)
    src, dst, w = sparse.find(W)
    src, dst, w = ef.transform(src, dst, w)
    if W_all is not None:
        w_all = np.asarray(sparse.csr_matrix(W_all)[src, dst]).ravel()
        keep = w > 0.5 * w_all
        src, dst, w = src[keep], dst[keep], w[keep]
    return sparse.csr_matrix((w, (src, dst)), shape=W.shape)


def detect(W, threshold=THETA, theta_w=THETA_W, group_membership=None, W_all=None, alpha=ALPHA):
    """Detect anomalous groups. W[i, j] = effective citations from journal i to j in year t
    (self-citations included: they count in the strengths s_out, s_in)."""
    W = sparse.csr_matrix(W)
    if group_membership is not None:
        group_membership = np.asarray(group_membership)
    Abar = excessive_edges(W, group_membership, W_all, alpha)

    # Peeling, as in Cidre.detect: drop nodes with max(donor, recipient) < threshold.
    N = W.shape[0]
    U = np.ones(N)
    indeg = np.maximum(np.asarray(W.sum(axis=0)).ravel(), 1.0)
    outdeg = np.maximum(np.asarray(W.sum(axis=1)).ravel(), 1.0)
    while True:
        donor = U * (Abar @ U) / outdeg
        recip = U * (U @ Abar) / indeg
        drop = (U > 0) & (np.maximum(donor, recip) < threshold)
        if not drop.any():
            break
        U[drop] = 0

    # Weakly connected components of the pruned network on U (isolates dropped).
    nodes = np.where(U)[0]
    sub = Abar[nodes][:, nodes]
    _, comp = connected_components(sub, directed=True, connection="weak")
    deg = np.asarray(sub.sum(axis=0)).ravel() + np.asarray(sub.sum(axis=1)).ravel()
    groups = []
    for c in np.unique(comp[deg > 0]):
        members = nodes[comp == c]
        g = Group(members, donor[members], recip[members], threshold)
        g.set_within_net(W, members)
        if g.get_num_edges() >= theta_w:
            groups.append(g)
    return groups


def overlap_detected(jcr_group, cidre_group):
    """Paper's matching rule: O = |U_JCR & U_CI| / |U_CI| >= 0.5 and >= 2 shared journals."""
    a, b = set(jcr_group), set(cidre_group)
    shared = len(a & b)
    return shared >= 2 and shared / len(b) >= 0.5
