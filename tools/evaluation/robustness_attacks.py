"""Frozen training-only attack families for the optional robustness study.

Logistic regression reuses the dependency-free existing implementation. Histogram
boosting uses the pinned scikit-learn implementation, not a local tree predictor.
Only feature rows and training labels enter fitting; calibration/test partitions
must be held by the caller. No model selection or calibration occurs here.

``fit_attack`` returns JSON-serializable metadata. For histogram boosting it also
writes a private, exclusive .joblib artifact and registers the freshly fitted
object in this process. ``predict_attack`` validates the metadata/file hash and
uses that registered object. It never deserializes a caller-supplied artifact.
Cross-process reproduction refits from the frozen inputs/protocol; the persisted
joblib file is a private audit artifact, not a portable public model interface.

Estimator reference:
https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html
"""

from copy import deepcopy
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import stat
import sys

from empirical_privacy import _labels, _rows, fit_classifier, predict_scores


SCHEMA = "ump.robustness-attack.v1"
SKLEARN_VERSION = "1.9.1"
FAMILIES = ("logistic", "hist_gradient_boosting")
LOGISTIC_PARAMETERS = {"l2": 0.1, "max_iterations": 500, "tolerance": 1e-8}
HGB_PARAMETERS = {
    "loss": "log_loss", "learning_rate": 0.1, "max_iter": 64,
    "max_leaf_nodes": 4, "max_depth": 2, "min_samples_leaf": 8,
    "l2_regularization": 1.0, "early_stopping": False,
    "random_state": 20261021,
}
_OWN_MODELS = {}


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError("Attack metadata must contain finite JSON values") from error


def _optional_libraries():
    if sys.version_info < (3, 11):
        raise RuntimeError("Histogram boosting requires Python >=3.11 and requirements-robustness.txt")
    try:
        import sklearn
        import joblib
        from sklearn.ensemble import HistGradientBoostingClassifier
        from threadpoolctl import threadpool_limits
    except ImportError as error:
        raise RuntimeError("Histogram boosting requires the optional requirements-robustness.txt environment") from error
    if sklearn.__version__ != SKLEARN_VERSION:
        raise RuntimeError(f"Histogram boosting requires scikit-learn=={SKLEARN_VERSION}; found {sklearn.__version__}")
    return HistGradientBoostingClassifier, joblib, threadpool_limits


def _model_path(value):
    if not isinstance(value, (str, Path)):
        raise ValueError("Histogram boosting requires a private absolute .joblib model_path")
    path = Path(value)
    if not path.is_absolute() or path.suffix != ".joblib" or ".." in path.parts:
        raise ValueError("model_path must be an absolute .joblib path without traversal")
    try:
        parent = path.parent.resolve(strict=True)
    except (FileNotFoundError, OSError) as error:
        raise ValueError("model_path parent directory must already exist") from error
    if parent != path.parent or not parent.is_dir():
        raise ValueError("model_path must use a canonical directory without symlinks")
    if path.is_symlink():
        raise ValueError("model_path must not be a symlink")
    return path


def _digest_model(path):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(str(path), flags)
    except OSError as error:
        raise ValueError("Private model file is unavailable or unsafe") from error
    with os.fdopen(descriptor, "rb") as source:
        status = os.fstat(source.fileno())
        if not stat.S_ISREG(status.st_mode) or status.st_mode & 0o077:
            raise ValueError("Private model must be a regular file accessible only to its owner")
        digest = hashlib.sha256()
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
        return digest.hexdigest()


def _probabilities(model, rows, limits):
    with limits(limits=1):
        values = model.predict_proba(rows)[:, 1].tolist()
    if any(not math.isfinite(value) or not 0 <= value <= 1 for value in values):
        raise ValueError("Attack prediction produced an invalid probability")
    return values


