"""
Parallel fetch utilities — ThreadPoolExecutor wrapper for batch operations.
Used by screener scan and single-ticker analysis for concurrent data fetching.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple


def batch_fetch(
    fn: Callable[[str], Any],
    items: List[str],
    max_workers: int = 20,
    delay: float = 0.05,
    on_progress: Optional[Callable[[int, int, str, bool], None]] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Execute `fn(item)` concurrently across `items` using a thread pool.

    Parameters
    ----------
    fn : callable(str) -> Any
        Function to call for each item. Returns result or None on failure.
    items : list[str]
        List of item keys (e.g. tickers).
    max_workers : int
        Max parallel threads (default 20).
    delay : float
        Per-worker delay in seconds to throttle API calls.
    on_progress : callable(done, total, item, success) -> None
        Optional progress callback.

    Returns
    -------
    (results_dict, failed_list)
        results_dict: {item: result} for successful fetches
        failed_list: list of items that returned None or raised
    """
    results: Dict[str, Any] = {}
    failed: List[str] = []
    total = len(items)

    if total == 0:
        return results, failed

    def _worker(item: str) -> Tuple[str, Any]:
        if delay > 0:
            time.sleep(delay)
        try:
            result = fn(item)
            return (item, result)
        except Exception:
            return (item, None)

    done_count = 0

    with ThreadPoolExecutor(max_workers=min(max_workers, total)) as executor:
        future_to_item = {executor.submit(_worker, item): item for item in items}

        for future in as_completed(future_to_item):
            item = future_to_item[future]
            done_count += 1
            try:
                _, result = future.result()
                if result is not None:
                    results[item] = result
                    if on_progress:
                        on_progress(done_count, total, item, True)
                else:
                    failed.append(item)
                    if on_progress:
                        on_progress(done_count, total, item, False)
            except Exception:
                failed.append(item)
                if on_progress:
                    on_progress(done_count, total, item, False)

    return results, failed


def parallel_run(
    tasks: Dict[str, Callable[[], Any]],
    max_workers: int = 8,
) -> Dict[str, Any]:
    """
    Run named tasks concurrently and collect results.
    Used for parallelizing independent analysis steps.

    Parameters
    ----------
    tasks : dict[name, callable]
        {task_name: zero-arg function} — each function returns its result.
    max_workers : int
        Max parallel threads.

    Returns
    -------
    dict[name, result_or_error]
        {task_name: result} for successes.
        {task_name: {"_error": str}} for failures.
    """
    results: Dict[str, Any] = {}

    if not tasks:
        return results

    with ThreadPoolExecutor(max_workers=min(max_workers, len(tasks))) as executor:
        future_to_name = {
            executor.submit(fn): name for name, fn in tasks.items()
        }

        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                results[name] = future.result()
            except Exception as e:
                results[name] = {"_error": str(e)}

    return results
