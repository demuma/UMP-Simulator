"""Bounded, spawn-based execution of independent recording groups.

Only the parent invokes admission/result callbacks. Workers own whole recordings;
this module never retries work, writes study artifacts, or schedules analysis.
"""
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import multiprocessing
import re

DEFAULT_WORKERS = 6
_GROUP_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*", re.ASCII)


class BatchFailure(RuntimeError):
    """A failed batch after all admitted work has settled.

    Mappings and ID tuples follow manifest order. ``completed_results`` contains
    successful worker results, including a result whose parent callback failed.
    ``cancelled_group_ids`` includes cancelled submissions and groups never
    submitted. ``unsubmitted_group_ids`` is the latter subset. A group assigned
    an admission error appears in ``errors`` instead of those ID tuples.
    """

    def __init__(self, completed_results, errors, cancelled_group_ids,
                 unsubmitted_group_ids=()):
        self.completed_results = dict(completed_results)
        self.errors = dict(errors)
        self.cancelled_group_ids = tuple(cancelled_group_ids)
        self.unsubmitted_group_ids = tuple(unsubmitted_group_ids)
        details = ", ".join(f"{identity}:{type(error).__name__}"
                            for identity, error in self.errors.items())
        super().__init__(f"Recording batch failed ({details}); "
                         f"completed={len(self.completed_results)}, "
                         f"cancelled={len(self.cancelled_group_ids)}")


def execute_recordings(groups, worker, *, workers=DEFAULT_WORKERS,
                       initializer=None, initargs=(), before_submit=None,
                       on_result=None):
    """Run each unique group once and return results in manifest order.

    ``worker(group)`` and an optional initializer must support multiprocessing's
    spawn pickling rules. At most ``workers`` futures are admitted at once.
    ``before_submit(group)`` runs centrally immediately before submission, for
    resource admission checks. ``on_result(group, result)`` runs in the parent
    when a worker succeeds; its order follows completion, not the manifest.
    Callbacks must not change ``group_id``. Top-level group dictionaries are
    copied, so callback additions do not modify the caller's dictionaries.

    On the first parent-observed exception, no further groups are admitted.
    Unstarted futures are cancelled when possible; running work is drained,
    including result callbacks. Worker, initializer, submission and callback
    errors are reported together in ``BatchFailure``. There are no retries.
    """
    if type(workers) is not int or not 1 <= workers <= DEFAULT_WORKERS:
        raise ValueError(f"workers must be an integer from 1 to {DEFAULT_WORKERS}")
    if not callable(worker):
        raise TypeError("worker must be callable")
    for name, callback in (("initializer", initializer),
                           ("before_submit", before_submit),
                           ("on_result", on_result)):
        if callback is not None and not callable(callback):
            raise TypeError(f"{name} must be callable or None")
    initargs = tuple(initargs)
    manifest, identities = [], []
    seen = set()
    for group in groups:
        if not isinstance(group, dict):
            raise ValueError("each recording group must be a dictionary")
        identity = group.get("group_id")
        if not isinstance(identity, str) or _GROUP_ID.fullmatch(identity) is None:
            raise ValueError("group_id must be a nonempty safe path component")
        if identity in seen:
            raise ValueError(f"duplicate group_id: {identity}")
        seen.add(identity)
        manifest.append(dict(group))
        identities.append(identity)
    if not manifest:
        return []

    completed, errors, submitted = {}, {}, set()
    pending = {}
    next_index = 0
    pool = None

    def cancel_pending():
        for future in tuple(pending):
            if future.cancel():
                del pending[future]

    def admit():
        nonlocal next_index
        while not errors and len(pending) < workers and next_index < len(manifest):
            # Observe completed work before filling a newly available slot.
            if any(future.done() for future in pending):
                break
            index = next_index
            next_index += 1
            group = manifest[index]
            try:
                if before_submit is not None:
                    before_submit(group)
                if group.get("group_id") != identities[index]:
                    raise ValueError("before_submit changed group_id")
                future = pool.submit(worker, group)
            except Exception as error:
                errors[index] = error
                break
            submitted.add(index)
            pending[future] = index

    try:
        pool = ProcessPoolExecutor(
            max_workers=workers, mp_context=multiprocessing.get_context("spawn"),
            initializer=initializer, initargs=initargs)
    except Exception as error:
        errors[0] = error
    else:
        try:
            admit()
            if errors:
                cancel_pending()
            while pending:
                done, _ = wait(tuple(pending), return_when=FIRST_COMPLETED)
                done.update(future for future in pending if future.done())
                for future in sorted(done, key=pending.__getitem__):
                    index = pending.pop(future)
                    if future.cancelled():
                        continue
                    try:
                        result = future.result()
                        completed[index] = result
                        if on_result is not None:
                            on_result(manifest[index], result)
                        if manifest[index].get("group_id") != identities[index]:
                            raise ValueError("on_result changed group_id")
                    except Exception as error:
                        errors[index] = error
                if errors:
                    cancel_pending()
                else:
                    admit()
                    if errors:
                        cancel_pending()
        finally:
            pool.shutdown(wait=True, cancel_futures=True)

    if errors:
        raise BatchFailure(
            {identities[i]: completed[i] for i in range(len(manifest)) if i in completed},
            {identities[i]: errors[i] for i in range(len(manifest)) if i in errors},
            [identity for i, identity in enumerate(identities)
             if i not in completed and i not in errors],
            [identity for i, identity in enumerate(identities)
             if i not in submitted and i not in errors])
    return [completed[i] for i in range(len(manifest))]