def fit_attack(features, labels, family, model_path=None):
    """Fit one predeclared family on training rows only and freeze its metadata.

    The histogram model file must not exist. It is written with owner-only access
    and serialization is checked through the same newly created file descriptor.
    Frozen parameters are not tuned using calibration or test data.
    """
    if family not in FAMILIES:
        raise ValueError(f"Unknown attack family: {family!r}")
    rows = _rows(features)
    labels = _labels(labels, len(rows))
    if set(labels) != {0, 1}:
        raise ValueError("Training requires both membership classes")
    metadata = {"schema": SCHEMA, "family": family, "feature_count": len(rows[0]),
                "training_rows": len(rows), "training_prior": sum(labels) / len(labels),
                "fit_partition": "training_only"}
    if family == "logistic":
        if model_path is not None:
            raise ValueError("Logistic model is embedded in JSON and does not use model_path")
        model = fit_classifier(rows, labels, **LOGISTIC_PARAMETERS)
        metadata.update(parameters=deepcopy(LOGISTIC_PARAMETERS), model=model,
                        converged=model["converged"], iterations=model["iterations"],
                        implementation="empirical_privacy.fit_classifier")
        return metadata

    path = _model_path(model_path)
    classifier, joblib, limits = _optional_libraries()
    model = classifier(**HGB_PARAMETERS)
    with limits(limits=1):
        model.fit(rows, labels)
    reference = _probabilities(model, rows[:32], limits)
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(str(path), flags, 0o600)
    try:
        with os.fdopen(descriptor, "w+b") as destination:
            joblib.dump(model, destination, compress=0, protocol=5)
            destination.flush()
            destination.seek(0)
            # Only our just-created file descriptor is deserialized. No arbitrary
            # metadata path ever reaches joblib.load in the public prediction API.
            restored = joblib.load(destination)
            if _probabilities(restored, rows[:32], limits) != reference:
                raise RuntimeError("Histogram model serialization changed predictions")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    versions = {name: importlib.metadata.version(name)
                for name in ("scikit-learn", "numpy", "scipy", "joblib", "threadpoolctl")}
    metadata.update(parameters=deepcopy(HGB_PARAMETERS), estimator_parameters=model.get_params(deep=True),
                    model_path=str(path), model_sha256=_digest_model(path),
                    iterations=int(model.n_iter_), convergence_evaluated=False,
                    threads=1, versions=versions, python_version=sys.version.split()[0],
                    implementation="sklearn.ensemble.HistGradientBoostingClassifier",
                    persistence="private_joblib_same_process_registered_prediction")
    _OWN_MODELS[str(path)] = (model, _canonical(metadata))
    return metadata


def predict_attack(artifact, features):
    """Predict without changing fitting/scaling; reject unknown histogram files.

    JSON round trips of metadata are supported within the fitting process. A file
    hash provides integrity, not permission to deserialize an external model.
    """
    if not isinstance(artifact, dict) or artifact.get("schema") != SCHEMA:
        raise ValueError(f"Expected attack metadata schema {SCHEMA}")
    family = artifact.get("family")
    if family not in FAMILIES:
        raise ValueError("Unknown attack family in metadata")
    dimension = artifact.get("feature_count")
    if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension < 1:
        raise ValueError("Invalid attack feature dimension")
    rows = _rows(features, dimension=dimension, nonempty=False)
    if family == "logistic":
        expected = {"schema", "family", "feature_count", "training_rows", "training_prior",
                    "fit_partition", "parameters", "model", "converged", "iterations", "implementation"}
        if set(artifact) != expected or artifact.get("parameters") != LOGISTIC_PARAMETERS:
            raise ValueError("Invalid frozen logistic attack metadata")
        model = artifact["model"]
        if not isinstance(model, dict) or any(artifact[key] != model.get(key)
                for key in ("feature_count", "training_rows", "training_prior", "converged", "iterations")):
            raise ValueError("Logistic metadata differs from embedded model")
        if artifact["fit_partition"] != "training_only" or artifact["implementation"] != "empirical_privacy.fit_classifier":
            raise ValueError("Invalid logistic fit provenance")
        return predict_scores(model, rows)
    path = _model_path(artifact.get("model_path"))
    registered = _OWN_MODELS.get(str(path))
    if registered is None or _canonical(artifact) != registered[1]:
        raise ValueError("Histogram model was not fitted with this exact metadata in this process")
    if _digest_model(path) != artifact.get("model_sha256"):
        raise ValueError("Private model SHA256 mismatch")
    if not rows:
        return []
    _, _, limits = _optional_libraries()
    return _probabilities(registered[0], rows, limits)
