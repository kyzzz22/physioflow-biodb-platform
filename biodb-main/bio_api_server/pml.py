"""
轻量 ML 模块（numpy 实现，无 sklearn 依赖）。

提供：
- KMeans 聚类（Lloyd 迭代，k-means++ 初始化）
- 线性回归（闭式解 / 岭回归）
- 从读回 JSON 构造特征矩阵（缺失值按列均值填充）

模型参数均为纯 JSON 可序列化的 dict，可直接存入 MongoDB（analysis_results.parameters）。
"""
import numpy as np


def result_to_matrix(result_json: dict, rows: list[str]) -> tuple[np.ndarray, list[str]]:
    """
    读回格式化结果（format_vm_data_with_original_metric_names 输出）转特征矩阵。

    返回 (X, usable_rows)：X 为 (n_samples, n_features) float64 矩阵；
    缺失值（None）按列均值填充；全空列被剔除，usable_rows 为实际参与列名。
    """
    time_strs = result_json.get("time", [])
    n_samples = len(time_strs)
    usable_rows = []
    columns = []
    for row in rows:
        values = result_json.get(row)
        if values is None:
            continue
        col = [v if v is not None else np.nan for v in values]
        arr = np.asarray(col, dtype=np.float64)
        if n_samples == 0 or np.isnan(arr).all():
            continue
        columns.append(arr)
        usable_rows.append(row)

    if not columns:
        return np.zeros((n_samples, 0)), []

    X = np.column_stack(columns)
    # 按列均值填充 NaN
    col_means = np.nanmean(X, axis=0)
    inds = np.where(np.isnan(X))
    X[inds] = np.take(col_means, inds[1])
    return X, usable_rows


class KMeans:
    """numpy KMeans 聚类（k-means++ 初始化）。"""

    def __init__(self, n_clusters: int = 3, max_iter: int = 100, n_init: int = 5, random_state: int = 42):
        self.n_clusters = int(n_clusters)
        self.max_iter = int(max_iter)
        self.n_init = int(n_init)
        self.random_state = int(random_state)
        self.centroids_: np.ndarray = None
        self.labels_: np.ndarray = None
        self.inertia_: float = None

    def _init_centroids(self, X: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        n_samples = X.shape[0]
        centroids = np.zeros((self.n_clusters, X.shape[1]))
        first = rng.integers(0, n_samples)
        centroids[0] = X[first]
        for k in range(1, self.n_clusters):
            dist = np.min(np.sum((X[:, None, :] - centroids[None, :k, :]) ** 2, axis=2), axis=1)
            probs = dist / dist.sum() if dist.sum() > 0 else np.ones(n_samples) / n_samples
            idx = rng.choice(n_samples, p=probs)
            centroids[k] = X[idx]
        return centroids

    def fit(self, X: np.ndarray):
        if X.shape[0] < self.n_clusters:
            raise ValueError(f"n_samples ({X.shape[0]}) must be >= n_clusters ({self.n_clusters})")
        if X.shape[1] == 0:
            raise ValueError("Feature matrix is empty")
        rng = np.random.default_rng(self.random_state)
        best_inertia = None
        best_centroids = None
        best_labels = None
        for _ in range(self.n_init):
            centroids = self._init_centroids(X, rng)
            labels = np.zeros(X.shape[0], dtype=int)
            for _ in range(self.max_iter):
                new_labels = np.argmin(
                    np.sum((X[:, None, :] - centroids[None, :, :]) ** 2, axis=2), axis=1
                )
                if np.array_equal(new_labels, labels):
                    labels = new_labels
                    break
                labels = new_labels
                for k in range(self.n_clusters):
                    cluster_points = X[labels == k]
                    if len(cluster_points) > 0:
                        centroids[k] = cluster_points.mean(axis=0)
            inertia = float(np.sum(
                np.min(np.sum((X[:, None, :] - centroids[None, :, :]) ** 2, axis=2), axis=1)
            ))
            if best_inertia is None or inertia < best_inertia:
                best_inertia = inertia
                best_centroids = centroids.copy()
                best_labels = labels.copy()
        self.centroids_ = best_centroids
        self.labels_ = best_labels
        self.inertia_ = best_inertia
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.centroids_ is None:
            raise RuntimeError("Model not fitted")
        return np.argmin(
            np.sum((X[:, None, :] - self.centroids_[None, :, :]) ** 2, axis=2), axis=1
        )

    def to_parameters(self) -> dict:
        return {
            "n_clusters": self.n_clusters,
            "centroids": self.centroids_.tolist(),
            "inertia": self.inertia_,
            "random_state": self.random_state,
        }

    @classmethod
    def from_parameters(cls, parameters: dict) -> "KMeans":
        model = cls(
            n_clusters=parameters.get("n_clusters", 3),
            random_state=parameters.get("random_state", 42),
        )
        model.centroids_ = np.asarray(parameters["centroids"], dtype=np.float64)
        model.inertia_ = parameters.get("inertia")
        return model


class LinearRegression:
    """numpy 线性回归（闭式解，支持可选 L2 岭正则）。"""

    def __init__(self, ridge_alpha: float = 0.0):
        self.ridge_alpha = float(ridge_alpha)
        self.coef_: np.ndarray = None
        self.intercept_: float = None

    def fit(self, X: np.ndarray, y: np.ndarray):
        if X.shape[0] != y.shape[0]:
            raise ValueError("X and y must have the same number of samples")
        if X.shape[0] < 2:
            raise ValueError("Need at least 2 samples for regression")
        Xb = np.hstack([np.ones((X.shape[0], 1)), X])
        n_features = Xb.shape[1]
        if self.ridge_alpha > 0:
            reg = self.ridge_alpha * np.eye(n_features)
            reg[0, 0] = 0  # 不惩罚截距
            theta = np.linalg.solve(Xb.T @ Xb + reg, Xb.T @ y)
        else:
            theta, *_ = np.linalg.lstsq(Xb, y, rcond=None)
        self.intercept_ = float(theta[0])
        self.coef_ = theta[1:].astype(float)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.coef_ is None:
            raise RuntimeError("Model not fitted")
        return self.intercept_ + X @ self.coef_

    def to_parameters(self) -> dict:
        return {
            "type": "linear_regression",
            "ridge_alpha": self.ridge_alpha,
            "intercept": self.intercept_,
            "coef": self.coef_.tolist(),
        }

    @classmethod
    def from_parameters(cls, parameters: dict) -> "LinearRegression":
        model = cls(ridge_alpha=parameters.get("ridge_alpha", 0.0))
        model.intercept_ = float(parameters.get("intercept", 0.0))
        model.coef_ = np.asarray(parameters.get("coef", []), dtype=np.float64)
        return model


def label_distribution(labels: np.ndarray) -> dict:
    """簇标签分布统计：{str(cluster_index): count}（MongoDB/JSON 要求字符串键）。"""
    unique, counts = np.unique(labels, return_counts=True)
    return {str(int(k)): int(c) for k, c in zip(unique, counts)}
